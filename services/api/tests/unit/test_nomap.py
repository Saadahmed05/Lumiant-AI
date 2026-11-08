"""No-mapping prototype: discovery, SQL safety, per-user limits and the chat loop, without any AI call."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest
import sqlglot

from lumiant.nomap.agent import WITHHELD, AnthropicModel, NoMapAgent
from lumiant.nomap.catalog import Catalog, Column, Table
from lumiant.nomap.discovery import discover
from lumiant.nomap.safe_sql import AccessPolicy, UnsafeSqlError, prepare
from lumiant.nomap.source import Source, SourceError

DATA = Path(__file__).parents[2] / "data" / "synthetic"
VIEWER = AccessPolicy(
    row_scope={"zv_stock": ("WERKS", frozenset({"3100"}))},
    hidden_columns={"zv_stock": {"VERPR"}},
    denied_tables={"zv_vendor"},
)


@pytest.fixture(scope="module")
def source(tmp_path_factory: pytest.TempPathFactory) -> Any:
    path = tmp_path_factory.mktemp("nomap") / "alpha.duckdb"
    shutil.copy(DATA / "demo-alpha.duckdb", path)
    src = Source.duckdb(path)
    yield src
    src.dispose()


@pytest.fixture(scope="module")
def catalog(source: Source) -> Catalog:
    return discover(source, exclude=frozenset({"_dataset_info"}))


def run(source: Source, catalog: Catalog, sql: str, access: AccessPolicy | None = None) -> Any:
    return source.execute(prepare(sql, catalog, access))


def test_discovery_reads_the_database_without_a_mapping_file(catalog: Catalog) -> None:
    stock = catalog.find("ZV_STOCK")
    assert stock is not None
    assert stock.rows == 1160
    assert catalog.find("_dataset_info") is None
    status = catalog.find("ZV_PURCHASE").column("ZZSTATUS")  # type: ignore[union-attr]
    assert set(status.samples) == {"OPEN", "RECEIVED"}  # type: ignore[union-attr]


def test_free_text_never_reaches_the_catalog(catalog: Catalog) -> None:
    assert catalog.find("ZV_MATERIAL").column("MAKTX").samples == ()  # type: ignore[union-attr]


def test_joins_are_found_by_testing_values(catalog: Catalog) -> None:
    joins = {(j.from_table, j.from_column, j.to_table, j.to_column) for j in catalog.joins}
    assert ("ZV_STOCK", "MATNR", "ZV_MATERIAL", "MATNR") in joins


def test_read_query_returns_the_known_total(source: Source, catalog: Catalog) -> None:
    result = run(source, catalog, "SELECT SUM(LABST * VERPR) FROM ZV_STOCK")
    assert str(round(result.rows[0][0], 2)) == "2767451.83"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM ZV_STOCK",
        "UPDATE ZV_STOCK SET LABST = 0",
        "INSERT INTO ZV_STOCK SELECT * FROM ZV_STOCK",
        "DROP TABLE ZV_STOCK",
        "CREATE TABLE x AS SELECT 1",
        "SELECT 1; DROP TABLE ZV_STOCK",
        "SELECT * INTO copy_of_stock FROM ZV_STOCK",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM duckdb_settings()",
        "SELECT * FROM read_csv('C:/secrets.csv')",
        "SELECT * FROM 'C:/secrets.csv'",
        "SELECT getenv('PATH')",
        "SELECT * FROM _dataset_info",
        "SELECT * FROM no_such_table",
        "WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM r) SELECT * FROM r",
    ],
)
def test_unsafe_sql_is_refused(catalog: Catalog, sql: str) -> None:
    with pytest.raises(UnsafeSqlError):
        prepare(sql, catalog)


def test_database_itself_refuses_writes_and_file_reads(source: Source) -> None:
    for sql in ("DELETE FROM ZV_STOCK", "SELECT * FROM read_csv('x.csv')"):
        with pytest.raises(SourceError):
            source.execute(sql)


def test_row_scope_holds_however_the_query_is_written(source: Source, catalog: Catalog) -> None:
    for sql in (
        "SELECT DISTINCT WERKS FROM ZV_STOCK",
        "SELECT DISTINCT s.WERKS FROM ZV_STOCK s JOIN ZV_MATERIAL m ON s.MATNR = m.MATNR",
        "SELECT DISTINCT WERKS FROM (SELECT * FROM ZV_STOCK) q",
        "WITH c AS (SELECT * FROM ZV_STOCK) SELECT DISTINCT WERKS FROM c",
        "SELECT DISTINCT WERKS FROM ZV_STOCK WHERE WERKS = '1100' OR 1 = 1",
        "SELECT WERKS FROM ZV_STOCK UNION SELECT WERKS FROM ZV_STOCK",
    ):
        assert {r[0] for r in run(source, catalog, sql, VIEWER).rows} == {"3100"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT VERPR FROM ZV_STOCK",
        "SELECT SUM(LABST * VERPR) FROM ZV_STOCK",
        "SELECT s.VERPR FROM ZV_STOCK s",
        'SELECT "verpr" FROM ZV_STOCK',
    ],
)
def test_hidden_column_cannot_be_read(source: Source, catalog: Catalog, sql: str) -> None:
    with pytest.raises((UnsafeSqlError, SourceError)):
        run(source, catalog, sql, VIEWER)


def test_select_star_omits_the_hidden_column(source: Source, catalog: Catalog) -> None:
    assert "VERPR" not in run(source, catalog, "SELECT * FROM ZV_STOCK", VIEWER).columns


def test_cte_cannot_shadow_a_real_table_to_escape_limits(catalog: Catalog) -> None:
    with pytest.raises(UnsafeSqlError, match="CTE"):
        prepare("WITH ZV_STOCK AS (SELECT 1 AS x) SELECT * FROM ZV_STOCK", catalog, VIEWER)


def test_denied_table_is_refused_and_gone_from_the_user_catalog(catalog: Catalog) -> None:
    with pytest.raises(UnsafeSqlError):
        prepare("SELECT * FROM ZV_VENDOR", catalog, VIEWER)
    view = catalog.without(VIEWER.hidden_columns, VIEWER.denied_tables)
    assert view.find("ZV_VENDOR") is None
    assert view.find("ZV_STOCK").column("VERPR") is None  # type: ignore[union-attr]


def _dialect_catalog(dialect: str) -> Catalog:
    columns = (Column("MATNR", "VARCHAR", 5, 5), Column("VERPR", "DECIMAL", 5, 5), Column("WERKS", "VARCHAR", 5, 2))
    return Catalog(dialect, (Table(None, "stock", 5, columns),))


@pytest.mark.parametrize("dialect", ["postgres", "tsql", "oracle", "mysql", "snowflake"])
def test_limits_compile_for_each_target_dialect(dialect: str) -> None:
    catalog = _dialect_catalog(dialect)
    access = AccessPolicy(row_scope={"stock": ("WERKS", frozenset({"A"}))}, hidden_columns={"stock": {"VERPR"}})
    sql = prepare("SELECT COUNT(*) AS n FROM stock", catalog, access)
    sqlglot.parse_one(sql, read=dialect)
    assert "VERPR" not in sql
    assert "'A'" in sql


def test_table_functions_are_refused_on_snowflake() -> None:
    with pytest.raises(UnsafeSqlError):
        prepare("SELECT * FROM TABLE(GENERATOR(ROWCOUNT => 1))", _dialect_catalog("snowflake"))


def test_single_number_query_needs_no_order_by_on_sql_server() -> None:
    # The governed compiler cannot do this (LA-51): it pages every query, and T-SQL paging needs ORDER BY.
    sql = prepare("SELECT COUNT(*) AS n FROM stock", _dialect_catalog("tsql"))
    assert "TOP" in sql
    assert "OFFSET" not in sql


class ScriptedModel:
    """Replays tool calls in order, like a model would."""

    def __init__(self, *turns: list[dict[str, Any]]) -> None:
        self.turns = list(turns)
        self.seen: list[Any] = []

    def create(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        self.seen.append((system, list(messages)))
        calls = self.turns.pop(0)
        blocks = [SimpleNamespace(type="tool_use", id=f"t{i}", **c) for i, c in enumerate(calls)]  # type: ignore[arg-type]
        return SimpleNamespace(stop_reason="tool_use", content=blocks)


def tool(name: str, **kwargs: Any) -> dict[str, Any]:
    return {"name": name, "input": kwargs}


def finish(kind: str, answer: str) -> dict[str, Any]:
    return tool("finish", kind=kind, answer=answer, how_calculated="x", assumptions=[])


def test_chat_answers_from_query_results(source: Source, catalog: Catalog) -> None:
    model = ScriptedModel(
        [tool("run_sql", sql="SELECT ROUND(SUM(LABST * VERPR), 2) FROM ZV_STOCK")],
        [finish("answer", "Total stock is worth USD 2,767,451.83.")],
    )
    result = NoMapAgent(source, catalog, model).ask("What is our inventory worth?")
    assert result.kind == "answer"
    assert result.queries


def test_answer_with_an_invented_number_is_withheld(source: Source, catalog: Catalog) -> None:
    model = ScriptedModel(
        [tool("run_sql", sql="SELECT COUNT(*) FROM ZV_STOCK")], [finish("answer", "You have 9,999 lines.")]
    )
    result = NoMapAgent(source, catalog, model).ask("How many lines?")
    assert result.kind == "blocked"
    assert result.answer == WITHHELD


def test_refused_sql_goes_back_to_the_model_and_nothing_runs(source: Source, catalog: Catalog) -> None:
    model = ScriptedModel([tool("run_sql", sql="DELETE FROM ZV_STOCK")], [finish("refuse", "I can only read data.")])
    result = NoMapAgent(source, catalog, model).ask("Delete everything")
    assert result.kind == "refuse"
    assert result.queries == []
    assert "Query refused" in model.seen[1][1][-1]["content"][0]["content"]


def test_restricted_user_gets_a_filtered_catalog_and_a_visible_warning(source: Source, catalog: Catalog) -> None:
    model = ScriptedModel(
        [tool("run_sql", sql="SELECT COUNT(*) FROM ZV_STOCK")], [finish("answer", "Stock lines listed.")]
    )
    result = NoMapAgent(source, catalog, model, VIEWER).ask("How many lines?")
    assert "VERPR" not in model.seen[0][0].split("TABLE ZV_STOCK")[1].split("TABLE")[0]
    assert any("limited_access" in w for w in result.warnings)


def test_loop_stops_when_the_model_never_finishes(source: Source, catalog: Catalog) -> None:
    model = ScriptedModel(*[[tool("run_sql", sql="SELECT 1")] for _ in range(20)])
    assert NoMapAgent(source, catalog, model).ask("x").kind == "failed"


def test_anthropic_adapter_sends_the_expected_request() -> None:
    sent: dict[str, Any] = {}

    def create(**kwargs: Any) -> str:
        sent.update(kwargs)
        return "response"

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    assert AnthropicModel(client, "claude-opus-5-5").create("s", [], []) == "response"
    assert sent["model"] == "claude-opus-5-5"
    assert sent["thinking"] == {"type": "adaptive"}
    assert "tool_choice" not in sent


def test_source_files_stay_unchanged_by_chat(tmp_path: Path) -> None:
    path = tmp_path / "copy.duckdb"
    shutil.copy(DATA / "demo-beta.duckdb", path)
    before = path.read_bytes()
    src = Source.duckdb(path)
    cat = discover(src, exclude=frozenset({"_dataset_info"}))
    assert cat.find("stock_on_hand", "inv") is not None
    assert src.execute(prepare("SELECT COUNT(*) FROM stock_on_hand", cat)).rows[0][0] == 454
    src.dispose()
    assert path.read_bytes() == before
    duckdb.connect(str(path)).close()

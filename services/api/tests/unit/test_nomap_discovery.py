"""No-mapping discovery at ERP scale: on-demand profiling, search, knowledge packs, health checks, user limits."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest

from lumiant.nomap.agent import NoMapAgent
from lumiant.nomap.catalog import Catalog
from lumiant.nomap.discovery import PROFILE_UP_TO, discover, profile_table
from lumiant.nomap.safe_sql import AccessPolicy, prepare
from lumiant.nomap.source import Source

DATA = Path(__file__).parents[2] / "data" / "synthetic"
HIDDEN = frozenset({"_dataset_info"})


def copy(tmp: Path, name: str) -> Source:
    path = tmp / f"{name}.duckdb"
    shutil.copy(DATA / f"demo-{name}.duckdb", path)
    return Source.duckdb(path)


@pytest.fixture(scope="module")
def alpha(tmp_path_factory: pytest.TempPathFactory) -> Any:
    src = copy(tmp_path_factory.mktemp("alpha"), "alpha")
    yield src, discover(src, exclude=HIDDEN)
    src.dispose()


@pytest.fixture(scope="module")
def gamma(tmp_path_factory: pytest.TempPathFactory) -> Any:
    src = copy(tmp_path_factory.mktemp("gamma"), "gamma")
    yield src, discover(src, exclude=HIDDEN)
    src.dispose()


@pytest.fixture(scope="module")
def wide(tmp_path_factory: pytest.TempPathFactory) -> Any:
    path = tmp_path_factory.mktemp("wide") / "wide.duckdb"
    con = duckdb.connect(str(path))
    for i in range(PROFILE_UP_TO + 10):
        con.execute(f"create table Z{i:04d} (MATNR varchar, WERKS varchar, ZQTY decimal(18,3))")
        con.execute(f"insert into Z{i:04d} values ('M1', 'P1', 1), ('M2', 'P2', 2)")
    con.execute("create table STOCK_BY_BIN (MATNR varchar, BIN varchar, ONHAND_QTY decimal(18,3))")
    con.execute("insert into STOCK_BY_BIN values ('M1', 'B1', 5)")
    con.close()
    src = Source.duckdb(path)
    yield src, discover(src)
    src.dispose()


class Script:
    def __init__(self, *turns: list[dict[str, Any]]) -> None:
        self.turns = list(turns)
        self.replies: list[Any] = []

    def create(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        if len(messages) > 1:
            self.replies.append(messages[-1]["content"][0]["content"])
        calls = self.turns.pop(0)
        blocks = [SimpleNamespace(type="tool_use", id=f"t{i}", **c) for i, c in enumerate(calls)]
        return SimpleNamespace(stop_reason="tool_use", content=blocks)


def call(name: str, **kwargs: Any) -> dict[str, Any]:
    return {"name": name, "input": kwargs}


DONE = call("finish", kind="refuse", answer="done", how_calculated="", assumptions=[])


def test_large_database_is_read_by_structure_and_profiled_on_demand(wide: Any) -> None:
    src, catalog = wide
    assert len(catalog.tables) > PROFILE_UP_TO
    assert not any(t.profiled for t in catalog.tables)
    model = Script([call("find_tables", query="on hand qty")], [call("describe_table", table="STOCK_BY_BIN")], [DONE])
    NoMapAgent(src, catalog, model).ask("How much is on hand?")
    assert model.replies[0].startswith("STOCK_BY_BIN")
    assert "(1 rows)" in model.replies[1]


def test_catalog_text_stays_within_budget(wide: Any) -> None:
    _, catalog = wide
    assert len(catalog.render(budget=2_000)) <= 2_000
    assert "find_tables" in catalog.render(budget=500)


def test_sap_pack_names_standard_fields(alpha: Any) -> None:
    _, catalog = alpha
    assert catalog.packs == ("SAP",)
    assert "unrestricted" in (catalog.find("ZV_STOCK").column("LABST").meaning or "")  # type: ignore[union-attr]
    assert catalog.search("unrestricted stock")[0].name == "ZV_STOCK"
    assert any("separate quantities" in n for n in catalog.notes)
    assert not any("PEINH" in n for n in catalog.notes)  # no PEINH column, so no PEINH rule


def test_pack_stays_off_without_enough_sap_fields(wide: Any) -> None:
    _, catalog = wide
    assert catalog.packs == ()


def test_health_checks_find_the_traps_in_an_sap_export(gamma: Any) -> None:
    _, catalog = gamma
    checks = {t.name: " | ".join(t.checks) for t in catalog.tables}
    assert "1 duplicate rows, ignoring row number source_row" in checks["sap_mb52"]
    assert "likely total rows" in checks["sap_mb52_totals"]
    assert "price_unit goes up to 100" in checks["sap_material_master"]
    assert "CHECK: 1 duplicate rows" in catalog.render()


def test_health_checks_do_not_cry_wolf(tmp_path: Path) -> None:
    src = copy(tmp_path, "beta")
    checks = " | ".join(c for t in discover(src, exclude=HIDDEN).tables for c in t.checks)
    src.dispose()
    assert "currency_code holds 2 currencies (GBP, EUR)" in checks
    for noise in ("unit_price", "unit_cost", "unit_value", "business_unit", "duplicate"):
        assert noise not in checks


def test_restricted_user_never_sees_statistics_over_other_warehouses(alpha: Any) -> None:
    src, catalog = alpha
    viewer = AccessPolicy(
        row_scope={"zv_stock": ("WERKS", frozenset({"3100"}))}, hidden_columns={"zv_stock": {"VERPR"}}
    )
    model = Script([call("describe_table", table="ZV_STOCK")], [DONE])
    NoMapAgent(src, catalog, model, viewer).ask("What is stored here?")
    profile = model.replies[0]
    assert "WERKS: VARCHAR; 1 distinct" in profile
    assert "values 3100" in profile
    assert "VERPR" not in profile
    scoped_rows = src.execute("select count(*) from ZV_STOCK where WERKS = '3100'").rows[0][0]
    assert f"({scoped_rows} rows)" in profile


def test_admin_catalog_statistics_are_not_shown_to_a_scoped_user(alpha: Any) -> None:
    _, catalog = alpha
    view = catalog.without({}, set(), frozenset({"zv_stock"}))
    stock = view.find("ZV_STOCK")
    assert stock is not None
    assert not stock.profiled
    assert all(not c.samples for c in stock.columns)


def test_discovery_and_limits_run_on_sqlite(tmp_path: Path) -> None:
    path = tmp_path / "erp.sqlite"
    con = sqlite3.connect(path)
    con.execute("create table stock (item text, site text, qty numeric, cost numeric)")
    con.executemany(
        "insert into stock values (?, ?, ?, ?)", [("A", "S1", 2, 10), ("B", "S2", 3, 20), ("B", "S2", 3, 20)]
    )
    con.commit()
    con.close()
    src = Source(f"sqlite:///{path.as_posix()}")
    catalog = discover(src)
    stock = catalog.find("stock")
    assert stock is not None
    assert stock.rows == 3
    assert any("1 duplicate rows" in c for c in stock.checks)
    viewer = AccessPolicy(row_scope={"stock": ("site", frozenset({"S1"}))}, hidden_columns={"stock": {"cost"}})
    assert src.execute(prepare("SELECT SUM(qty) FROM stock", catalog, viewer)).rows[0][0] == 2
    assert profile_table(src, catalog, stock.structure_only(), viewer).rows == 1
    src.dispose()


def test_profiling_a_table_with_nothing_profiled_yet(tmp_path: Path) -> None:
    src = copy(tmp_path, "alpha")
    catalog = discover(src, exclude=HIDDEN, profile_up_to=0)
    assert isinstance(catalog, Catalog)
    plant = catalog.find("ZV_PLANT")
    assert plant is not None
    assert profile_table(src, catalog, plant).rows == 6
    src.dispose()

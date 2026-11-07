"""A figure is either correct or withheld: summaries survive row limits, failed checks never read as good news, and
text a model wrote without running a tool cannot carry numbers to the user."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lumiant.agent.providers import AnthropicProvider
from lumiant.agent.service import AgentService
from lumiant.analyses.risks import run_expiring
from lumiant.audit.store import AuditStore
from lumiant.auth.principal import Principal
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.core.config import Settings
from lumiant.core.errors import AppError
from lumiant.insights import engine
from lumiant.insights.engine import Insight, InsightService
from lumiant.main import create_app
from lumiant.query.service import QueryService
from lumiant.tenancy.registry import TenantRegistry
from tests.helpers import app_db_url, raw_duckdb

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}
SETTINGS = Settings(_env_file=None)  # type: ignore[call-arg]


def truth(alpha_db: Path, as_of: str, days: int = 60) -> tuple[int, int]:
    """(expired, expiring within `days`) stock lines from independent SQL."""
    con = raw_duckdb(alpha_db)
    row = con.execute(
        """
        SELECT count(*) FILTER (WHERE b.VFDAT < ?::DATE),
               count(*) FILTER (WHERE b.VFDAT >= ?::DATE AND b.VFDAT <= ?::DATE + to_days(?))
        FROM ZV_STOCK s JOIN ZV_BATCH b USING (CHARG) WHERE s.LABST > 0
        """,
        [as_of, as_of, as_of, days],
    ).fetchone()
    con.close()
    assert row is not None
    return int(row[0]), int(row[1])


# ------------------------------------------------------------------------------------------- counts survive limits
@pytest.mark.parametrize("limit", [1, 2, 200])
def test_expiring_summary_does_not_depend_on_the_row_limit(
    query_service: QueryService, principals: dict[str, Principal], alpha_db: Path, limit: int
) -> None:
    res = run_expiring(query_service, principals["alpha.admin"], days=60, limit=limit)
    expired, expiring = truth(alpha_db, res.provenance["parameters"]["as_of"])
    assert expired + expiring > 2, "synthetic data must hold more expiring lines than the smallest limit"
    assert (res.summary or {})["expired"] == expired
    assert (res.summary or {})["expiring"] == expiring
    assert len(res.rows) == min(limit, expired + expiring)


def test_expiring_insight_reports_the_true_counts(
    query_service: QueryService, principals: dict[str, Principal], alpha_db: Path
) -> None:
    feed = InsightService(query_service).feed(principals["alpha.admin"], fresh=True)
    card = next(i for i in feed["insights"] if i["id"] == "expiring_lots")
    as_of = run_expiring(query_service, principals["alpha.admin"], days=60, limit=1).provenance["parameters"]["as_of"]
    expired, expiring = truth(alpha_db, as_of)
    assert [m["value"] for m in card["metrics"]] == [expired, expiring]


def test_expiring_answer_reports_the_true_counts_and_says_the_table_is_partial(
    query_service: QueryService, principals: dict[str, Principal], alpha_db: Path
) -> None:
    out = AgentService(query_service, SETTINGS).chat(
        principals["alpha.admin"], "Which lots are nearing expiry in the next 3650 days?"
    )
    as_of = out["provenance"][0]["parameters"]["as_of"]
    expired, expiring = truth(alpha_db, as_of, 3650)
    assert out["answer"].startswith(f"{expired} lots on hand have already expired and {expiring} more")
    assert out["grounding"]["passed"]
    if expired + expiring > 15:
        assert "first 15" in out["answer"]


def test_expiring_scope_applies_to_the_counts(query_service: QueryService, principals: dict[str, Principal]) -> None:
    everyone = run_expiring(query_service, principals["alpha.admin"], days=3650, limit=1)
    scoped = run_expiring(query_service, principals["alpha.analyst"], days=3650, limit=1)
    admin, analyst = everyone.summary or {}, scoped.summary or {}
    assert analyst["expired"] + analyst["expiring"] < admin["expired"] + admin["expiring"]


# ------------------------------------------------------------------------------------------- failure is not good news
@pytest.fixture
def dead_source(registry: TenantRegistry, tmp_path: Path, audit_store: AuditStore) -> Iterator[QueryService]:
    """Every tenant's warehouse file is missing, as when a source goes down."""
    connectors = ConnectorRegistry(registry, tmp_path)
    yield QueryService(registry, connectors, audit_store)
    connectors.dispose_all()


def test_feed_reports_rules_that_could_not_run(dead_source: QueryService, principals: dict[str, Principal]) -> None:
    feed = InsightService(dead_source).feed(principals["alpha.admin"], fresh=True)
    assert feed["complete"] is False
    assert feed["insights"] == []
    assert {f["id"] for f in feed["failed"]} >= {"below_reorder", "expiring_lots", "dormant"}
    assert all(f["code"] == "source_unavailable" for f in feed["failed"])


def test_failed_feed_is_not_cached(
    query_service: QueryService, principals: dict[str, Principal], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def flaky(_: Any, __: Any) -> list[Insight]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise AppError("query_timeout", "The query took too long and was stopped.", 504)
        return []

    monkeypatch.setattr(engine, "RULES", [("flaky", flaky, ())])
    service = InsightService(query_service)
    first = service.feed(principals["alpha.admin"])
    second = service.feed(principals["alpha.admin"])
    assert first["complete"] is False
    assert second["complete"] is True
    assert calls["n"] == 2


def test_partial_failure_keeps_the_findings_that_did_run(
    query_service: QueryService, principals: dict[str, Principal], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_: Any, __: Any) -> list[Insight]:
        raise AppError("query_failed", "The data source could not answer this query.", 502)

    def working(_: Any, __: Any) -> list[Insight]:
        return [Insight("ok", "info", "value", "A finding", "Detail", "Ask")]

    monkeypatch.setattr(engine, "RULES", [("broken", broken, ()), ("working", working, ())])
    feed = InsightService(query_service).feed(principals["alpha.admin"], fresh=True)
    assert [i["id"] for i in feed["insights"]] == ["ok"]
    assert [f["id"] for f in feed["failed"]] == ["broken"]
    assert feed["complete"] is False


def test_unmapped_data_is_a_gap_not_a_failure(query_service: QueryService, principals: dict[str, Principal]) -> None:
    feed = InsightService(query_service).feed(principals["gamma.admin"], fresh=True)
    assert feed["gaps"]
    assert feed["failed"] == []
    assert feed["complete"] is True


def test_assistant_never_gives_the_all_clear_when_checks_failed(
    dead_source: QueryService, principals: dict[str, Principal]
) -> None:
    out = AgentService(dead_source, SETTINGS).chat(principals["alpha.admin"], "Anything unusual I should worry about?")
    assert "Nothing stands out" not in out["answer"]
    assert "could not" in out["answer"]
    assert any(w["code"] == "insights_incomplete" for w in out["warnings"])
    assert any(s["id"] == "tool:0" and s["status"] == "failed" for s in out["steps"])


# ------------------------------------------------------------------------------------------- model text without tools
class FakeClient:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **_: Any) -> Any:
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])


def model_says(query: QueryService, reply: str) -> AgentService:
    agent = AgentService(query, SETTINGS)
    provider = AnthropicProvider("k", "m", client=FakeClient(reply))
    agent._provider = lambda principal: (provider, None)  # type: ignore[method-assign]
    return agent


@pytest.mark.security
def test_invented_figures_never_reach_the_user(query_service: QueryService, principals: dict[str, Principal]) -> None:
    agent = model_says(query_service, "Total inventory is USD 48,250,000 across 7 warehouses.")
    out = agent.chat(principals["alpha.admin"], "How much inventory do we have?")
    assert "48,250,000" not in out["answer"]
    assert out["grounding"]["passed"] is False
    assert out["grounding"]["source"] == "blocked"
    assert out["grounding"]["ungrounded"] == ["48,250,000", "7"]
    assert out["follow_ups"]


@pytest.mark.security
def test_a_model_cannot_confirm_a_figure_the_user_typed(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    agent = model_says(query_service, "Yes, the total is 5,000,000.")
    out = agent.chat(principals["alpha.admin"], "Is the total 5000000?")
    assert "5,000,000" not in out["answer"]
    assert out["grounding"]["source"] == "blocked"


def test_model_text_without_figures_is_shown(query_service: QueryService, principals: dict[str, Principal]) -> None:
    agent = model_says(query_service, "Which warehouse do you mean?")
    out = agent.chat(principals["alpha.admin"], "How much stock is there?")
    assert out["answer"] == "Which warehouse do you mean?"
    assert out["grounding"]["passed"] is True


def test_withheld_answer_is_audited(
    query_service: QueryService, principals: dict[str, Principal], audit_store: AuditStore
) -> None:
    model_says(query_service, "Stock is worth 123456.").chat(principals["alpha.admin"], "What is it worth?")
    chats = [e for e in audit_store.recent("demo-alpha", limit=10) if e.action == "agent:chat"]
    assert chats[0].reason_code == "anthropic:unsupported:blocked"


def test_built_in_clarifications_keep_their_numbers(
    query_service: QueryService, principals: dict[str, Principal], alpha_db: Path
) -> None:
    """Deterministic wording is not model text: "held in 3 warehouses" must still reach the user."""
    con = raw_duckdb(alpha_db)
    row = con.execute("SELECT MATNR FROM ZV_STOCK GROUP BY MATNR HAVING count(DISTINCT WERKS) > 1 LIMIT 1").fetchone()
    con.close()
    assert row is not None
    out = AgentService(query_service, SETTINGS).chat(
        principals["alpha.admin"], f"Compare latest price with average cost for item {row[0]}"
    )
    assert out["kind"] == "clarify"
    assert "warehouses" in out["answer"]
    assert out["grounding"]["passed"] is True


# ------------------------------------------------------------------------------------------- HTTP
@pytest.fixture(scope="module")
def client(data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="integrity-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path_factory.mktemp("integritydb") / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        yield c


def test_insights_endpoint_states_completeness(client: TestClient) -> None:
    assert client.post("/api/auth/dev-login", json={"username": "alpha.admin"}, headers=CSRF).status_code == 200
    body = client.get("/api/insights?fresh=true").json()
    assert body["complete"] is True
    assert body["failed"] == []

# Current State

_Rewritten at the end of every session. Last update: 2026-11-11, S07 (M11 visual refresh of the web app: graphite + emerald, Inter, theme follows the device, shared control layer; web only; committed and pushed to `main` at the owner's request)._

## Milestone
**M1–M6 complete on synthetic data; M8 (client SAP extract, local only), M9 (Gemini-ready agent with screen context, streaming and insights) and M10 D1–D3 + part of D4 (command-center UI, Analyst Lens, four overview areas) done; **M11 visual refresh done and pushed** (ADR-0011).** Code is on GitHub (`syedmukheeth/Lumiant-AI`, `main`), all PRs merged, none open. CI was last green on `647ef7b`; not re-checked since — confirm on the M11 push.
**Next:** confirm CI is green on the S07 fix push (ISSUES #54); the owner looks at the new look on their own screen (ISSUES #51); a live Gemini check with the owner's key on a synthetic tenant; the rest of D4 (inventory grid, Material 360, Data sources); decide whether `lumiant.nomap` (prototype, not wired in) informs ADR-0002; the client's answers and further SAP files (Q-019…Q-026). M7 still needs `../07-customer/OPEN_QUESTIONS.md`.

## What works (verified by automated tests and manual browser checks)

| Capability | Evidence |
|---|---|
| Three synthetic tenants (alpha SAP-style USD; beta EUR+GBP; gamma = twin of the client's SAP exports, SAR) | `test_synthetic.py`, `test_sap_ingest.py`, `test_sap_extract.py` |
| Tenant config + canonical model + mapping + value maps, validated at startup | `test_tenancy.py`, `test_mapping.py` |
| Query engine: plan validation, scope injection, cost-field control, currency/UoM rails, parameterized SQL, sqlglot guard, read-only DuckDB, timeouts, provenance, audit; totals equal independent raw SQL | `test_validator.py`, `test_compiler_and_guard.py`, `test_query_service.py`, `*_matches_independent_sql` |
| Dev-only auth, RBAC, warehouse scope, tenant isolation, CSRF, safe errors; OIDC with local keys; rate limits (optional Redis); nonce CSP | `test_api.py`, `test_oidc.py`, `test_hardening.py`, e2e CSP test |
| M2 costing, ABC, risk analyses; M4 reports/exports/guided menu; M5 drift check, capability matrix, reconciliation, audit explorer | `test_costing.py`, `test_m2_analyses.py`, `test_reports.py`, `test_admin.py`, e2e |
| **M8** client SAP extract: `lumiant-ingest sap` → git-ignored DuckDB with a hard control-total gate (real import passed, nothing tracked), `customer_extract` class (ADR-0008), stock statuses, source-vs-computed value check, SAP data-quality checks | `07-customer/CLIENT_DATA_INTAKE.md`, `test_private_data_guard.py`, session log S03 |
| **M9** agent: 12 typed tools incl. `concentration` and `insights`; screen context + follow-ups (validated, scope-checked, narrowing only); SSE streaming; insight feed with capability gaps; Gemini + Anthropic adapters behind tenant approval (fake-client tested) | `test_agent.py` (golden/adversarial incl. 8 new), `test_agent_context.py` (24), ADR-0009/0010 |
| **M10** UI: dark-first command-center design system, rail + command bar, ⌘K palette, shortcuts; Overview with insight feed; **Analyst Lens** (right-click / ✦ / `L` on KPIs, panels, bars, rows, insights), persistent dock with streamed trace, pins; assistant page on the same renderer | web unit 50 (`analyst.test.tsx` …), e2e 23/23, browser check S04-9 |
| **M11** visual refresh: graphite + emerald tokens in dark and light, Inter for text and numbers, Geist Mono for identifiers, theme follows the device, one primitive layer (`components/ui/`) under every page | ADR-0011; contrast and palette gates (TEST_RUNS S07-1, S07-2); `ui.test.tsx`; headless screenshot review S07-6; live check in the in-app browser S07-9 |
| Checks (S07, Windows, working tree, web only) | lint/tsc clean · token lint 0 literals · unit 74 · e2e 26/26 (one earlier run: 2 timeouts, passed on rerun) · API 465 passed + 6 skips on a fresh clone (S07-8) |
| Checks (S06, Windows, on the merged tree) | API 465 passed + 6 env-gated skips · ruff/format/mypy strict clean · web lint/tsc clean · unit 61 · e2e not re-run this session · GitHub Actions not re-checked since `647ef7b` |
| Linux / containers / PostgreSQL 16 / Redis 7 | cloud verification CV-1…CV-6; CI `docker` and `api-postgres-redis` jobs |

## What is simulated (not evidence of customer readiness)
- **Demo data is synthetic** (alpha, beta, gamma). The **client extract** is real but a one-off local snapshot (no system connection), visible only on the owner's machine with the dev flags.
- **External AI has never been called.** Anthropic and Gemini adapters are tested with fake clients (ISSUES #13); external AI is off for the client extract until the client approves a provider (Q-013).
- **Authentication is development-only in practice**; OIDC never ran against a real IdP (Q-010).
- **The only connector is DuckDB** (plus the XLSX importer for SAP list exports). `lumiant.nomap` (PR #3) adds a no-mapping, AI-written-SQL prototype tested against PostgreSQL and a real Odoo 18; it is **not wired into the API or UI**, and letting the AI write SQL reverses ADR-0002 — bringing it into the product is the owner's decision.

## Not built yet
D4 rest: virtualized inventory grid + Material 360, Admin › Data sources (ISSUES #39) · axe run · LIFO, ageing buckets, price-movement alerts · editable query chips, glossary, drill-through, saved views (server-side), background reports · mapping editor/approval, profiling · real IdP, managed PostgreSQL/Redis · M7.

## Known limitations
`../logs/ISSUES.md` — open: #1, #2, #5, #6, #8, #13 (live AI), #14, #15, #16, #23–#30 (SAP extract), #31–#33 (dev tooling), #36 (SSE through production proxies not measured), #37 (per-process insight cache), #38 (touch Lens, per-browser pins), #39 (D4 rest), #50 (no-JS theme is dark), #51 (owner's own screen), #52 (exact numbers in answer sentences, by design), #53 (one flaky e2e run).

## Blocked on the customer
`../07-customer/OPEN_QUESTIONS.md` — Q-001, Q-003, Q-006–Q-008, Q-010, Q-012, Q-013 (AI provider approval, now incl. Gemini), Q-019…Q-026 (SAP code meanings, stock statuses, next files: MB51/MSEG, MARC, MCHB/MCH1, T001W/T001L, EKPO).

## Next step
0. Check GitHub Actions is green on the S07 fix push (ISSUES #54); owner opens the app on their own screen (ISSUES #51).
1. Owner: put a **paid** Gemini key in `services/api/.env` (`LUMIANT_AGENT_PROVIDER=gemini`, `LUMIANT_GEMINI_API_KEY=…`), set `ai.external_provider_approved: true` on a synthetic tenant only, and run a live check (closes part of ISSUES #13).
2. Build D4 rest (ISSUES #39) on the same design system.
3. Send Q-019…Q-026 and the file list to the client; load MB51/MARC/MCHB when they arrive to unlock dormant, reorder and expiry insights on real data.
4. Re-run e2e and confirm GitHub Actions is green on the new `main` tip (`155610f`); owner to decide on `lumiant.nomap` / ADR-0002.

## How to run
`docs/06-operations/DEV_SETUP.md` (setup) · `docs/06-operations/TESTING.md` (tests). After large CSS changes clear `apps/web/.next/dev` and `.next/cache` (ISSUES #33).

# AI Agent and Query Engine Review

Audit date 2026-10-31, commit `647ef7b`. Labels: **[V]** verified · **[R]** recommendation · **[A]** assumption.

> **Update 2026-10-31:** LA-02, LA-03 and LA-04 below are fixed (ISSUES #40–#42). They are kept as the audited record. LA-10 and the other items remain open.

## 1. Verdict

**The query engine is the strongest part of the repository. The "AI" is mostly a regex matcher, and no external model has ever run.**

| Component | State |
|---|---|
| Plan → validate → compile → guard → read-only execute | **Solid** on synthetic data |
| 12 typed tools | Working; the safety design is right |
| Default answering | **Built-in regex matching**, no LLM (`agent/providers.py:136`) |
| Anthropic and Gemini adapters | Fake clients only (ISSUES #13). **Never called live** |
| Natural-language capability | Fixed question shapes |

Calling this "AI-powered" today would overstate it. It is a governed analytics engine with an AI-shaped interface and a tested, unproven path to a real model.

## 2. Your ten questions, tested live

Run as `alpha.admin` on demo-alpha, built-in matcher [V probe 11]:

| # | Question | Result | Verdict |
|---|---|---|---|
| 1 | How much inventory do we currently have? | "I couldn't find an item matching that" | **Fail.** The headline question is treated as an item lookup |
| 2 | Which items are below reorder level? | 80 pairs, correct | Pass |
| 3 | Show me all A-category items. | "I can't answer that yet" | **Fail** though `abc_class` is mapped |
| 4 | Which warehouse has the highest inventory value? | Correct; wording "The highest warehouse"; unrounded `1128850.11776790` | Pass, poor wording |
| 5 | Latest purchase price of this item? | "couldn't find an item" | **Fail** without a selection. Works with a code |
| 6 | What is its average cost? | Same | **Fail**, no pronoun resolution without context |
| 7 | Show slow-moving items. | Dormant 270-day list | **Partial.** Dormant is not slow-moving |
| 8 | Which items have not moved in 180 days? | 49 pairs | Pass |
| 9 | Compare inventory value across warehouses. | Headline + bar chart | Pass |
| 10 | Highest obsolescence risk? | Refuses and explains | **Pass.** Honest behaviour |

**Five answered, one partial, four failed** with no model, while saying so honestly rather than guessing. On the SAP-layout tenant, `Show inventory value by warehouse` fails with `Field 'warehouse.name' is not available` because `agent/tools.py:186` hard-codes the name (ISSUES #29, reproduced).

## 3. The pipeline

You proposed: identity → permission → intent → structured plan → mapping → validation → parameterized read-only execution → deterministic calculation → result validation → response → provenance.

| Stage | State | Evidence |
|---|---|---|
| Identity verification | **Yes** | `auth/deps.py` |
| Permission check | **Yes**: route and tool level; schemas filtered per role | `providers.py`, `tools_for` |
| Intent interpretation | Regex; model when approved | `providers.py:250-357` |
| Structured query plan | **Yes**: strict Pydantic, floats rejected | `query/plan.py` |
| Schema mapping | **Yes** | `mapping/resolver.py` |
| Query validation | **Yes** | `query/validator.py` |
| Parameterized read-only execution | **Yes** | `compiler.py`, `sql_guard.py`, connector |
| Deterministic calculations | **Yes**, Decimal | `costing/engine.py` |
| **Result validation** | **Largely missing** | See LA-02, LA-05 |
| Response generation | Templates; model optional | `service.py` |
| Provenance | **Yes, strong**; lacks mapping version | `query/service.py:245-300` |

**One genuinely good design choice:** the model cannot write SQL or even a plan, only choose a typed tool with typed arguments (ADR-0002). That removes a whole class of risk. Keep it. Do **not** add the planned generic `query_inventory(plan)` tool for external models without a reason; a small tool set is easier to evaluate.

Analyses that assemble their own `Select` (`below_reorder.py`, `risks.py`) bypass the plan validator, repeating the scope logic by hand. They do reach the SQL guard, audit and connector. Each is a place where a future edit could forget scope. Probes found no leak today, but this is the riskiest pattern in the engine. Centralise it in a helper that cannot be skipped.

## 4. Defects

### LA-02 Expiry figures are wrong (P0)

`run_expiring` counts from the rows it returned, after the limit (`analyses/risks.py:251-261`). The insight calls it with `limit=1` (`insights/engine.py:271`), the assistant with `limit=15` (`agent/tools.py:380`).

| Source | Expired | Expiring within 60 days |
|---|---|---|
| Raw SQL, verified | **29** | **9** |
| Overview, CRITICAL card | **1** | **0** |
| Assistant | **15** | **0** |

Worse, `grounding` passes because the wrong number is in the evidence. **Grounding proves a number came from the tool, not that it is right.** Add a `COUNT` query, and test summary against SQL. Truncation is also hidden: the UI filters out `truncated` warnings (`answer-view.tsx:165`).

### LA-03 Failure looks like good news (P0)

`InsightService.feed` catches all `AppError`s and only logs (`insights/engine.py:355-359`), then **caches the empty result** for 120 s. With the data source gone [V probe 8]:

```text
GET /api/insights?fresh=true → 200 {"insights": [], "gaps": []}
Assistant: "Nothing stands out in the analyses available for your data."
GET /api/metrics/inventory_value_total → 503   (correct behaviour for comparison)
```

A failed risk scan telling a manager "nothing stands out" is the most dangerous kind of failure. Return a per-rule status; never cache a failed run.

### LA-04 Invented numbers shipped (P0)

If a model replies with text and no tool, `decision.message` becomes the answer (`service.py:222`). The guard then flags it, and **ships it anyway**, despite the code comment "never ship an ungrounded number" (`service.py:243-246`). Probe 6 returned to the user:

```text
Total inventory is USD 48,250,000 across 7 warehouses.
grounding: {passed: false, ungrounded: ['48,250,000', '7']}
```

The UI never reads `grounding.passed` (`answer-view.tsx:202`). Fix: refuse any model text containing numbers when no tool ran, and render a failure state.

### LA-10 Grounding limits (P1)

Results from [V probe 5]:

| Text | Outcome | Problem |
|---|---|---|
| "about three million dollars" | Passes | Number words not detected |
| "Inventory is 1100 dollars" | Passes | Warehouse id from provenance counts as evidence |
| "USD 12.5" | Passes | Query duration counts as evidence |
| "Yes, the total is 5,000,000" after a question containing it | Passes | Question is treated as evidence |

**Fix:** evidence only from declared numeric result fields, excluding provenance and the question. Attach unit and role to each value, detect number words, and compare meaning: a model may not use a warehouse id as money. Safest of all: **structured composition**, where the model writes placeholders such as `{{total_value}}` and code fills them in. Numbers then cannot be invented.

Also note the docs' "fail → one regeneration" step does not exist; it falls back straight to the template, which is a reasonable choice. Update the doc.

### Other

| ID | Issue |
|---|---|
| LA-05 | Fan-out on unverified joins. See `AI_SCHEMA_DISCOVERY.md` |
| LA-14 | `AVG` returns a binary float in JSON (`887.2957746478874`), breaking the repo's no-float rule [V probe 2]. Cast to DECIMAL |
| LA-09 | Guard and compiler not portable (see `ERP_INTEGRATION_ANALYSIS.md`) |
| LA-16 | Insights and ABC hit row caps. See `TECHNICAL_BOTTLENECKS.md` |
| — | `NE`/`NOT_IN` silently exclude NULLs (`compiler.py:44-49`). Worth a warning |

## 5. Failure states must stay distinct

| State you asked for | Today | Gap |
|---|---|---|
| No records found | **Yes** ("no stock… in your scope") | Ambiguous with "not authorized" by design for scope; acceptable |
| Data unavailable (not mapped) | **Yes** (`analysis_unavailable`, capability matrix, gaps) | Strong |
| Data not authorized | **Yes** | Good |
| Data stale | **Yes**: warning | Does not block; OK. Insights do not show staleness |
| Unsupported feature | **Yes** | Good |
| Query execution failure | **Partly** | **LA-03** merges this into "nothing stands out" |

## 6. Threats

| Threat | Assessment |
|---|---|
| SQL injection | Well controlled: no string SQL, bind params, value-map codes constrained by regex |
| Prompt injection | Blast radius small: no privileged tools, args typed, scope in code. Prose can still mislead. Item descriptions go to the model raw. **Untested with a real model** |
| Unauthorized field | Blocked (cost). See LA-13 for attributes |
| Unauthorized warehouse | Blocked |
| Cross-tenant | Blocked by construction, tested |
| Expensive queries | Row cap and timeout; no cost estimate or concurrency limit |
| Large results | Capped at `max_rows`. Silent in places, flagged in others |
| Ambiguous requests | Clarification implemented for items and warehouses. Good |
| Missing data | Handled well; unpriced lines are excluded and counted |
| Forged history | Client-sent `history` is re-validated, and tools re-check permission. Acceptable |

## 7. Recommended agent design

1. **Fix LA-02, 03, 04** first.
2. **Run a live test on synthetic data only** with an approved key, closing ISSUES #13. Expect adapter issues.
3. **Intent-only mode** as the default for customer data.
4. **Metric-level semantic layer:** make questions resolve to governed metrics (`inventory_value`, `dormant_stock`) with allowed dimensions and filters, instead of 12 special-case tools. This gives broader coverage with the same safety. "Show me all A-category items" and "How much inventory" would then work.
5. **Evaluation as a release gate.** `evals/golden.yaml` and `adversarial.yaml` exist; add your ten questions, measure routing accuracy per model, and track refusals. Compare hosted and local models on this set before choosing.
6. **Provenance per answer** already exists: add mapping version and model id.
7. Model pinning, per-tenant budgets, timeouts, and clear fallback messaging.

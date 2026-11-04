# No-mapping evaluation: first run, 2026-10-31

**Question tested:** can an agent answer inventory questions from a raw database, with no mapping and no documentation?

**Answer on this data:** yes. No answer was silently wrong. This does not yet show it works on real SAP.

## Setup

- Three synthetic databases: SAP-style names (20 questions), plain English names (16), and an MB52-layout export (16).
- `_dataset_info` was removed from the copies, because it lists the planted problems.
- The answer key is hand-written SQL in `cases.py`. Where the governed app has the same figure, they matched: Alpha 2,767,451.83, 80 below reorder and 49 dormant; Beta EUR 463,984.11, GBP 464,922.86, 33 and 23.
- The model was Claude Opus 5.5, in three fresh sessions, one per database. Each had only the `catalog`, `describe` and `sql` commands of `lumiant.nomap.cli`, under the rules in `agent.py`. Transcripts show no access to tenant YAML, `eval/nomap` or `_dataset_info`.
- Scoring is exact to the cent. Answers are in `results/`.

## Results

| Outcome | Count | Which |
|---|---|---|
| Matched the key exactly | 46 | |
| Right on reading | 3 | a20 injection, b06 and b13 across currencies |
| Asked a question instead | 1 | a13: the top supplier changes with how same-name IDs and open orders are treated |
| Differs from the key, and says so | 2 | g01, g02 |
| Wrong with no warning | **0** | |

**g01 and g02:** the agent found that source rows 9 and 5064 are identical and removed one, so its figures are SAR 882.20 lower than SAP's own footer. It reported both figures and the reason. The rows are confirmed identical, but whether this is a true duplicate is the customer's call. The headline does not reconcile to the report, which is why these are not counted as matches. The governed app counts the row.

**Traps handled:**
- GBP and EUR were never added together.
- Quantities were reported per unit of measure.
- The per-100 price column was used correctly, and the SAP totals table was not added to the detail rows.
- All 12 requests the data cannot answer were refused or questioned, including deletes and dates before the history starts.
- Both Arabic questions were answered.
- The injected instruction in item 3212000066 was reported as a data problem and not obeyed.
- An attempt to read system tables was refused by the guard.

## Limits of this result

- **The `ask` loop has not run against a live model.** No API key exists on this machine, so `AnthropicModel` is covered only by a fake client. The sessions followed the same rules and tools by hand.
- **Questions shared a session,** so later ones could benefit from what earlier ones learned. The product asks each one cold.
- **One run only.** No repeat runs, so nothing here measures how consistent it is.
- **The data is small and tidy:** 9 to 12 tables and about 7,000 characters of catalog. Real SAP has tens of thousands of tables, cryptic codes and customer fields. Published results on real SAP data are far lower.
- **The author of the questions knew the traps.** A real user will ask less tidy questions.
- **Permissions and dialects:** limits are tested on DuckDB, and compiled but not run on PostgreSQL, SQL Server, Oracle, MySQL and Snowflake. No live database was used.
- **Not built:** ERP knowledge packs, automatic reconciliation, and remembering corrections.

## Second round, 2026-11-03: ERP scale and real engines

**Scale.** Discovery used to profile every column up front: 0.9 s and about 600 tokens per table. At SAP's tens of thousands of tables, that is hours of profiling and millions of tokens. Now structure is read in one pass, small databases (up to 60 tables) are still profiled up front, and larger ones are profiled table by table when the agent describes them. The agent searches with `find_tables`.

| Tables | Before | After |
|---|---|---|
| 200 × 40 columns | 187 s, about 120,000 tokens | 1 s, about 14,000 tokens |
| 2,000 × 40 columns | not run | 16 s, under 100 tokens, plus search |

**Crowded ERP test.** The SAP-style demo was hidden among 300 noise tables, a stale backup (`ZV_STOCK_BAK_2024`, quantities ×1.3) and a 200-row test copy. A fresh session (Claude Opus 5.5, tools only) answered **8 of 8 exactly**. It picked the live stock table and said why it rejected the backup, the test copy and the noise tables. The transcript shows it used only the question file, the database tool and its own answer file. Answers are in `results/crowded/`.

**PostgreSQL, live.** `live_postgres.py` loads all three demos into PostgreSQL, keeping schemas and stored name case, and compares them with DuckDB. Before the fixes below, 15 of 16 Alpha answer-key queries failed. After them, all 37 match, catalogs, health checks and joins are identical, user limits hold, and a 2 s timeout stops a runaway query at 2.1 s. SQLite runs in the unit tests. SQL Server, Oracle, HANA and Snowflake are still checked by compiling only.

**Fixed in this round:**
- **Name case:** column and table names are now quoted in their stored case, because PostgreSQL lower-cases unquoted names, so `LABST` became `labst`.
- **Percent signs:** a `%` in a LIKE pattern crashed the PostgreSQL driver. Queries now run on the driver's cursor without parameters.
- **Timeouts:** they only worked on DuckDB, and a 2 s limit let a PostgreSQL query run 89 s. Queries are now cancelled through the driver, and PostgreSQL also gets a server-side `statement_timeout`.
- **Statistics leak:** catalog statistics were gathered over all rows and shown to scoped users, so sample values listed other warehouses. Statistics are now removed for scoped tables and gathered again within the user's limits.
- **Health checks** now run on every profiled table:
  - duplicate rows, ignoring export row numbers
  - total rows
  - totals tables
  - mixed currencies and units
  - price-per-N units

  They found every trap the first round's agent had to find by hand. A first version raised false alarms on `unit_price` and `business_unit`, and missed duplicates that differed only by row number. Both are fixed.
- **SAP knowledge pack:** standard meanings for about 50 SAP fields and 15 tables, applied only when at least 6 SAP field names appear. Its rules appear only when their field exists. The meanings are SAP's standard descriptions, not yet confirmed on a real SAP sandbox.

**Still open:**
- **Profiling cost:** every column is counted in full, which will be costly on tables the size of MATDOC. Sampling is needed.
- **Joins:** suggested only for databases of up to 60 tables, and single-column only.
- **Search:** it matches words, so custom fields with no pack meaning are found by name only.
- **Live AI:** the `ask` loop has still not run against a live model.

## Third round, 2026-11-04: a real ERP (Odoo 18)

**Setup.** Official Odoo 18 with demo data (Inventory, Purchase, Sales) on PostgreSQL. The agent connected through a read-only login; the database refuses writes on its own. The answer key was computed by Odoo's own engine (`odoo/run_answer_key.py`), not by hand-written SQL. A fresh AI session (Claude Opus 5.5) was not told which ERP it was.

**Result: 8 exact, 2 defensible and stated, 2 clarifying questions, 0 silently wrong** (`odoo/score.py`).
- **Defensible differences:**
  - It counted 27 storable products against 33 variants.
  - It counted 4 confirmed purchase orders with nothing received, against 1 with an open receipt; the demo created no receipts for three of them.
  - It stated its choice both times.
- **Clarifying questions:** "late deliveries" had three valid definitions in the data, and reordering rules differ between on-hand and forecast.
- **Traps it avoided:**
  - Mirror stock in virtual locations, which makes a naive total exactly 0.
  - Costs stored as JSON per company.
  - Valuation entries that are all zero.
  - Two companies.

**Fixed after this round:**
- JSON columns broke profiling.
- No check for rows that cancel out.
- Search ranking.
- The command name.
- No Odoo knowledge pack, which has not yet been measured with a rerun.

**Caveat:** the session's transcript file was empty, so its isolation is self-reported.

## Rerun

```bash
python eval/nomap/prepare.py <folder>
python eval/nomap/score.py <folder>
```

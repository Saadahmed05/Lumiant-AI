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

## Rerun

```bash
python eval/nomap/prepare.py <folder>
python eval/nomap/score.py <folder>
```

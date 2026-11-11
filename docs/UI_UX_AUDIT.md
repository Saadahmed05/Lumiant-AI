# UI/UX Audit

Reviewed live on 2026-10-31 in the built-in browser against `next dev` and the API at commit `647ef7b`, as `alpha.admin`, `alpha.analyst` and `gamma.admin`, at 1440 px and 375 px.

**Limits of this review:** dev build on a machine with about 1 GB of free memory, with the browser pane hidden for much of it. Timing is indicative only. No screen reader or full keyboard pass was done, and no axe run. With light mode emulated, the app stayed dark, and its theme toggle was not exercised, so **light mode was not assessed**.

> **Update 2026-10-31:** UX-01 and UX-02 are fixed (ISSUES #40, #42). All other findings here remain open.
>
> **Update 2026-11-11:** the visual layer was refreshed at the owner's request (ADR-0011): new palette, typeface, shared controls, theme that follows the device. This review describes the look before that change. Its functional findings (UX-03 to UX-20) are untouched by the refresh and remain open, except that the plainer look of Risks, Costs, Reports and Admin noted in §1 no longer applies. Light mode, not assessed here, now has the same contrast gate as dark (TEST_RUNS S07-1).

## 1. Assessment

The interface looks credible and considered: a clear "command centre" with strong typography and a disciplined dark palette. Its best feature, provenance on every number, is rare and exactly right for finance users.

The main problems are not visual. A wrong number sits at the top of the main screen, the SAP-style tenant looks unfinished, and the polish is uneven across pages: the pages shown in demos are finished, and those used by administrators and analysts are simpler.

## 2. Strengths [verified]

| Area | Observation |
|---|---|
| Hierarchy | KPI strip, then ranked insights, then breakdowns |
| Trust | "Source" slip, draft labels, "Data as of", persistent SYNTHETIC tape |
| Honesty | "Your role cannot view values"; per-currency display; "5 lines… not included"; gaps name the file that unlocks them |
| Roles | Cost columns, Costs and Admin vanish for no-cost users, and the API independently refuses |
| Navigation | Grouped rail; Ctrl+K palette; `G` shortcuts |
| Responsive | No page-level horizontal overflow at 375 px; bottom nav on mobile |
| Semantics | One `h1`, `lang`, landmarks; all checked inputs labelled, no unnamed buttons on Inventory |

## 3. Findings

Priority: **P0** misleads · **P1** blocks real use · **P2** quality · **P3** polish.

| ID | P | Finding | Where | Recommendation |
|---|---|---|---|---|
| UX-01 | P0 | **Top CRITICAL card says "1 lot on hand is expired and 0 more expire"; truth 29 and 9** (LA-02) | Overview | Fix backend; card must match the list it opens |
| UX-02 | P0 | Assistant has no visual state for a failed number check; "numbers checked" only appears on success | `answer-view.tsx:202` | Show failure explicitly and hide the claim |
| UX-03 | P1 | **SAP-style tenant shows raw error** in the Below Reorder tile: "Could not load this… ref …", though the insight area explains the same gap gracefully | Overview, demo-gamma | "Needs reorder points (MARC)" empty state |
| UX-04 | P1 | Stray "—" under inventory value (currency-less group), plus "Shown per currency" with only one currency | Overview, demo-gamma | Show as "23 lines unpriced"; drop the dash |
| UX-05 | P1 | `GM01 · Not set` on warehouse chart | demo-gamma | Show code alone |
| UX-06 | P1 | Codes humanized into nonsense: `DG-ROH008` → `Dg-roh008`; same pattern would hit real SAP codes | `humanize` | Never humanize codes |
| UX-07 | P1 | Inventory table hides **Value**, the most important column, 35 px past the edge at 1440 px, with no scroll cue | Inventory | Pin key columns; column chooser; sticky first column |
| UX-08 | P1 | Rows are stock lines only: no item-level detail, history or movements. "Material 360" unbuilt | Inventory | Item drawer: stock, cost, movements, source |
| UX-09 | P1 | **Inconsistent counts:** "593 items in stock" vs "85 of 577 stocked items" on one screen, for valid but unexplained reasons | Overview, demo-gamma | Say "577 with value" |
| UX-10 | P1 | Assistant fails your headline question "How much inventory do we have?" | Assistant | Route to the value metric |
| UX-11 | P2 | Mixed number formats: "USD 2,767,451.83", "USD 2.8M", "USD 1296621.21", "1128850.11776790" in prose | Insights, Assistant | One formatter; never raw decimals |
| UX-12 | P2 | Assistant sentence "The highest warehouse is…" | Assistant | Rewrite templates |
| UX-13 | P2 | Mobile table scrolls within a card, with key columns off-screen; bottom nav scrolls sideways, cutting off "Reports" with no cue | Inventory 375 px | Card layout for rows |
| UX-14 | P2 | Costs page requires typing an item id; no search | Costs | Reuse item picker |
| UX-15 | P2 | Reports opens with an empty dropdown | Reports | Gallery of report cards |
| UX-16 | P2 | Filters take one value each, though the API accepts many; filter bar wraps with stock status (ISSUES #30) | Inventory | Multi-select, removable chips |
| UX-17 | P2 | Admin is technical, shows table names, and has no mapping tools | Admin | See `AI_SCHEMA_DISCOVERY.md` |
| UX-18 | P3 | No skip link | Global | Add |
| UX-19 | P3 | Lens depends on hover and right-click, weak on touch (ISSUES #38); right-click overrides the browser menu | Global | Keep ✦ as primary; document Shift-right-click |
| UX-20 | P3 | Date format inconsistencies and US-style 12-hour time, with no locale setting | Header | Per-user locale |

**Not a defect:** pages were sometimes captured partly faded while the browser pane was hidden. The e2e test for this (ISSUES #10) passed on a production build, so this was treated as an artefact of the review environment.

## 4. Dashboard: can users understand…

| Question | Answer |
|---|---|
| Total value | **Yes**, per currency |
| Total quantity | **No, and rightly not as one number.** Mixed units cannot be added. Show per unit if requested |
| By warehouse / category | **Yes** |
| ABC | **Yes** on assigned; empty on SAP-style data (ISSUES #28) |
| Stage | **Yes**; SAP-style data reads `unmapped` until the client explains codes |
| Low stock | **Yes** |
| Slow-moving | Dormant only |
| Ageing | **No data view.** Add once receipt dates exist |
| Cost trends | **No.** Needs snapshots or history |

## 5. Inventory explorer

| Capability | State |
|---|---|
| Search | Code, description, debounced |
| Filtering | Warehouse, group, ABC, stage, status; URL-shareable. Single-select in UI |
| Sorting | On main columns, `aria-sort` set |
| Pagination | Server-side, 50 per page, offset-based |
| Item details | **Missing** |
| Warehouse information | Code, location, name |
| Cost information | Price, value, cost-gated |
| Source information | "Source" slip |
| Bulk actions / export from view | **Missing** |
| Filter options | Silently limited to 100 values (LA-16) |

## 6. AI chat design

Keep the Analyst dock. It is the best interaction idea here: **ask about what you are looking at**.

| Element | Recommendation |
|---|---|
| Suggested questions | Generated from what this tenant can answer (capability matrix) and this role |
| Query history | Server-side, per user, with retention controls |
| Follow-ups | Keep; show what changed ("now filtered to warehouse 2100") |
| Tables and charts | Rendered from results, never from prose. Already true |
| Explanations | Show interpretation before the answer ("I read this as dormant stock, 180 days, all warehouses"), with editable chips |
| Source provenance | Keep as is; add mapping version and model used |
| Export | Respect `export:data`; same watermark as reports |
| Error handling | Five distinct states: nothing found, not available, not allowed, stale, failed |
| Permissions | Say what was excluded and why, without revealing restricted values |
| AI disclosure | Show one consistent indicator: "Built-in", "Private AI", or "External AI: Provider", with what was sent |
| Graphical navigation | Every answer links to the full page with those filters; each chart can start a question |

## 7. Enterprise credibility

The visual identity suits a demo. Enterprise buyers also expect a light default option, density settings, column management, saved views shared across a team, print and export quality, and a clear "AI off" state. The dark look is impressive in a sales demo, but long-term daily use by warehouse and finance staff should be tested with those users.

## 8. Improvement plan

| Order | Work | Effort |
|---|---|---|
| 1 | UX-01, 02 with backend fixes | S |
| 2 | SAP-tenant empty states and labels: UX-03 to 06, 09 | S |
| 3 | Number formatting: UX-11, 12 | S |
| 4 | Accessibility run: axe, keyboard, screen reader, light mode | M |
| 5 | Table: pinned columns, chooser, multi-select | M |
| 6 | Item 360 drawer | L |
| 7 | Reports gallery, item picker | M |
| 8 | Saved views on the server | M |
| 9 | Chat improvements: interpretation chips, disclosure indicator | M |
| 10 | Mapping review UI, when the registry exists | L |

**Do not redesign.** The system is sound, and connectors are a higher priority.

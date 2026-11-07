# Technical Bottlenecks

Audit date 2026-10-31, commit `647ef7b`. **No load test was run and no customer-scale data exists.** Timings below are single-user readings on a dev laptop with little free memory, against small DuckDB files. They show relative cost only and predict nothing about a customer warehouse.

## 1. Evidence

Query counts are independent of hardware and are the best evidence here [V `probe_fanout`]:

| User action | HTTP requests | Warehouse queries | Audit rows |
|---|---|---|---|
| Overview load (uncached) | 13 | **52** | 33 |
| Insight feed | 1 | **32** | 19 |
| Data quality | 1 | **18** | 12 |
| Inventory page | 2 | 8 | 5 |

Single-user readings through the dev proxy (demo-alpha):

| Call | Observed |
|---|---|
| Metric | ~100 ms |
| Balances, 50 rows | ~95 ms |
| Filters | ~150 ms |
| Data quality | ~520 ms |
| Insights, fresh | ~1.4 s |
| Schema check, 10 tables | ~3.3 s |

Current data: 600 items, 1,160 stock lines, 2,331 lots, 7,697 purchase lines, 82,345 movements. A real customer can be orders of magnitude larger.

## 2. Hard limits that become feature failures

| Limit | Where | Effect at scale |
|---|---|---|
| ABC: 1,000 items | `risks.py:586` | Returns `analysis_too_large`. **Fails for most enterprises** |
| Cost comparison: 1,000 movements per pair | `risks.py:671,682` | Fails for fast-moving items |
| Max rows: 10,000 ceiling, 1,000 in demo | `tenancy/models.py:52` | Exports truncate (flagged). Concentration shows "needs more than…" |
| Filter options: 100 | `api/inventory.py:63-70` | **Silently** incomplete dropdowns: no truncation warning used |
| Item-code check: 1,000 | `risks.py:351` | Reports `partial` honestly |
| Group charts: 50 | `metrics/catalog.py:77` | Top 50 only |
| Timeout: 15 s demo, 120 s max | policy | Long analyses die |

## 3. Bottlenecks and fixes

| Priority | Area | Problem | Fix |
|---|---|---|---|
| **P0** | Query chattiness | Each insight rule is several queries; the Overview duplicates work (`below-reorder` twice, totals plus counts) | Batch endpoint; merge related metrics into one query; share below-reorder between tile and panel |
| **P0** | In-Python analytics | ABC, Pareto, FIFO load rows | Window functions for ABC and Pareto; stream movements for FIFO |
| **P1** | Connection pool | 4 + 2 per tenant; insights alone can exhaust it with several users; timeout then returns 500 (LA-15) | Per-tenant concurrency limit with queueing; friendly 503 |
| **P1** | Sync workers | Default threadpool; long analyses occupy threads; no cancel on client disconnect | Worker for long jobs; propagate cancellation |
| **P1** | LLM latency and cost | Two model calls per question; 30 s timeouts; no budget or token logging | Intent-only is one call; cache identical routing; per-tenant budget; record tokens |
| **P1** | Expensive queries | Row cap + timeout only (ISSUES #6) | `EXPLAIN` cost check per dialect; deny-list unindexed free-text scans on huge tables; per-tenant concurrency |
| **P1** | `contains` search | Leading-wildcard `LIKE`; full scans on real data | Search index or prefix match; item-search endpoint |
| **P1** | Offset pagination | `OFFSET` cost grows; `with_total` doubles queries | Keyset pagination; estimated totals |
| **P2** | Schema discovery | Per-column calls would be slow on tens of thousands of tables | Bulk catalog reads; background job; cache by snapshot hash |
| **P2** | Audit writes | Synchronous, one transaction per event; 33 rows per dashboard | Batch by request, keeping fail-closed semantics |
| **P2** | Caching | Per-process, feed only | Shared per-tenant, keyed by mapping version + scope + freshness. **Never** cross scope |
| **P2** | Multi-tenant fairness | One noisy tenant can consume threads | Per-tenant limits; or single-tenant deployments, which sidesteps this |
| **P2** | Connector latency | Model A/C add a round trip per query | Batching; agent-side cache; pre-aggregates |
| **P2** | Data refresh | Static files; no scheduler | Incremental by watermark; snapshot jobs; freshness SLA per dataset |
| **P3** | Importer | XLSX reading took minutes (ISSUES #26) | Prefer CSV or database |
| **P3** | Provenance size | Repeated on each row group response | Lazy load on demand |

## 4. Technique evaluation

| Technique | Use? |
|---|---|
| Async jobs | **Yes**: discovery, extracts, large reports, snapshots |
| Background processing | **Yes**: worker sharing the API codebase |
| Query caching | **Yes**, short TTL, keyed by scope and data version |
| Metadata caching | **Yes**; simple, already partly done |
| Pagination | **Yes**; move to keyset |
| Query timeouts | **Yes**; needs driver-level cancel per connector |
| Result limits | **Yes**, and always say when applied |
| Connection pooling | **Yes**, per-tenant with queueing. Check PgBouncer compatibility if used |
| Incremental refresh | **Yes** for snapshots |
| Materialized views | **Customer-side**, with DBA agreement. Best fix for dashboards on large warehouses |
| Streaming | Chat only. SSE through production proxies is unmeasured (ISSUES #36) |
| Async Python drivers | **No** for now. Sync with a worker is simpler and matches driver support |

## 5. Required measurement

Before quoting any performance figure to a customer:

1. Scale generator: 100k and 1M items; 10M–100M movements.
2. Real engines in containers, not only DuckDB.
3. Load test with representative concurrency, recording p50/p95, pool waits, warehouse load.
4. Test with added latency to simulate the agent model.
5. Agree a budget with the customer DBA: queries per minute, peak windows, replica use.

The DBA will ask how much load Lumiant adds. Today nobody can answer that, and it should be the first thing measured after the first SQL connector.

# Inventory Domain Review

Audit date 2026-10-31, commit `647ef7b`. Labels: **[V]** verified · **[R]** recommendation · **[A]** assumption · **[X]** external source. All calculation definitions in the repo are drafts until a customer approves them, and the UI says so.

> **Update 2026-10-31:** LA-02 is fixed (ISSUES #40). All other findings here remain open.

## 1. Assessment

The domain modelling is unusually careful for a project this young: exact decimals, no summing across currency or unit, source valuation kept separate from recomputed cost, and refusal to predict obsolescence without evidence. Gaps fall into two groups: **features not built** and **SAP realities the synthetic data does not expose**.

## 2. Coverage

| Area | State | Evidence |
|---|---|---|
| Inventory stages | **Implemented** as a canonical string with value maps. Customer-defined allowed; unknown codes shown as `unmapped` | `catalog.py:118`, `resolver.py` |
| ABC, assigned | **Implemented** at item and plant level; SAP tile fails (ISSUES #28) | `catalog.py:119,226`; probe 12 |
| ABC, computed | **Implemented**, capped (see below) | `costing/abc.py`, `risks.py:567` |
| Item master | ~14 fields + typed extension attributes | `catalog.py:110-130` |
| Batch, lot, expiry | **Implemented**; ambiguous join key | `catalog.py:212,264` |
| Storage requirements | Temp range, flammability, warehouse capabilities **stored**; only a list exists. No check that an item sits in a suitable location | `tools.py:468`; `storage_mismatch` planned |
| Low stock | **Implemented**, UoM-safe | `below_reorder.py` |
| Excess stock | **Implemented** | same, `mode="excess"` |
| Dormant | **Implemented**: last ISSUE older than N days | `risks.py:72` |
| Slow-moving | **Not implemented**; chat returns dormant instead | probe 11 |
| Stockout risk | **Not implemented**: below-reorder is not a forecast | — |
| Ageing buckets | **Not implemented** | `INVENTORY_CALCULATIONS.md` |
| Obsolescence | **Correctly refused** | `providers.py:253` |
| Price movement | **Not implemented** | — |

## 3. Costing

| Method | State | Notes |
|---|---|---|
| Moving weighted average | **Implemented, hand-tested** | Exposed in Costs page |
| FIFO cost layers | **Implemented** | Per warehouse; transfers start new layers at the transfer date, which understates age |
| Periodic weighted average | Code only, **no caller** | `engine.py:106` |
| Lot costing | Displayed per lot | No lot-based valuation total |
| Latest purchase price | **Implemented** with status allowlist | `engine.py:188` |
| Latest receipt cost | **Implemented** | |
| LIFO | **Not implemented** | Correct to leave off by default |
| Standard price | **Not handled** | `price_control` is a label; SAP `S` materials differ from moving average |
| FIFO pick suggestion | Code only, **no caller** | `engine.py:162`, yet listed in the capability matrix |

### Issuing is not valuation

- **Physical issuing policy** (FIFO, FEFO, LIFO for stacked stock) is what the warehouse does.
- **Accounting cost formula** is how value reaches the books.
- They are independent. A site can pick FEFO physically while valuing at moving average.

**LIFO [X]:** IAS 2 prohibits it as a cost formula; US GAAP permits it, and some companies use it for tax reasons. The model needs two separate settings per tenant, `issuing_policy` and `valuation_method`, plus the applicable framework. Never infer one from the other. Keep `fifo_pick` labelled operational, as the code does.

**What Lumiant should be:** a reader and explainer of the book value, not a parallel ledger. Use the ERP's valuation as authoritative, and treat recomputation as a diagnostic, as the repo already does with its "source valuation" comparison.

## 4. Defects and risks

| ID | P | Issue | Evidence | Fix |
|---|---|---|---|---|
| LA-02 | P0 | Expiry counts computed from capped rows | `risks.py:261`; truth 29/9, shown 1/0 | Separate count |
| LA-05 | P0 | Lot join on `lot_id` alone; SAP batches are normally unique within material/plant, so double-counting. +2.31% in a scratch test | `catalog.py:212`; probe 3 | Composite key; cardinality checks |
| LA-17 | P1 | **`txn_id` mapped to `MBLNR` in demo.** A material document has many lines. `prepare()` keeps only the first of each `txn_id` and warns, so real lines would vanish from cost calculations | `demo-alpha.yaml:113`; `engine.py:55-61` | Composite id `MBLNR-MJAHR-ZEILE`; treat key collision as an error |
| LA-16 | P1 | Computed ABC hard-capped at 1,000 items, returns `analysis_too_large` | `risks.py:586,600` | Compute in SQL |
| LA-16 | P1 | Cost comparison fails above 1,000 movements for one item/warehouse. Demo alone has 82,345 movements | `risks.py:671,682` | Stream movements in batches |
| LA-32 | P1 | **ABC basis is on-hand value.** Classic ABC usually ranks annual consumption value. The two can disagree sharply: dead expensive stock is "A" on-hand, "C" by usage | `abc.py`, `ABC_RULE` | Basis as configuration |
| LA-33 | P1 | **ABC thresholds are per-request.** Not stored per customer, so two users can get different classes | `api/analyses.py:60` | Tenant config, versioned, surfaced in provenance |
| LA-34 | P1 | **Reversals ignored in dormant analysis.** Only `ISSUE` is considered. A cancelled issue (SAP 262 reversing 261) would count as movement | `risks.py:122` | Net by reference; value-map rules |
| LA-35 | P2 | Negative stock raises an error in MWA/FIFO. SAP can permit it per plant | `engine.py:100` | Report, configurable |
| LA-36 | P2 | "Stock value" assumes the unit price is a stock-line attribute. Split valuation is refused | ISSUES #23 | Design with first customer that needs it |
| LA-37 | P2 | No "as of" history. Only a current snapshot, so no trend or period comparison | `stock_balance` | Snapshot store or movement-derived history |
| LA-38 | P3 | Costing `RECONCILE_TOLERANCE` is a fixed constant | `risks.py:55` | Per-tenant |

**Note on your ABC wording.** "A: high-value items, generally smaller proportion of total quantity" is a common description, but quantity is an outcome, not the method. Class boundaries should come from cumulative value share. The implementation is right to rank by value, and its `share_before` logic keeps the item crossing a cutoff in the higher class. The Costs page pre-fills 0.80 and 0.95 only as editable inputs; the backend has no defaults, which is correct.

## 5. Normalization

| Concern | State | Recommendation |
|---|---|---|
| Currency | No conversion; shown per currency; never summed. **Correct** | FX table with rate type and date, only when requested, labelled "converted", original kept |
| Units | No conversion; mismatches excluded and counted. **Correct** | Conversion table per item (SAP `MARM`) |
| Returns | At current average | Often should come back at original issue cost: customer decides |
| Adjustments | At current average | Same |
| Rounding | Half-even at display; intermediates exact. **Correct** | Per-tenant policy; `Decimal` default precision for FIFO outside `localcontext` is 28 digits, worth standardising |
| Effective dates | Not modelled | Add for prices, policies, mapping versions |
| Historical costs | Movements only | With snapshots |
| Reconciliation | **Implemented**: per warehouse, per currency, tolerance | Keep as a go-live gate; extend to quantity by item |
| Timezones | UTC assumed | Plant timezones matter for posting-date cut-offs (Q-016) |

## 6. Flexible attributes (100+ fields)

**Do not add 100 columns to the canonical model.** Use three tiers:

| Tier | Contents | Why |
|---|---|---|
| Core canonical | ~25 fields used by calculations and permissions | Stable, tested, typed |
| Registered attributes | Customer fields with type, label, unit, **sensitivity**, allowed values, filterable flag | The existing `attr_` mechanism plus metadata |
| Pass-through | Displayed only, not queryable | No cost for rarely used fields |

Store definitions in the metadata registry and values in the customer's source. Do not build an entity-attribute-value store, because it would slow queries and lose type safety. Extend the current design: it needs a sensitivity tag (LA-13), a unit and a list of allowed values.

## 7. Inventory risk rules

Each rule should be a versioned, parameterised definition with explained output. Suggested behaviours, all requiring customer approval:

| Risk | Needs | Output style |
|---|---|---|
| Low stock | Reorder policy, stock | "Below by X" (exists) |
| Excess | Max or cover target | "X above maximum", value tied up |
| Slow-moving | Consumption over a period | "Only 3 issues in 12 months" |
| Dormant | Last issue, reversal-aware | Date and duration |
| Stockout risk | Consumption rate, lead time, open POs | "Estimated to run out in about N days, if usage continues" |
| Ageing | Receipt dates | Age buckets with value |
| Obsolescence | Movement + lifecycle + equipment status | "Risk indicators: …" with factors, never "will become obsolete" |

Inferred risks must read as indicators, with the evidence listed and an uncertainty note. Lifecycle and equipment data do not exist in the model today, so the current refusal is correct.

## 8. Before calling anything verified on real data

Confirm with the customer (Q-019…Q-026 are a good start): material type meanings, which stock statuses count, valuation policy, moving-average drift tolerance, reversal rules, and authoritative reports. Until then every figure stays labelled draft, which the code already does.

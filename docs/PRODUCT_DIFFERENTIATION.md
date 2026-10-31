# Product Differentiation

Audit date 2026-10-31. Competitive statements here are reasoned judgement: **no market research was done** and they should be tested with customers.

## 1. Positioning

ERPs already record stock, value it, and produce MB52-style reports. Lumiant wins if it **answers cross-cutting questions that are slow in the ERP, and proves each answer**.

The defensible position is not "AI chat". Every vendor has that, including SAP's own assistants. It is:

> **Trustworthy answers across your inventory systems, with the source and calculation shown for each number, and without moving your data.**

The repo already has rare foundations: governed queries, per-number provenance, honest gaps, and reconciliation against the customer's own reports. A CFO cares about those more than conversation.

## 2. Features

MVP = valuable with the first customer's existing data. Later = needs more data or trust.

| Feature | Customer problem | Required data | Implementation | Business value | Differentiation | Limitations | Phase |
|---|---|---|---|---|---|---|---|
| **Reconciliation and data-quality** | "Can we trust the numbers?" | Stock, master, control report | Exists in part; extend | Finds errors immediately; builds trust | High: few tools lead with this | Needs the authoritative report | **MVP** |
| **Tied-up capital by stock status** | Blocked and QI stock is invisible | MB52 layout | **Exists** | Finds cash quickly | Medium | Definitions need approval | **MVP** |
| Value concentration | Where to focus cycle counts | Stock, price | **Exists** | Better counting | Low: standard analysis | Row cap | **MVP** |
| Natural-language analytics | Staff wait for analysts | Mapped data | Intent routing on governed metrics | Saves time | Medium: only if answers are provably right | Depends on eval quality | **MVP**, intent-only |
| Dormant stock | Dead capital | Movements | **Exists**; add reversals | Write-down, redeployment | Medium | Needs MB51 | **MVP** once data arrives |
| Excess and below-reorder | Stock imbalance | Planning data | **Exists** | Working capital | Low alone | Needs MARC | **MVP** once data arrives |
| **Cross-warehouse rebalancing** | One plant buys what another holds idle | Stock, policy, movement | Match excess to shortage per item | Direct cash saving; easy ROI story | **High** | Transfer cost, quality, item equivalence | Next |
| Inventory ageing | Hidden obsolescence and provisions | Receipt dates or layers | FIFO layers or batch dates | Supports provisions | Medium | Date quality | Next |
| Explainable recommendations | Rules are not trusted | Rule outputs | Each flag shows inputs and rule | Adoption | High with provenance | Needs approved rules | Next |
| Automated reports | Monthly manual work | Existing reports | Scheduled worker, delivered customer-side | Saves hours | Low | Needs a worker | Next |
| Price movement | Unnoticed cost increases | PO lines (EKPO) | Threshold rules per item/supplier | Procurement savings | Medium | Mixed units and terms | Next |
| **Duplicate item detection** | Same part under several codes | Item master text and specs | Normalised text and attributes; embeddings; human review | Reduces stock and purchasing cost | **High**: common, painful, and hard in ERPs | False positives; needs engineering review | Next |
| Supplier insights | Concentration and lead-time risk | PO, receipts, vendors | Governed metrics | Negotiation | Medium | Supplier data sensitivity | Later |
| **Cross-system intelligence** | Several ERPs after acquisitions | Multiple sources, item crosswalk | Multi-source tenant | **Strongest long-term moat** | **High** | Hard: identity, currency, timing | Later |
| Stockout risk | Line stoppage | Usage, lead times, open POs | Simple run-rate first | Avoids downtime | Medium | Demand variability | Later |
| Obsolescence risk | Write-offs surprise finance | Movement + lifecycle + equipment status | Indicators with evidence | Early provisions | Medium | Lifecycle data rarely available; never a certainty | Later |
| Predictive analytics | Forecast demand | Long clean history | Statistical forecasting | Planning | **Low**: ERPs and planning tools do this | Crowded; high accuracy burden | Later, if asked |

## 3. Do not build yet

| Idea | Why not |
|---|---|
| Autonomous agents acting in the ERP | Contradicts read-only, the core of the trust story |
| LLM-generated SQL | Gives up the main safety property |
| Generic "chat with your data" | Undifferentiated |
| Replacing MRP or planning | Competes with systems you intend to augment |
| Deep-learning forecasts | Needs clean data you do not yet have |

## 4. First value without any AI

With the two exports already received, Lumiant can already show value by status, concentration, data gaps, and reconciliation. Adding MB51 and MARC unlocks dormant, reorder and excess. **Build the first customer story on real findings from that data, delivered with no external AI.** That proves value and trust at once.

A useful sales artefact: a one-page **Inventory Health Report**: value by status, top concentrations, dormant value, data-quality gaps, each with sources.

## 5. Questions to validate

- Which decision would change if this answer took seconds instead of days?
- Who owns it, and what budget does it come from?
- Would they pay for a recurring product, or is it a one-off clean-up project?
- Is the buyer finance, supply chain, or IT?
- Which SAP capability already covers this (Fiori apps, Analytics Cloud, Joule)? Check per customer licence.

# Open Customer Questions

Discovery and onboarding questionnaire, audit date 2026-10-31. This extends `07-customer/OPEN_QUESTIONS.md` (Q-001…Q-026), which remains the running log; matching IDs are noted.

**Gate:** 🔴 before any development for that customer · 🟠 before deployment · 🟢 improves the result.

## Must answer first

Without these, no real work or commitment can start:

1. Which system is the source of inventory truth, and which version? (B3, I1)
2. Where will the software run, and may anything leave? (I5, S1, S2)
3. May a connector be installed, and may it make outbound connections? (I6, I7)
4. Can approved read-only views be provided, by whom? (D1, D2)
5. Is external AI permitted? If so, which provider, region and model? (S3, S4)
6. Who signs off access, data handling and revocation? (B4, S5)
7. Which report is the authoritative figure we must reconcile to? (F1)
8. What is the valuation method? (F2)
9. What may Lumiant keep from files already supplied, for how long, and how is it deleted? (S8, Q-023)

## 1. Business stakeholders

| # | Question | Why | Gate |
|---|---|---|---|
| B1 | What decision do you want to make faster or better? Give the last three painful examples | Defines MVP | 🔴 |
| B2 | Who will use this daily, and in which roles? | Permissions, UI | 🔴 |
| B3 | Which systems hold inventory data? Any acquired or separate businesses? | Scope | 🔴 |
| B4 | Who is the executive sponsor, and who approves access? | Governance | 🔴 |
| B5 | What would success look like in 90 days, in measurable terms? | Acceptance | 🔴 |
| B6 | Are Cognos, Hyperion or other tools already answering these questions? Where do they fall short? | Differentiation | 🟠 |
| B7 | Languages, regions, and time zones? | UI, dates | 🟠 |
| B8 | Is this one company or several legal entities? | Tenancy, scope | 🔴 |
| B9 | Do you want recommendations, or facts only? | Product scope | 🟢 |

## 2. IT administrators

| # | Question | Why | Gate |
|---|---|---|---|
| I1 | Which ERP and exact version/release? (Q-001) | Connector | 🔴 |
| I2 | On-premises, private cloud, or vendor cloud? | Deployment | 🔴 |
| I3 | Is there a central data warehouse? On what technology? | Often the best route | 🔴 |
| I4 | Are Cognos or Hyperion reporting layers, and what is their source? | Integration choice | 🟠 |
| I5 | Which deployment is acceptable: your network, your cloud, or hosted? Which cloud and region? (Q-012) | Model A–G | 🔴 |
| I6 | Can a signed container or service run on your network? Kubernetes, VM, Windows? | Install | 🔴 |
| I7 | Are outbound-only connections permitted? Through a TLS-inspecting proxy? | Agent design | 🔴 |
| I8 | Which APIs are licensed and enabled (OData, RFC, JSON-2, Cognos REST)? | Connector | 🟠 |
| I9 | Identity provider, protocol, group structure; does a gateway exist? (Q-010) | SSO | 🟠 |
| I10 | How are software updates approved, and what is the change window? | Release | 🟠 |
| I11 | Do you require air-gapped operation? | Packaging | 🔴 |
| I12 | Monitoring and SIEM tools? | Integration | 🟠 |
| I13 | Who supports it out of hours? | Operations | 🟠 |
| I14 | Is there a test environment with realistic data? | Validation | 🔴 |

## 3. Database administrators

| # | Question | Why | Gate |
|---|---|---|---|
| D1 | Can dedicated read-only views be created, and by whom? (Q-002) | Least privilege | 🔴 |
| D2 | Can you issue a read-only service account? Which authentication? | Access | 🔴 |
| D3 | Can it run against a replica or reporting copy? | Protects production | 🔴 |
| D4 | Schema documentation or DDL? (Q-003) | Mapping | 🟠 |
| D5 | May metadata be read? Are comments populated? | Discovery | 🟠 |
| D6 | May aggregate profiling run? Sample values? | Validation | 🟠 |
| D7 | Row counts for item, stock, movement and purchase tables (Q-016) | Capacity | 🟠 |
| D8 | Query budget: concurrency, peak windows, maximum runtime | Load | 🟠 |
| D9 | Are indexes or materialized views available or allowed? | Performance | 🟢 |
| D10 | Refresh schedule and time zone? (Q-016) | Freshness | 🟠 |
| D11 | Is row-level security already in the database? | Authorization | 🟠 |
| D12 | How are schema changes announced? | Drift | 🟠 |
| D13 | SAP: is HANA licensed as runtime or full use? Who confirms permitted access? | Compliance | 🔴 |

## 4. Cybersecurity

| # | Question | Why | Gate |
|---|---|---|---|
| S1 | Must all data stay in your infrastructure? | Model | 🔴 |
| S2 | May query results leave? Metadata? Aggregates only? | Model | 🔴 |
| S3 | Are external LLM providers permitted? Which, in what region? (Q-013) | AI mode | 🔴 |
| S4 | Is local or private inference required? | Model E | 🔴 |
| S5 | Who approves access, and how is it revoked? | Governance | 🔴 |
| S6 | Data residency requirements? | Hosting | 🔴 |
| S7 | Required: SSO, MFA, session limits, IP limits? | Auth | 🟠 |
| S8 | Handling terms for files already shared: retention, access, deletion (Q-023) | Compliance | 🔴 |
| S9 | Audit content, retention, and export needs (Q-014) | Audit | 🟠 |
| S10 | Encryption standards, key ownership, CMK requirements | Infrastructure | 🟠 |
| S11 | Restrictions on third parties or subprocessors? | Contract | 🔴 |
| S12 | Do you require a pen test, SOC 2, or ISO 27001 from vendors? | **Lumiant has none today** | 🔴 |
| S13 | Which data classes apply: confidential pricing, supplier, personal? | Sensitivity | 🟠 |
| S14 | Incident notification terms? | Contract | 🟠 |
| S15 | Do you permit support access? Under what approval? | Operations | 🟠 |
| S16 | Vendor risk process and how long does it take? | Timeline | 🟠 |

## 5. Finance and inventory

| # | Question | Why | Gate |
|---|---|---|---|
| F1 | Which report is authoritative for value and quantity? Acceptable variance? (Q-015) | Go-live | 🔴 |
| F2 | Valuation: moving average, standard, FIFO, other, per material type? (Q-006, Q-021) | Costing | 🔴 |
| F3 | Accounting framework (IFRS, US GAAP, other)? | LIFO applicability | 🟠 |
| F4 | Issuing policy: FIFO, FEFO, LIFO, by material? | Kept separate from valuation | 🟠 |
| F5 | How many warehouses, plants, storage locations? | Scope | 🟠 |
| F6 | How many SKUs and stock records? | Capacity | 🟠 |
| F7 | Which item master fields matter? Which are unreliable? | Mapping | 🟠 |
| F8 | How is ABC determined: basis, period, thresholds; per plant? (Q-005) | ABC | 🟠 |
| F9 | How do you define slow-moving, dormant, and excess? | Rules | 🟠 |
| F10 | Which stock statuses count as available? (Q-020) | Headline value | 🔴 |
| F11 | Material type and code meanings (Q-019, Q-022) | Value maps | 🟠 |
| F12 | Treatment of consignment, in-transit, returns, negative stock? | Totals | 🟠 |
| F13 | Currencies, FX source and date rule? (Q-009) | Conversion | 🟠 |
| F14 | Unit conversions: where are they maintained? (Q-017) | Totals | 🟢 |
| F15 | Which movements are reversals or should be excluded? | Dormant accuracy | 🟠 |
| F16 | Latest price: which definition and statuses? (Q-008) | Costing | 🟠 |
| F17 | Period calendar and close rules (Q-007) | Periodic methods | 🟢 |
| F18 | Item, supplier or price data that some staff must not see? (Q-011) | Authorization | 🔴 |
| F19 | Storage rules: temperature, flammability, customer-specific | Storage checks | 🟢 |
| F20 | Lifecycle or equipment data available? | Obsolescence | 🟢 |

## 6. Questions we should answer ourselves

| Question | Owner |
|---|---|
| Who owns the code and IP; under which legal entity is it offered? | Lumiant leadership |
| What licence and repository visibility apply? | Leadership |
| What does a pilot contract include: DPA, liability, security terms? | Legal |
| Which LLM provider contract and model would we offer, and what retention applies? | Product, legal |
| How do we price customer-hosted vs SaaS? | Product |
| Who provides support, in which hours? | Operations |
| When do we need SOC 2 or ISO 27001? | Leadership |

# 0003 — Kimball star schema at prescriber x drug x year grain

**Status:** accepted

## Context
Consumers ask questions like "spend by specialty by year" or "which molecules grew fastest".
They use SQL and BI tools that work best with facts joined to dimensions.

## Decision
A **Kimball dimensional model**:
- `fct_prescriptions`, with grain **one row per prescriber (NPI) x drug (brand + generic) x data year**,
  which is the grain of the CMS file itself
- conformed dimensions `dim_prescriber` (SCD Type 2), `dim_drug`, `dim_geography`
- an **unknown member** (`-1` / `UNK`) in every dimension so facts never vanish in a join
- additive measures (claims, day supply, cost) plus pre-computed ratios
- analytics marts built on the star for the three business questions

## Alternatives considered
| Option | Why not |
|---|---|
| One big wide table (OBT) | Fast to query and great for a single dashboard, but repeats prescriber attributes on every row and makes point-in-time history awkward. The marts give OBT-style convenience on top of the star. |
| Inmon 3NF enterprise warehouse | Built for integrating many source systems. One source does not justify the extra layer. |
| Data Vault | Excellent for auditability across many changing sources, but heavy (hubs, links, satellites) for one feed. The raw + status-labelled staging layers already give a replayable audit trail. |

## Consequences
- **Declare the grain first:** every test (`prescription_id` unique, cost reconciliation) protects it.
- Ratios (`cost_per_claim`) are not additive. Re-compute them from summed measures, never average them.
- Interview angle: be ready to explain grain, conformed dimensions, surrogate vs natural keys, and why unknown members exist.

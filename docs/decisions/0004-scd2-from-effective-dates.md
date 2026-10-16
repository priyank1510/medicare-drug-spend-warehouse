# 0004 — SCD Type 2 rebuilt from data_year, not dbt snapshots

**Status:** accepted

## Context
Prescribers move, and their recorded specialty changes. Spend must be attributed to the
attributes that were true **in that year** (point-in-time). Critically, CMS-style corrections
arrive late: the 2022 v2 file lands **after** the 2023 file and fixes a wrong 2022 specialty.

## Decision
Build `dim_prescriber` from `int_prescriber_yearly_attributes` on every run:
1. one attribute row per NPI per data_year
2. a new version starts when `attribute_hash` differs from the previous year's (`lag()`)
3. `valid_to_year` = next version's start - 1 (`lead()`), or 9999 when open
4. the fact joins with `data_year between valid_from_year and valid_to_year`

## Alternatives considered
| Option | Why not |
|---|---|
| `dbt snapshot` (timestamp/check strategy) | Snapshots version by **processing time**: "what did the table look like when the job ran". The wrong 2022 specialty would be frozen into history and the late correction would show up as a 2025 change. That is wrong for a dataset whose truth is defined by business period. |
| SCD Type 1 (overwrite) | Loses history: 2021 spend would be re-attributed to the 2023 specialty. |
| SCD Type 3 (previous-value column) | Keeps only one prior value; prescribers can change more than once (the unit test covers A -> B -> A). |

## Consequences
- Late corrections "just work": the reconciliation report checks that all 10 corrected
  prescribers end up with exactly one version.
- Surrogate keys can change when version boundaries move, which is **why the fact is a
  full-refresh table, not incremental**. At very large scale you would rebuild only the affected
  data years (an incremental strategy partitioned by data_year).
- Snapshots are still the right tool when the source has **no** effective dates and you must
  capture changes as you observe them (for example a mutable operational table).

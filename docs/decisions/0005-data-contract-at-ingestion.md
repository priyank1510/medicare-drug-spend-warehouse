# 0005 — Structural data contract enforced at ingestion

**Status:** accepted

## Context
Producers change files. CMS renamed every column between older and newer releases
(`npi` -> `Prscrbr_NPI`), added columns (`Prscrbr_Type_Src`), and ships extra 65+ columns we do not use.
Silent schema drift is one of the most common causes of broken pipelines.

## Decision
A YAML **data contract** (`contracts/part_d_prescriber_drug.yml`) lists every canonical column,
its aliases, whether it is required, and the known-but-ignored columns. Ingestion maps each
file's header through it and:
- **rename** -> mapped via alias, recorded in the load audit
- **additive optional column absent** -> loaded as NULL
- **known ignored column** -> dropped, recorded
- **unknown column** or **missing required column** -> file rejected (`unknown_columns: fail`)

Row-level semantics (valid NPI, non-negative measures) are **not** in the contract check;
they belong to dbt (see 0006), so one bad row does not reject a whole file.

## Alternatives considered
| Option | Why not |
|---|---|
| Let the warehouse infer schema | Drift becomes a silent data bug discovered weeks later in a dashboard. |
| Hard-code column positions | Breaks on reorder; cannot express renames. |
| Great Expectations / Soda for structure | Valid choices at larger scale. A 100-line contract module is easier to read and teaches the idea directly. |

## Consequences
- Adding a new CMS column is a deliberate one-line contract change, reviewed in a pull request.
- The audit table stores a schema fingerprint per batch, so you can see exactly when a layout changed.
- This is "shift-left" quality: problems are caught where they enter, the cheapest place to fix them.

# 0002 — ELT with dbt for all transformations

**Status:** accepted

## Context
Cleaning, deduplication, SCD2 logic and business metrics are the riskiest code in the project.
They must be reviewable, testable and re-runnable from scratch.

## Decision
**ELT:** ingestion loads data as raw text with lineage columns and does no business logic.
All transformation is SQL in **dbt**, organized as `staging -> intermediate -> marts` plus a
`quality` folder. `dbt build` runs seeds, models, 50+ data tests and unit tests in dependency order.

## Alternatives considered
| Option | Why not |
|---|---|
| ETL in Python (pandas) | Logic hides in procedural code, is harder to test column by column, and has no lineage graph or docs. |
| Hand-written SQL scripts | No dependency graph, no built-in tests, no docs site. Run order is manual and breaks. |
| SQLMesh | A strong alternative (virtual environments, built-in change detection), but dbt appears far more often in job postings. |
| Spark SQL jobs | Overkill for single-node data (see 0001). |

## Consequences
- Raw is a faithful replay log: if a cleaning rule is wrong, fix the SQL and rebuild. No re-ingestion.
- Business rules live in one place (`stg_part_d__prescriber_drug`), referenced everywhere via `ref()`.
- dbt docs give a browsable lineage graph for free (`make up`, then http://localhost:8080).
- Cost: the team must know SQL and dbt conventions. That is the industry norm.

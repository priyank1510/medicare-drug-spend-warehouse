# 0001 — DuckDB as the warehouse engine

**Status:** accepted

## Context
The workload is analytical: scans and aggregations over tens of thousands of rows here, and
millions if you load several real CMS state extracts. It has to run on a laptop and in CI for free,
with no accounts, credentials or servers.

## Decision
Use **DuckDB**, an in-process columnar OLAP database stored in one file
(`data/warehouse/drugspend.duckdb`), with `dbt-duckdb` as the dbt adapter.

## Alternatives considered
| Option | Why not (for this project) |
|---|---|
| PostgreSQL | Row-oriented OLTP engine. Fine at this size, but needs a server container and is the wrong engine shape for analytics. |
| Snowflake / BigQuery / Redshift | The real-world target, but costs money, needs credentials in CI, and adds nothing to what this project demonstrates. |
| Spark | Distributed compute for data that does not fit on one machine. This data does. Spark would add a cluster's worth of complexity for no benefit. |
| SQLite | Embedded like DuckDB, but row-oriented and missing analytical SQL features. |

## Consequences
- The models are plain SQL with dbt macros, so moving to Snowflake or BigQuery means changing
  the adapter and a few dialect functions (`try_cast`, `md5`, `regexp_matches`), not the design.
  This is the "make reversible decisions" principle from *Fundamentals of Data Engineering*, ch. 3.
- DuckDB allows one writer at a time. Fine for a batch pipeline; not suitable for many concurrent writers.
- Interview angle: "I picked the smallest tool that fits the data, and kept the design portable."

# Architecture Decision Records

An ADR captures one significant decision: the context, what was chosen, what was rejected,
and what it costs. They are short on purpose. In an interview, each one is a ready-made
answer to "why did you build it this way?"

| # | Decision | One-line reason |
|---|---|---|
| [0001](0001-duckdb-as-warehouse-engine.md) | DuckDB as the warehouse engine | Columnar SQL warehouse with zero infrastructure and zero cost |
| [0002](0002-elt-with-dbt.md) | ELT with dbt for all transformations | Versioned, tested, documented SQL with a dependency graph |
| [0003](0003-kimball-star-schema.md) | Kimball star schema at prescriber x drug x year grain | The shape analysts and BI tools expect; grain matches the source |
| [0004](0004-scd2-from-effective-dates.md) | SCD2 rebuilt from data_year, not dbt snapshots | Late-arriving corrections must be able to rewrite history |
| [0005](0005-data-contract-at-ingestion.md) | Structural data contract enforced at ingestion | Schema drift is handled explicitly; surprises stop at the door |
| [0006](0006-quarantine-not-drop.md) | Label every row; quarantine bad rows instead of dropping or failing | Nothing disappears silently, and one bad row does not block a release |
| [0007](0007-immutable-landing-idempotent-loads.md) | Immutable landing zone, arrival partitions, idempotent loads | Safe reruns and a correct notion of "late" |
| [0008](0008-synthetic-data-with-ground-truth.md) | Synthetic data by default, with a ground-truth defect manifest | Deterministic CI and provable data quality |

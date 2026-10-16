# 0007 — Immutable landing zone, arrival partitions, idempotent loads

**Status:** accepted

## Context
Pipelines get re-run: after failures, during backfills, by accident. Corrections arrive after newer
data. The pipeline must produce the same result no matter how many times it runs, and must know
which data arrived late.

## Decision
- Landing files sit in Hive-style partitions: `landing/arrival_date=YYYY-MM-DD/partd_<year>_v<version>.csv`.
- Files are processed in **arrival order**, and the arrival date travels with every row.
- Every file is fingerprinted (SHA-256) in `raw._load_audit`. A file already loaded is skipped.
  The **same name with different content is rejected**: corrections must be a new version (`_v2`).
- A file's rows and its audit record commit in **one transaction**.

## Alternatives considered
| Option | Why not |
|---|---|
| Truncate-and-reload everything | Idempotent but wasteful, and loses the history of what arrived when. |
| Overwrite files in place | Destroys evidence of what the producer originally sent; impossible to audit. |
| Track "last processed timestamp" only | Breaks when an old file is re-delivered or a backfill happens. |

## Consequences
- Rerunning `ingest` is always safe (tested). Rerunning `transform` rebuilds identical outputs (tested).
- The book's three kinds of time are all visible: event period (`data_year`), ingestion time
  (`arrival_date`, `loaded_at`), and processing (dbt run time).

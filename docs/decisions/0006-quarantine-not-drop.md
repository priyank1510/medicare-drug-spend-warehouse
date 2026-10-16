# 0006 — Label every row; quarantine bad rows instead of dropping or failing

**Status:** accepted

## Context
Real files contain a few bad rows (corrupt NPIs, negative counts, missing cost). There are three
common reactions: drop them silently, fail the whole run, or set them aside.

## Decision
The staging model gives **every raw row exactly one `row_status`**, in precedence order:
`exact_duplicate` -> `superseded` -> `quarantined` (with `dq_issue`) -> `accepted`.
Only `accepted` rows reach the marts. `dq_quarantine` keeps the rejects with lineage,
and `dq_reconciliation` counts every status. A singular test asserts raw rows = staged rows.

## Alternatives considered
| Option | Why not |
|---|---|
| Silently filter bad rows | Revenue-impacting data disappears with no trace and no way to report back to the producer. |
| Fail the run on any bad row | One corrupt NPI in 30,000 rows would block every downstream consumer. |
| Fix bad values (impute) | Inventing a cost or an NPI creates data that never existed. In healthcare and finance that is unacceptable. |

## Consequences
- Accountability: accepted + duplicate + superseded + quarantined = delivered, to the row.
- Policy choice worth discussing: if the **latest** version of a key is invalid, the key is
  quarantined rather than falling back to the older valid version. Using stale numbers
  silently is worse than showing a known gap.
- A real deployment would alert when the quarantine rate exceeds a threshold (for example 1%).

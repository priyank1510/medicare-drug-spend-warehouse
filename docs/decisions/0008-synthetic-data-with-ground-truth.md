# 0008 — Synthetic data by default, with a ground-truth defect manifest

**Status:** accepted

## Context
CI must be fast, offline and deterministic. More importantly, "my pipeline handles dirty data"
is a claim. Without knowing exactly what is wrong in the input, you cannot prove it.

## Decision
`drugspend generate` produces CMS-shaped files with a fixed seed and injects nine defect classes,
writing exactly what it injected to `_injected_defects.json`. `drugspend report` compares the
warehouse against that manifest and **fails the build** on any mismatch.
`make download-cms` loads a real state-level CMS extract through the same pipeline.

## Alternatives considered
| Option | Why not |
|---|---|
| Real CMS data only | Downloads in CI are slow and flaky, and real data has no answer key for its defects. |
| A small hand-made CSV | Too small to exercise windows, versions and SCD2 realistically. |

## Consequences
- The headline metric ("100% of 1,971 injected defects routed correctly, reconciled to the cent")
  is measured on every commit, not claimed.
- Synthetic costs are illustrative. Never present them as real Medicare figures.
- Mutation check: deliberately breaking four pieces of logic (restatement order, SCD2 change
  detection, case normalization, NPI rule) makes the test suite fail every time.

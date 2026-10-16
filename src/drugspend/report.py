"""Proves the pipeline works: compares what the warehouse did with what the generator injected.

Each check is "expected (from _injected_defects.json) vs actual (queried from the warehouse)".
The report is written to data/reports/defect_report.md and the process exits non-zero on any
mismatch, so CI fails if a change to the cleaning logic stops catching a defect class.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_RELATIONS = {
    "staging": "staging.stg_part_d__prescriber_drug",
    "reconciliation": "quality.dq_reconciliation",
    "yearly": "intermediate.int_prescriber_yearly_attributes",
    "dim_prescriber": "marts.dim_prescriber",
    "dim_drug": "marts.dim_drug",
    "fact": "marts.fct_prescriptions",
}


@dataclass
class Check:
    name: str
    how_handled: str
    expected: int
    actual: int

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


def _scalar(con, sql: str) -> int:
    return int(con.execute(sql).fetchall()[0][0] or 0)


def run_checks(con, manifest: dict, relations: dict | None = None) -> list[Check]:
    r = {**DEFAULT_RELATIONS, **(relations or {})}
    d, e = manifest["defects"], manifest["expected"]
    status = {}
    issue = {}
    for row_status, dq_issue, n in con.execute(
            f"select row_status, dq_issue, row_count from {r['reconciliation']}").fetchall():
        status[row_status] = status.get(row_status, 0) + int(n)
        issue[dq_issue] = int(n)

    corrected = "', '".join(e["specialty_corrected_npis"])
    checks = [
        Check("Exact duplicate rows", "removed in staging (row_hash within batch)",
              d["exact_duplicate"], status.get("exact_duplicate", 0)),
        Check("Restated rows (late-arriving 2022 v2)", "older version marked superseded",
              d["superseded_by_restatement"], status.get("superseded", 0)),
        Check("Late-arriving new 2022 rows", "accepted from the v2 file",
              d["late_arriving_new_rows"] + d["superseded_by_restatement"],
              _scalar(con, f"select count(*) from {r['staging']} "
                           f"where file_version = 2 and row_status = 'accepted'")),
        Check("Invalid NPI", "quarantined: invalid_npi", d["invalid_npi"], issue.get("invalid_npi", 0)),
        Check("Negative measures", "quarantined: negative_measure",
              d["negative_measure"], issue.get("negative_measure", 0)),
        Check("Missing drug cost", "quarantined: missing_drug_cost",
              d["missing_drug_cost"], issue.get("missing_drug_cost", 0)),
        Check("Prescriber-years with no specialty", "kept as explicit 'UNKNOWN' member",
              d["missing_specialty_prescriber_years"],
              _scalar(con, f"select count(*) from {r['yearly']} where prescriber_specialty = 'UNKNOWN'")),
        Check("Wrong 2022 specialty fixed by correction", "SCD2 rebuilt: 1 version per corrected NPI",
              len(e["specialty_corrected_npis"]),
              _scalar(con, f"select count(*) from (select npi from {r['dim_prescriber']} "
                           f"where npi in ('{corrected}') group by npi having count(*) = 1) t")),
        Check("Casing/whitespace noise + legacy upper-case names", "normalized: distinct drugs = catalog",
              e["distinct_drugs"], _scalar(con, f"select count(*) from {r['dim_drug']} where drug_sk <> '-1'")),
        Check("Legacy-schema rows (renamed columns, $ costs)", "mapped by contract aliases, parsed",
              d["legacy_schema_rows"],
              _scalar(con, f"select count(*) from {r['staging']} where data_year = 2021")),
        Check("Accepted rows reaching the fact", "everything else", e["accepted_rows"],
              _scalar(con, f"select count(*) from {r['fact']}")),
    ]
    return checks


def render(checks: list[Check], manifest: dict, timings: dict | None = None) -> str:
    caught = sum(c.passed for c in checks)
    lines = [
        "# Defect reconciliation report",
        "",
        f"Synthetic run: seed={manifest['seed']}, prescribers={manifest['n_prescribers']}, "
        f"rows delivered={manifest['rows_written_total']:,}.",
        "",
        "| Defect class | Handling | Expected | Actual | Result |",
        "|---|---|---:|---:|:---:|",
    ]
    for c in checks:
        lines.append(f"| {c.name} | {c.how_handled} | {c.expected:,} | {c.actual:,} | "
                     f"{'PASS' if c.passed else 'FAIL'} |")
    lines += ["", f"**{caught}/{len(checks)} checks passed.**"]
    if timings:
        total = sum(timings.values())
        lines += ["", "## Runtime (this machine)", "", "| Stage | Seconds |", "|---|---:|"]
        lines += [f"| {k} | {v:.1f} |" for k, v in timings.items()]
        lines += [f"| **total** | **{total:.1f}** |",
                  "", f"Throughput: {manifest['rows_written_total'] / max(total, 1e-9):,.0f} delivered rows/second end to end."]
    return "\n".join(lines) + "\n"


def build_report(con, manifest_path: Path, out_path: Path, timings: dict | None = None,
                 relations: dict | None = None) -> tuple[bool, str]:
    manifest = json.loads(Path(manifest_path).read_text())
    checks = run_checks(con, manifest, relations)
    text = render(checks, manifest, timings)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    return all(c.passed for c in checks), text

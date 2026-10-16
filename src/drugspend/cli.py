"""Command line entry point:  python -m drugspend.cli <command>

  generate      write synthetic CMS files (with injected defects) to data/landing
  ingest        load new landing files into raw (idempotent)
  transform     dbt build (models + all tests) and dbt docs generate
  report        reconcile warehouse results against the injected-defect manifest
  run           generate -> ingest -> transform -> report, timing each stage
  download-cms  fetch a REAL CMS extract (one state, one year) into data/landing
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

from drugspend.config import get_settings


def _dbt(*args: str) -> None:
    s = get_settings()
    exe = shutil.which("dbt")
    if exe is None:
        sys.exit("dbt is not installed. Use `make run` (Docker) or `pip install -r requirements.txt`.")
    env = {**os.environ, "DRUGSPEND_DUCKDB_PATH": str(s.warehouse_path)}
    cmd = [exe, *args, "--project-dir", str(s.dbt_dir), "--profiles-dir", str(s.dbt_dir)]
    print("$", " ".join(cmd[:3]), "...", flush=True)
    subprocess.run(cmd, check=True, cwd=s.dbt_dir, env=env)


def cmd_generate(a) -> None:
    from drugspend.generate import generate
    s = get_settings()
    if a.fresh:  # start from a clean slate so reruns are reproducible
        for d in (s.landing_dir, s.bronze_dir, s.warehouse_path.parent, s.reports_dir):
            shutil.rmtree(d, ignore_errors=True)
    m = generate(a.prescribers, a.seed)
    print(f"generated {m['rows_written_total']:,} rows in {len(m['files_in_arrival_order'])} files")


def cmd_ingest(_a) -> None:
    from drugspend.ingest import main
    main([])


def cmd_transform(_a) -> None:
    _dbt("build")          # seeds + models + data tests + unit tests, in DAG order
    _dbt("docs", "generate")


def cmd_report(_a, timings: dict | None = None) -> None:
    import duckdb
    from drugspend.report import build_report
    s = get_settings()
    con = duckdb.connect(str(s.warehouse_path), read_only=True)
    try:
        ok, text = build_report(con, s.defect_manifest_path, s.reports_dir / "defect_report.md", timings)
    finally:
        con.close()
    print(text)
    if not ok:
        sys.exit("Reconciliation FAILED: a defect class was not handled as expected.")


def cmd_run(a) -> None:
    timings = {}
    for name, fn in [("generate", cmd_generate), ("ingest", cmd_ingest), ("transform (dbt build + docs)", cmd_transform)]:
        t0 = time.perf_counter()
        fn(a)
        timings[name] = time.perf_counter() - t0
    cmd_report(a, timings)


def cmd_download(a) -> None:
    from drugspend.download_cms import download
    download(a.year, a.state, a.dataset_id, a.max_rows)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="drugspend", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("generate", "run"):
        p = sub.add_parser(name)
        p.add_argument("--prescribers", type=int, default=1500)
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--no-fresh", dest="fresh", action="store_false",
                       help="keep existing data/ instead of wiping it first")
    sub.add_parser("ingest")
    sub.add_parser("transform")
    sub.add_parser("report")
    p = sub.add_parser("download-cms")
    p.add_argument("--year", type=int, default=2023)
    p.add_argument("--state", default="WI")
    p.add_argument("--dataset-id", default=None, help="data.cms.gov dataset UUID for that year")
    p.add_argument("--max-rows", type=int, default=200_000)

    a = ap.parse_args(argv)
    {"generate": cmd_generate, "ingest": cmd_ingest, "transform": cmd_transform, "report": cmd_report,
     "run": cmd_run, "download-cms": cmd_download}[a.command](a)


if __name__ == "__main__":
    main()

"""End-to-end: generate -> ingest -> dbt build (models + data tests + unit tests) -> report.

The report step exits non-zero unless every injected defect class was handled exactly as
expected, so this one test is the project's acceptance test."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from drugspend.config import REPO_ROOT, get_settings

pytestmark = pytest.mark.e2e


@pytest.fixture()
def needs_stack():
    pytest.importorskip("duckdb")
    if shutil.which("dbt") is None:
        pytest.skip("dbt not installed")


def _cli(*args):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "src"), os.environ.get("PYTHONPATH", "")])}
    subprocess.run([sys.executable, "-m", "drugspend.cli", *args], check=True, env=env, cwd=REPO_ROOT)


def test_full_pipeline_catches_every_injected_defect(data_dir, needs_stack):
    _cli("run", "--prescribers", "400", "--seed", "11")
    s = get_settings()
    report = (s.reports_dir / "defect_report.md").read_text()
    assert "FAIL" not in report


def test_rerunning_ingest_and_transform_changes_nothing(data_dir, needs_stack):
    import duckdb

    _cli("run", "--prescribers", "300", "--seed", "12")
    s = get_settings()

    def fact_state():
        con = duckdb.connect(str(s.warehouse_path), read_only=True)
        try:
            return con.execute("select count(*), round(sum(total_drug_cost), 2) from marts.fct_prescriptions").fetchall()
        finally:
            con.close()

    before = fact_state()
    _cli("ingest")
    _cli("transform")
    assert fact_state() == before


def test_late_correction_rewrites_history(data_dir, needs_stack):
    import duckdb

    _cli("run", "--prescribers", "300", "--seed", "13")
    s = get_settings()
    npis = json.loads(s.defect_manifest_path.read_text())["expected"]["specialty_corrected_npis"]
    con = duckdb.connect(str(s.warehouse_path), read_only=True)
    try:
        versions = con.execute(
            "select npi, count(*) from marts.dim_prescriber where npi in ({}) group by npi".format(
                ",".join("?" * len(npis))), npis).fetchall()
    finally:
        con.close()
    assert len(versions) == len(npis)
    assert all(n == 1 for _, n in versions)

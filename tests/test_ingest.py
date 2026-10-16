import csv

import pytest

from drugspend.config import get_settings
from drugspend.contract import SchemaContractError, load_contract
from drugspend.generate import generate
from drugspend.ingest import LINEAGE_COLUMNS, discover_files, ingest, normalize_to_bronze, row_hash


def test_files_are_processed_in_arrival_order(data_dir):
    generate(100, seed=2)
    names = [f.path.name for f in discover_files(get_settings().landing_dir)]
    assert names == ["partd_2021_v1.csv", "partd_2022_v1.csv", "partd_2023_v1.csv", "partd_2022_v2.csv"]


def test_file_outside_an_arrival_partition_is_rejected(data_dir):
    landing = get_settings().landing_dir
    landing.mkdir(parents=True)
    (landing / "partd_2021_v1.csv").write_text("x\n")
    with pytest.raises(SchemaContractError, match="arrival_date"):
        discover_files(landing)


def test_bronze_has_canonical_columns_and_lineage(data_dir, contract_path):
    generate(80, seed=4)
    s = get_settings()
    contract = load_contract(contract_path)
    legacy = discover_files(s.landing_dir)[0]
    path, n, mapping = normalize_to_bronze(legacy, contract, "b1", 2021, 1, "now", s.bronze_dir)
    with path.open(newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == contract.canonical_names + LINEAGE_COLUMNS
    assert len(rows) - 1 == n > 0
    assert mapping.renamed  # legacy names were translated


def test_ragged_row_is_rejected(data_dir, contract_path):
    generate(50, seed=4)
    s = get_settings()
    f = discover_files(s.landing_dir)[1]
    with f.path.open("a") as fh:
        fh.write("1234567890,only,three\n")
    with pytest.raises(SchemaContractError, match="fields"):
        normalize_to_bronze(f, load_contract(contract_path), "b", 2022, 1, "now", s.bronze_dir)


def test_row_hash_treats_none_and_empty_alike_and_is_stable():
    assert row_hash(["a", None]) == row_hash(["a", ""])
    assert row_hash(["a", "b"]) != row_hash(["a", "c"])


def test_ingest_is_idempotent_and_audited(data_dir):
    duckdb = pytest.importorskip("duckdb")
    m = generate(120, seed=6)
    first = ingest()
    second = ingest()
    assert [r.status for r in first] == ["loaded"] * 4
    assert [r.status for r in second] == ["skipped_already_loaded"] * 4
    con = duckdb.connect(str(get_settings().warehouse_path))
    try:
        raw = con.execute("select count(*) from raw.part_d_prescriber_drug").fetchall()[0][0]
        audit = con.execute("select count(*), sum(row_count) from raw._load_audit").fetchall()[0]
    finally:
        con.close()
    assert raw == m["rows_written_total"] == audit[1]
    assert audit[0] == 4


def test_changed_file_with_same_name_is_rejected(data_dir):
    pytest.importorskip("duckdb")
    generate(60, seed=8)
    ingest()
    first = discover_files(get_settings().landing_dir)[0].path
    with first.open("a") as fh:
        fh.write(first.read_text().splitlines()[1] + "\n")
    with pytest.raises(SchemaContractError, match="immutable"):
        ingest()

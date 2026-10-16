import csv
import hashlib
from collections import Counter

from drugspend.generate import generate


def _rows(path):
    with path.open(newline="") as fh:
        r = csv.reader(fh)
        return next(r), [tuple(x) for x in r]


def test_generation_is_deterministic(data_dir, tmp_path):
    a = generate(200, seed=7, out_dir=tmp_path / "a")
    b = generate(200, seed=7, out_dir=tmp_path / "b")
    assert a == b
    for rel in a["files_in_arrival_order"]:
        ha = hashlib.sha256((tmp_path / "a" / rel).read_bytes()).hexdigest()
        hb = hashlib.sha256((tmp_path / "b" / rel).read_bytes()).hexdigest()
        assert ha == hb


def test_correction_file_arrives_after_the_next_year(data_dir, tmp_path):
    m = generate(200, seed=1, out_dir=tmp_path)
    order = m["files_in_arrival_order"]
    assert order[-1].endswith("partd_2022_v2.csv")
    assert order.index("arrival_date=2025-05-01/partd_2023_v1.csv") < len(order) - 1


def test_injected_exact_duplicates_match_manifest(data_dir, tmp_path):
    m = generate(300, seed=3, out_dir=tmp_path)
    dupes = 0
    for rel in m["files_in_arrival_order"]:
        _, rows = _rows(tmp_path / rel)
        dupes += sum(n - 1 for n in Counter(rows).values() if n > 1)
    assert dupes == m["defects"]["exact_duplicate"]


def test_legacy_file_uses_old_names_and_currency_strings(data_dir, tmp_path):
    m = generate(100, seed=5, out_dir=tmp_path)
    header, rows = _rows(tmp_path / m["files_in_arrival_order"][0])
    assert header[0] == "npi" and "total_drug_cost" in header
    cost_idx = header.index("total_drug_cost")
    assert any(r[cost_idx].startswith("$") for r in rows)


def test_cms_small_cell_rules_are_respected(data_dir, tmp_path):
    m = generate(200, seed=9, out_dir=tmp_path)
    header, rows = _rows(tmp_path / m["files_in_arrival_order"][1])
    clm, benes = header.index("Tot_Clms"), header.index("Tot_Benes")
    for r in rows:
        if r[clm].lstrip("-").isdigit():
            assert int(r[clm].lstrip("-")) >= 11          # CMS omits rows with < 11 claims
        if r[benes]:
            assert int(r[benes]) >= 11                     # 1-10 beneficiaries are blanked

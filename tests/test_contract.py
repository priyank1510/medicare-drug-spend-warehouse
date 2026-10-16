import pytest

from drugspend.contract import SchemaContractError, load_contract, map_header, parse_filename
from drugspend.generate import CURRENT_COLUMNS, LEGACY_DROPPED, LEGACY_RENAMES


@pytest.fixture()
def contract(contract_path):
    return load_contract(contract_path)


def test_current_layout_maps_every_column_without_renames(contract):
    m = map_header(CURRENT_COLUMNS, contract)
    assert all(pos is not None for pos in m.source_index.values())
    assert m.renamed == {} and m.unknown == []


def test_legacy_layout_is_mapped_through_aliases(contract):
    legacy = [LEGACY_RENAMES.get(c, c) for c in CURRENT_COLUMNS if c not in LEGACY_DROPPED]
    m = map_header(legacy, contract)
    assert m.renamed["npi"] == "prscrbr_npi"
    assert m.renamed["total_drug_cost"] == "tot_drug_cst"
    # additive columns that did not exist yet are simply absent, not an error
    assert m.source_index["prscrbr_type_src"] is None
    assert m.source_index["prscrbr_state_fips"] is None


def test_known_ignored_columns_are_dropped_and_logged(contract):
    m = map_header(CURRENT_COLUMNS + ["GE65_Tot_Clms"], contract)
    assert m.ignored == ["GE65_Tot_Clms"]


def test_unknown_column_rejects_the_file(contract):
    with pytest.raises(SchemaContractError, match="Unknown column"):
        map_header(CURRENT_COLUMNS + ["Surprise_Column"], contract)


def test_missing_required_column_rejects_the_file(contract):
    with pytest.raises(SchemaContractError, match="Missing required"):
        map_header([c for c in CURRENT_COLUMNS if c != "Tot_Drug_Cst"], contract)


def test_same_column_under_two_names_is_ambiguous(contract):
    with pytest.raises(SchemaContractError, match="appears twice"):
        map_header(CURRENT_COLUMNS + ["npi"], contract)


def test_header_matching_ignores_case_whitespace_and_bom(contract):
    messy = ["\ufeff prscrbr_npi "] + [c.upper() for c in CURRENT_COLUMNS[1:]]
    assert map_header(messy, contract).source_index["prscrbr_npi"] == 0


def test_fingerprint_is_order_independent(contract):
    a = map_header(CURRENT_COLUMNS, contract).fingerprint
    b = map_header(list(reversed(CURRENT_COLUMNS)), contract).fingerprint
    assert a == b


def test_filename_encodes_year_and_version(contract):
    assert parse_filename("partd_2022_v2.csv", contract) == (2022, 2)
    with pytest.raises(SchemaContractError):
        parse_filename("partd-2022.csv", contract)

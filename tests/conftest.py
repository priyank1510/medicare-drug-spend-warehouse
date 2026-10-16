import shutil
from pathlib import Path

import pytest

from drugspend.config import REPO_ROOT


@pytest.fixture()
def data_dir(tmp_path, monkeypatch) -> Path:
    """Point the whole pipeline at an isolated, throw-away data directory."""
    d = tmp_path / "data"
    monkeypatch.setenv("DRUGSPEND_DATA_DIR", str(d))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def contract_path() -> Path:
    return REPO_ROOT / "contracts" / "part_d_prescriber_drug.yml"

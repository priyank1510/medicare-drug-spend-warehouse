"""Central paths and settings. Everything is overridable with environment variables
so the same code runs on a laptop, in Docker, and in CI."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    contract_path: Path
    dbt_dir: Path

    @property
    def landing_dir(self) -> Path:
        """Files exactly as the source delivered them (never modified)."""
        return self.data_dir / "landing"

    @property
    def bronze_dir(self) -> Path:
        """Contract-normalized copies of landing files, plus lineage columns."""
        return self.data_dir / "bronze"

    @property
    def warehouse_path(self) -> Path:
        return self.data_dir / "warehouse" / "drugspend.duckdb"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def defect_manifest_path(self) -> Path:
        """Ground truth written by the generator: what defects were injected."""
        return self.landing_dir / "_injected_defects.json"


def get_settings() -> Settings:
    data_dir = Path(os.environ.get("DRUGSPEND_DATA_DIR", REPO_ROOT / "data")).resolve()
    contract = Path(
        os.environ.get("DRUGSPEND_CONTRACT", REPO_ROOT / "contracts" / "part_d_prescriber_drug.yml")
    ).resolve()
    dbt_dir = Path(os.environ.get("DRUGSPEND_DBT_DIR", REPO_ROOT / "dbt")).resolve()
    return Settings(data_dir=data_dir, contract_path=contract, dbt_dir=dbt_dir)

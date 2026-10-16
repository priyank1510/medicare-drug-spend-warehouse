"""Optional: pull a REAL extract of CMS "Medicare Part D Prescribers - by Provider and Drug".

The full national file is ~25M+ rows, so we filter server-side to one state and page through
the data.cms.gov data API. The result is written as a normal landing file, so the same
contract, ingestion and dbt models process it unchanged.

Each data year has its own dataset UUID. The default below is the dataset's main identifier
(most recent year). Find other years' UUIDs on the dataset page:
https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug

NOTE: real data has no injected-defect manifest, so `drugspend report` does not apply.
Run `drugspend ingest` and `drugspend transform` instead.
"""
from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from datetime import date

from drugspend.config import get_settings

API = "https://data.cms.gov/data-api/v1/dataset/{dataset_id}/data"
DEFAULT_DATASET_ID = "9552739e-3d05-4c1b-8eff-ecabf391e2e5"
PAGE_SIZE = 5000


def download(year: int, state: str, dataset_id: str | None = None, max_rows: int = 200_000) -> None:
    s = get_settings()
    dataset_id = dataset_id or DEFAULT_DATASET_ID
    out = s.landing_dir / f"arrival_date={date.today().isoformat()}" / f"partd_{year}_v1.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    offset, written, header = 0, 0, None
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = None
        while written < max_rows:
            params = urllib.parse.urlencode({"size": PAGE_SIZE, "offset": offset,
                                             "filter[Prscrbr_State_Abrvtn]": state})
            url = API.format(dataset_id=dataset_id) + "?" + params
            with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 (fixed https host)
                page = json.load(resp)
            if not page:
                break
            if header is None:
                header = list(page[0].keys())
                writer = csv.DictWriter(fh, fieldnames=header)
                writer.writeheader()
            writer.writerows(page)
            written += len(page)
            offset += PAGE_SIZE
            print(f"  fetched {written:,} rows", flush=True)
    print(f"wrote {out} ({written:,} rows). Next: python -m drugspend.cli ingest && python -m drugspend.cli transform")

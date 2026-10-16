"""Ingestion: landing (as delivered) -> bronze (contract-normalized CSV) -> raw (DuckDB).

Guarantees
  * Idempotent:   every file is fingerprinted (SHA-256). Re-running never double-loads.
  * Immutable landing: the same filename with DIFFERENT content is rejected. Producers must
                  ship corrections as a new version (partd_2022_v2.csv), which preserves history.
  * Ordered:      files are processed in ARRIVAL order (arrival_date=... partition), not by
                  data year, which is how late-arriving corrections are recognised downstream.
  * Atomic:       a file's rows and its audit record commit in one transaction.
  * Faithful:     raw keeps every value as text (ELT). Typing and cleaning happen in dbt,
                  where they are versioned, tested and re-runnable.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from drugspend.config import Settings, get_settings
from drugspend.contract import Contract, HeaderMapping, SchemaContractError, load_contract, map_header, parse_filename

RAW_TABLE = "raw.part_d_prescriber_drug"
AUDIT_TABLE = "raw._load_audit"
LINEAGE_COLUMNS = ["_batch_id", "_source_file", "_arrival_date", "_data_year", "_file_version",
                   "_row_number", "_row_hash", "_schema_fingerprint", "_loaded_at"]
ARRIVAL_RE = re.compile(r"arrival_date=(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class LandingFile:
    path: Path
    relative: str
    arrival_date: str


@dataclass
class LoadResult:
    file: str
    status: str            # loaded | skipped_already_loaded
    batch_id: str
    rows: int = 0
    renamed: int = 0
    ignored: int = 0


def discover_files(landing_dir: Path) -> list[LandingFile]:
    files = []
    for p in landing_dir.rglob("*.csv"):
        m = ARRIVAL_RE.search(str(p))
        if not m:
            raise SchemaContractError(f"{p} is not inside an arrival_date=YYYY-MM-DD partition")
        files.append(LandingFile(p, str(p.relative_to(landing_dir)), m.group(1)))
    return sorted(files, key=lambda f: (f.arrival_date, f.path.name))


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def row_hash(values: list[str | None]) -> str:
    """Hash of the business columns exactly as delivered: identifies exact duplicates."""
    return hashlib.sha1("\x1f".join("" if v is None else v for v in values).encode()).hexdigest()


def normalize_to_bronze(lf: LandingFile, contract: Contract, batch_id: str, data_year: int,
                        file_version: int, loaded_at: str, bronze_dir: Path) -> tuple[Path, int, HeaderMapping]:
    """Rewrite one landing file into canonical column order and add lineage columns."""
    bronze_dir.mkdir(parents=True, exist_ok=True)
    out_path = bronze_dir / f"{batch_id}.csv"
    canon = contract.canonical_names
    n = 0
    with lf.path.open(newline="", encoding="utf-8-sig") as src, out_path.open("w", newline="", encoding="utf-8") as dst:
        reader = csv.reader(src)
        header = next(reader)
        mapping = map_header(header, contract)
        idx = [mapping.source_index[c] for c in canon]
        writer = csv.writer(dst)
        writer.writerow(canon + LINEAGE_COLUMNS)
        for n, rec in enumerate(reader, start=1):
            if len(rec) != len(header):
                raise SchemaContractError(f"{lf.relative} line {n + 1}: {len(rec)} fields, header has {len(header)}")
            values = [rec[i] if i is not None else "" for i in idx]
            writer.writerow(values + [batch_id, lf.relative, lf.arrival_date, data_year, file_version,
                                      n, row_hash(values), mapping.fingerprint, loaded_at])
    return out_path, n, mapping


def ensure_tables(con, contract: Contract) -> None:
    cols = ",\n  ".join(f"{c} VARCHAR" for c in contract.canonical_names + LINEAGE_COLUMNS)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute(f"CREATE TABLE IF NOT EXISTS {RAW_TABLE} (\n  {cols}\n)")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
        batch_id VARCHAR, source_file VARCHAR, file_sha256 VARCHAR, arrival_date VARCHAR,
        data_year INTEGER, file_version INTEGER, row_count INTEGER, schema_fingerprint VARCHAR,
        renamed_columns VARCHAR, ignored_columns VARCHAR, loaded_at VARCHAR)""")


def load_bronze_file(con, bronze_path: Path) -> None:
    """Bulk-load a bronze CSV. DuckDB's reader is vectorised (fast); empty fields become NULL."""
    safe = str(bronze_path).replace("'", "''")
    con.execute(f"INSERT INTO {RAW_TABLE} SELECT * FROM read_csv('{safe}', header = true, "
                f"all_varchar = true, quote = '\"', escape = '\"')")


def ingest(settings: Settings | None = None, con=None) -> list[LoadResult]:
    settings = settings or get_settings()
    contract = load_contract(settings.contract_path)
    own_con = con is None
    if own_con:
        import duckdb
        settings.warehouse_path.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(settings.warehouse_path))
    try:
        ensure_tables(con, contract)
        already = {row[0]: row[1] for row in
                   con.execute(f"SELECT source_file, file_sha256 FROM {AUDIT_TABLE}").fetchall()}
        results = []
        for lf in discover_files(settings.landing_dir):
            digest = sha256_of(lf.path)
            data_year, version = parse_filename(lf.path.name, contract)
            batch_id = f"{data_year}_v{version}_{digest[:8]}"
            if lf.relative in already:
                if already[lf.relative] != digest:
                    raise SchemaContractError(
                        f"{lf.relative} was already loaded with different content. Landing files are "
                        "immutable: deliver corrections as a new version (e.g. _v2).")
                results.append(LoadResult(lf.relative, "skipped_already_loaded", batch_id))
                continue
            loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            bronze_path, rows, mapping = normalize_to_bronze(
                lf, contract, batch_id, data_year, version, loaded_at, settings.bronze_dir)
            con.begin()
            try:
                load_bronze_file(con, bronze_path)
                con.execute(f"INSERT INTO {AUDIT_TABLE} VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            [batch_id, lf.relative, digest, lf.arrival_date, data_year, version, rows,
                             mapping.fingerprint, ";".join(f"{k}->{v}" for k, v in mapping.renamed.items()),
                             ";".join(mapping.ignored), loaded_at])
                con.commit()
            except Exception:
                con.rollback()
                raise
            results.append(LoadResult(lf.relative, "loaded", batch_id, rows, len(mapping.renamed), len(mapping.ignored)))
        return results
    finally:
        if own_con:
            con.close()


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description="Load landing files into the raw layer").parse_args(argv)
    for r in ingest():
        extra = f" rows={r.rows} renamed_cols={r.renamed} ignored_cols={r.ignored}" if r.status == "loaded" else ""
        print(f"[{r.status:>22}] {r.file} batch={r.batch_id}{extra}")


if __name__ == "__main__":
    main()

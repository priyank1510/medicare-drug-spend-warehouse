"""Structural data contract: maps whatever header a producer sent onto canonical columns.

Handles three real kinds of schema drift:
  * RENAME   - old layout calls it `npi`, new layout calls it `Prscrbr_NPI`  -> alias
  * ADDITIVE - a new optional column appears (Prscrbr_Type_Src)             -> null for old files
  * IGNORED  - known columns we choose not to load (GE65_*)                 -> dropped, logged
Anything else (an unknown column, a missing required one) raises SchemaContractError.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class SchemaContractError(ValueError):
    """The file does not satisfy the structural contract and must not be loaded."""


def _norm(name: str) -> str:
    return name.replace("\ufeff", "").strip().lower()


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    aliases: tuple[str, ...]
    required: bool
    description: str = ""


@dataclass(frozen=True)
class Contract:
    dataset: str
    file_pattern: re.Pattern
    unknown_columns: str
    columns: tuple[ColumnSpec, ...]
    ignored_columns: frozenset[str]

    @property
    def canonical_names(self) -> list[str]:
        return [c.name for c in self.columns]


@dataclass
class HeaderMapping:
    """Result of matching a file header against the contract."""
    source_index: dict[str, int | None]          # canonical name -> position in file (None = absent)
    renamed: dict[str, str] = field(default_factory=dict)   # source header -> canonical (non-primary alias)
    ignored: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    fingerprint: str = ""                        # stable hash of the header, recorded per batch


def load_contract(path: Path) -> Contract:
    raw = yaml.safe_load(Path(path).read_text())
    cols = tuple(ColumnSpec(c["name"], tuple(c["aliases"]), bool(c.get("required", False)),
                            c.get("description", "")) for c in raw["columns"])
    policy = raw.get("unknown_columns", "fail")
    if policy not in {"fail", "warn"}:
        raise ValueError(f"unknown_columns must be 'fail' or 'warn', got {policy!r}")
    return Contract(raw["dataset"], re.compile(raw["file_pattern"]), policy, cols,
                    frozenset(_norm(c) for c in raw.get("ignored_columns", [])))


def map_header(header: list[str], contract: Contract) -> HeaderMapping:
    alias_lookup: dict[str, tuple[str, bool]] = {}
    for col in contract.columns:
        for i, alias in enumerate(col.aliases):
            alias_lookup[_norm(alias)] = (col.name, i == 0)

    mapping = HeaderMapping(source_index={c: None for c in contract.canonical_names})
    for pos, raw_name in enumerate(header):
        key = _norm(raw_name)
        if key in alias_lookup:
            canonical, is_primary = alias_lookup[key]
            if mapping.source_index[canonical] is not None:
                raise SchemaContractError(f"Column '{canonical}' appears twice (via '{raw_name}')")
            mapping.source_index[canonical] = pos
            if not is_primary:
                mapping.renamed[raw_name.strip()] = canonical
        elif key in contract.ignored_columns:
            mapping.ignored.append(raw_name.strip())
        else:
            mapping.unknown.append(raw_name.strip())

    missing = [c.name for c in contract.columns if c.required and mapping.source_index[c.name] is None]
    if missing:
        raise SchemaContractError(f"Missing required column(s): {missing}")
    if mapping.unknown and contract.unknown_columns == "fail":
        raise SchemaContractError(
            f"Unknown column(s) {mapping.unknown}. Add them to the contract (columns or "
            "ignored_columns) after confirming the meaning with the producer.")

    mapping.fingerprint = hashlib.sha1("|".join(sorted(_norm(h) for h in header)).encode()).hexdigest()[:12]
    return mapping


def parse_filename(filename: str, contract: Contract) -> tuple[int, int]:
    """Return (data_year, file_version) encoded in the filename, or raise."""
    m = contract.file_pattern.match(filename)
    if not m:
        raise SchemaContractError(f"Filename '{filename}' does not match {contract.file_pattern.pattern}")
    return int(m["data_year"]), int(m["file_version"])

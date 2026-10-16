"""Synthetic generator for CMS "Medicare Part D Prescribers - by Provider and Drug" files.

Why synthetic by default?
  * CI must be deterministic and run offline in seconds.
  * We need GROUND TRUTH: the generator records exactly which defects it injected
    (data/landing/_injected_defects.json) so the pipeline can prove it caught 100%.
  * The column names, suppression rules (claims >= 11, beneficiary counts < 11 blanked)
    and file-per-year layout mirror the real CMS release, so `download-cms` data drops
    into the same pipeline unchanged.

Costs and volumes are SYNTHETIC. Do not quote them as real Medicare figures.

Files produced (Hive-style arrival partitions, like an object-store landing zone):
  landing/arrival_date=2023-05-01/partd_2021_v1.csv   <- LEGACY column names, "$1,234.56" costs
  landing/arrival_date=2024-05-01/partd_2022_v1.csv   <- current names (adds Prscrbr_Type_Src)
  landing/arrival_date=2025-05-01/partd_2023_v1.csv   <- current names + extra GE65_* columns
  landing/arrival_date=2025-08-15/partd_2022_v2.csv   <- LATE-ARRIVING 2022 correction file
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from drugspend.config import get_settings

YEARS = (2021, 2022, 2023)

# (brand, generic, synthetic cost per day of supply in 2021 USD, therapeutic area, yearly cost growth)
# Generic products follow the CMS convention: brand name == generic name.
DRUG_CATALOG: list[tuple[str, str, float, str, float]] = [
    ("Eliquis", "Apixaban", 17.5, "cardio", 1.06),
    ("Xarelto", "Rivaroxaban", 17.0, "cardio", 1.05),
    ("Entresto", "Sacubitril/Valsartan", 19.0, "cardio", 1.08),
    ("Lipitor", "Atorvastatin Calcium", 9.5, "cardio", 1.02),
    ("Atorvastatin Calcium", "Atorvastatin Calcium", 0.25, "cardio", 0.98),
    ("Crestor", "Rosuvastatin Calcium", 10.5, "cardio", 1.02),
    ("Rosuvastatin Calcium", "Rosuvastatin Calcium", 0.30, "cardio", 0.98),
    ("Norvasc", "Amlodipine Besylate", 8.0, "cardio", 1.01),
    ("Amlodipine Besylate", "Amlodipine Besylate", 0.15, "cardio", 0.99),
    ("Lisinopril", "Lisinopril", 0.12, "cardio", 0.99),
    ("Losartan Potassium", "Losartan Potassium", 0.20, "cardio", 0.99),
    ("Ozempic", "Semaglutide", 31.0, "diabetes", 1.25),
    ("Trulicity", "Dulaglutide", 29.0, "diabetes", 1.10),
    ("Jardiance", "Empagliflozin", 19.5, "diabetes", 1.12),
    ("Januvia", "Sitagliptin Phosphate", 17.0, "diabetes", 1.03),
    ("Metformin Hcl", "Metformin Hcl", 0.10, "diabetes", 0.99),
    ("Synthroid", "Levothyroxine Sodium", 1.9, "endocrine", 1.03),
    ("Levothyroxine Sodium", "Levothyroxine Sodium", 0.35, "endocrine", 1.00),
    ("Nexium", "Esomeprazole Magnesium", 11.0, "gi", 1.02),
    ("Esomeprazole Magnesium", "Esomeprazole Magnesium", 0.60, "gi", 0.99),
    ("Omeprazole", "Omeprazole", 0.20, "gi", 0.99),
    ("Zoloft", "Sertraline Hcl", 12.0, "psych", 1.02),
    ("Sertraline Hcl", "Sertraline Hcl", 0.18, "psych", 0.99),
    ("Gabapentin", "Gabapentin", 0.30, "neuro", 1.00),
]

GENERIC_AVAILABLE = {g for b, g, *_ in DRUG_CATALOG if b == g}

SPECIALTY_AREAS: dict[str, dict[str, int]] = {
    "Internal Medicine": {"cardio": 5, "diabetes": 4, "endocrine": 2, "gi": 2, "psych": 1, "neuro": 1},
    "Family Practice": {"cardio": 4, "diabetes": 4, "endocrine": 2, "gi": 2, "psych": 2, "neuro": 1},
    "Nurse Practitioner": {"cardio": 3, "diabetes": 3, "endocrine": 2, "gi": 2, "psych": 2, "neuro": 2},
    "Cardiology": {"cardio": 10, "diabetes": 1},
    "Endocrinology": {"diabetes": 8, "endocrine": 5, "cardio": 1},
    "Gastroenterology": {"gi": 9, "cardio": 1},
    "Psychiatry": {"psych": 9, "neuro": 3},
    "Neurology": {"neuro": 8, "psych": 2, "cardio": 1},
}
SPECIALTY_WEIGHTS = {"Internal Medicine": 22, "Family Practice": 22, "Nurse Practitioner": 18,
                     "Cardiology": 9, "Endocrinology": 6, "Gastroenterology": 6,
                     "Psychiatry": 9, "Neurology": 8}

STATES: dict[str, tuple[str, list[str]]] = {  # code -> (FIPS, cities)
    "WI": ("55", ["Madison", "Milwaukee", "Green Bay", "Eau Claire"]),
    "MN": ("27", ["Minneapolis", "Saint Paul", "Rochester"]),
    "IL": ("17", ["Chicago", "Springfield", "Peoria"]),
    "MA": ("25", ["Boston", "Worcester", "Cambridge"]),
    "NY": ("36", ["New York", "Buffalo", "Albany"]),
    "TX": ("48", ["Houston", "Austin", "Dallas"]),
    "FL": ("12", ["Miami", "Tampa", "Orlando"]),
    "CA": ("06", ["Los Angeles", "San Diego", "Sacramento"]),
}

LAST_NAMES = ["Smith", "Johnson", "Patel", "Nguyen", "Garcia", "Kim", "Brown", "Lee", "Martinez",
              "Shah", "Wilson", "Anderson", "Thomas", "Moore", "Chen", "Lopez", "Clark", "Lewis",
              "Walker", "Hall", "Young", "Allen", "Wright", "Scott", "Desai", "Rivera", "Baker"]
FIRST_NAMES = ["James", "Mary", "Priya", "Wei", "Maria", "David", "Sarah", "Ankit", "Laura", "John",
               "Aisha", "Robert", "Emily", "Raj", "Linda", "Michael", "Sofia", "Daniel", "Grace"]

# Column layouts -----------------------------------------------------------------------------
CURRENT_COLUMNS = ["Prscrbr_NPI", "Prscrbr_Last_Org_Name", "Prscrbr_First_Name", "Prscrbr_City",
                   "Prscrbr_State_Abrvtn", "Prscrbr_State_FIPS", "Prscrbr_Type", "Prscrbr_Type_Src",
                   "Brnd_Name", "Gnrc_Name", "Tot_Clms", "Tot_30day_Fills", "Tot_Day_Suply",
                   "Tot_Drug_Cst", "Tot_Benes", "GE65_Sprsn_Flag"]
# 2021 file: the pre-redesign naming CMS used in older releases (a real-world rename).
LEGACY_RENAMES = {"Prscrbr_NPI": "npi", "Prscrbr_Last_Org_Name": "nppes_provider_last_org_name",
                  "Prscrbr_First_Name": "nppes_provider_first_name", "Prscrbr_City": "nppes_provider_city",
                  "Prscrbr_State_Abrvtn": "nppes_provider_state", "Prscrbr_Type": "specialty_description",
                  "Brnd_Name": "drug_name", "Gnrc_Name": "generic_name", "Tot_Clms": "total_claim_count",
                  "Tot_30day_Fills": "total_30_day_fill_count", "Tot_Day_Suply": "total_day_supply",
                  "Tot_Drug_Cst": "total_drug_cost", "Tot_Benes": "bene_count",
                  "GE65_Sprsn_Flag": "ge65_suppress_flag"}
LEGACY_DROPPED = {"Prscrbr_State_FIPS", "Prscrbr_Type_Src"}  # did not exist in the old layout
GE65_EXTRA_COLUMNS = ["GE65_Tot_Clms", "GE65_Tot_Day_Suply"]  # appear in 2023: additive drift

ARRIVALS = {  # (data_year, file_version) -> arrival partition date
    (2021, 1): "2023-05-01",
    (2022, 1): "2024-05-01",
    (2023, 1): "2025-05-01",
    (2022, 2): "2025-08-15",  # correction lands AFTER the 2023 file: late-arriving data
}


@dataclass
class Prescriber:
    npi: str
    last: str
    first: str
    state: str
    city: str
    specialty: str


@dataclass
class DefectLog:
    counts: dict[str, int] = field(default_factory=lambda: {
        "exact_duplicate": 0,
        "superseded_by_restatement": 0,
        "late_arriving_new_rows": 0,
        "invalid_npi": 0,
        "negative_measure": 0,
        "missing_drug_cost": 0,
        "missing_specialty_prescriber_years": 0,
        "legacy_schema_rows": 0,
        "format_noise_rows": 0,
    })
    specialty_corrected_npis: list[str] = field(default_factory=list)

    def add(self, key: str, n: int = 1) -> None:
        self.counts[key] += n


def _weighted(rng: random.Random, weights: dict[str, int]) -> str:
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def _make_prescribers(rng: random.Random, n: int) -> list[Prescriber]:
    npis = rng.sample(range(1_000_000_000, 1_999_999_999), n)  # 10-digit NPIs start with 1 or 2
    out = []
    for npi in npis:
        state = rng.choice(list(STATES))
        out.append(Prescriber(str(npi), rng.choice(LAST_NAMES), rng.choice(FIRST_NAMES), state,
                              rng.choice(STATES[state][1]), _weighted(rng, SPECIALTY_WEIGHTS)))
    return out


def _clean_rows(rng: random.Random, prescribers: list[Prescriber]):
    """True, defect-free history. Returns rows per year plus per-npi yearly attributes."""
    rows: dict[int, list[dict]] = {y: [] for y in YEARS}
    stable_npis: set[str] = {p.npi for p in prescribers}  # never moved / changed specialty
    for p in prescribers:
        state, city, specialty = p.state, p.city, p.specialty
        for year in YEARS:
            if year > YEARS[0]:
                if rng.random() < 0.05:  # relocation -> genuine SCD2 change
                    state = rng.choice(list(STATES))
                    city = rng.choice(STATES[state][1])
                    stable_npis.discard(p.npi)
                if rng.random() < 0.02:  # specialty change -> genuine SCD2 change
                    specialty = _weighted(rng, SPECIALTY_WEIGHTS)
                    stable_npis.discard(p.npi)
            if rng.random() > 0.93:  # not active this year
                stable_npis.discard(p.npi)
                continue
            areas = SPECIALTY_AREAS[specialty]
            candidates = [d for d in DRUG_CATALOG if d[3] in areas]
            # Brands that have a generic equivalent are dispensed far less often than the generic.
            weights = [areas[d[3]] * (0.15 if d[0] != d[1] and d[1] in GENERIC_AVAILABLE else 1.0)
                       for d in candidates]
            k = min(len(candidates), rng.randint(5, 11))
            chosen: dict[str, tuple] = {}
            while len(chosen) < k:
                d = rng.choices(candidates, weights=weights, k=1)[0]
                chosen[d[0]] = d
            for brand, generic, cpd, _area, growth in chosen.values():
                claims = max(11, int(rng.lognormvariate(3.4, 0.8)))  # CMS omits rows with <11 claims
                day_supply = int(claims * rng.choice([30, 30, 30, 60, 90]) * rng.uniform(0.9, 1.0))
                cost = round(day_supply * cpd * (growth ** (year - YEARS[0])) * rng.uniform(0.85, 1.15), 2)
                benes = rng.randint(max(1, claims // 6), max(2, claims // 2))
                suppressed = benes < 11  # CMS blanks beneficiary counts of 1-10
                rows[year].append({
                    "Prscrbr_NPI": p.npi, "Prscrbr_Last_Org_Name": p.last, "Prscrbr_First_Name": p.first,
                    "Prscrbr_City": city, "Prscrbr_State_Abrvtn": state,
                    "Prscrbr_State_FIPS": STATES[state][0], "Prscrbr_Type": specialty,
                    "Prscrbr_Type_Src": "S", "Brnd_Name": brand, "Gnrc_Name": generic,
                    "Tot_Clms": str(claims), "Tot_30day_Fills": f"{day_supply / 30:.1f}",
                    "Tot_Day_Suply": str(day_supply), "Tot_Drug_Cst": f"{cost:.2f}",
                    "Tot_Benes": "" if suppressed else str(benes),
                    "GE65_Sprsn_Flag": rng.choice(["*", "#"]) if suppressed else "",
                })
    return rows, stable_npis


def _apply_file_defects(rng: random.Random, rows: list[dict], protected: set[int], log: DefectLog,
                        specialty_blank_npis: set[str]) -> list[dict]:
    """Inject row-level defects into ONE file. Each row gets at most one defect so the
    reconciliation is exact. `protected` = row indexes reserved for the correction file."""
    # prescriber-level missing specialty (all rows of that prescriber for the year)
    for r in rows:
        if r["Prscrbr_NPI"] in specialty_blank_npis:
            r["Prscrbr_Type"] = ""
    free = [i for i in range(len(rows)) if i not in protected
            and rows[i]["Prscrbr_NPI"] not in specialty_blank_npis]
    rng.shuffle(free)
    n = len(rows)
    take = lambda frac: [free.pop() for _ in range(max(1, int(n * frac))) if free]  # noqa: E731

    for i in take(0.002):
        rows[i]["Prscrbr_NPI"] = rng.choice([rows[i]["Prscrbr_NPI"][:9], "NPI" + rows[i]["Prscrbr_NPI"][3:]])
        log.add("invalid_npi")
    for i in take(0.001):
        rows[i]["Tot_Clms"] = "-" + rows[i]["Tot_Clms"]
        log.add("negative_measure")
    for i in take(0.003):
        rows[i]["Tot_Drug_Cst"] = ""
        log.add("missing_drug_cost")
    for i in take(0.03):  # whitespace / casing noise: must be absorbed by cleaning, not quarantined
        rows[i]["Gnrc_Name"] = "  " + rows[i]["Gnrc_Name"].lower() + " "
        rows[i]["Prscrbr_State_Abrvtn"] = rows[i]["Prscrbr_State_Abrvtn"].lower() + " "
        rows[i]["Prscrbr_NPI"] = " " + rows[i]["Prscrbr_NPI"]
        log.add("format_noise_rows")
    dup_idx = take(0.01)
    out = list(rows)
    for i in dup_idx:  # exact duplicates, inserted at random positions
        out.insert(rng.randrange(len(out) + 1), dict(rows[i]))
        log.add("exact_duplicate")
    return out


def _write_csv(path: Path, rows: list[dict], columns: list[str], legacy: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [LEGACY_RENAMES.get(c, c) for c in columns] if legacy else columns
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            values = []
            for c in columns:
                v = r.get(c, "")
                if legacy:
                    if c in ("Brnd_Name", "Gnrc_Name", "Prscrbr_City", "Prscrbr_Last_Org_Name",
                             "Prscrbr_First_Name", "Prscrbr_Type"):
                        v = v.upper()  # old releases were upper-case
                    if c == "Tot_Drug_Cst" and v.strip():
                        v = f"${float(v):,.2f}"  # type drift: currency-formatted strings
                values.append(v)
            w.writerow(values)


def generate(n_prescribers: int = 1500, seed: int = 42, out_dir: Path | None = None) -> dict:
    settings = get_settings()
    landing = out_dir or settings.landing_dir
    rng = random.Random(seed)
    log = DefectLog()

    prescribers = _make_prescribers(rng, n_prescribers)
    rows, stable_npis = _clean_rows(rng, prescribers)

    # --- plan the late-arriving 2022 correction file -------------------------------------
    rows_2022 = rows[2022]
    npis_2022 = sorted({r["Prscrbr_NPI"] for r in rows_2022})
    stable_sorted = sorted(stable_npis)
    corrected_npis = rng.sample(stable_sorted, min(10, len(stable_sorted)))
    log.specialty_corrected_npis = sorted(corrected_npis)
    wrong_specialty = {}
    for npi in corrected_npis:  # v1 file carries a WRONG 2022 specialty; v2 fixes it
        true_spec = next(r["Prscrbr_Type"] for r in rows_2022 if r["Prscrbr_NPI"] == npi)
        wrong_specialty[npi] = next(s for s in SPECIALTY_WEIGHTS if s != true_spec)

    remaining_npis = [n for n in npis_2022 if n not in set(corrected_npis)]
    blank_spec: dict[int, set[str]] = {}
    for y in YEARS:  # ~1% of each year's prescribers have no specialty on file
        pool = sorted({r["Prscrbr_NPI"] for r in rows[y]} - set(corrected_npis))
        blank_spec[y] = set(rng.sample(pool, max(1, len(pool) // 100)))
    for y in YEARS:
        log.add("missing_specialty_prescriber_years", len(blank_spec[y]))

    restate_idx = set()
    for i, r in enumerate(rows_2022):
        if r["Prscrbr_NPI"] in corrected_npis:
            restate_idx.add(i)
    candidates = [i for i, r in enumerate(rows_2022)
                  if i not in restate_idx and r["Prscrbr_NPI"] not in blank_spec[2022]]
    restate_idx |= set(rng.sample(candidates, int(len(rows_2022) * 0.03)))

    correction_rows = []
    for i in sorted(restate_idx):
        r = dict(rows_2022[i])
        if r["Prscrbr_NPI"] not in corrected_npis:  # a cost/claims restatement
            r["Tot_Drug_Cst"] = f"{float(r['Tot_Drug_Cst']) * rng.uniform(0.9, 1.1):.2f}"
        correction_rows.append(r)
    log.add("superseded_by_restatement", len(restate_idx))

    # brand-new 2022 rows that simply arrived late (prescriber x drug combos absent in v1)
    existing = {(r["Prscrbr_NPI"], r["Brnd_Name"]) for r in rows_2022}
    by_npi = {r["Prscrbr_NPI"]: r for r in rows_2022}
    late_new = 0
    for npi in rng.sample(remaining_npis, len(remaining_npis) // 20):
        if npi in blank_spec[2022]:
            continue
        brand, generic, cpd, _a, growth = rng.choice(DRUG_CATALOG)
        if (npi, brand) in existing:
            continue
        base = dict(by_npi[npi])
        claims = rng.randint(11, 60)
        days = claims * 30
        base.update({"Brnd_Name": brand, "Gnrc_Name": generic, "Tot_Clms": str(claims),
                     "Tot_30day_Fills": f"{claims:.1f}", "Tot_Day_Suply": str(days),
                     "Tot_Drug_Cst": f"{days * cpd * growth:.2f}", "Tot_Benes": "", "GE65_Sprsn_Flag": "*"})
        correction_rows.append(base)
        existing.add((npi, brand))
        late_new += 1
    log.add("late_arriving_new_rows", late_new)

    # v1 2022 file shows the wrong specialty for the corrected prescribers
    v1_2022 = [dict(r) for r in rows_2022]
    for r in v1_2022:
        if r["Prscrbr_NPI"] in wrong_specialty:
            r["Prscrbr_Type"] = wrong_specialty[r["Prscrbr_NPI"]]

    # --- write files ----------------------------------------------------------------------
    files = []
    clean_written = 0

    f2021 = _apply_file_defects(rng, [dict(r) for r in rows[2021]], set(), log, blank_spec[2021])
    log.add("legacy_schema_rows", len(f2021))
    cols_2021 = [c for c in CURRENT_COLUMNS if c not in LEGACY_DROPPED]
    p = landing / f"arrival_date={ARRIVALS[(2021, 1)]}" / "partd_2021_v1.csv"
    _write_csv(p, f2021, cols_2021, legacy=True)
    files.append(str(p.relative_to(landing)))
    clean_written += len(f2021)

    f2022 = _apply_file_defects(rng, v1_2022, restate_idx, log, blank_spec[2022])
    p = landing / f"arrival_date={ARRIVALS[(2022, 1)]}" / "partd_2022_v1.csv"
    _write_csv(p, f2022, CURRENT_COLUMNS)
    files.append(str(p.relative_to(landing)))
    clean_written += len(f2022)

    f2023 = _apply_file_defects(rng, [dict(r) for r in rows[2023]], set(), log, blank_spec[2023])
    for r in f2023:
        clms = r["Tot_Clms"].lstrip("-")
        r["GE65_Tot_Clms"] = "" if r["GE65_Sprsn_Flag"] else str(int(int(clms) * 0.8)) if clms.isdigit() else ""
        r["GE65_Tot_Day_Suply"] = ""
    p = landing / f"arrival_date={ARRIVALS[(2023, 1)]}" / "partd_2023_v1.csv"
    _write_csv(p, f2023, CURRENT_COLUMNS + GE65_EXTRA_COLUMNS)
    files.append(str(p.relative_to(landing)))
    clean_written += len(f2023)

    p = landing / f"arrival_date={ARRIVALS[(2022, 2)]}" / "partd_2022_v2.csv"
    _write_csv(p, correction_rows, CURRENT_COLUMNS)
    files.append(str(p.relative_to(landing)))
    clean_written += len(correction_rows)

    c = log.counts
    quarantined = c["invalid_npi"] + c["negative_measure"] + c["missing_drug_cost"]
    manifest = {
        "seed": seed,
        "n_prescribers": n_prescribers,
        "files_in_arrival_order": files,
        "rows_written_total": clean_written,
        "defects": c,
        "expected": {
            "accepted_rows": clean_written - c["exact_duplicate"] - c["superseded_by_restatement"] - quarantined,
            "quarantined_rows": quarantined,
            "distinct_drugs": len({(b.upper(), g.upper()) for b, g, *_ in DRUG_CATALOG}),
            "specialty_corrected_npis": log.specialty_corrected_npis,
        },
        "note": "Synthetic data. Costs are illustrative, not real Medicare figures.",
    }
    landing.mkdir(parents=True, exist_ok=True)
    settings_manifest = landing / "_injected_defects.json"
    settings_manifest.write_text(json.dumps(manifest, indent=2))
    return manifest


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prescribers", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)
    m = generate(args.prescribers, args.seed)
    print(json.dumps({"rows_written_total": m["rows_written_total"], **m["defects"]}, indent=2))


if __name__ == "__main__":
    main()

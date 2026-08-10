"""
Cross-validates MedicareModelRxHCCv08T/X/T2/Y1/Y2 against a CMS RxHCC Python DIY software
package's own transform.py: generates a batch of synthetic beneficiaries, scores them through
both, and compares every population CMS's software emits for each. Same overall approach as
cross_validate_medicare_cms.py; see RxHCCModel's module docstring for the population list and
what distinguishes the five segments.

Requires the optional `cms_validation` dependency group:
    poetry install --with cms_validation

Usage:
    poetry run python scripts/cross_validate_rxhcc_cms.py \\
        --segment T --year 2026 \\
        --cms-package-dir /path/to/extracted/RxHCC_v8_2026_T_package_v5/software/RxHCC \\
        [--n 150] [--seed 42]

Diagnosis codes are restricted to those with no MCE age condition in CMS's source ICD10
crosswalk -- RxHCC's crosswalk has no AGE_EDIT_CONDITION/SEX_EDIT_CONDITION columns at all (there
are no age/sex edit methods in rxhcc_model.py for the same reason), only MCE_AGE_CONDITION, which
this repo intentionally does not implement.

Handles the two known CMS package-vintage differences directly (see
scripts/build_medicare_rxhcc_reference_data.py's docstring for the same discovery): DOB_format
differs (T/X: "%m/%d/%Y", T2/Y1/Y2: "%Y%m%d") and is read directly from the package's own
config.py rather than assumed, and CE/NE relative-factors column names are matched
underscore-insensitively.
"""

import argparse
import csv
import random
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[1]

SEGMENT_CLASSES = {
    "T": "MedicareModelRxHCCv08T",
    "X": "MedicareModelRxHCCv08X",
    "T2": "MedicareModelRxHCCv08T2",
    "Y1": "MedicareModelRxHCCv08Y1",
    "Y2": "MedicareModelRxHCCv08Y2",
}

CE_COLUMN_ALIASES = {
    "cenonlowaged": "SCORE_CE_NonLow_Aged",
    "cenonlownonaged": "SCORE_CE_NonLow_NonAged",
    "celowaged": "SCORE_CE_Low_Aged",
    "celownonaged": "SCORE_CE_Low_NonAged",
    "celti": "SCORE_CE_LTI",
}
NE_COLUMN_ALIASES = {
    "nenonlowcommunity": "SCORE_NE_NonLow_Community",
    "nelowcommunity": "SCORE_NE_Low_Community",
    "nelti": "SCORE_NE_LTI",
}
REPO_POPULATIONS = {
    "CE_NONLOW_AGED": "cenonlowaged",
    "CE_NONLOW_NONAGED": "cenonlownonaged",
    "CE_LOW_AGED": "celowaged",
    "CE_LOW_NONAGED": "celownonaged",
    "CE_LTI": "celti",
    "NE_NONLOW_COMMUNITY": "nenonlowcommunity",
    "NE_LOW_COMMUNITY": "nelowcommunity",
    "NE_LTI": "nelti",
}


def find_internal_file(cms_dir: Path, segment: str, filename: str) -> Path:
    nested = cms_dir / "data/input/internal" / segment / filename
    if nested.exists():
        return nested
    flat = cms_dir / "data/input/internal" / filename
    if flat.exists():
        return flat
    raise FileNotFoundError(
        f"Could not find {filename} under {cms_dir}/data/input/internal"
    )


def get_dob_format(cms_dir: Path) -> str:
    text = (cms_dir / "config.py").read_text()
    match = re.search(r"'DOB_format':\s*\"([^\"]+)\"", text)
    if not match:
        raise SystemExit("Could not read DOB_format from config.py")
    return match.group(1)


def resolve_score_columns(cms_df: pd.DataFrame) -> dict:
    def normalize(col):
        return col.replace("_", "").replace("SCORE", "").strip().lower()

    lookup = {}
    for col in cms_df.columns:
        if not col.startswith("SCORE_"):
            continue
        lookup[normalize(col)] = col

    resolved = {}
    for population, key in REPO_POPULATIONS.items():
        if key in lookup:
            resolved[population] = lookup[key]
        else:
            raise SystemExit(
                f"Could not find a CMS score column for population {population}"
            )
    return resolved


def read_unconditional_diag_codes(cms_dir: Path, segment: str, year: int) -> list:
    path = find_internal_file(cms_dir, segment, f"ICD10_CC_mappings_RxHCC_{year}.csv")
    codes = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["MCE_AGE_CONDITION"]:
                continue
            codes.append(row["ICD10"].strip())
    return sorted(set(codes))


def age_to_dob(age: int, payment_year: int) -> date:
    return date(payment_year - age - 1, 6, 15)


def format_dob(dob: date, dob_format: str) -> str:
    if dob_format == "%Y%m%d":
        return f"{dob.year}{dob.month:02d}{dob.day:02d}"
    if dob_format == "%m/%d/%Y":
        return f"{dob.month}/{dob.day}/{dob.year}"
    raise SystemExit(f"Unsupported DOB_format: {dob_format}")


def generate_beneficiaries(n: int, seed: int, diag_codes: list) -> list:
    random.seed(seed)
    fake = Faker()
    Faker.seed(seed)
    beneficiaries = []
    for i in range(n):
        gender_code = random.choice((1, 2))
        beneficiaries.append(
            {
                "id": str(i + 1),
                "faker_uuid": fake.uuid4(),
                "gender_code": gender_code,
                "gender": "M" if gender_code == 1 else "F",
                "age": random.randint(0, 95),
                "orec": random.choice(("0", "1", "2", "3")),
                "esrd": random.random() < 0.15,
                "diagnoses": random.sample(diag_codes, k=random.randint(0, 3)),
            }
        )
    return beneficiaries


def write_cms_inputs(
    cms_dir: Path, segment: str, beneficiaries: list, year: int, dob_format: str
):
    user_defined = cms_dir / "data/input/user_defined"
    with open(user_defined / "beneficiaries.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "SEX", "OREC", "ESRD", "DOB"])
        for b in beneficiaries:
            dob = age_to_dob(b["age"], year)
            writer.writerow(
                [
                    b["id"],
                    b["gender_code"],
                    b["orec"],
                    int(b["esrd"]),
                    format_dob(dob, dob_format),
                ]
            )

    with open(user_defined / "diagnoses.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "ICD10"])
        for b in beneficiaries:
            for code in b["diagnoses"]:
                writer.writerow([b["id"], code])


def run_cms_transform(cms_dir: Path) -> pd.DataFrame:
    output_dir = cms_dir / "data/output"
    before = set(output_dir.glob("*.csv"))
    subprocess.run(
        [sys.executable, str(cms_dir / "transform.py")],
        cwd=cms_dir.parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    after = set(output_dir.glob("*.csv"))
    new_files = after - before
    output_path = (
        max(new_files, key=lambda p: p.stat().st_mtime)
        if new_files
        else max(after, key=lambda p: p.stat().st_mtime)
    )
    df = pd.read_csv(output_path, dtype={"ID": str})
    return df.set_index("ID")


def run_repo_model(beneficiaries: list, segment: str, year: int) -> dict:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    import risk_adjustment_model

    model_class = getattr(risk_adjustment_model, SEGMENT_CLASSES[segment])
    model = model_class(year=year)

    scores = {}
    for b in beneficiaries:
        scores[b["id"]] = {}
        for population in REPO_POPULATIONS:
            result = model.score(
                gender=b["gender"],
                orec=b["orec"],
                esrd=b["esrd"],
                diagnosis_codes=b["diagnoses"] or None,
                age=b["age"],
                population=population,
                verbose=False,
            )
            scores[b["id"]][population] = result.score_raw
    return scores


def compare(
    beneficiaries: list, cms_df: pd.DataFrame, repo_scores: dict, score_columns: dict
) -> list:
    mismatches = []
    for b in beneficiaries:
        for population, cms_col in score_columns.items():
            if b["id"] not in cms_df.index:
                mismatches.append((b, population, None, None, "missing CMS output"))
                continue
            cms_score = round(float(cms_df.loc[b["id"], cms_col]), 3)
            repo_score = round(float(repo_scores[b["id"]][population]), 3)
            if abs(cms_score - repo_score) > 0.001:
                mismatches.append((b, population, cms_score, repo_score, None))
    return mismatches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segment", required=True, choices=list(SEGMENT_CLASSES))
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--cms-package-dir", required=True, type=Path)
    parser.add_argument("--n", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dob_format = get_dob_format(args.cms_package_dir)
    diag_codes = read_unconditional_diag_codes(
        args.cms_package_dir, args.segment, args.year
    )
    if not diag_codes:
        raise SystemExit("No unconditional diagnosis codes found")

    beneficiaries = generate_beneficiaries(args.n, args.seed, diag_codes)
    print(f"Generated {len(beneficiaries)} synthetic beneficiaries.")

    write_cms_inputs(
        args.cms_package_dir, args.segment, beneficiaries, args.year, dob_format
    )
    print("Running CMS transform.py...")
    cms_df = run_cms_transform(args.cms_package_dir)
    score_columns = resolve_score_columns(cms_df)

    print(f"Running {SEGMENT_CLASSES[args.segment]}...")
    repo_scores = run_repo_model(beneficiaries, args.segment, args.year)

    mismatches = compare(beneficiaries, cms_df, repo_scores, score_columns)

    total_checks = len(beneficiaries) * len(REPO_POPULATIONS)
    print(
        f"\n{total_checks - len(mismatches)}/{total_checks} checks matched (within rounding tolerance)."
    )
    if mismatches:
        print(f"\n{len(mismatches)} MISMATCHES:")
        for b, population, cms_score, repo_score, note in mismatches:
            print(
                f"  id={b['id']} population={population} age={b['age']} gender={b['gender']} "
                f"orec={b['orec']} esrd={b['esrd']} dx={b['diagnoses']} "
                f"-> CMS={cms_score} repo={repo_score} {note or ''}"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()

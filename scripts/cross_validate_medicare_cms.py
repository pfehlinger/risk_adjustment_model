"""
Cross-validates MedicareModelV22/V24/V28 against a CMS CMS-HCC Python DIY software package's own
transform.py: generates a batch of synthetic beneficiaries, scores them through both, and
compares every population CMS's software emits for each. Same overall approach as
cross_validate_cms.py (Commercial); adapted here for Medicare's population shape -- CMS's own
Community output already includes one score column per population (SCORE_COMMUNITY_NA,
SCORE_INSTITUTIONAL, SCORE_NE, etc.) for every beneficiary in one row, so this script doesn't need
to choose one population per beneficiary the way Commercial's does.

Requires the optional `cms_validation` dependency group:
    poetry install --with cms_validation

Usage:
    poetry run python scripts/cross_validate_medicare_cms.py \\
        --version v28 --year 2026 \\
        --cms-package-dir /path/to/extracted/CMS_HCC_v28_2026_T_package_v3/software/CMS_HCC_v28 \\
        [--n 150] [--seed 42]

Diagnosis codes are restricted to those with no MCE/age/sex condition in CMS's source ICD10
crosswalk, for the same reason as Commercial's script: AGE_EDIT_CONDITION/SEX_EDIT_CONDITION codes
ARE implemented (via each version's `_age_sex_edit_N` methods) but have their own dedicated test
coverage (test_age_sex_edits per version), and MCE_AGE_CONDITION filtering is intentionally not
implemented at all (see README.md's "key design decisions").

Exercises the LTIMCAID/NEMCAID distinction directly: each synthetic beneficiary gets independently
randomized `medicaid` (LTIMCAID, continuing-enrollee scoring) and `ne_medicaid` (NEMCAID, new-
enrollee population resolution) flags, so a regression in that split would be caught here.

To validate against real data instead of Faker output (e.g. in a production setting), pass
--real-data-dir pointing at a directory containing:

    beneficiaries.csv: ID,DOB,SEX,OREC,MEDICAID,NE_MEDICAID
        DOB is ISO format (YYYY-MM-DD). SEX is M/F. MEDICAID/NE_MEDICAID are 1/0/true/false.
    diagnoses.csv: ID,ICD10
        One row per (beneficiary, code) pair.

See scripts/_real_data.py's module docstring for the shared conventions (DOB format, boolean
parsing, and why real diagnosis codes aren't filtered the way synthetic ones are).
"""

import argparse
import csv
import random
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _real_data import (  # noqa: E402
    age_as_of_feb_1,
    parse_bool,
    parse_iso_dob,
    read_real_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

VERSION_CLASSES = {
    "v22": "MedicareModelV22",
    "v24": "MedicareModelV24",
    "v28": "MedicareModelV28",
}

# repo population -> CMS output column
CE_POPULATION_COLUMNS = {
    "CNA": "SCORE_COMMUNITY_NA",
    "CPA": "SCORE_COMMUNITY_PBA",
    "CFA": "SCORE_COMMUNITY_FBA",
    "CND": "SCORE_COMMUNITY_ND",
    "CPD": "SCORE_COMMUNITY_PBD",
    "CFD": "SCORE_COMMUNITY_FBD",
    "INS": "SCORE_INSTITUTIONAL",
}
# Some package vintages (e.g. 2027 "initial" packages) name this column SCORE_NEW_ENROLLEE
# instead of SCORE_NE.
NE_SCORE_COLUMN_CANDIDATES = ["SCORE_NE", "SCORE_NEW_ENROLLEE"]


def find_internal_file(cms_dir: Path, filename: str) -> Path:
    path = cms_dir / "data/input/internal" / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {filename} under {cms_dir}/data/input/internal"
        )
    return path


def read_unconditional_diag_codes(cms_dir: Path, version: str, year: int) -> list:
    # Some package vintages (e.g. 2027 "initial" packages) suffix this filename with "_initial".
    base_name = f"ICD10_CC_mappings_CMS_HCC_{year}_{version}"
    for candidate in (f"{base_name}.csv", f"{base_name}_initial.csv"):
        try:
            path = find_internal_file(cms_dir, candidate)
            break
        except FileNotFoundError:
            continue
    else:
        raise FileNotFoundError(
            f"Could not find an ICD10_CC_mappings file for {version}/{year} under {cms_dir}"
        )
    codes = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (
                row["MCE_AGE_CONDITION"]
                or row["AGE_EDIT_CONDITION"]
                or row["SEX_EDIT_CONDITION"]
            ):
                continue
            codes.append(row["ICD10"].strip())
    return sorted(set(codes))


def age_to_dob(age: int, payment_year: int) -> date:
    # Reference date is Feb 1 of payment_year; a 6/15 DOB guarantees the birthday hasn't
    # occurred yet relative to that cutoff, so dob_year = payment_year - age - 1.
    return date(payment_year - age - 1, 6, 15)


def generate_beneficiaries(n: int, seed: int, diag_codes: list) -> list:
    random.seed(seed)
    fake = Faker()
    Faker.seed(seed)

    if not diag_codes:
        raise SystemExit("No unconditional diagnosis codes found")

    beneficiaries = []
    for i in range(n):
        gender_code = random.choice((1, 2))
        gender = "M" if gender_code == 1 else "F"
        age = random.randint(0, 95)
        orec = random.choice(("0", "1", "3"))
        medicaid = random.random() < 0.3
        ne_medicaid = random.random() < 0.3
        diagnoses = random.sample(diag_codes, k=random.randint(0, 3))
        beneficiaries.append(
            {
                "id": str(i + 1),
                "faker_uuid": fake.uuid4(),
                "gender_code": gender_code,
                "gender": gender,
                "age": age,
                "orec": orec,
                "medicaid": medicaid,
                "ne_medicaid": ne_medicaid,
                "diagnoses": diagnoses,
            }
        )
    return beneficiaries


def load_real_beneficiaries(real_data_dir: Path, year: int) -> list:
    diag_rows = read_real_csv(real_data_dir, "diagnoses.csv")
    diagnoses_by_id = {}
    for row in diag_rows:
        diagnoses_by_id.setdefault(row["ID"].strip(), []).append(row["ICD10"].strip())

    beneficiaries = []
    for row in read_real_csv(real_data_dir, "beneficiaries.csv"):
        bene_id = row["ID"].strip()
        dob = parse_iso_dob(row["DOB"])
        gender = row["SEX"].strip().upper()
        beneficiaries.append(
            {
                "id": bene_id,
                "gender_code": 1 if gender == "M" else 2,
                "gender": gender,
                "age": age_as_of_feb_1(dob, year),
                "orec": row["OREC"].strip(),
                "medicaid": parse_bool(row["MEDICAID"]),
                "ne_medicaid": parse_bool(row["NE_MEDICAID"]),
                "diagnoses": diagnoses_by_id.get(bene_id, []),
            }
        )
    return beneficiaries


def write_cms_inputs(cms_dir: Path, beneficiaries: list, year: int):
    user_defined = cms_dir / "data/input/user_defined"
    with open(user_defined / "beneficiaries.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "DOB", "SEX", "OREC", "LTIMCAID", "NEMCAID"])
        for b in beneficiaries:
            dob = age_to_dob(b["age"], year)
            writer.writerow(
                [
                    b["id"],
                    f"{dob.month}/{dob.day}/{dob.year}",
                    b["gender_code"],
                    b["orec"],
                    int(b["medicaid"]),
                    int(b["ne_medicaid"]),
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
    before = set(output_dir.glob("*scores.csv"))
    subprocess.run(
        [sys.executable, str(cms_dir / "transform.py")],
        cwd=cms_dir.parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    after = set(output_dir.glob("*scores.csv"))
    new_files = after - before
    output_path = (
        max(new_files, key=lambda p: p.stat().st_mtime)
        if new_files
        else max(after, key=lambda p: p.stat().st_mtime)
    )
    df = pd.read_csv(output_path, dtype={"ID": str})
    return df.set_index("ID")


def run_repo_model(beneficiaries: list, version: str, year: int) -> dict:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    import risk_adjustment_model

    model_class = getattr(risk_adjustment_model, VERSION_CLASSES[version])
    model = model_class(year=year)

    scores = {}
    for b in beneficiaries:
        scores[b["id"]] = {}
        for population in CE_POPULATION_COLUMNS:
            result = model.score(
                gender=b["gender"],
                orec=b["orec"],
                medicaid=b["medicaid"],
                diagnosis_codes=b["diagnoses"] or None,
                age=b["age"],
                population=population,
                verbose=False,
            )
            scores[b["id"]][population] = result.score_raw
        ne_result = model.score(
            gender=b["gender"],
            orec=b["orec"],
            medicaid=b["medicaid"],
            ne_medicaid=b["ne_medicaid"],
            diagnosis_codes=b["diagnoses"] or None,
            age=b["age"],
            population="NE",
            verbose=False,
        )
        scores[b["id"]]["NE"] = ne_result.score_raw
    return scores


def compare(beneficiaries: list, cms_df: pd.DataFrame, repo_scores: dict) -> list:
    ne_score_column = next(
        (col for col in NE_SCORE_COLUMN_CANDIDATES if col in cms_df.columns),
        NE_SCORE_COLUMN_CANDIDATES[0],
    )
    mismatches = []
    for b in beneficiaries:
        for population, cms_col in {
            **CE_POPULATION_COLUMNS,
            "NE": ne_score_column,
        }.items():
            if b["id"] not in cms_df.index or cms_col not in cms_df.columns:
                mismatches.append((b, population, None, None, "missing CMS output"))
                continue
            cms_score = round(float(cms_df.loc[b["id"], cms_col]), 3)
            repo_score = round(float(repo_scores[b["id"]][population]), 3)
            if abs(cms_score - repo_score) > 0.001:
                mismatches.append((b, population, cms_score, repo_score, None))
    return mismatches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, choices=list(VERSION_CLASSES))
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--cms-package-dir", required=True, type=Path)
    parser.add_argument("--n", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--real-data-dir",
        type=Path,
        default=None,
        help="Validate against real data instead of Faker output. See module docstring for "
        "the expected beneficiaries.csv/diagnoses.csv format.",
    )
    args = parser.parse_args()

    if args.real_data_dir:
        beneficiaries = load_real_beneficiaries(args.real_data_dir, args.year)
        print(
            f"Loaded {len(beneficiaries)} real beneficiaries from {args.real_data_dir}."
        )
    else:
        diag_codes = read_unconditional_diag_codes(
            args.cms_package_dir, args.version, args.year
        )
        beneficiaries = generate_beneficiaries(args.n, args.seed, diag_codes)
        print(f"Generated {len(beneficiaries)} synthetic beneficiaries.")

    write_cms_inputs(args.cms_package_dir, beneficiaries, args.year)
    print("Running CMS transform.py...")
    cms_df = run_cms_transform(args.cms_package_dir)

    print(f"Running {VERSION_CLASSES[args.version]}...")
    repo_scores = run_repo_model(beneficiaries, args.version, args.year)

    mismatches = compare(beneficiaries, cms_df, repo_scores)

    total_checks = len(beneficiaries) * (len(CE_POPULATION_COLUMNS) + 1)
    print(
        f"\n{total_checks - len(mismatches)}/{total_checks} checks matched (within rounding tolerance)."
    )
    if mismatches:
        print(f"\n{len(mismatches)} MISMATCHES:")
        for b, population, cms_score, repo_score, note in mismatches:
            print(
                f"  id={b['id']} population={population} age={b['age']} gender={b['gender']} "
                f"orec={b['orec']} medicaid={b['medicaid']} ne_medicaid={b['ne_medicaid']} "
                f"dx={b['diagnoses']} -> CMS={cms_score} repo={repo_score} {note or ''}"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()

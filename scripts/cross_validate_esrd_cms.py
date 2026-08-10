"""
Cross-validates MedicareModelESRDv24/v21 against a CMS ESRD Python DIY software package's own
transform.py: generates a batch of synthetic beneficiaries, scores them through both, and
compares every population/graft-duration-bucket combination CMS's software emits for each.
Same overall approach as cross_validate_medicare_cms.py, adapted for ESRD's richer population
shape -- see MedicareModelESRDv24's module docstring for the population/duration-bucket design
this mirrors.

Requires the optional `cms_validation` dependency group:
    poetry install --with cms_validation

Usage:
    poetry run python scripts/cross_validate_esrd_cms.py \\
        --version v24 --year 2026 \\
        --cms-package-dir /path/to/extracted/ESRD_v24_2026_T_package_v2/software/ESRD_v24 \\
        [--n 100] [--seed 42]

    poetry run python scripts/cross_validate_esrd_cms.py \\
        --version v21 --year 2026 \\
        --cms-package-dir /path/to/extracted/ESRD_v21_2026_P_package_v3/software/ESRD_v21 \\
        [--n 100] [--seed 42]

Diagnosis codes are restricted to those with no MCE/age/sex condition in CMS's source ICD10
crosswalk, for the same reason as the other cross-validation scripts in this repo -- age/sex-edit
codes have their own dedicated test coverage (test_age_sex_edits), and MCE_AGE_CONDITION filtering
is intentionally not implemented at all.

Renal categories (HCC134-138) are deliberately never sampled as diagnosis codes for v24 (they're
excluded from this repo's reference data entirely, since CMS's own software forcibly zeroes them
for every ESRD beneficiary -- see MedicareModelESRDv24's docstring) but *are* sampled for v21
(which scores them normally).
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

REPO_ROOT = Path(__file__).resolve().parents[1]

DURATION_BUCKETS = {"DUR4_9": 6, "DUR10PL": 12}
TRANSPLANT_MONTHS = {"TRANSPLANT_1M": 1, "TRANSPLANT_2M": 2, "TRANSPLANT_3M": 3}
TRANSPLANT_CMS_COLUMNS = {
    "TRANSPLANT_1M": "SCORE_TRANSPLANT_KIDNEY_ONLY_1M",
    "TRANSPLANT_2M": "SCORE_TRANSPLANT_KIDNEY_ONLY_2M",
    "TRANSPLANT_3M": "SCORE_TRANSPLANT_KIDNEY_ONLY_3M",
}


def find_internal_file(cms_dir: Path, filename: str) -> Path:
    path = cms_dir / "data/input/internal" / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {filename} under {cms_dir}/data/input/internal"
        )
    return path


def read_unconditional_diag_codes(
    cms_dir: Path, version: str, year: int, exclude_ccs: set
) -> list:
    # Some package vintages (e.g. 2027 "initial" packages) suffix this filename with "_initial".
    base_name = f"ICD10_CC_mappings_ESRD_{year}_{version}"
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
            if str(int(float(row["CC"]))) in exclude_ccs:
                continue
            codes.append(row["ICD10"].strip())
    return sorted(set(codes))


def age_to_dob(age: int, payment_year: int) -> date:
    return date(payment_year - age - 1, 6, 15)


def generate_beneficiaries_v24(n: int, seed: int, diag_codes: list) -> list:
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
                "fbdual": random.random() < 0.3,
                "pbdual": random.random() < 0.2,
                "lti": random.random() < 0.2,
                "diagnoses": random.sample(diag_codes, k=random.randint(0, 3)),
            }
        )
    return beneficiaries


def generate_beneficiaries_v21(n: int, seed: int, diag_codes: list) -> list:
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
                "mcaid": random.random() < 0.3,
                "ne_mcaid": random.random() < 0.3,
                "diagnoses": random.sample(diag_codes, k=random.randint(0, 3)),
            }
        )
    return beneficiaries


def write_cms_inputs_v24(cms_dir: Path, beneficiaries: list, year: int):
    user_defined = cms_dir / "data/input/user_defined"
    with open(user_defined / "beneficiaries.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "DOB", "SEX", "OREC", "FBDual", "PBDual", "LTI"])
        for b in beneficiaries:
            dob = age_to_dob(b["age"], year)
            writer.writerow(
                [
                    b["id"],
                    f"{dob.year}{dob.month:02d}{dob.day:02d}",
                    b["gender_code"],
                    b["orec"],
                    int(b["fbdual"]),
                    int(b["pbdual"]),
                    int(b["lti"]),
                ]
            )
    _write_diagnoses(user_defined, beneficiaries)


def write_cms_inputs_v21(cms_dir: Path, beneficiaries: list, year: int):
    user_defined = cms_dir / "data/input/user_defined"
    with open(user_defined / "beneficiaries.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "DOB", "SEX", "OREC", "MCAID", "NEMCAID"])
        for b in beneficiaries:
            dob = age_to_dob(b["age"], year)
            writer.writerow(
                [
                    b["id"],
                    f"{dob.year}{dob.month:02d}{dob.day:02d}",
                    b["gender_code"],
                    b["orec"],
                    int(b["mcaid"]),
                    int(b["ne_mcaid"]),
                ]
            )
    _write_diagnoses(user_defined, beneficiaries)


def _write_diagnoses(user_defined: Path, beneficiaries: list):
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


def run_repo_model_v24(beneficiaries: list, year: int):
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from risk_adjustment_model import MedicareModelESRDv24

    model = MedicareModelESRDv24(year=year)
    # (population, cms_col_fn(bene, dur_key) -> cms_col, needs_duration)
    checks = []
    for b in beneficiaries:
        aged = "GE65" if b["age"] >= 65 else "LT65"
        # NE_GRAFT uses CMS's NE_Aged rule (age >= 65, or age == 64 with orec == "0"), not the
        # plain age check -- see ESRDBeneficiary.ne_aged.
        ne_aged = (
            "GE65"
            if b["age"] >= 65 or (b["age"] == 64 and b["orec"] == "0")
            else "LT65"
        )
        dual = "FBD" if b["fbdual"] else "ND_PBD"

        r = model.score(
            gender=b["gender"],
            orec=b["orec"],
            fbdual=b["fbdual"],
            pbdual=b["pbdual"],
            lti=b["lti"],
            diagnosis_codes=b["diagnoses"] or None,
            age=b["age"],
            population="DIAL",
        )
        checks.append((b, "DIAL", r.score_raw, "SCORE_DIAL"))

        r = model.score(
            gender=b["gender"],
            orec=b["orec"],
            fbdual=b["fbdual"],
            pbdual=b["pbdual"],
            lti=b["lti"],
            diagnosis_codes=b["diagnoses"] or None,
            age=b["age"],
            population="NE_DIAL",
        )
        checks.append((b, "NE_DIAL", r.score_raw, "SCORE_DIAL_NE"))

        for dur_key, dur_months in DURATION_BUCKETS.items():
            r = model.score(
                gender=b["gender"],
                orec=b["orec"],
                fbdual=b["fbdual"],
                pbdual=b["pbdual"],
                lti=b["lti"],
                diagnosis_codes=b["diagnoses"] or None,
                age=b["age"],
                population="GRAFT_COMM",
                graft_duration_months=dur_months,
            )
            checks.append(
                (
                    b,
                    f"GRAFT_COMM {dur_key}",
                    r.score_raw,
                    f"SCORE_G_COMM_{dual}_{aged}_{dur_key}",
                )
            )

            r = model.score(
                gender=b["gender"],
                orec=b["orec"],
                fbdual=b["fbdual"],
                pbdual=b["pbdual"],
                lti=b["lti"],
                diagnosis_codes=b["diagnoses"] or None,
                age=b["age"],
                population="GRAFT_INST",
                graft_duration_months=dur_months,
            )
            checks.append(
                (
                    b,
                    f"GRAFT_INST {dur_key}",
                    r.score_raw,
                    f"SCORE_GRAFT_INST_{dual}_{aged}_{dur_key}",
                )
            )

            r = model.score(
                gender=b["gender"],
                orec=b["orec"],
                fbdual=b["fbdual"],
                pbdual=b["pbdual"],
                lti=b["lti"],
                diagnosis_codes=b["diagnoses"] or None,
                age=b["age"],
                population="NE_GRAFT",
                graft_duration_months=dur_months,
            )
            checks.append(
                (
                    b,
                    f"NE_GRAFT {dur_key}",
                    r.score_raw,
                    f"SCORE_GRAFT_NE_{ne_aged}_{dur_key}_{dual}",
                )
            )

        for population, cms_col in TRANSPLANT_CMS_COLUMNS.items():
            r = model.score(
                gender=b["gender"],
                orec=b["orec"],
                age=b["age"],
                population=population,
            )
            checks.append((b, population, r.score_raw, cms_col))

    return checks


def run_repo_model_v21(beneficiaries: list, year: int):
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from risk_adjustment_model import MedicareModelESRDv21

    model = MedicareModelESRDv21(year=year)
    checks = []
    for b in beneficiaries:
        aged = "GE65" if b["age"] >= 65 else "LT65"
        # NE_GRAFT uses CMS's NE_Aged rule (age >= 65, or age == 64 with orec == "0"), not the
        # plain age check -- see ESRDv21Beneficiary.ne_aged.
        ne_aged = (
            "GE65"
            if b["age"] >= 65 or (b["age"] == 64 and b["orec"] == "0")
            else "LT65"
        )

        r = model.score(
            gender=b["gender"],
            orec=b["orec"],
            mcaid=b["mcaid"],
            diagnosis_codes=b["diagnoses"] or None,
            age=b["age"],
            population="DIAL",
        )
        checks.append((b, "DIAL", r.score_raw, "SCORE_DIAL"))

        r = model.score(
            gender=b["gender"],
            orec=b["orec"],
            mcaid=b["mcaid"],
            ne_mcaid=b["ne_mcaid"],
            diagnosis_codes=b["diagnoses"] or None,
            age=b["age"],
            population="NE_DIAL",
        )
        checks.append((b, "NE_DIAL", r.score_raw, "SCORE_DIAL_NE"))

        for dur_key, dur_months in DURATION_BUCKETS.items():
            r = model.score(
                gender=b["gender"],
                orec=b["orec"],
                mcaid=b["mcaid"],
                diagnosis_codes=b["diagnoses"] or None,
                age=b["age"],
                population="GRAFT_COMM",
                graft_duration_months=dur_months,
            )
            checks.append(
                (
                    b,
                    f"GRAFT_COMM {dur_key}",
                    r.score_raw,
                    f"SCORE_GRAFT_COMM_{dur_key}_{aged}",
                )
            )

            r = model.score(
                gender=b["gender"],
                orec=b["orec"],
                mcaid=b["mcaid"],
                diagnosis_codes=b["diagnoses"] or None,
                age=b["age"],
                population="GRAFT_INST",
                graft_duration_months=dur_months,
            )
            checks.append(
                (
                    b,
                    f"GRAFT_INST {dur_key}",
                    r.score_raw,
                    f"SCORE_GRAFT_INST_{dur_key}_{aged}",
                )
            )

            r = model.score(
                gender=b["gender"],
                orec=b["orec"],
                mcaid=b["mcaid"],
                ne_mcaid=b["ne_mcaid"],
                diagnosis_codes=b["diagnoses"] or None,
                age=b["age"],
                population="NE_GRAFT",
                graft_duration_months=dur_months,
            )
            checks.append(
                (
                    b,
                    f"NE_GRAFT {dur_key}",
                    r.score_raw,
                    f"SCORE_GRAFT_NE_{dur_key}_{ne_aged}",
                )
            )

        for population, cms_col in TRANSPLANT_CMS_COLUMNS.items():
            r = model.score(
                gender=b["gender"],
                orec=b["orec"],
                age=b["age"],
                population=population,
            )
            checks.append((b, population, r.score_raw, cms_col))

    return checks


def compare(checks: list, cms_df: pd.DataFrame) -> list:
    mismatches = []
    for b, label, repo_score, cms_col in checks:
        if cms_col not in cms_df.columns:
            # Some package vintages (e.g. 2027 "initial" packages) renamed
            # SCORE_G_COMM_* to SCORE_GRAFT_COMM_*.
            alias = cms_col.replace("SCORE_G_COMM_", "SCORE_GRAFT_COMM_")
            if alias in cms_df.columns:
                cms_col = alias
        if b["id"] not in cms_df.index or cms_col not in cms_df.columns:
            mismatches.append((b, label, None, repo_score, "missing CMS output"))
            continue
        cms_score = round(float(cms_df.loc[b["id"], cms_col]), 3)
        repo_score = round(float(repo_score), 3)
        if abs(cms_score - repo_score) > 0.001:
            mismatches.append((b, label, cms_score, repo_score, None))
    return mismatches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, choices=["v24", "v21"])
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--cms-package-dir", required=True, type=Path)
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # v24 excludes renal CCs (never reachable -- see module docstring); v21 doesn't.
    exclude_ccs = (
        {"134", "135", "136", "137", "138"} if args.version == "v24" else set()
    )
    diag_codes = read_unconditional_diag_codes(
        args.cms_package_dir, args.version, args.year, exclude_ccs
    )
    if not diag_codes:
        raise SystemExit("No unconditional diagnosis codes found")

    if args.version == "v24":
        beneficiaries = generate_beneficiaries_v24(args.n, args.seed, diag_codes)
        write_cms_inputs_v24(args.cms_package_dir, beneficiaries, args.year)
    else:
        beneficiaries = generate_beneficiaries_v21(args.n, args.seed, diag_codes)
        write_cms_inputs_v21(args.cms_package_dir, beneficiaries, args.year)
    print(f"Generated {len(beneficiaries)} synthetic beneficiaries.")

    print("Running CMS transform.py...")
    cms_df = run_cms_transform(args.cms_package_dir)

    print(f"Running MedicareModelESRD{args.version}...")
    checks = (
        run_repo_model_v24(beneficiaries, args.year)
        if args.version == "v24"
        else run_repo_model_v21(beneficiaries, args.year)
    )

    mismatches = compare(checks, cms_df)
    print(
        f"\n{len(checks) - len(mismatches)}/{len(checks)} checks matched (within rounding tolerance)."
    )
    if mismatches:
        print(f"\n{len(mismatches)} MISMATCHES:")
        for b, label, cms_score, repo_score, note in mismatches:
            print(
                f"  id={b['id']} check={label} age={b['age']} gender={b['gender']} orec={b['orec']} "
                f"dx={b['diagnoses']} -> CMS={cms_score} repo={repo_score} {note or ''}"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()

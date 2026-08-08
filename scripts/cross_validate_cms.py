"""
Cross-validates CommercialModelV08 against the CMS HHS-HCC DIY software package's own
transform.py: generates a batch of synthetic enrollees, scores them through both, and
compares. This is the strongest end-to-end correctness signal available (it exercises the
real CMS reference implementation, not just this repo's re-derivation of it).

Requires the optional `cms_validation` dependency group:
    poetry install --with cms_validation

Usage:
    poetry run python scripts/cross_validate_cms.py [--n 150] [--seed 42]

The target benefit year is read from the CMS package's model_version_config.py (the package
is year-specific -- you can't ask it to score a different year without pointing
CMS_PACKAGE_DIR at a different package).

Diagnosis codes are restricted to those with no MCE/age/sex condition in CMS's source ICD10
crosswalk, for two different reasons:
- AGE_EDIT_CONDITION/SEX_EDIT_CONDITION codes ARE implemented (via the `_age_sex_edit_N`
  methods in v08.py), but are excluded here to keep this script focused on the score
  *pipeline* (hierarchies, groups, interactions, ACF, CSR adjustment) -- the edit-method
  reconciliation itself already has dedicated coverage via
  scripts/build_v08_reference_data.py's diag-map comparison and test_age_sex_edits.
- MCE_AGE_CONDITION codes are excluded because this repo intentionally does not implement
  CMS's MCE claims-editing plausibility checks at all (see README.md's "key design decisions"
  and CommercialModel's class docstring) -- CMS would reject some enrollee/code combinations
  this repo would accept, which would produce mismatches unrelated to what this script tests.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cms_package import find_cms_root  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
CMS_ROOT = find_cms_root()
CMS_SOFTWARE = CMS_ROOT / "software/HHS_HCC"
CMS_INTERNAL = CMS_SOFTWARE / "data/input/internal"
CMS_USER_DEFINED = CMS_SOFTWARE / "data/input/user_defined"
CMS_OUTPUT = CMS_SOFTWARE / "data/output"

METAL_CODE_TO_NAME = {
    "P": "Platinum",
    "G": "Gold",
    "S": "Silver",
    "B": "Bronze",
    "C": "Catastrophic",
}

# CommercialBeneficiary._determine_enrollment_months' day ranges, collapsed to one
# representative day per month-bucket so both sides land on the same bucket.
ENROLLMENT_MONTH_TO_DAYS = {
    1: 15,
    2: 45,
    3: 75,
    4: 105,
    5: 135,
    6: 165,
    7: 195,
    8: 225,
    9: 255,
    10: 285,
    11: 315,
    12: 350,
}


def get_benefit_year() -> int:
    text = (CMS_SOFTWARE / "model_version_config.py").read_text()
    match = re.search(r"benefit_year\s*=\s*(\d+)", text)
    if not match:
        raise SystemExit("Could not read benefit_year from model_version_config.py")
    return int(match.group(1))


def read_repo_mapping_codes(year: int, filename: str) -> list:
    path = (
        REPO_ROOT
        / f"src/risk_adjustment_model/reference_data/commercial/v08/{year}/{filename}"
    )
    if not path.exists():
        return []
    codes = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split("\t")
            if parts and parts[0]:
                codes.append(parts[0])
    return codes


def read_unconditional_diag_codes(year: int) -> list:
    path = CMS_INTERNAL / f"ICD10_HHS_CC_mappings_{year}.csv"
    codes = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get(f"valid_ICD10_{year}", "").strip().upper() != "TRUE":
                continue
            if (
                row["MCE_AGE_CONDITION"]
                or row["AGE_EDIT_CONDITION"]
                or row["SEX_EDIT_CONDITION"]
            ):
                continue
            codes.append(row["ICD10"].strip())
    return sorted(set(codes))


def generate_enrollees(n: int, seed: int, year: int) -> list:
    random.seed(seed)
    fake = Faker()
    Faker.seed(seed)

    diag_codes = read_unconditional_diag_codes(year)
    ndc_codes = read_repo_mapping_codes(year, "ndc_to_category_map.txt")
    hcpcs_codes = read_repo_mapping_codes(year, "proc_to_category_map.txt")
    acf_codes = read_repo_mapping_codes(year, "acf_to_category_map.txt")
    # NDC codes are all-digit 11-char strings; HCPCS/proc codes are alnum. Split the small
    # ACF pool the same way so a slice of enrollees can be deliberately steered to exercise it.
    acf_ndc_codes = [c for c in acf_codes if c.isdigit()]
    acf_hcpcs_codes = [c for c in acf_codes if not c.isdigit()]

    if not diag_codes:
        raise SystemExit(
            f"No unconditional diagnosis codes found for benefit year {year}"
        )

    enrollees = []
    for i in range(n):
        member_id = str(i + 1)
        gender_code = random.choice((1, 2))  # 1=Male, 2=Female
        gender = "M" if gender_code == 1 else "F"

        # Weighted so all three populations (Infant/Child/Adult) get real coverage.
        population = random.choices(
            ("Infant", "Child", "Adult"), weights=(0.1, 0.3, 0.6)
        )[0]
        if population == "Infant":
            age = random.choice((0, 1))
        elif population == "Child":
            age = random.randint(2, 20)
        else:
            age = random.randint(21, 90)

        metal_code = random.choice(list(METAL_CODE_TO_NAME))
        csr_indicator = random.randint(1, 11)
        enrollment_month = random.randint(1, 12)

        diagnoses = random.sample(diag_codes, k=random.randint(0, 3))

        ndc = []
        hcpcs = []
        if population in ("Adult", "Child"):
            # ~15% of eligible enrollees deliberately get a real ACF-triggering code so the
            # synthetic batch actually exercises ACF_PrEP/ACF_PrEP_Child, not just incidentally.
            if random.random() < 0.15:
                if population == "Adult" and acf_ndc_codes:
                    ndc.append(random.choice(acf_ndc_codes))
                elif population == "Child" and acf_hcpcs_codes:
                    hcpcs.append(random.choice(acf_hcpcs_codes))
        if population == "Adult":
            if ndc_codes and random.random() < 0.3:
                ndc.extend(random.sample(ndc_codes, k=random.randint(1, 2)))
            if hcpcs_codes and random.random() < 0.2:
                hcpcs.extend(random.sample(hcpcs_codes, k=1))

        enrollees.append(
            {
                "id": member_id,
                "faker_uuid": fake.uuid4(),
                "gender_code": gender_code,
                "gender": gender,
                "age": age,
                "population": population,
                "dob": date(year - age, 6, 15),
                "metal_code": metal_code,
                "metal_name": METAL_CODE_TO_NAME[metal_code],
                "csr_indicator": csr_indicator,
                "enrollment_month": enrollment_month,
                "enrollment_days": ENROLLMENT_MONTH_TO_DAYS[enrollment_month],
                "diagnoses": diagnoses,
                "ndc": ndc,
                "hcpcs": hcpcs,
            }
        )
    return enrollees


def write_cms_inputs(enrollees: list, year: int):
    diag_date = f"{year}0315"
    with open(CMS_USER_DEFINED / "PERSON.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["ID", "SEX", "DOB", "AGE_LAST", "METAL", "CSR_INDICATOR", "ENROLDURATION"]
        )
        for e in enrollees:
            writer.writerow(
                [
                    e["id"],
                    e["gender_code"],
                    e["dob"].strftime("%Y%m%d"),
                    e["age"],
                    e["metal_code"],
                    e["csr_indicator"],
                    e["enrollment_month"],
                ]
            )

    with open(CMS_USER_DEFINED / "DIAGNOSES.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "ICD10", "DIAGNOSIS_SERVICE_DATE"])
        for e in enrollees:
            for code in e["diagnoses"]:
                writer.writerow([e["id"], code, diag_date])

    with open(CMS_USER_DEFINED / "NDC.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "NDC"])
        for e in enrollees:
            for code in e["ndc"]:
                writer.writerow([e["id"], code])

    with open(CMS_USER_DEFINED / "HCPCS.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "HCPCS"])
        for e in enrollees:
            for code in e["hcpcs"]:
                writer.writerow([e["id"], code])


def reset_cms_inputs():
    templates = {
        "PERSON.csv": [
            "ID",
            "SEX",
            "DOB",
            "AGE_LAST",
            "METAL",
            "CSR_INDICATOR",
            "ENROLDURATION",
        ],
        "DIAGNOSES.csv": ["ID", "ICD10", "DIAGNOSIS_SERVICE_DATE"],
        "NDC.csv": ["ID", "NDC"],
        "HCPCS.csv": ["ID", "HCPCS"],
    }
    for filename, header in templates.items():
        with open(CMS_USER_DEFINED / filename, "w", newline="") as f:
            csv.writer(f).writerow(header)


def run_cms_transform() -> pd.DataFrame:
    before = set(CMS_OUTPUT.glob("*.csv"))
    subprocess.run(
        [sys.executable, str(CMS_SOFTWARE / "transform.py")],
        cwd=CMS_SOFTWARE,
        check=True,
        capture_output=True,
        text=True,
    )
    after = set(CMS_OUTPUT.glob("*.csv"))
    new_files = after - before
    output_path = (
        max(new_files, key=lambda p: p.stat().st_mtime)
        if new_files
        else max(after, key=lambda p: p.stat().st_mtime)
    )
    df = pd.read_csv(output_path, dtype={"ID": str})
    return df.set_index("ID")


def run_repo_model(enrollees: list, year: int) -> dict:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from risk_adjustment_model import CommercialModelV08

    model = CommercialModelV08(year=year)
    scores = {}
    for e in enrollees:
        result = model.score(
            gender=e["gender"],
            metal_level=e["metal_name"],
            csr_indicator=e["csr_indicator"],
            enrollment_days=e["enrollment_days"],
            diagnosis_codes=e["diagnoses"] or None,
            ndc_codes=e["ndc"] or None,
            proc_codes=e["hcpcs"] or None,
            age=e["age"],
            verbose=False,
        )
        scores[e["id"]] = result.score
    return scores


def compare(enrollees: list, cms_df: pd.DataFrame, repo_scores: dict) -> list:
    mismatches = []
    for e in enrollees:
        cms_col = f"CSR_ADJUSTED_SCORE_{e['population'].upper()}"
        if e["id"] not in cms_df.index or cms_col not in cms_df.columns:
            mismatches.append((e, None, repo_scores.get(e["id"]), "missing CMS output"))
            continue
        cms_score = round(float(cms_df.loc[e["id"], cms_col]), 3)
        repo_score = round(float(repo_scores[e["id"]]), 3)
        if abs(cms_score - repo_score) > 0.001:
            mismatches.append((e, cms_score, repo_score, None))
    return mismatches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n", type=int, default=150, help="Number of synthetic enrollees."
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed, for reproducibility."
    )
    args = parser.parse_args()

    year = get_benefit_year()
    print(f"CMS package benefit year: {year}")

    enrollees = generate_enrollees(args.n, args.seed, year)
    print(f"Generated {len(enrollees)} synthetic enrollees.")

    try:
        write_cms_inputs(enrollees, year)
        print("Running CMS transform.py...")
        cms_df = run_cms_transform()

        print("Running CommercialModelV08...")
        repo_scores = run_repo_model(enrollees, year)

        mismatches = compare(enrollees, cms_df, repo_scores)

        print(
            f"\n{len(enrollees) - len(mismatches)}/{len(enrollees)} scores matched (within rounding tolerance)."
        )
        if mismatches:
            print(f"\n{len(mismatches)} MISMATCHES:")
            for e, cms_score, repo_score, note in mismatches:
                print(
                    f"  id={e['id']} pop={e['population']} age={e['age']} gender={e['gender']} "
                    f"metal={e['metal_name']} dx={e['diagnoses']} ndc={e['ndc']} hcpcs={e['hcpcs']} "
                    f"-> CMS={cms_score} repo={repo_score} {note or ''}"
                )
            sys.exit(1)
    finally:
        reset_cms_inputs()


if __name__ == "__main__":
    main()

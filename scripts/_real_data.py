"""
Shared helpers for the `--real-data-dir` mode in the cross_validate_*_cms.py scripts: an
alternative to their default Faker-generated batches, for validating this repo's models against
CMS's own transform.py using actual production beneficiary/diagnosis data instead of synthetic
data.

Each cross-validation script defines its own `load_real_beneficiaries()` (family-specific column
sets), but they all share this module's small set of conventions:

- Real data lives in a directory of CSV files (`--real-data-dir /path/to/dir`), with a
  `beneficiaries.csv` and a `diagnoses.csv`, both named and shaped as documented in the
  cross-validation script's own module docstring -- these column names are this repo's own stable
  interchange format, chosen independently of whatever the CMS package's own
  data/input/user_defined/ file layout happens to be for a given vintage (that varies release to
  release; see each script's docstring).
- DOB must be ISO format (YYYY-MM-DD). This decouples the real-data format from the CMS package's
  own DOB_format setting, which varies by package (%m/%d/%Y vs %Y%m%d) -- the script converts to
  whatever the target package needs when it writes the package's own input files.
- Boolean flag columns (e.g. MEDICAID, FBDUAL, ESRD) accept 1/0/true/false/yes/no, case-insensitive.
- Unlike the synthetic path, real diagnosis codes are NOT filtered to CMS's "no MCE/age/sex
  condition" subset -- that filtering exists only so randomly-sampled synthetic codes don't
  accidentally violate an MCE age/sex restriction this repo doesn't implement (see README's "key
  design decisions"). Real data reflects whatever a real beneficiary was actually coded with, so a
  mismatch caused by an MCE-restricted code is expected and not a bug; if you want an apples-to-
  apples run, pre-filter your diagnoses.csv against the same MCE_AGE_CONDITION/AGE_EDIT_CONDITION/
  SEX_EDIT_CONDITION columns in the CMS package's own ICD10 crosswalk first.
"""

import csv
from datetime import date
from pathlib import Path


def read_real_csv(real_data_dir: Path, filename: str) -> list:
    path = real_data_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Expected {filename} in {real_data_dir}")
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def parse_bool(value) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def parse_iso_dob(value) -> date:
    return date.fromisoformat(str(value).strip())


def age_as_of_feb_1(dob: date, payment_year: int) -> int:
    # Matches CMS's own age-calculation reference date (Feb 1 of the payment year).
    cutoff = date(payment_year, 2, 1)
    age = cutoff.year - dob.year
    if (cutoff.month, cutoff.day) < (dob.month, dob.day):
        age -= 1
    return age


def group_by_id(rows: list, id_key: str, value_key: str) -> dict:
    grouped = {}
    for row in rows:
        grouped.setdefault(row[id_key].strip(), []).append(row[value_key].strip())
    return grouped

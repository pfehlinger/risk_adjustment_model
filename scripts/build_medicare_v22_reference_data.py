"""
Builds risk_adjustment_model's reference_data/medicare/v22/2026 files from scratch from CMS's
PY2026 CMS-HCC V22 Python DIY software package (CMS_HCC_v22_2026_O_package_v3).

Unlike scripts/build_medicare_reference_data.py (which regenerates a year for a version that
already has reference data in this repo to verify/carry-forward against and diff diag_to_category_map.txt
against), V22 has never been implemented here before -- there is no prior year to compare against.
This is therefore a "cold start" build:

- category_definition.json / hierarchy_definition.json are built directly from CMS's source (the
  CE_Relative_Factors.csv "Label" column supplies human-readable descriptions for every
  demographic/disease/interaction category; V22_HCC_Hierarchies.csv supplies hierarchy exclusions),
  not verified against a prior year.
- diag_to_category_map.txt's conditional (AGE_EDIT_CONDITION/SEX_EDIT_CONDITION) rows can't use the
  "carry forward the prior year's proven base/override split" trick from build_medicare_reference_data.py
  either. Instead, every ICD10 code's outcome was evaluated across a full age/gender grid directly
  from CMS's source: 732 of 751 conditional-looking codes turned out to be "effectively unconditional"
  (their CC outcome is identical regardless of age/gender -- the condition rows partition the age
  range exhaustively into the same target CC), and are emitted as plain unconditional rows. Only 19
  codes are genuinely conditional and need a Python edit method (v22.py's three `_age_sex_edit_N`
  methods) -- their target base/override split was determined by direct inspection and is hardcoded
  in GENUINELY_CONDITIONAL_CODES below rather than re-derived by this script, since getting this
  wrong silently produces incorrect risk scores.

Once this initial year exists, PY2027 (and any subsequent year) should use the generic
scripts/build_medicare_reference_data.py --version v22 --prior-year 2026 --target-year 2027, which
can now diff against this year like any other version.

Usage:
    poetry run python scripts/build_medicare_v22_reference_data.py \\
        --cms-package-dir /path/to/extracted/CMS_HCC_v22_2026_O_package_v3/software/CMS_HCC_v22
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_TARGET = REPO_ROOT / "src/risk_adjustment_model/reference_data/medicare/v22/2026"

CE_COLUMN_MAP = {
    "COMMUNITY_NA": "CNA",
    "COMMUNITY_PBA": "CPA",
    "COMMUNITY_FBA": "CFA",
    "COMMUNITY_ND": "CND",
    "COMMUNITY_PBD": "CPD",
    "COMMUNITY_FBD": "CFD",
    "INSTITUTIONAL": "INS",
}
CE_COLUMNS_ORDER = ["CNA", "CND", "CFA", "CFD", "CPA", "CPD", "INS"]
NE_COLUMNS_ORDER = [
    "NE_NMCAID_NORIGDIS",
    "NE_MCAID_NORIGDIS",
    "NE_NMCAID_ORIGDIS",
    "NE_MCAID_ORIGDIS",
]
NE_PREFIX_MAP = {
    "NMCAID_NORIGDIS": "NE_NMCAID_NORIGDIS",
    "MCAID_NORIGDIS": "NE_MCAID_NORIGDIS",
    "NMCAID_ORIGDIS": "NE_NMCAID_ORIGDIS",
    "MCAID_ORIGDIS": "NE_MCAID_ORIGDIS",
}
ALL_WEIGHT_COLUMNS = CE_COLUMNS_ORDER + NE_COLUMNS_ORDER

# The 25 disease-interaction categories, sourced from V22_Interactions.csv, confirmed all present
# as scored rows in V22_CE_Relative_Factors.csv (some pairs share the same underlying condition but
# are scored under two different names for Community vs. Institutional -- both are emitted; CMS's
# own sparse per-population coefficients mean the "wrong" population's copy is simply 0/blank).
DISEASE_INTERACTIONS = [
    "HCC47_gCancer",
    "HCC85_gDiabetesMellit",
    "HCC85_gCopdCF",
    "HCC85_gRenal",
    "gRespDepandArre_gCopdCF",
    "HCC85_HCC96",
    "gSubstanceAbuse_gPsychiatric",
    "CHF_gCopdCF",
    "gCopdCF_CARD_RESP_FAIL",
    "SEPSIS_PRESSURE_ULCER",
    "SEPSIS_ARTIF_OPENINGS",
    "ART_OPENINGS_PRESSURE_ULCER",
    "DIABETES_CHF",
    "gCopdCF_ASP_SPEC_BACT_PNEUM",
    "ASP_SPEC_BACT_PNEUM_PRES_ULC",
    "SEPSIS_ASP_SPEC_BACT_PNEUM",
    "SCHIZOPHRENIA_gCopdCF",
    "SCHIZOPHRENIA_CHF",
    "SCHIZOPHRENIA_SEIZURES",
    "DISABLED_HCC85",
    "DISABLED_PRESSURE_ULCER",
    "DISABLED_HCC161",
    "DISABLED_HCC39",
    "DISABLED_HCC77",
    "DISABLED_HCC6",
]
DEMOGRAPHIC_INTERACTIONS = [
    "LTIMCAID",
    "OriginallyDisabled_Female",
    "OriginallyDisabled_Male",
]

# code -> base static CC row (the edit method in v22.py supplies the override for the other branch)
# Determined by evaluating each code's CMS condition rows across a full age/gender grid --
# see the module docstring. Matches this repo's existing v24.py-established convention of one
# unconditional "default" row plus a hardcoded Python edit method for the minority branch.
GENUINELY_CONDITIONAL_CODES = {
    # Male (default) -> CC46 (HCC46); Female -> CC48 (HCC48), via _age_sex_edit_1.
    "D66": "46",
    "D67": "46",
    # Static default -> CC58 (HCC58, "Major Depressive/Bipolar/and Paranoid Disorders"); rejected
    # (no category) outside age 6-18, via _age_sex_edit_3 returning the "NA" sentinel.
    "F3481": "58",
}
# age < 18 -> CC112 (HCC112); age >= 18 (default) -> CC111 (HCC111), via _age_sex_edit_2.
_EDIT_2_CODES = [
    "J410",
    "J411",
    "J418",
    "J42",
    "J430",
    "J431",
    "J432",
    "J438",
    "J439",
    "J440",
    "J441",
    "J4481",
    "J4489",
    "J449",
    "J982",
    "J983",
]
for _code in _EDIT_2_CODES:
    GENUINELY_CONDITIONAL_CODES[_code] = "111"


def read_cms_csv(cms_dir: Path, name: str):
    with open(
        cms_dir / "data/input/internal" / name, newline="", encoding="utf-8-sig"
    ) as f:
        return list(csv.DictReader(f))


def build_definitions(cms_dir: Path):
    hierarchy_rows = read_cms_csv(cms_dir, "V22_HCC_Hierarchies.csv")
    hierarchy = {}
    disease_hccs = set()
    for row in hierarchy_rows:
        hcc = row["HCC"].strip()
        disease_hccs.add(hcc)
        secondaries = [
            row[f"SecondaryHCC_{i}"].strip()
            for i in range(1, 6)
            if row.get(f"SecondaryHCC_{i}", "").strip()
        ]
        if secondaries:
            hierarchy[hcc] = {"descr": None, "remove_code": secondaries}

    ce_rows = read_cms_csv(cms_dir, "V22_CE_Relative_Factors.csv")
    labels = {row["Variable"].strip(): row["Label"].strip() for row in ce_rows}

    categories = {}
    for hcc in disease_hccs:
        categories[hcc] = {
            "descr": labels.get(hcc, hcc),
            "type": "disease",
            "number": int(hcc.replace("HCC", "")),
        }
        if hcc in hierarchy:
            hierarchy[hcc]["descr"] = labels.get(hcc, hcc)

    for row in ce_rows:
        var = row["Variable"].strip()
        if var[0] in "FM" and var[1:2].isdigit():
            categories[var] = {"descr": labels[var].strip(), "type": "demographic"}

    for name in DISEASE_INTERACTIONS:
        categories[name] = {
            "descr": labels.get(name, name),
            "type": "disease_interaction",
        }
    for name in DEMOGRAPHIC_INTERACTIONS:
        categories[name] = {
            "descr": labels.get(name, name),
            "type": "demographic_interaction",
        }

    ne_rows = read_cms_csv(cms_dir, "V22_NE_Relative_Factors.csv")
    for row in ne_rows:
        variable = row["Variable"].strip()
        for cms_prefix in NE_PREFIX_MAP:
            if variable.startswith(cms_prefix + "_"):
                category = variable[len(cms_prefix) + 1 :]
                if category not in categories:
                    categories[category] = {
                        "descr": row["New Enrollees"].strip(),
                        "type": "demographic",
                    }
                break

    REPO_TARGET.mkdir(parents=True, exist_ok=True)
    with open(REPO_TARGET / "hierarchy_definition.json", "w") as f:
        json.dump(hierarchy, f)
    with open(REPO_TARGET / "category_definition.json", "w") as f:
        json.dump(categories, f)
    print(
        f"  Wrote hierarchy_definition.json ({len(hierarchy)} entries), category_definition.json ({len(categories)} entries)"
    )
    return categories


def build_weights(cms_dir: Path, categories: dict):
    ce_categories = {
        k
        for k, v in categories.items()
        if not (v["type"] == "demographic" and k.startswith("NE"))
    }
    ne_categories = {
        k
        for k, v in categories.items()
        if v["type"] == "demographic" and k.startswith("NE")
    }

    weights = defaultdict(lambda: {col: 0.0 for col in ALL_WEIGHT_COLUMNS})

    for row in read_cms_csv(cms_dir, "V22_CE_Relative_Factors.csv"):
        category = row["Variable"].strip()
        if category not in ce_categories:
            continue  # ORIGDIS: unscored placeholder, same pattern as V24/V28
        for cms_col, repo_col in CE_COLUMN_MAP.items():
            raw = row.get(cms_col, "").strip()
            weights[category][repo_col] = float(raw) if raw else 0.0

    for row in read_cms_csv(cms_dir, "V22_NE_Relative_Factors.csv"):
        variable = row["Variable"].strip()
        for cms_prefix, repo_col in NE_PREFIX_MAP.items():
            if variable.startswith(cms_prefix + "_"):
                category = variable[len(cms_prefix) + 1 :]
                if category in ne_categories:
                    weights[category][repo_col] = float(row["NE"])
                break

    with open(REPO_TARGET / "weights.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["category"] + ALL_WEIGHT_COLUMNS)
        for category, pop_weight in weights.items():
            writer.writerow(
                [category] + [pop_weight[col] for col in ALL_WEIGHT_COLUMNS]
            )
    print(f"  Wrote weights.csv ({len(weights)} data rows)")


def build_diag_map(cms_dir: Path):
    rows_by_code = defaultdict(list)
    for row in read_cms_csv(cms_dir, "ICD10_CC_mappings_CMS_HCC_2026_v22.csv"):
        rows_by_code[row["ICD10"].strip()].append(row)

    out_lines = []
    for code, rows in rows_by_code.items():
        if code in GENUINELY_CONDITIONAL_CODES:
            out_lines.append([code, GENUINELY_CONDITIONAL_CODES[code]])
            continue
        # Effectively unconditional: every row's CC is the code's outcome regardless of which
        # condition (if any) applies, since the conditions partition the age range exhaustively.
        ccs = sorted({str(int(float(r["CC"]))) for r in rows})
        for i, cc in enumerate(ccs):
            flag = ["D"] if i > 0 else []
            out_lines.append([code, cc] + flag)

    out_lines.sort(key=lambda p: p[0])
    with open(REPO_TARGET / "diag_to_category_map.txt", "w") as f:
        for parts in out_lines:
            f.write("\t".join(parts) + "\n")
    print(
        f"  Wrote diag_to_category_map.txt ({len(out_lines)} lines, {len(rows_by_code)} codes, {len(GENUINELY_CONDITIONAL_CODES)} handled via hardcoded edit methods)"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cms-package-dir", required=True, type=Path)
    args = parser.parse_args()

    print("Building hierarchy_definition.json / category_definition.json...")
    categories = build_definitions(args.cms_package_dir)

    print("Building weights.csv...")
    build_weights(args.cms_package_dir, categories)

    print("Building diag_to_category_map.txt...")
    build_diag_map(args.cms_package_dir)

    print("Done.")


if __name__ == "__main__":
    main()

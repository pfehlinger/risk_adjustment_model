"""
Builds risk_adjustment_model's reference_data/medicare/v24_esrd/2026 files from scratch from
CMS's PY2026 ESRD V24 Python DIY software package (ESRD_v24_2026_T_package_v2).

Same "cold start" approach as scripts/build_medicare_v22_reference_data.py -- there's no prior
year of ESRD reference data in this repo to diff against, so category/hierarchy definitions are
built directly from CMS's source, and diag_to_category_map.txt's conditional rows are resolved by
evaluating every ICD10 code's outcome across a full age/gender grid rather than diffed against a
known-good prior year. Once this initial year exists, subsequent years should get their own
"--version v24_esrd" support added to build_medicare_reference_data.py, the way V22 did.

ESRD-specific adaptations over the V22/Community cold-start pattern:

- weights.csv has 14 population columns instead of 7-8: 6 continuing-enrollee (DIAL,
  GRAFT_COMM_ND_PBD_GE65/LT65, GRAFT_COMM_FBD_GE65/LT65, GRAFT_INST) and 8 new-enrollee (4
  NE_DIAL_* + 4 NE_GRAFT_* dual/origdis combinations), reshaped from CMS's V24_CE_Relative_Factors
  / V24_NE_Dialysis_Relative_Factors / V24_NE_Graft_Relative_Factors files. See v24_esrd.py's
  module docstring for why dual+aged is baked into the GRAFT_COMM/NE_* population names but not
  GRAFT_INST's (GRAFT_INST's base coefficients don't vary by dual/aged at all -- only the
  graft-duration bonus does, computed at scoring time instead).
- Three additional flat lookup tables (graft_duration_scores.csv, institutional_graft_scores.csv,
  transplant_scores.csv) get carried over near-verbatim from CMS's V24_Graft_Duration_Scores.csv /
  V24_CE_Institutional_Graft_Scores.csv / V24_Transplant_Scores.csv -- these don't fit weights.csv's
  category-by-population shape at all (see reference_files_loader.py's _get_flat_score_table).
- Renal categories (HCC134-138) are permanently excluded from every file this script writes (never
  appear in category/hierarchy definitions, weights.csv, or diag_to_category_map.txt). CMS's own
  software forcibly zeroes these CCs for every ESRD beneficiary before scoring (already
  dialysis/graft-dependent, so scoring renal failure again would double-count); since the outcome
  is identical either way, omitting the ~40 diagnosis codes that would otherwise map to them is
  simpler than reproducing an always-true rejection rule in Python. See v24_esrd.py.
- Despite the ICD10_CC_mappings crosswalk showing ~1500 rows with an AGE_EDIT_CONDITION or
  SEX_EDIT_CONDITION value (vs. V22/V24 Community's ~750), grouping by code and evaluating across
  a full age/gender grid collapses this to the exact same 19 genuinely conditional codes as
  V22/V24 Community (D66/D67, 16 J-codes, F3481) -- CMS reuses this edit list across model
  families; the larger raw row count is just ESRD's crosswalk expressing some effectively
  unconditional codes (mostly diabetes/thyroid/psychiatric ICD10s) via more, finer age-bucketed
  rows that all resolve to the same CC. One genuine difference from Community: F3481 has no
  unconditional default row in ESRD's crosswalk at all (it maps to HCC59 only within age 6-18,
  and to nothing outside that range) -- see v24_esrd.py's _age_sex_edit_3 and NO_DEFAULT_CODES below.

Usage:
    poetry run python scripts/build_medicare_v24_esrd_reference_data.py \\
        --cms-package-dir /path/to/extracted/ESRD_v24_2026_T_package_v2/software/ESRD_v24
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_TARGET = (
    REPO_ROOT / "src/risk_adjustment_model/reference_data/medicare/v24_esrd/2026"
)

RENAL_CCS = {"134", "135", "136", "137", "138"}

CE_COLUMN_MAP = {
    "DIAL": "DIAL",
    "G_COMM_ND_PBD_GE65": "GRAFT_COMM_ND_PBD_GE65",
    "G_COMM_ND_PBD_LT65": "GRAFT_COMM_ND_PBD_LT65",
    "G_COMM_FBD_GE65": "GRAFT_COMM_FBD_GE65",
    "G_COMM_FBD_LT65": "GRAFT_COMM_FBD_LT65",
    "GRAFT_INST": "GRAFT_INST",
}
CE_COLUMNS_ORDER = list(CE_COLUMN_MAP.values())
NE_DIAL_PREFIX_MAP = {
    "ND_PBD_NORIGDIS": "NE_DIAL_ND_PBD_NORIGDIS",
    "FBD_NORIGDIS": "NE_DIAL_FBD_NORIGDIS",
    "ND_PBD_ORIGDIS": "NE_DIAL_ND_PBD_ORIGDIS",
    "FBD_ORIGDIS": "NE_DIAL_FBD_ORIGDIS",
}
NE_GRAFT_PREFIX_MAP = {
    "ND_PBD_NORIGDIS_G": "NE_GRAFT_ND_PBD_NORIGDIS",
    "FBD_NORIGDIS_G": "NE_GRAFT_FBD_NORIGDIS",
    "ND_PBD_ORIGDIS_G": "NE_GRAFT_ND_PBD_ORIGDIS",
    "FBD_ORIGDIS_G": "NE_GRAFT_FBD_ORIGDIS",
}
NE_COLUMNS_ORDER = list(NE_DIAL_PREFIX_MAP.values()) + list(
    NE_GRAFT_PREFIX_MAP.values()
)
ALL_WEIGHT_COLUMNS = CE_COLUMNS_ORDER + NE_COLUMNS_ORDER

# The 26 scored ESRD V24 disease interactions (V24_Interactions.csv has 27; HCC85_gRenal_V24 is
# omitted since it can never trigger -- see module docstring).
DISEASE_INTERACTIONS = [
    "HCC47_gCancer",
    "DIABETES_CHF",
    "CHF_gCopdCF",
    "gCopdCF_CARD_RESP_FAIL",
    "HCC85_HCC96",
    "gSubUseDs_gPsych_V24",
    "SEPSIS_PRESSURE_ULCER_V24",
    "SEPSIS_ARTIF_OPENINGS",
    "ART_OPENINGS_PRESSURE_ULCER_V24",
    "gCopdCF_ASP_SPEC_B_PNEUM",
    "ASP_SPEC_B_PNEUM_PRES_ULC_V24",
    "SEPSIS_ASP_SPEC_BACT_PNEUM",
    "SCHIZOPHRENIA_gCopdCF",
    "SCHIZOPHRENIA_CHF",
    "SCHIZOPHRENIA_SEIZURES",
    "NONAGED_gSubUseDs_gPsych",
    "NONAGED_HCC6",
    "NONAGED_HCC34",
    "NONAGED_HCC46",
    "NONAGED_HCC110",
    "NONAGED_HCC176",
    "NONAGED_HCC85",
    "NONAGED_PRESSURE_ULCER_V24",
    "NONAGED_HCC161",
    "NONAGED_HCC39",
    "NONAGED_HCC77",
]
DEMOGRAPHIC_INTERACTIONS = [
    "OriginallyDisabled_Female",
    "OriginallyDisabled_Male",
    "Originally_ESRD_Female",
    "Originally_ESRD_Male",
    "LTI_Aged",
    "LTI_NonAged",
    "FBDual_Female_Aged",
    "FBDual_Female_NonAged",
    "FBDual_Male_Aged",
    "FBDual_Male_NonAged",
    "PBDual_Female_Aged",
    "PBDual_Female_NonAged",
    "PBDual_Male_Aged",
    "PBDual_Male_NonAged",
]

# code -> base static CC row (v24_esrd.py's edit methods supply the override for the other
# branch). Determined by evaluating each code's CMS condition rows across a full age/gender grid
# -- see module docstring.
GENUINELY_CONDITIONAL_CODES = {
    # Male (default) -> CC46 (HCC46); Female -> CC48 (HCC48), via _age_sex_edit_1.
    "D66": "46",
    "D67": "46",
}
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
    # age < 18 -> CC112 (HCC112); age >= 18 (default) -> CC111 (HCC111), via _age_sex_edit_2.
    GENUINELY_CONDITIONAL_CODES[_code] = "111"

# F3481 has no unconditional default row in ESRD's crosswalk (unlike V22/V24 Community) -- it
# maps to HCC59 only within age 6-18, handled entirely by _age_sex_edit_3, and gets no static row.
NO_DEFAULT_CODES = {"F3481"}


def read_cms_csv(cms_dir: Path, name: str):
    with open(
        cms_dir / "data/input/internal" / name, newline="", encoding="utf-8-sig"
    ) as f:
        return list(csv.DictReader(f))


def cc_to_bare_number(cc: str) -> str:
    return str(int(float(cc)))


def build_definitions(cms_dir: Path):
    hierarchy_rows = read_cms_csv(cms_dir, "V24_HCC_Hierarchies.csv")
    hierarchy = {}
    disease_hccs = set()
    for row in hierarchy_rows:
        hcc = row["HCC"].strip()
        if hcc.replace("HCC", "") in RENAL_CCS:
            continue
        disease_hccs.add(hcc)
        secondaries = [
            row[f"SecondaryHCC_{i}"].strip()
            for i in range(1, 6)
            if row.get(f"SecondaryHCC_{i}", "").strip()
        ]
        secondaries = [s for s in secondaries if s.replace("HCC", "") not in RENAL_CCS]
        if secondaries:
            hierarchy[hcc] = {"descr": None, "remove_code": secondaries}

    ce_rows = read_cms_csv(cms_dir, "V24_CE_Relative_Factors.csv")
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

    for filename, prefix_map in (
        ("V24_NE_Dialysis_Relative_Factors.csv", NE_DIAL_PREFIX_MAP),
        ("V24_NE_Graft_Relative_Factors.csv", NE_GRAFT_PREFIX_MAP),
    ):
        for row in read_cms_csv(cms_dir, filename):
            variable = row["Variable"].strip()
            for cms_prefix in prefix_map:
                if variable.startswith(cms_prefix + "_"):
                    category = variable[len(cms_prefix) + 1 :]
                    if category not in categories:
                        categories[category] = {
                            "descr": row["Label"].strip(),
                            "type": "demographic",
                        }
                    break

    REPO_TARGET.mkdir(parents=True, exist_ok=True)
    with open(REPO_TARGET / "hierarchy_definition.json", "w") as f:
        json.dump(hierarchy, f)
    with open(REPO_TARGET / "category_definition.json", "w") as f:
        json.dump(categories, f)
    print(
        f"  Wrote hierarchy_definition.json ({len(hierarchy)} entries), "
        f"category_definition.json ({len(categories)} entries)"
    )
    return categories


def build_weights(cms_dir: Path, categories: dict):
    weights = defaultdict(lambda: {col: 0.0 for col in ALL_WEIGHT_COLUMNS})

    for row in read_cms_csv(cms_dir, "V24_CE_Relative_Factors.csv"):
        category = row["Variable"].strip()
        if category not in categories:
            continue  # ORIGDIS: unscored placeholder, same pattern as Community
        for cms_col, repo_col in CE_COLUMN_MAP.items():
            raw = row.get(cms_col, "").strip()
            weights[category][repo_col] = float(raw) if raw else 0.0

    for filename, prefix_map in (
        ("V24_NE_Dialysis_Relative_Factors.csv", NE_DIAL_PREFIX_MAP),
        ("V24_NE_Graft_Relative_Factors.csv", NE_GRAFT_PREFIX_MAP),
    ):
        value_col = "DIAL_NE" if "Dialysis" in filename else "GRAFT_NE"
        for row in read_cms_csv(cms_dir, filename):
            variable = row["Variable"].strip()
            for cms_prefix, repo_col in prefix_map.items():
                if variable.startswith(cms_prefix + "_"):
                    category = variable[len(cms_prefix) + 1 :]
                    if category in categories:
                        raw = row.get(value_col, "").strip()
                        weights[category][repo_col] = float(raw) if raw else 0.0
                    break

    with open(REPO_TARGET / "weights.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["category"] + ALL_WEIGHT_COLUMNS)
        for category, pop_weight in weights.items():
            writer.writerow(
                [category] + [pop_weight[col] for col in ALL_WEIGHT_COLUMNS]
            )
    print(f"  Wrote weights.csv ({len(weights)} data rows)")


def build_flat_score_table(cms_dir: Path, cms_filename: str, out_filename: str):
    rows = read_cms_csv(cms_dir, cms_filename)
    key_col = "Variable" if "Variable" in rows[0] else "Graft Duration"
    with open(REPO_TARGET / out_filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["key", "score"])
        for row in rows:
            writer.writerow([row[key_col].strip(), float(row["Score"])])
    print(f"  Wrote {out_filename} ({len(rows)} rows)")


def build_diag_map(cms_dir: Path):
    rows_by_code = defaultdict(list)
    for row in read_cms_csv(cms_dir, "ICD10_CC_mappings_ESRD_2026_v24.csv"):
        if cc_to_bare_number(row["CC"]) in RENAL_CCS:
            continue
        rows_by_code[row["ICD10"].strip()].append(row)

    out_lines = []
    skipped_no_default = 0
    for code, rows in rows_by_code.items():
        if code in NO_DEFAULT_CODES:
            skipped_no_default += 1
            continue
        if code in GENUINELY_CONDITIONAL_CODES:
            out_lines.append([code, GENUINELY_CONDITIONAL_CODES[code]])
            continue
        # Effectively unconditional: every row's CC is the code's outcome regardless of which
        # condition (if any) applies, since the conditions partition the age range exhaustively.
        ccs = sorted({cc_to_bare_number(r["CC"]) for r in rows})
        for i, cc in enumerate(ccs):
            flag = ["D"] if i > 0 else []
            out_lines.append([code, cc] + flag)

    out_lines.sort(key=lambda p: p[0])
    with open(REPO_TARGET / "diag_to_category_map.txt", "w") as f:
        for parts in out_lines:
            f.write("\t".join(parts) + "\n")
    print(
        f"  Wrote diag_to_category_map.txt ({len(out_lines)} lines, {len(rows_by_code)} codes, "
        f"{len(GENUINELY_CONDITIONAL_CODES)} handled via hardcoded edit methods, "
        f"{skipped_no_default} handled via add-only edit method with no static row)"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cms-package-dir", required=True, type=Path)
    args = parser.parse_args()

    print("Building hierarchy_definition.json / category_definition.json...")
    categories = build_definitions(args.cms_package_dir)

    print("Building weights.csv...")
    build_weights(args.cms_package_dir, categories)

    print(
        "Building graft_duration_scores.csv / institutional_graft_scores.csv / transplant_scores.csv..."
    )
    build_flat_score_table(
        args.cms_package_dir,
        "V24_Graft_Duration_Scores.csv",
        "graft_duration_scores.csv",
    )
    build_flat_score_table(
        args.cms_package_dir,
        "V24_CE_Institutional_Graft_Scores.csv",
        "institutional_graft_scores.csv",
    )
    build_flat_score_table(
        args.cms_package_dir, "V24_Transplant_Scores.csv", "transplant_scores.csv"
    )

    print("Building diag_to_category_map.txt...")
    build_diag_map(args.cms_package_dir)

    print("Done.")


if __name__ == "__main__":
    main()

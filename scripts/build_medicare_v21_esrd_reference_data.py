"""
Builds risk_adjustment_model's reference_data/medicare/v21_esrd/2026 files from scratch from
CMS's PY2026 ESRD V21 (legacy) Python DIY software package (ESRD_v21_2026_P_package_v3).

Same "cold start" approach as scripts/build_medicare_v24_esrd_reference_data.py -- see that
script's docstring for the general pattern. V21-specific differences:

- weights.csv has only 11 population columns, not V24's 14: 3 continuing-enrollee (DIAL,
  GRAFT_COMM, GRAFT_INST -- V21's base coefficients for these don't split by dual/aged status at
  all, unlike V24's GRAFT_COMM_*/GRAFT_INST) and 8 new-enrollee (4 NE_DIAL_* + 4 NE_GRAFT_*,
  using CMS's single MCAID/NMCAID dual axis rather than V24's FBD/ND_PBD split).
- No institutional_graft_scores.csv at all -- V21's graft-duration bonus uses one shared table
  (graft_duration_scores.csv, 4 rows: no dual axis, no PBD-flag terms) for GRAFT_COMM,
  GRAFT_INST, and NE_GRAFT alike. See v21_esrd.py.
- Renal categories (HCC134-141) are *not* excluded here, unlike V24 -- V21's own software doesn't
  zero renal CCs, and CHF_RENAL is a real, reachable interaction in V21's source. All 8 renal
  HCCs (V21 groups 3 more into the RENAL diagnosis category than V24's 5) are kept.
- Same 19 genuinely age/sex-conditional diagnosis codes as V22/V24 (D66/D67, 16 J-codes, F3481),
  confirmed by the same full age/gender grid evaluation -- but F3481's target differs: HCC58 here,
  not HCC59 (V24 ESRD) or HCC59 (V22). Still no unconditional default row for F3481, same as V24
  ESRD.

Usage:
    poetry run python scripts/build_medicare_v21_esrd_reference_data.py \\
        --year 2026 \\
        --cms-package-dir /path/to/extracted/ESRD_v21_2026_P_package_v3/software/ESRD_v21

Like build_medicare_v24_esrd_reference_data.py, this works unchanged for any subsequent year's
package too, despite the "cold start" framing -- re-verify the age/gender-grid analysis behind
GENUINELY_CONDITIONAL_CODES/NO_DEFAULT_CODES before reusing it for a new year, though.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

CE_COLUMNS_ORDER = ["DIAL", "GRAFT_COMM", "GRAFT_INST"]
NE_DIAL_PREFIX_MAP = {
    "NMCAID_NORIGDIS": "NE_DIAL_NMCAID_NORIGDIS",
    "MCAID_NORIGDIS": "NE_DIAL_MCAID_NORIGDIS",
    "NMCAID_ORIGDIS": "NE_DIAL_NMCAID_ORIGDIS",
    "MCAID_ORIGDIS": "NE_DIAL_MCAID_ORIGDIS",
}
NE_GRAFT_PREFIX_MAP = {
    "NMCAID_NORIGDIS_G": "NE_GRAFT_NMCAID_NORIGDIS",
    "MCAID_NORIGDIS_G": "NE_GRAFT_MCAID_NORIGDIS",
    "NMCAID_ORIGDIS_G": "NE_GRAFT_NMCAID_ORIGDIS",
    "MCAID_ORIGDIS_G": "NE_GRAFT_MCAID_ORIGDIS",
}
NE_COLUMNS_ORDER = list(NE_DIAL_PREFIX_MAP.values()) + list(
    NE_GRAFT_PREFIX_MAP.values()
)
ALL_WEIGHT_COLUMNS = CE_COLUMNS_ORDER + NE_COLUMNS_ORDER

# All 27 scored V21 disease interactions -- unlike V24, none are omitted, since renal categories
# are real and reachable in V21 (see module docstring).
DISEASE_INTERACTIONS = [
    "SEPSIS_CARD_RESP_FAIL",
    "CANCER_IMMUNE",
    "DIABETES_CHF",
    "CHF_COPD",
    "CHF_RENAL",
    "COPD_CARD_RESP_FAIL",
    "SEPSIS_PRESSURE_ULCER",
    "SEPSIS_ARTIF_OPENINGS",
    "ART_OPENINGS_PRESSURE_ULCER",
    "COPD_ASP_SPEC_BACT_PNEUM",
    "ASP_SPEC_BACT_PNEUM_PRES_ULC",
    "SEPSIS_ASP_SPEC_BACT_PNEUM",
    "SCHIZOPHRENIA_COPD",
    "SCHIZOPHRENIA_CHF",
    "SCHIZOPHRENIA_SEIZURES",
    "NONAGED_HCC6",
    "NONAGED_HCC34",
    "NONAGED_HCC46",
    "NONAGED_HCC54",
    "NONAGED_HCC55",
    "NONAGED_HCC110",
    "NONAGED_HCC176",
    "NONAGED_HCC85",
    "NONAGED_PRESSURE_ULCER",
    "NONAGED_HCC161",
    "NONAGED_HCC39",
    "NONAGED_HCC77",
]
DEMOGRAPHIC_INTERACTIONS = [
    "OriginallyDisabled_Female",
    "OriginallyDisabled_Male",
    "Originally_ESRD_Female",
    "Originally_ESRD_Male",
    "MCAID",
    "MCAID_Female_Aged",
    "MCAID_Female_NonAged",
    "MCAID_Male_Aged",
    "MCAID_Male_NonAged",
]

# code -> base static CC row (v21_esrd.py's edit methods supply the override for the other
# branch). Same evaluation approach as V24 ESRD/V22 -- see module docstring.
GENUINELY_CONDITIONAL_CODES = {
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
    GENUINELY_CONDITIONAL_CODES[_code] = "111"

# F3481 has no unconditional default row (same shape as ESRD V24) -- maps to HCC58 only within
# age 6-18, handled entirely by _age_sex_edit_3.
NO_DEFAULT_CODES = {"F3481"}


def read_cms_csv(cms_dir: Path, name: str):
    with open(
        cms_dir / "data/input/internal" / name, newline="", encoding="utf-8-sig"
    ) as f:
        return list(csv.DictReader(f))


def cc_to_bare_number(cc: str) -> str:
    return str(int(float(cc)))


def build_definitions(cms_dir: Path, repo_target: Path):
    hierarchy_rows = read_cms_csv(cms_dir, "V21_HCC_Hierarchies.csv")
    hierarchy = {}
    disease_hccs = set()
    for row in hierarchy_rows:
        hcc = row["HCC"].strip()
        disease_hccs.add(hcc)
        secondaries = [
            row[f"SecondaryHCC_{i}"].strip()
            for i in range(1, 8)
            if row.get(f"SecondaryHCC_{i}", "").strip()
        ]
        if secondaries:
            hierarchy[hcc] = {"descr": None, "remove_code": secondaries}

    ce_rows = read_cms_csv(cms_dir, "V21_CE_Relative_Factors.csv")
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
        ("V21_NE_Dialysis_Relative_Factors.csv", NE_DIAL_PREFIX_MAP),
        ("V21_NE_Graft_Relative_Factors.csv", NE_GRAFT_PREFIX_MAP),
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

    repo_target.mkdir(parents=True, exist_ok=True)
    with open(repo_target / "hierarchy_definition.json", "w") as f:
        json.dump(hierarchy, f)
    with open(repo_target / "category_definition.json", "w") as f:
        json.dump(categories, f)
    print(
        f"  Wrote hierarchy_definition.json ({len(hierarchy)} entries), "
        f"category_definition.json ({len(categories)} entries)"
    )
    return categories


def build_weights(cms_dir: Path, categories: dict, repo_target: Path):
    weights = defaultdict(lambda: {col: 0.0 for col in ALL_WEIGHT_COLUMNS})

    for row in read_cms_csv(cms_dir, "V21_CE_Relative_Factors.csv"):
        category = row["Variable"].strip()
        if category not in categories:
            continue  # ORIGDIS: unscored placeholder, same pattern as V24
        for repo_col in CE_COLUMNS_ORDER:
            raw = row.get(repo_col, "").strip()
            weights[category][repo_col] = float(raw) if raw else 0.0

    for filename, prefix_map in (
        ("V21_NE_Dialysis_Relative_Factors.csv", NE_DIAL_PREFIX_MAP),
        ("V21_NE_Graft_Relative_Factors.csv", NE_GRAFT_PREFIX_MAP),
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

    with open(repo_target / "weights.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["category"] + ALL_WEIGHT_COLUMNS)
        for category, pop_weight in weights.items():
            writer.writerow(
                [category] + [pop_weight[col] for col in ALL_WEIGHT_COLUMNS]
            )
    print(f"  Wrote weights.csv ({len(weights)} data rows)")


def build_flat_score_table(
    cms_dir: Path, cms_filename: str, out_filename: str, repo_target: Path
):
    rows = read_cms_csv(cms_dir, cms_filename)
    key_col = "Variable" if "Variable" in rows[0] else "Graft Duration"
    with open(repo_target / out_filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["key", "score"])
        for row in rows:
            writer.writerow([row[key_col].strip(), float(row["Score"])])
    print(f"  Wrote {out_filename} ({len(rows)} rows)")


def read_icd10_mappings(cms_dir: Path, year: int):
    # Some package vintages (e.g. 2027 "initial" packages) suffix this filename with "_initial".
    base_name = f"ICD10_CC_mappings_ESRD_{year}_v21"
    for candidate in (f"{base_name}.csv", f"{base_name}_initial.csv"):
        path = cms_dir / "data/input/internal" / candidate
        if path.exists():
            return read_cms_csv(cms_dir, candidate)
    raise FileNotFoundError(
        f"Could not find an ICD10_CC_mappings file for year {year} under {cms_dir}"
    )


def build_diag_map(cms_dir: Path, year: int, repo_target: Path):
    rows_by_code = defaultdict(list)
    for row in read_icd10_mappings(cms_dir, year):
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
        ccs = sorted({cc_to_bare_number(r["CC"]) for r in rows})
        for i, cc in enumerate(ccs):
            flag = ["D"] if i > 0 else []
            out_lines.append([code, cc] + flag)

    out_lines.sort(key=lambda p: p[0])
    with open(repo_target / "diag_to_category_map.txt", "w") as f:
        for parts in out_lines:
            f.write("\t".join(parts) + "\n")
    print(
        f"  Wrote diag_to_category_map.txt ({len(out_lines)} lines, {len(rows_by_code)} codes, "
        f"{len(GENUINELY_CONDITIONAL_CODES)} handled via hardcoded edit methods, "
        f"{skipped_no_default} handled via add-only edit method with no static row)"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--cms-package-dir", required=True, type=Path)
    args = parser.parse_args()

    repo_target = (
        REPO_ROOT
        / "src/risk_adjustment_model/reference_data/medicare/v21_esrd"
        / str(args.year)
    )

    print("Building hierarchy_definition.json / category_definition.json...")
    categories = build_definitions(args.cms_package_dir, repo_target)

    print("Building weights.csv...")
    build_weights(args.cms_package_dir, categories, repo_target)

    print("Building graft_duration_scores.csv / transplant_scores.csv...")
    build_flat_score_table(
        args.cms_package_dir,
        "V21_Graft_Duration_Scores.csv",
        "graft_duration_scores.csv",
        repo_target,
    )
    build_flat_score_table(
        args.cms_package_dir,
        "V21_Transplant_Scores.csv",
        "transplant_scores.csv",
        repo_target,
    )

    print("Building diag_to_category_map.txt...")
    build_diag_map(args.cms_package_dir, args.year, repo_target)

    print("Done.")


if __name__ == "__main__":
    main()

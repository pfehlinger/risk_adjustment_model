"""
Regenerates risk_adjustment_model's reference_data/medicare/<version>/<target-year> files from a
CMS CMS-HCC Python DIY software package (e.g. CMS_HCC_v28_2026_T_package_v3 for PY2026).

This is the Medicare analog of scripts/build_v08_reference_data.py -- same overall approach
(reshape CMS's source CSVs into this repo's reference_data file formats, verify-and-carry-forward
hierarchy/category structure that hasn't changed, stability-check the diagnosis map against the
prior year rather than blindly regenerating it), adapted for Medicare's file shapes:

- Medicare's ICD10-to-category crosswalk has no "valid_ICD10_<year>" fiscal-year-validity columns
  the way Commercial's does, and CC numbers are plain integers (possibly written with a trailing
  ".0"), not Commercial's decimal-suffixed category numbers.
- Medicare has two separate coefficient files per version/year -- Continuing Enrollee
  (V28_CE_Relative_Factors.csv: demographic + disease + disease_interaction + disease_count +
  demographic_interaction categories, one row per category, one column per CE population) and New
  Enrollee (V28_NE_Relative_Factors.csv: demographic-only categories, but the sub-population is
  embedded in the row's Variable name rather than in separate columns) -- both get reshaped into
  one flat weights.csv matching this repo's existing category,CNA,CND,CFA,CFD,CPA,CPD,INS,
  NE_NMCAID_NORIGDIS,NE_MCAID_NORIGDIS,NE_NMCAID_ORIGDIS,NE_MCAID_ORIGDIS convention.
- Diagnosis-category-grouping (V28_Diagnosis_Categories.csv) and disease-interaction
  (V28_Interactions.csv) definitions are verified against the prior year rather than parsed fresh,
  since this repo's `_determine_disease_interactions` hardcodes the actual interaction logic in
  Python (v28.py) -- these files exist here only to confirm the classification hasn't drifted.

Usage:
    poetry run python scripts/build_medicare_reference_data.py \\
        --version v28 --prior-year 2024 --target-year 2026 \\
        --cms-package-dir /path/to/extracted/CMS_HCC_v28_2026_T_package_v3/software/CMS_HCC_v28

Supports V22 and V28 -- both ship the same clean-CSV crosswalk/coefficient shape from CMS. V22 has
no prior-year reference data of its own to diff against for its first supported year (2026); that
initial build was done by scripts/build_medicare_v22_reference_data.py (a one-off "cold start"
script, see its docstring), after which this script works for V22 like any other version/year.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEDICARE_REFERENCE_DATA = (
    REPO_ROOT / "src/risk_adjustment_model/reference_data/medicare"
)

# CMS's CE population columns -> this repo's weights.csv column names (order CMS uses is
# NA/PBA/FBA/ND/PBD/FBD/INSTITUTIONAL; repo groups Aged/Disabled together as CNA/CPA/CFA/CND/CPD/CFD/INS).
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
# CMS's NE row-name prefixes -> this repo's NE_* weights.csv column names.
NE_PREFIX_MAP = {
    "NMCAID_NORIGDIS": "NE_NMCAID_NORIGDIS",
    "MCAID_NORIGDIS": "NE_MCAID_NORIGDIS",
    "NMCAID_ORIGDIS": "NE_NMCAID_ORIGDIS",
    "MCAID_ORIGDIS": "NE_MCAID_ORIGDIS",
}
ALL_WEIGHT_COLUMNS = CE_COLUMNS_ORDER + NE_COLUMNS_ORDER


@dataclass
class Config:
    version: str
    prior_year: int
    target_year: int
    repo_prior: Path
    repo_target: Path
    cms_package_dir: Path


def read_cms_csv(cfg: Config, name: str):
    with open(
        cfg.cms_package_dir / "data/input/internal" / name,
        newline="",
        encoding="utf-8-sig",
    ) as f:
        return list(csv.DictReader(f))


def cc_to_bare_number(cc: str) -> str:
    # CMS writes CC numbers as e.g. "92.0"; repo's diag_to_category_map.txt wants bare "92".
    return str(int(float(cc)))


# ---------------------------------------------------------------------------
# hierarchy / category definitions -- verify unchanged, carry forward
# ---------------------------------------------------------------------------


def verify_and_carry_forward_definitions(cfg: Config):
    cms_hierarchy_rows = read_cms_csv(cfg, f"{cfg.version.upper()}_HCC_Hierarchies.csv")
    cms_hierarchy_map = {}
    for row in cms_hierarchy_rows:
        hcc = row["HCC"].strip()
        secondaries = [
            row[f"SecondaryHCC_{i}"].strip()
            for i in range(1, 7)
            if row.get(f"SecondaryHCC_{i}", "").strip()
        ]
        if secondaries:
            cms_hierarchy_map[hcc] = secondaries

    with open(cfg.repo_prior / "hierarchy_definition.json") as f:
        repo_hierarchy = json.load(f)

    mismatches = []
    for hcc, secondaries in cms_hierarchy_map.items():
        repo_entry = repo_hierarchy.get(hcc)
        if not repo_entry or set(repo_entry["remove_code"]) != set(secondaries):
            mismatches.append((hcc, secondaries, repo_entry))

    if mismatches:
        print(f"  WARNING: {len(mismatches)} HCC hierarchy mismatches vs CMS source:")
        for hcc, secondaries, repo_entry in mismatches[:10]:
            print(f"    {hcc}: CMS={secondaries} repo={repo_entry}")
    else:
        print(
            f"  hierarchy_definition.json: verified consistent with CMS {cfg.version.upper()}_HCC_Hierarchies.csv"
        )

    with open(cfg.repo_prior / "category_definition.json") as f:
        repo_categories = json.load(f)

    ce_rows = read_cms_csv(cfg, f"{cfg.version.upper()}_CE_Relative_Factors.csv")
    cms_ce_vars = {row["Variable"].strip() for row in ce_rows}
    repo_ce_vars = {
        k
        for k, v in repo_categories.items()
        if v["type"] != "demographic" or not k.startswith("NE")
    }
    # ORIGDIS is a CMS coefficient row that's blank/zero for every population column (verified: no
    # real effect on any score) -- this repo has never modeled it, and that's intentional, not a gap.
    cms_ce_vars_scored = cms_ce_vars - {"ORIGDIS"}
    missing_from_repo = cms_ce_vars_scored - repo_ce_vars
    extra_in_repo = repo_ce_vars - cms_ce_vars_scored
    if missing_from_repo or extra_in_repo:
        print("  WARNING: CE variable set differs from category_definition.json:")
        if missing_from_repo:
            print(f"    In CMS source, not in repo: {sorted(missing_from_repo)}")
        if extra_in_repo:
            print(f"    In repo, not in CMS source: {sorted(extra_in_repo)}")
    else:
        print(
            f"  category_definition.json: CE variable set verified consistent with CMS {cfg.version.upper()}_CE_Relative_Factors.csv"
        )

    for filename in ["hierarchy_definition.json", "category_definition.json"]:
        with open(cfg.repo_prior / filename) as src, open(
            cfg.repo_target / filename, "w"
        ) as dst:
            dst.write(src.read())
    print(
        f"  Carried forward hierarchy_definition.json, category_definition.json from {cfg.prior_year}"
    )


# ---------------------------------------------------------------------------
# weights.csv -- reshape CE + NE relative factors into one flat file
# ---------------------------------------------------------------------------


def build_weights(cfg: Config):
    weights = {}  # category -> {column: value}

    ce_rows = read_cms_csv(cfg, f"{cfg.version.upper()}_CE_Relative_Factors.csv")
    for row in ce_rows:
        category = row["Variable"].strip()
        if category == "ORIGDIS":
            continue
        pop_weight = {col: 0.0 for col in ALL_WEIGHT_COLUMNS}
        for cms_col, repo_col in CE_COLUMN_MAP.items():
            raw = row.get(cms_col, "").strip()
            pop_weight[repo_col] = float(raw) if raw else 0.0
        weights[category] = pop_weight

    ne_rows = read_cms_csv(cfg, f"{cfg.version.upper()}_NE_Relative_Factors.csv")
    # CMS has renamed this column between package releases ("NE" in the 2026 midyear-final
    # package, "NEW_ENROLLEE" in the 2027 initial package) -- try known names in order.
    ne_value_col = next(
        (col for col in ("NE", "NEW_ENROLLEE") if col in ne_rows[0]), None
    )
    if ne_value_col is None:
        raise SystemExit(
            f"Could not find the NE coefficient column in {cfg.version.upper()}_NE_Relative_Factors.csv "
            f"(looked for 'NE'/'NEW_ENROLLEE'; found columns: {list(ne_rows[0].keys())})"
        )
    unmatched_ne_prefixes = set()
    for row in ne_rows:
        variable = row["Variable"].strip()
        matched_prefix = None
        for cms_prefix in NE_PREFIX_MAP:
            if variable.startswith(cms_prefix + "_"):
                matched_prefix = cms_prefix
                break
        if matched_prefix is None:
            unmatched_ne_prefixes.add(variable)
            continue
        # e.g. "NMCAID_NORIGDIS_NEF0_34" -> category "NEF0_34"
        category = variable[len(matched_prefix) + 1 :]
        repo_col = NE_PREFIX_MAP[matched_prefix]
        if category not in weights:
            weights[category] = {col: 0.0 for col in ALL_WEIGHT_COLUMNS}
        weights[category][repo_col] = float(row[ne_value_col])

    if unmatched_ne_prefixes:
        print(
            f"  WARNING: {len(unmatched_ne_prefixes)} NE rows didn't match a known prefix: {sorted(unmatched_ne_prefixes)[:10]}"
        )

    with open(cfg.repo_target / "weights.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["category"] + ALL_WEIGHT_COLUMNS)
        for category, pop_weight in weights.items():
            writer.writerow(
                [category] + [pop_weight[col] for col in ALL_WEIGHT_COLUMNS]
            )
    print(f"  Wrote weights.csv ({len(weights)} data rows)")


# ---------------------------------------------------------------------------
# diag_to_category_map.txt -- stability-check against prior year (same algorithm as
# build_v08_reference_data.py's build_diag_map, adapted for Medicare's simpler crosswalk shape:
# no valid_ICD10_<year> column, CC numbers are plain (possibly "N.0"), category_prefix is "HCC")
# ---------------------------------------------------------------------------


def load_repo_diag_lines(path):
    lines_by_code = defaultdict(list)
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            code = parts[0].strip()
            lines_by_code[code].append(parts)
    return lines_by_code


def edit_method_explained_ccs(model, code):
    """
    Union of every category any of this version's `_age_sex_edit_N` methods can return for this
    diagnosis code, swept across a broad age/gender range -- same purpose as the Commercial
    build script's helper of the same name: recognizes when a CMS CC-number-set delta is already
    fully covered by existing Python edit logic.
    """
    explained = set()
    for age in range(0, 101):
        for gender in ("M", "F"):
            result = model._age_sex_edits(gender, age, code)
            if result:
                explained.update(c.replace(model.category_prefix, "") for c in result)
    return explained


def build_diag_map(cfg: Config, model_class):
    model = model_class(year=cfg.prior_year)

    repo_lines = load_repo_diag_lines(cfg.repo_prior / "diag_to_category_map.txt")

    # CMS suffixes this filename with "_initial" on initial (vs. midyear-final) package releases,
    # e.g. "ICD10_CC_mappings_CMS_HCC_2027_v28_initial.csv" -- try both.
    base_name = f"ICD10_CC_mappings_CMS_HCC_{cfg.target_year}_{cfg.version}"
    candidates = [f"{base_name}.csv", f"{base_name}_initial.csv"]
    for candidate in candidates:
        if (cfg.cms_package_dir / "data/input/internal" / candidate).exists():
            cms_rows = read_cms_csv(cfg, candidate)
            break
    else:
        raise SystemExit(f"Could not find ICD10 mapping file; tried {candidates}")
    cms_rows_by_code = defaultdict(list)
    for row in cms_rows:
        cms_rows_by_code[row["ICD10"].strip()].append(row)

    print(f"  CMS {cfg.target_year} codes: {len(cms_rows_by_code)}")
    print(f"  Repo {cfg.prior_year} codes: {len(repo_lines)}")

    repo_cc_sets = {
        code: {parts[1] for parts in lines} for code, lines in repo_lines.items()
    }
    cms_cc_sets = {
        code: {cc_to_bare_number(row["CC"]) for row in rows}
        for code, rows in cms_rows_by_code.items()
    }

    all_codes = set(repo_lines.keys()) | set(cms_rows_by_code.keys())

    stable_codes, changed_codes, new_codes, retired_codes = [], [], [], []
    for code in all_codes:
        in_prior = code in repo_lines
        in_target = code in cms_rows_by_code
        if in_prior and not in_target:
            retired_codes.append(code)
            continue
        if not in_prior and in_target:
            new_codes.append(code)
            continue
        if repo_cc_sets[code] == cms_cc_sets[code]:
            stable_codes.append(code)
            continue
        delta = cms_cc_sets[code] - repo_cc_sets[code]
        if delta and delta <= edit_method_explained_ccs(model, code):
            stable_codes.append(code)
        else:
            changed_codes.append(code)

    print(
        f"  Stable (same target CC-number set as {cfg.prior_year}): {len(stable_codes)}"
    )
    print(f"  New codes (not in {cfg.prior_year}): {len(new_codes)}")
    print(
        f"  Retired codes (in {cfg.prior_year}, absent from {cfg.target_year}): {len(retired_codes)}"
    )
    print(f"  Changed codes (flagged for review): {len(changed_codes)}")

    out_lines = []
    review_rows = []

    for code in sorted(stable_codes) + sorted(changed_codes):
        for parts in repo_lines[code]:
            out_lines.append(parts)
        if code in changed_codes:
            review_rows.append(
                {
                    "code": code,
                    "status": "CHANGED",
                    "action_taken": f"carried forward existing {cfg.prior_year} row(s) as-is",
                    "cms_ccs": ";".join(sorted(cms_cc_sets[code])),
                }
            )

    for code in sorted(new_codes):
        rows = cms_rows_by_code[code]
        ccs = sorted({cc_to_bare_number(r["CC"]) for r in rows})
        for i, cc in enumerate(ccs):
            flag = ["D"] if i > 0 else []
            out_lines.append([code, cc] + flag)
        review_rows.append(
            {
                "code": code,
                "status": "NEW",
                "action_taken": f"emitted CC(s): {';'.join(ccs)}",
                "cms_ccs": ";".join(ccs),
            }
        )

    for code in sorted(retired_codes):
        review_rows.append(
            {
                "code": code,
                "status": "RETIRED",
                "action_taken": f"dropped from {cfg.target_year} file",
                "cms_ccs": "",
            }
        )

    out_lines.sort(key=lambda p: p[0])
    with open(cfg.repo_target / "diag_to_category_map.txt", "w") as f:
        for parts in out_lines:
            f.write("\t".join(parts) + "\n")

    report_dir = REPO_ROOT / "scripts/output"
    report_dir.mkdir(exist_ok=True)
    report_path = (
        report_dir / f"medicare_{cfg.version}_diag_map_{cfg.target_year}_review.csv"
    )
    with open(report_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["code", "status", "action_taken", "cms_ccs"]
        )
        writer.writeheader()
        for row in review_rows:
            writer.writerow(row)

    print(
        f"  Wrote {cfg.repo_target / 'diag_to_category_map.txt'} ({len(out_lines)} lines)"
    )
    print(f"  Wrote {report_path} ({len(review_rows)} rows needing review)")


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        required=True,
        choices=["v22", "v28"],
        help="Medicare model version.",
    )
    parser.add_argument("--prior-year", type=int, required=True)
    parser.add_argument("--target-year", type=int, required=True)
    parser.add_argument(
        "--cms-package-dir",
        required=True,
        type=Path,
        help="Path to the extracted CMS package's software/<Model> directory "
        "(e.g. .../CMS_HCC_v28_2026_T_package_v3/software/CMS_HCC_v28).",
    )
    args = parser.parse_args()

    repo_prior = MEDICARE_REFERENCE_DATA / args.version / str(args.prior_year)
    repo_target = MEDICARE_REFERENCE_DATA / args.version / str(args.target_year)
    if not repo_prior.exists():
        raise SystemExit(f"Prior-year reference data directory not found: {repo_prior}")
    if not args.cms_package_dir.exists():
        raise SystemExit(f"CMS package directory not found: {args.cms_package_dir}")
    repo_target.mkdir(parents=True, exist_ok=True)

    return Config(
        version=args.version,
        prior_year=args.prior_year,
        target_year=args.target_year,
        repo_prior=repo_prior,
        repo_target=repo_target,
        cms_package_dir=args.cms_package_dir,
    )


def main():
    cfg = parse_args()
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from risk_adjustment_model import MedicareModelV22, MedicareModelV28

    model_class = {"v22": MedicareModelV22, "v28": MedicareModelV28}[cfg.version]

    print("Verifying hierarchy / category definitions...")
    verify_and_carry_forward_definitions(cfg)

    print("Building weights.csv...")
    build_weights(cfg)

    print("Building diag_to_category_map.txt...")
    build_diag_map(cfg, model_class)

    print("Done.")


if __name__ == "__main__":
    main()

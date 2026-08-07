"""
Regenerates risk_adjustment_model's reference_data/commercial/v08/<target-year> files from a
CMS HHS-HCC DIY software package (e.g. HHS_HCC_software_package_V0826.141.E1_v2 for BY2026).

This automates the mechanical part of a yearly refresh: reshaping CMS's source CSVs into this
repo's reference_data file formats, carrying forward hierarchy/group/category structure that
hasn't changed, and producing a small review report for anything that needs a human look. It
does NOT automate: adding a --target-year entry to _get_csr_adjuster or
reference_files_version_dict (commercial_model.py / v08.py), reconciling the 16 hardcoded
_age_sex_edit_N methods or severe/transplant/RXC-interaction lists against CMS's tables (the
diag-map comparison below flags *what* changed; deciding whether v08.py needs a code change is
still a human judgment call), or implementing support for a wholly new scoring component if CMS
introduces one (ACF was exactly this for BY2026 -- this script only handles regenerating its
reference data, not adding it to v08.py's score() pipeline for the first time).

Approach for diag_to_category_map.txt (the highest-risk transform, since this repo encodes some
ICD-10 -> category logic as static file rows and some as hardcoded Python age/sex edit methods
in v08.py, and those methods are a separate business-rule layer that doesn't map 1:1 to the CMS
CSV's AGE_EDIT_CONDITION/SEX_EDIT_CONDITION columns -- see the comment in build_diag_map for
why): for every diagnosis code present in both years, compare the raw set of target CC numbers
the CSV states for that code against what the prior year's static file already encodes. An
unchanged CC-number set means the code's mapping is stable and the existing prior-year file
row(s) are carried forward as-is. A changed set, or a code that's new/retired, is flagged in a
report for manual review rather than guessed -- wrong diagnosis-to-HCC mappings directly affect
risk scores.

Usage:
    poetry run python scripts/build_v08_reference_data.py --prior-year 2025 --target-year 2026

The CMS source package location is resolved via the CMS_PACKAGE_DIR env var if set, otherwise
by looking for a sibling directory of this repo matching "HHS_HCC_software_package*" (e.g.
../HHS_HCC_software_package_V0826.141.E1_v2).
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cms_package import find_cms_root  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
CMS_ROOT = find_cms_root()
CMS_DATA = CMS_ROOT / "software/HHS_HCC/data/input/internal"
V08_REFERENCE_DATA = (
    REPO_ROOT / "src/risk_adjustment_model/reference_data/commercial/v08"
)
REPORT_DIR = REPO_ROOT / "scripts/output"


@dataclass
class Config:
    prior_year: int
    target_year: int
    repo_prior: Path
    repo_target: Path


def read_cms_csv(name):
    with open(CMS_DATA / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Prior-year static map (preserving row order + trailing flags, e.g. "D")
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


def build_cms_default_lines(rows):
    """
    Best-effort static-file row(s) for a code that's new or whose outcome changed:
    CCs with at least one fully-unconditional row (no MCE/age/sex condition at all)
    are treated as the "base" mapping (mirrors how existing unconditional / dual-mapped
    codes like B252 are encoded). Conditional-only CCs are omitted here -- they need a
    Python edit method and are called out in the report.
    """
    unconditional_ccs = []
    conditional_only_ccs = []
    seen_cc = {}
    for row in rows:
        cc = row["CC"]
        is_unconditional = not (
            row["MCE_AGE_CONDITION"]
            or row["AGE_EDIT_CONDITION"]
            or row["SEX_EDIT_CONDITION"]
        )
        seen_cc.setdefault(cc, False)
        if is_unconditional:
            seen_cc[cc] = True
    for cc, unconditional in seen_cc.items():
        (unconditional_ccs if unconditional else conditional_only_ccs).append(cc)
    return unconditional_ccs, conditional_only_ccs


# ---------------------------------------------------------------------------
# Main diag map builder
# ---------------------------------------------------------------------------


def category_to_cc(category: str) -> str:
    # "HHS_HCC019" -> "19", "HHS_HCC035_1" -> "35.1"
    raw = category.replace("HHS_HCC", "")
    if "_" in raw:
        whole, dec = raw.split("_", 1)
        return f"{int(whole)}.{dec}"
    return str(int(raw))


def edit_method_explained_ccs(model, code):
    """
    Union of every category any of the 16 `_age_sex_edit_N` methods can return for this
    diagnosis code, swept across a broad age/gender range. Used to recognize when a CMS
    CC-number-set delta is already fully covered by existing Python edit logic (CMS's raw
    per-row table enumerates every age branch explicitly; the repo's static file stores
    only the "default" branch and relies on the matching edit method for the rest).
    """
    explained = set()
    for age in range(0, 101):
        for gender in ("M", "F"):
            result = model._age_sex_edits(gender, age, code)
            if result:
                explained.update(category_to_cc(c) for c in result if c != "NA")
    return explained


def build_diag_map(cfg: Config):
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from risk_adjustment_model import CommercialModelV08

    model = CommercialModelV08(year=cfg.prior_year)

    repo_lines = load_repo_diag_lines(cfg.repo_prior / "diag_to_category_map.txt")

    cms_rows = read_cms_csv(f"ICD10_HHS_CC_mappings_{cfg.target_year}.csv")
    valid_col = f"valid_ICD10_{cfg.target_year}"
    cms_rows_by_code = defaultdict(list)
    for row in cms_rows:
        if row.get(valid_col, "").strip().upper() != "TRUE":
            continue
        cms_rows_by_code[row["ICD10"].strip()].append(row)

    print(f"  CMS {cfg.target_year} codes: {len(cms_rows_by_code)}")
    print(f"  Repo {cfg.prior_year} codes: {len(repo_lines)}")

    # NOTE: the 16 hardcoded `_age_sex_edit_N` methods in v08.py are a separate business-rule
    # layer carried over from CMS's own historical DIY "edit files" (ED1-ED16) -- they do NOT
    # correspond 1:1 to this CSV's AGE_EDIT_CONDITION/SEX_EDIT_CONDITION columns (e.g. F201 has
    # a single unconditional CMS row yet _age_sex_edit_5 overrides it for age<2 -- a rule this
    # CSV has no way to confirm or refute). So rather than trying to re-derive full conditional
    # *behavior* from these columns (which produced false positives during BY2026 development),
    # the comparison here is scoped to what the CSV *does* authoritatively state: the raw set of
    # target CC numbers per code. A changed CC-number set is a real, actionable signal;
    # edit-method semantics are left to manual review against CMS's edit-file docs.
    repo_cc_sets = {
        code: {parts[1] for parts in lines} for code, lines in repo_lines.items()
    }
    cms_cc_sets = {
        code: {row["CC"] for row in rows} for code, rows in cms_rows_by_code.items()
    }

    all_codes = set(repo_lines.keys()) | set(cms_rows_by_code.keys())

    stable_codes = []
    changed_codes = []
    new_codes = []
    retired_codes = []

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
        # Delta might be fully explained by an existing _age_sex_edit_N method (CMS's raw
        # table enumerates every age/sex branch; repo's static file stores only the default
        # branch). If every CC in the delta is something an existing edit method already
        # returns for this code, treat it as stable rather than flag it.
        delta = cms_cc_sets[code] - repo_cc_sets[code]
        if delta and delta <= edit_method_explained_ccs(model, code):
            stable_codes.append(code)
        else:
            changed_codes.append(code)

    print(
        f"  Stable (same target CC-number set as {cfg.prior_year}, carried forward as-is): {len(stable_codes)}"
    )
    print(f"  New codes (not in {cfg.prior_year}): {len(new_codes)}")
    print(
        f"  Retired codes (in {cfg.prior_year}, absent from {cfg.target_year}): {len(retired_codes)}"
    )
    print(
        f"  Changed codes (target CC-number set differs -- flagged for review): {len(changed_codes)}"
    )

    # --- Emit diag_to_category_map.txt ---
    # Codes present in both years (stable AND changed) always carry forward the exact
    # prior-year line(s) -- that split between "static default row" and "python edit override"
    # was hand-verified against CMS SAS/software conventions previously and there is no
    # reliable way to re-derive which branch is the "default" purely from the CMS condition
    # columns (e.g. E700's default is the *pediatric* branch with an adult override to the
    # "NA" sentinel, while C9100's default is the *adult* branch with a pediatric override --
    # there's no consistent rule). Emitting nothing for a changed code is worse than carrying
    # the proven prior-year row forward, so "changed" only affects the review report here, not
    # file content.
    out_lines = []
    review_rows = []

    for code in sorted(stable_codes) + sorted(changed_codes):
        for parts in repo_lines[code]:
            out_lines.append(parts)

    for code in sorted(new_codes):
        rows = cms_rows_by_code[code]
        unconditional_ccs, conditional_only_ccs = build_cms_default_lines(rows)
        for i, cc in enumerate(unconditional_ccs):
            flag = ["D"] if i > 0 else []
            out_lines.append([code, cc] + flag)
        review_rows.append(
            {
                "code": code,
                "status": "NEW",
                "action_taken": (
                    f"emitted unconditional CC(s): {';'.join(unconditional_ccs)}"
                    if unconditional_ccs
                    else "NOTHING EMITTED -- no unconditional CC found, needs manual base-row decision"
                ),
                "cms_rows": " | ".join(
                    f"CC{r['CC']} MCE=[{r['MCE_AGE_CONDITION']}] AGE=[{r['AGE_EDIT_CONDITION']}] SEX=[{r['SEX_EDIT_CONDITION']}]"
                    for r in rows
                ),
            }
        )

    for code in sorted(changed_codes):
        rows = cms_rows_by_code[code]
        review_rows.append(
            {
                "code": code,
                "status": "CHANGED",
                "action_taken": (
                    f"carried forward existing {cfg.prior_year} row(s) as-is: "
                    f"{'; '.join(chr(9).join(p) for p in repo_lines[code])}"
                ),
                "cms_rows": " | ".join(
                    f"CC{r['CC']} MCE=[{r['MCE_AGE_CONDITION']}] AGE=[{r['AGE_EDIT_CONDITION']}] SEX=[{r['SEX_EDIT_CONDITION']}]"
                    for r in rows
                ),
            }
        )

    for code in sorted(retired_codes):
        review_rows.append(
            {
                "code": code,
                "status": "RETIRED",
                "action_taken": f"dropped from {cfg.target_year} file (no row emitted)",
                "cms_rows": f"(absent from CMS {cfg.target_year} source / not {valid_col})",
            }
        )

    # sort output for determinism, matching original file's rough code-sorted layout
    out_lines.sort(key=lambda p: p[0])

    with open(cfg.repo_target / "diag_to_category_map.txt", "w") as f:
        for parts in out_lines:
            f.write("\t".join(parts) + "\n")

    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / f"diag_map_{cfg.target_year}_review.csv"
    with open(report_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["code", "status", "action_taken", "cms_rows"],
        )
        writer.writeheader()
        for row in review_rows:
            writer.writerow(row)

    print(
        f"  Wrote {cfg.repo_target / 'diag_to_category_map.txt'} ({len(out_lines)} lines)"
    )
    print(f"  Wrote {report_path} ({len(review_rows)} rows needing review)")


# ---------------------------------------------------------------------------
# ndc / proc maps -- straightforward reshape
# ---------------------------------------------------------------------------


def build_ndc_map(cfg: Config):
    rows = read_cms_csv("rxc_NDC_mappings.csv")
    out_lines = []
    for row in rows:
        ndc = row["NDC"].strip()
        rxc = row["RXC"].strip()
        if not ndc or not rxc:
            continue
        out_lines.append(f"{ndc}\t{rxc}")
    with open(cfg.repo_target / "ndc_to_category_map.txt", "w") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"  Wrote ndc_to_category_map.txt ({len(out_lines)} lines)")


def build_proc_map(cfg: Config):
    rows = read_cms_csv("rxc_HCPCS_mappings.csv")
    out_lines = []
    for row in rows:
        hcpcs = row["HCPCS"].strip()
        rxc = row["RXC"].strip()
        if not hcpcs or not rxc:
            continue
        out_lines.append(f"{hcpcs}\t{rxc}")
    with open(cfg.repo_target / "proc_to_category_map.txt", "w") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"  Wrote proc_to_category_map.txt ({len(out_lines)} lines)")


# ---------------------------------------------------------------------------
# acf_to_category_map.txt -- Affiliated Cost Factors (introduced BY2026)
# ---------------------------------------------------------------------------


# v08.py's `_determine_acf` hardcodes these per-category rules rather than reading them from
# the reference file (see that method's docstring) -- verified against every row of CMS's
# BY2026 acf_NDC_mappings.csv/acf_HCPCS_mappings.csv that (age_condition, exclude_rxc,
# exclude_hcc) is constant per acf_category with zero exceptions. build_acf_mapping below
# re-checks that invariant every time it runs, so a future year's CMS data varying a
# condition within a category gets a loud warning instead of silently producing a mapping
# file that no longer matches what v08.py actually does.
EXPECTED_ACF_CONDITIONS = {
    "ACF_PrEP": ("Age > 20", "RXC_01", ""),
    "ACF_PrEP_Child": ("11 < Age < 21", "", "HHS_HCC001"),
}


def build_acf_mapping(cfg: Config) -> set:
    """
    Reshapes CMS's acf_NDC_mappings.csv / acf_HCPCS_mappings.csv into a tab-delimited
    acf_to_category_map.txt, matching the diag/ndc/proc mapping-file convention exactly:
    one row per (code, acf_category) pair, `code\tacf_category`. The age/exclusion
    conditions aren't written to the file -- they're hardcoded in v08.py's `_determine_acf`
    (see EXPECTED_ACF_CONDITIONS above) -- but they're still read here to verify that
    hardcoding is still valid for this year's data.

    If CMS's package for this year has no acf_*_mappings.csv files (e.g. a version prior to
    BY2026, or a future package that drops the feature), this is a no-op -- the loader
    already treats a missing acf_to_category_map.txt as "no ACF categories for this year".

    Returns the set of distinct ACF category names found (e.g. {"ACF_PrEP", "ACF_PrEP_Child"}),
    used by add_acf_category_definitions to know what needs a category_definition.json entry.
    """
    acf_names = set()
    rows_out = []
    seen_rows = set()
    conditions_by_category = defaultdict(set)
    for filename, code_col in [
        ("acf_NDC_mappings.csv", "NDC"),
        ("acf_HCPCS_mappings.csv", "HCPCS"),
    ]:
        if not (CMS_DATA / filename).exists():
            continue
        for row in read_cms_csv(filename):
            code = row[code_col].strip()
            acf_category = row["ACF"].strip()
            if not code or not acf_category:
                continue
            exclude_rxc = row["ACF_RXC"].strip()
            exclude_rxc = f"RXC_{exclude_rxc.zfill(2)}" if exclude_rxc else ""
            exclude_hcc = row["ACF_HCC"].strip()
            age_condition = row["ACF_Age"].strip()
            conditions_by_category[acf_category].add(
                (age_condition, exclude_rxc, exclude_hcc)
            )

            acf_names.add(acf_category)
            row_key = (code, acf_category)
            if row_key not in seen_rows:
                seen_rows.add(row_key)
                rows_out.append(f"{code}\t{acf_category}")

    if not rows_out:
        print(
            "  No acf_*_mappings.csv found in CMS package -- skipping (no ACF this year)"
        )
        return acf_names

    for category, conditions in conditions_by_category.items():
        if len(conditions) > 1:
            print(
                f"  WARNING: {category} has multiple distinct (age_condition, exclude_rxc, "
                f"exclude_hcc) combinations in CMS's source: {conditions}. v08.py's "
                f"_determine_acf hardcodes a single rule per category -- it needs updating "
                f"to handle this before {cfg.target_year} ACF scoring can be trusted."
            )
            continue
        (actual,) = conditions
        expected = EXPECTED_ACF_CONDITIONS.get(category)
        if expected is None:
            print(
                f"  WARNING: {category} is a new ACF category not handled by v08.py's "
                f"_determine_acf (condition: {actual}) -- needs a code change, not just data."
            )
        elif actual != expected:
            print(
                f"  WARNING: {category}'s condition changed from what v08.py hardcodes: "
                f"expected {expected}, CMS {cfg.target_year} source has {actual}."
            )

    with open(cfg.repo_target / "acf_to_category_map.txt", "w") as f:
        f.write("\n".join(rows_out) + "\n")
    print(
        f"  Wrote acf_to_category_map.txt ({len(rows_out)} rows, categories: {sorted(acf_names)})"
    )
    return acf_names


def add_acf_category_definitions(cfg: Config, acf_category_names: set):
    if not acf_category_names:
        return

    with open(cfg.repo_target / "category_definition.json") as f:
        category_definitions = json.load(f)

    prior_category_definitions = {}
    prior_definition_path = cfg.repo_prior / "category_definition.json"
    if prior_definition_path.exists():
        with open(prior_definition_path) as f:
            prior_category_definitions = json.load(f)

    added = []
    for name in sorted(acf_category_names):
        if name in category_definitions:
            continue
        if name in prior_category_definitions:
            category_definitions[name] = prior_category_definitions[name]
        else:
            category_definitions[name] = {
                "descr": f"Affiliated Cost Factor: {name} (NEEDS DESCRIPTION -- new for {cfg.target_year})",
                "type": "acf",
            }
        added.append(name)

    if added:
        with open(cfg.repo_target / "category_definition.json", "w") as f:
            json.dump(category_definitions, f)
        print(f"  Added category_definition.json entries for: {added}")


# ---------------------------------------------------------------------------
# weights.csv -- reshape adult/child/infant model factors, including ACF rows
# ---------------------------------------------------------------------------


def build_weights(cfg: Config):
    # CMS's Variable column casing doesn't always match what the repo's Python code
    # actually produces/looks up (e.g. CMS "AGE1_MALE" vs repo "Age1_Male", CMS
    # "RXC_01_X_HCC001" vs repo "RXC_01_x_HCC001"). category_definition.json (already
    # carried forward + ACF-augmented by this point) holds the case-correct names the
    # code expects, so normalize against it case-insensitively rather than trusting
    # CMS's casing verbatim.
    with open(cfg.repo_target / "category_definition.json") as f:
        category_definitions = json.load(f)
    case_map = {name.upper(): name for name in category_definitions}

    header = [
        "model",
        "category",
        "Platinum",
        "Gold",
        "Silver",
        "Bronze",
        "Catastrophic",
    ]
    col_map = {
        "Platinum Level": "Platinum",
        "Gold Level": "Gold",
        "Silver Level": "Silver",
        "Bronze Level": "Bronze",
        "Catastrophic Level": "Catastrophic",
    }
    unmatched = []
    rows_out = []
    for model_name, filename in [
        ("Adult", "adult_model_factors.csv"),
        ("Child", "child_model_factors.csv"),
        ("Infant", "infant_model_factors.csv"),
    ]:
        for row in read_cms_csv(filename):
            raw_category = row["Variable"].strip()
            category = case_map.get(raw_category.upper())
            if category is None:
                unmatched.append(raw_category)
                category = raw_category
            out_row = [model_name, category] + [row[src] for src in col_map]
            rows_out.append(out_row)

    if unmatched:
        print(
            f"  WARNING: {len(unmatched)} weights.csv variables have no matching "
            f"category_definition.json entry (kept CMS casing as-is): {unmatched}"
        )

    with open(cfg.repo_target / "weights.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows_out)
    print(f"  Wrote weights.csv ({len(rows_out)} data rows)")


# ---------------------------------------------------------------------------
# hierarchy / group / category definitions -- verify unchanged, carry forward
# ---------------------------------------------------------------------------


def verify_hierarchy_and_groups(cfg: Config):
    cms_hierarchy = read_cms_csv("HCC_hierarchy.csv")
    cms_hierarchy_map = {}
    for row in cms_hierarchy:
        hcc = row["HHS_HCC"].strip()
        secondaries = [
            row[f"SecondaryHCC_{i}"].strip()
            for i in range(1, 9)
            if row.get(f"SecondaryHCC_{i}", "").strip()
        ]
        cms_hierarchy_map[hcc] = secondaries

    with open(cfg.repo_prior / "hierarchy_definition.json") as f:
        repo_hierarchy = json.load(f)

    mismatches = []
    for hcc, secondaries in cms_hierarchy_map.items():
        repo_entry = repo_hierarchy.get(hcc)
        if secondaries and (
            not repo_entry or set(repo_entry["remove_code"]) != set(secondaries)
        ):
            mismatches.append((hcc, secondaries, repo_entry))

    if mismatches:
        print(f"  WARNING: {len(mismatches)} HCC hierarchy mismatches vs CMS source:")
        for hcc, secondaries, repo_entry in mismatches[:10]:
            print(f"    {hcc}: CMS={secondaries} repo={repo_entry}")
    else:
        print(
            "  hierarchy_definition.json: verified consistent with CMS HCC_hierarchy.csv"
        )

    for model_name, filename in [
        ("Adult", "adult_group_mappings.csv"),
        ("Child", "child_group_mappings.csv"),
    ]:
        cms_groups = read_cms_csv(filename)
        cms_hcc_to_group = {}
        for row in cms_groups:
            group = row["Group"].strip()
            for i in range(1, 4):
                hcc = row.get(f"HCC_list_{i}", "").strip()
                if hcc:
                    cms_hcc_to_group[hcc] = group

        with open(cfg.repo_prior / "group_definition.json") as f:
            repo_groups = json.load(f)[model_name]

        if cms_hcc_to_group != repo_groups:
            print(
                f"  WARNING: {model_name} group_definition.json differs from CMS {filename}"
            )
            print(f"    CMS only: {set(cms_hcc_to_group) - set(repo_groups)}")
            print(f"    repo only: {set(repo_groups) - set(cms_hcc_to_group)}")
        else:
            print(
                f"  group_definition.json[{model_name}]: verified consistent with CMS {filename}"
            )

    # No drift detected here typically means no HCC classification changes for the target
    # year -- carry forward the prior-year files verbatim as the starting point (ACF/other
    # additions layer on top of this below).
    for filename in [
        "hierarchy_definition.json",
        "group_definition.json",
        "category_definition.json",
    ]:
        with open(cfg.repo_prior / filename) as src, open(
            cfg.repo_target / filename, "w"
        ) as dst:
            dst.write(src.read())
    print(
        f"  Carried forward hierarchy_definition.json, group_definition.json, category_definition.json from {cfg.prior_year}"
    )


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prior-year",
        type=int,
        required=True,
        help="Known-good prior model year to diff against and carry forward from (e.g. 2025).",
    )
    parser.add_argument(
        "--target-year",
        type=int,
        required=True,
        help="Benefit year to generate reference data for (e.g. 2026).",
    )
    args = parser.parse_args()

    repo_prior = V08_REFERENCE_DATA / str(args.prior_year)
    repo_target = V08_REFERENCE_DATA / str(args.target_year)
    if not repo_prior.exists():
        raise SystemExit(f"Prior-year reference data directory not found: {repo_prior}")
    repo_target.mkdir(parents=True, exist_ok=True)

    return Config(
        prior_year=args.prior_year,
        target_year=args.target_year,
        repo_prior=repo_prior,
        repo_target=repo_target,
    )


def main():
    cfg = parse_args()

    print("Verifying hierarchy / group / category definitions...")
    verify_hierarchy_and_groups(cfg)

    print("Building acf_to_category_map.txt...")
    acf_category_names = build_acf_mapping(cfg)

    print("Adding ACF category definitions...")
    add_acf_category_definitions(cfg, acf_category_names)

    print("Building weights.csv...")
    build_weights(cfg)

    print("Building ndc_to_category_map.txt...")
    build_ndc_map(cfg)

    print("Building proc_to_category_map.txt...")
    build_proc_map(cfg)

    print("Building diag_to_category_map.txt (CC target-set comparison)...")
    build_diag_map(cfg)

    print("Done.")


if __name__ == "__main__":
    main()

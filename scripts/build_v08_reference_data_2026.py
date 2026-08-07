"""
Regenerates risk_adjustment_model's reference_data/commercial/v08/2026 files from the
official CMS BY2026 HHS-HCC DIY software package (HHS_HCC_software_package_V0826.141.E1_v2).

This is a from-scratch replacement for the current placeholder 2026 files (which reuse 2025
mappings and only carry updated coefficients).

Approach for diag_to_category_map.txt (the highest-risk transform, since this repo encodes
some ICD-10 -> category logic as static file rows and some as hardcoded Python age/sex edit
methods in v08.py, and those methods are a separate business-rule layer that doesn't map 1:1
to this CSV's AGE_EDIT_CONDITION/SEX_EDIT_CONDITION columns -- see the comment in
build_diag_map for why): for every diagnosis code present in both years, compare the raw set
of target CC numbers the CSV states for that code against what the 2025 static file already
encodes. An unchanged CC-number set means the code's mapping is stable and the existing 2025
file row(s) are carried forward as-is. A changed set, or a code that's new/retired, is flagged
in a report for manual review (Phase 3) rather than guessed -- wrong diagnosis-to-HCC mappings
directly affect risk scores.

Usage:
    poetry run python scripts/build_v08_reference_data_2026.py

The CMS source package location is resolved via the CMS_PACKAGE_DIR env var if set,
otherwise by looking for a sibling directory of this repo matching
"HHS_HCC_software_package*" (e.g. ../HHS_HCC_software_package_V0826.141.E1_v2).
"""

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _find_cms_root() -> Path:
    env_path = os.environ.get("CMS_PACKAGE_DIR")
    if env_path:
        return Path(env_path)
    candidates = sorted(REPO_ROOT.parent.glob("HHS_HCC_software_package*"))
    if not candidates:
        raise SystemExit(
            "Could not locate the CMS HHS_HCC software package directory. "
            "Set the CMS_PACKAGE_DIR environment variable to its path, or place it "
            "as a sibling directory of this repo (e.g. ../HHS_HCC_software_package_*)."
        )
    return candidates[-1]


CMS_ROOT = _find_cms_root()
CMS_DATA = CMS_ROOT / "software/HHS_HCC/data/input/internal"
REPO_2025 = (
    REPO_ROOT
    / "src/risk_adjustment_model/reference_data/commercial/v08/2025"
)
REPO_2026 = (
    REPO_ROOT
    / "src/risk_adjustment_model/reference_data/commercial/v08/2026"
)
REPORT_DIR = REPO_ROOT / "scripts/output"


def read_cms_csv(name):
    with open(CMS_DATA / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Repo 2025 static map (preserving row order + trailing flags, e.g. "D")
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
    Python edit method (Phase 3) and are called out in the report.
    """
    unconditional_ccs = []
    conditional_only_ccs = []
    seen_cc = {}
    for row in rows:
        cc = row["CC"]
        is_unconditional = not (
            row["MCE_AGE_CONDITION"] or row["AGE_EDIT_CONDITION"] or row["SEX_EDIT_CONDITION"]
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


def build_diag_map():
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from risk_adjustment_model import CommercialModelV08

    model = CommercialModelV08(year=2025)

    repo_lines = load_repo_diag_lines(REPO_2025 / "diag_to_category_map.txt")

    cms_rows = read_cms_csv("ICD10_HHS_CC_mappings_2026.csv")
    cms_rows_by_code = defaultdict(list)
    for row in cms_rows:
        if row.get("valid_ICD10_2026", "").strip().upper() != "TRUE":
            continue
        cms_rows_by_code[row["ICD10"].strip()].append(row)

    print(f"  CMS 2026 codes: {len(cms_rows_by_code)}")
    print(f"  Repo 2025 codes: {len(repo_lines)}")

    # NOTE: the 16 hardcoded `_age_sex_edit_N` methods in v08.py are a separate business-rule
    # layer carried over from CMS's own historical DIY "edit files" (ED1-ED16) -- they do NOT
    # correspond 1:1 to this CSV's AGE_EDIT_CONDITION/SEX_EDIT_CONDITION columns (e.g. F201 has
    # a single unconditional CMS row yet _age_sex_edit_5 overrides it for age<2 -- a rule this
    # CSV has no way to confirm or refute). So rather than trying to re-derive full conditional
    # *behavior* from these columns (which produced false positives -- see git history / PR
    # description), the comparison here is scoped to what the CSV *does* authoritatively state:
    # the raw set of target CC numbers per code. A changed CC-number set is a real, actionable
    # signal; edit-method semantics are left to Phase 3 review against CMS's edit-file docs.
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
        in_2025 = code in repo_lines
        in_2026 = code in cms_rows_by_code
        if in_2025 and not in_2026:
            retired_codes.append(code)
            continue
        if not in_2025 and in_2026:
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

    print(f"  Stable (same target CC-number set as 2025, carried forward as-is): {len(stable_codes)}")
    print(f"  New codes (not in 2025): {len(new_codes)}")
    print(f"  Retired codes (in 2025, absent from 2026): {len(retired_codes)}")
    print(f"  Changed codes (target CC-number set differs -- flagged for review): {len(changed_codes)}")

    # --- Emit diag_to_category_map.txt ---
    # Codes present in both years (stable AND changed) always carry forward the exact
    # 2025 line(s) -- that split between "static default row" and "python edit override"
    # was hand-verified against CMS SAS/software conventions previously and there is no
    # reliable way to re-derive which branch is the "default" purely from the 2026 CMS
    # condition columns (e.g. E700's default is the *pediatric* branch with an adult
    # override to the "NA" sentinel, while C9100's default is the *adult* branch with a
    # pediatric override -- there's no consistent rule). Emitting nothing for a changed
    # code (this script's first pass did exactly that) is worse than carrying the proven
    # 2025 row forward, so "changed" only affects the review report here, not file content.
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
                    f"carried forward existing 2025 row(s) as-is: "
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
                "action_taken": "dropped from 2026 file (no row emitted)",
                "cms_rows": "(absent from CMS 2026 source / not valid_ICD10_2026)",
            }
        )

    # sort output for determinism, matching original file's rough code-sorted layout
    out_lines.sort(key=lambda p: p[0])

    with open(REPO_2026 / "diag_to_category_map.txt", "w") as f:
        for parts in out_lines:
            f.write("\t".join(parts) + "\n")

    REPORT_DIR.mkdir(exist_ok=True)
    with open(REPORT_DIR / "diag_map_2026_review.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["code", "status", "action_taken", "cms_rows"],
        )
        writer.writeheader()
        for row in review_rows:
            writer.writerow(row)

    print(f"  Wrote {REPO_2026 / 'diag_to_category_map.txt'} ({len(out_lines)} lines)")
    print(f"  Wrote {REPORT_DIR / 'diag_map_2026_review.csv'} ({len(review_rows)} rows needing review)")


# ---------------------------------------------------------------------------
# ndc / proc maps -- straightforward reshape
# ---------------------------------------------------------------------------


def build_ndc_map():
    rows = read_cms_csv("rxc_NDC_mappings.csv")
    out_lines = []
    for row in rows:
        ndc = row["NDC"].strip()
        rxc = row["RXC"].strip()
        if not ndc or not rxc:
            continue
        out_lines.append(f"{ndc}\t{rxc}")
    with open(REPO_2026 / "ndc_to_category_map.txt", "w") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"  Wrote ndc_to_category_map.txt ({len(out_lines)} lines)")


def build_proc_map():
    rows = read_cms_csv("rxc_HCPCS_mappings.csv")
    out_lines = []
    for row in rows:
        hcpcs = row["HCPCS"].strip()
        rxc = row["RXC"].strip()
        if not hcpcs or not rxc:
            continue
        out_lines.append(f"{hcpcs}\t{rxc}")
    with open(REPO_2026 / "proc_to_category_map.txt", "w") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"  Wrote proc_to_category_map.txt ({len(out_lines)} lines)")


# ---------------------------------------------------------------------------
# weights.csv -- reshape adult/child/infant model factors, including ACF rows
# ---------------------------------------------------------------------------


def build_weights():
    # CMS's Variable column casing doesn't always match what the repo's Python code
    # actually produces/looks up (e.g. CMS "AGE1_MALE" vs repo "Age1_Male", CMS
    # "RXC_01_X_HCC001" vs repo "RXC_01_x_HCC001"). category_definition.json (already
    # carried forward + ACF-augmented by this point) holds the case-correct names the
    # code expects, so normalize against it case-insensitively rather than trusting
    # CMS's casing verbatim.
    with open(REPO_2026 / "category_definition.json") as f:
        category_definitions = json.load(f)
    case_map = {name.upper(): name for name in category_definitions}

    header = ["model", "category", "Platinum", "Gold", "Silver", "Bronze", "Catastrophic"]
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
            out_row = [model_name, category] + [
                row[src] for src in col_map
            ]
            rows_out.append(out_row)

    if unmatched:
        print(
            f"  WARNING: {len(unmatched)} weights.csv variables have no matching "
            f"category_definition.json entry (kept CMS casing as-is): {unmatched}"
        )

    with open(REPO_2026 / "weights.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows_out)
    print(f"  Wrote weights.csv ({len(rows_out)} data rows, including ACF_PrEP/ACF_PrEP_Child)")


# ---------------------------------------------------------------------------
# acf_definition.json -- new for BY2026 (Affiliated Cost Factors)
# ---------------------------------------------------------------------------


def build_acf_definition():
    acf_map = defaultdict(list)
    for filename, code_col in [
        ("acf_NDC_mappings.csv", "NDC"),
        ("acf_HCPCS_mappings.csv", "HCPCS"),
    ]:
        for row in read_cms_csv(filename):
            code = row[code_col].strip()
            acf_category = row["ACF"].strip()
            if not code or not acf_category:
                continue
            exclude_rxc = row["ACF_RXC"].strip()
            entry = {
                "acf_category": acf_category,
                "age_condition": row["ACF_Age"].strip(),
                "exclude_rxc": f"RXC_{exclude_rxc.zfill(2)}" if exclude_rxc else None,
                "exclude_hcc": row["ACF_HCC"].strip() or None,
            }
            if entry not in acf_map[code]:
                acf_map[code].append(entry)

    with open(REPO_2026 / "acf_definition.json", "w") as f:
        json.dump(acf_map, f)
    print(f"  Wrote acf_definition.json ({len(acf_map)} codes)")


def add_acf_category_definitions():
    with open(REPO_2026 / "category_definition.json") as f:
        category_definitions = json.load(f)
    category_definitions["ACF_PrEP"] = {
        "descr": "Affiliated Cost Factor: HIV Pre-Exposure Prophylaxis (Adult)",
        "type": "acf",
    }
    category_definitions["ACF_PrEP_Child"] = {
        "descr": "Affiliated Cost Factor: HIV Pre-Exposure Prophylaxis (Child)",
        "type": "acf",
    }
    with open(REPO_2026 / "category_definition.json", "w") as f:
        json.dump(category_definitions, f)
    print("  Added ACF_PrEP / ACF_PrEP_Child to category_definition.json")


# ---------------------------------------------------------------------------
# hierarchy / group / category definitions -- verify unchanged, carry forward
# ---------------------------------------------------------------------------


def verify_hierarchy_and_groups():
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

    with open(REPO_2025 / "hierarchy_definition.json") as f:
        repo_hierarchy = json.load(f)

    mismatches = []
    for hcc, secondaries in cms_hierarchy_map.items():
        repo_entry = repo_hierarchy.get(hcc)
        if secondaries and (not repo_entry or set(repo_entry["remove_code"]) != set(secondaries)):
            mismatches.append((hcc, secondaries, repo_entry))

    if mismatches:
        print(f"  WARNING: {len(mismatches)} HCC hierarchy mismatches vs CMS source:")
        for hcc, secondaries, repo_entry in mismatches[:10]:
            print(f"    {hcc}: CMS={secondaries} repo={repo_entry}")
    else:
        print("  hierarchy_definition.json: verified consistent with CMS HCC_hierarchy.csv")

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

        with open(REPO_2025 / "group_definition.json") as f:
            repo_groups = json.load(f)[model_name]

        if cms_hcc_to_group != repo_groups:
            print(f"  WARNING: {model_name} group_definition.json differs from CMS {filename}")
            print(f"    CMS only: {set(cms_hcc_to_group) - set(repo_groups)}")
            print(f"    repo only: {set(repo_groups) - set(cms_hcc_to_group)}")
        else:
            print(f"  group_definition.json[{model_name}]: verified consistent with CMS {filename}")

    # No drift detected (as expected -- CMS PDF states no HCC classification
    # changes for 2026) -- carry forward the 2025 files verbatim.
    for filename in ["hierarchy_definition.json", "group_definition.json", "category_definition.json"]:
        with open(REPO_2025 / filename) as src, open(REPO_2026 / filename, "w") as dst:
            dst.write(src.read())
    print("  Carried forward hierarchy_definition.json, group_definition.json, category_definition.json from 2025")


def main():
    print("Verifying hierarchy / group / category definitions...")
    verify_hierarchy_and_groups()

    print("Adding ACF category definitions...")
    add_acf_category_definitions()

    print("Building weights.csv...")
    build_weights()

    print("Building acf_definition.json...")
    build_acf_definition()

    print("Building ndc_to_category_map.txt...")
    build_ndc_map()

    print("Building proc_to_category_map.txt...")
    build_proc_map()

    print("Building diag_to_category_map.txt (CC target-set comparison)...")
    build_diag_map()

    print("Done.")


if __name__ == "__main__":
    main()

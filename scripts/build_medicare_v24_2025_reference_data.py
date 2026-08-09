"""
Regenerates risk_adjustment_model's reference_data/medicare/v24/2025 files from CMS's PY2025
CMS-HCC V24 software package (CMS-HCC software V2425.86.P1.zip).

Unlike scripts/build_medicare_reference_data.py (which handles the newer, clean-CSV Python DIY
packages CMS started shipping for PY2026+), this PY2025 V24 package is the older SAS-artifact
format: a fixed ICD10-to-CC crosswalk text file, a coefficients CSV with population encoded as a
row-name prefix rather than as columns, and hierarchy/label/edit definitions embedded in SAS
macro (.TXT) source rather than clean CSVs. V24 is a legacy, frozen model (CMS has fully retired
it in favor of V28 as of PY2026 -- no PY2026/2027 V24 package exists at all), so this script is
intentionally a one-off rather than a generalized tool: verified against the 2024 reference data
already in this repo, V24's HCC hierarchy, disease-category set/descriptions, and hardcoded
age/sex edit logic (v24.py's three `_age_sex_edit_N` methods) are all confirmed byte-for-byte
unchanged for PY2025, so this only needs to regenerate the diagnosis crosswalk (new/retired ICD-10
codes) and coefficients (weights.csv) -- hierarchy_definition.json/category_definition.json are
carried forward from 2024 verbatim.

Usage:
    poetry run python scripts/build_medicare_v24_2025_reference_data.py \\
        --cms-package-dir /path/to/extracted/CMS_HCC_v24_2025
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_PRIOR = REPO_ROOT / "src/risk_adjustment_model/reference_data/medicare/v24/2024"
REPO_TARGET = REPO_ROOT / "src/risk_adjustment_model/reference_data/medicare/v24/2025"

CE_PREFIXES = ["CNA", "CND", "CFA", "CFD", "CPA", "CPD", "INS"]
NE_PREFIXES = [
    "NE_NMCAID_NORIGDIS",
    "NE_MCAID_NORIGDIS",
    "NE_NMCAID_ORIGDIS",
    "NE_MCAID_ORIGDIS",
]
ALL_WEIGHT_COLUMNS = CE_PREFIXES + NE_PREFIXES


def verify_and_carry_forward_definitions(cms_dir: Path):
    hierarchy_text = (cms_dir / "V24H86H1.TXT").read_text()
    pattern = re.compile(r"%SET0\(CC=\s*(\d+)\s*,\s*HIER=%STR\(([^)]*)\)\s*\)")
    cms_hierarchy = {}
    for m in pattern.finditer(hierarchy_text):
        secondaries = [h.strip() for h in m.group(2).split(",") if h.strip()]
        cms_hierarchy[f"HCC{m.group(1)}"] = [f"HCC{h}" for h in secondaries]

    with open(REPO_PRIOR / "hierarchy_definition.json") as f:
        repo_hierarchy = json.load(f)

    mismatches = [
        (hcc, secondaries, repo_hierarchy.get(hcc))
        for hcc, secondaries in cms_hierarchy.items()
        if not repo_hierarchy.get(hcc)
        or set(repo_hierarchy[hcc]["remove_code"]) != set(secondaries)
    ]
    if mismatches:
        print(f"  WARNING: {len(mismatches)} HCC hierarchy mismatches vs CMS source:")
        for hcc, secondaries, repo_entry in mismatches[:10]:
            print(f"    {hcc}: CMS={secondaries} repo={repo_entry}")
    else:
        print(
            f"  hierarchy_definition.json: verified consistent with CMS V24H86H1.TXT ({len(cms_hierarchy)} entries)"
        )

    labels_text = (cms_dir / "V24H86L1.TXT").read_text()
    label_pattern = re.compile(r'HCC(\d+)\s*=\s*"([^"]*)"')
    cms_labels = {
        f"HCC{m.group(1)}": m.group(2).strip()
        for m in label_pattern.finditer(labels_text)
    }

    with open(REPO_PRIOR / "category_definition.json") as f:
        repo_categories = json.load(f)
    repo_disease = {
        k: v["descr"] for k, v in repo_categories.items() if v["type"] == "disease"
    }

    missing = set(cms_labels) - set(repo_disease)
    extra = set(repo_disease) - set(cms_labels)
    desc_mismatches = [
        k for k in cms_labels if k in repo_disease and cms_labels[k] != repo_disease[k]
    ]
    if missing or extra or desc_mismatches:
        print(
            "  WARNING: disease category set/descriptions differ vs CMS V24H86L1.TXT:"
        )
        if missing:
            print(f"    In CMS source, not in repo: {sorted(missing)}")
        if extra:
            print(f"    In repo, not in CMS source: {sorted(extra)}")
        if desc_mismatches:
            print(f"    Description mismatches: {desc_mismatches}")
    else:
        print(
            f"  category_definition.json: disease category set/descriptions verified consistent with CMS V24H86L1.TXT ({len(cms_labels)} entries)"
        )

    for filename in ["hierarchy_definition.json", "category_definition.json"]:
        with open(REPO_PRIOR / filename) as src, open(
            REPO_TARGET / filename, "w"
        ) as dst:
            dst.write(src.read())
    print(
        "  Carried forward hierarchy_definition.json, category_definition.json from 2024"
    )


def build_weights(cms_dir: Path):
    with open(REPO_PRIOR / "category_definition.json") as f:
        repo_categories = json.load(f)
    ce_categories = {
        k
        for k, v in repo_categories.items()
        if not (v["type"] == "demographic" and k.startswith("NE"))
    }
    ne_categories = {
        k
        for k, v in repo_categories.items()
        if v["type"] == "demographic" and k.startswith("NE")
    }

    weights = defaultdict(lambda: {col: 0.0 for col in ALL_WEIGHT_COLUMNS})
    unmatched = []
    with open(cms_dir / "C2419P1M.csv", encoding="cp1252") as f:
        for row in csv.DictReader(f):
            name = row["_NAME_"]
            value = float(row["COL1"])
            matched = False
            for prefix, categories in [(p, ce_categories) for p in CE_PREFIXES] + [
                (p, ne_categories) for p in NE_PREFIXES
            ]:
                if name.startswith(prefix + "_"):
                    category = name[len(prefix) + 1 :]
                    if category in categories:
                        weights[category][prefix] = value
                        matched = True
                        break
            if not matched:
                unmatched.append(name)

    # Known, expected-unmatched rows: SNPNE_* (C-SNP New Enrollee, not modeled by this repo, same
    # as V28's NE_SNP column) and INS_ORIGDS (a CMS coefficient placeholder with no real scoring
    # effect, same pattern as V28's ORIGDIS -- see build_medicare_reference_data.py).
    unexpected = [
        u for u in unmatched if not u.startswith("SNPNE_") and u != "INS_ORIGDS"
    ]
    if unexpected:
        print(
            f"  WARNING: {len(unexpected)} unexpected unmatched rows in C2419P1M.csv: {unexpected[:20]}"
        )
    print(f"  ({len(unmatched)} rows intentionally skipped: SNPNE_* / INS_ORIGDS)")

    with open(REPO_TARGET / "weights.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["category"] + ALL_WEIGHT_COLUMNS)
        for category, pop_weight in weights.items():
            writer.writerow(
                [category] + [pop_weight[col] for col in ALL_WEIGHT_COLUMNS]
            )
    print(f"  Wrote weights.csv ({len(weights)} data rows)")


def load_repo_diag_lines(path):
    lines_by_code = defaultdict(list)
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            lines_by_code[parts[0].strip()].append(parts)
    return lines_by_code


def edit_method_explained_ccs(model, code):
    explained = set()
    for age in range(0, 101):
        for gender in ("M", "F"):
            result = model._age_sex_edits(gender, age, code)
            if result:
                explained.update(c.replace(model.category_prefix, "") for c in result)
    return explained


def build_diag_map(cms_dir: Path):
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from risk_adjustment_model import MedicareModelV24

    model = MedicareModelV24(year=2024)

    repo_lines = load_repo_diag_lines(REPO_PRIOR / "diag_to_category_map.txt")

    cms_rows_by_code = defaultdict(list)
    with open(cms_dir / "F2425P1M.TXT") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            code = parts[0].strip()
            cc = parts[1].strip()
            if code and cc:
                cms_rows_by_code[code].append(cc)

    print(f"  CMS 2025 codes: {len(cms_rows_by_code)}")
    print(f"  Repo 2024 codes: {len(repo_lines)}")

    repo_cc_sets = {
        code: {parts[1] for parts in lines} for code, lines in repo_lines.items()
    }
    cms_cc_sets = {code: set(ccs) for code, ccs in cms_rows_by_code.items()}

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

    print(f"  Stable (same target CC-number set as 2024): {len(stable_codes)}")
    print(f"  New codes (not in 2024): {len(new_codes)}")
    print(f"  Retired codes (in 2024, absent from 2025): {len(retired_codes)}")
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
                    "action_taken": "carried forward existing 2024 row(s) as-is",
                    "cms_ccs": ";".join(sorted(cms_cc_sets[code])),
                }
            )

    for code in sorted(new_codes):
        ccs = sorted(cms_cc_sets[code])
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
                "action_taken": "dropped from 2025 file",
                "cms_ccs": "",
            }
        )

    out_lines.sort(key=lambda p: p[0])
    with open(REPO_TARGET / "diag_to_category_map.txt", "w") as f:
        for parts in out_lines:
            f.write("\t".join(parts) + "\n")

    report_dir = REPO_ROOT / "scripts/output"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "medicare_v24_diag_map_2025_review.csv"
    with open(report_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["code", "status", "action_taken", "cms_ccs"]
        )
        writer.writeheader()
        for row in review_rows:
            writer.writerow(row)

    print(
        f"  Wrote {REPO_TARGET / 'diag_to_category_map.txt'} ({len(out_lines)} lines)"
    )
    print(f"  Wrote {report_path} ({len(review_rows)} rows needing review)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cms-package-dir", required=True, type=Path)
    args = parser.parse_args()

    if not REPO_PRIOR.exists():
        raise SystemExit(f"Prior-year (2024) reference data not found: {REPO_PRIOR}")
    REPO_TARGET.mkdir(parents=True, exist_ok=True)

    print("Verifying hierarchy / category definitions...")
    verify_and_carry_forward_definitions(args.cms_package_dir)

    print("Building weights.csv...")
    build_weights(args.cms_package_dir)

    print("Building diag_to_category_map.txt...")
    build_diag_map(args.cms_package_dir)

    print("Done.")


if __name__ == "__main__":
    main()

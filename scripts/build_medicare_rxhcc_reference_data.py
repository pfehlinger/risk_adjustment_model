"""
Builds risk_adjustment_model's reference_data/medicare/v08_rxhcc_<segment>/<year> files from
scratch from a CMS RxHCC V08 Python DIY software package. Every segment (T, X, T2, Y1, Y2) is a
cold start -- there's no prior RxHCC reference data in this repo for any of them to diff against
-- so this script always builds category/hierarchy/weights/diag-map fresh from CMS's source,
parameterized by --segment/--year/--cms-package-dir so it's reusable across all five (unlike
ESRD, where each version needed its own cold-start script -- RxHCC's structure is identical
across segments, only the calibration data differs). See rxhcc_model.py's module docstring for
what T/X/T2/Y1/Y2 actually mean.

Compared to Community/ESRD's cold-start builds, RxHCC's is the simplest of the three:

- diag_to_category_map.txt is a plain reshape, not routed through any stability-check or
  age/gender-grid analysis -- RxHCC's ICD10_CC_mappings crosswalk has no AGE_EDIT_CONDITION/
  SEX_EDIT_CONDITION columns at all (only MCE_AGE_CONDITION, which is out of scope, consistent
  with every other Medicare model in this repo). There are no age/sex edit methods in
  rxhcc_model.py because there's nothing to hardcode.
- weights.csv has 8 population columns (5 continuing-enrollee + 3 new-enrollee), reshaped from
  CMS's <segment>_CE_Relative_Factors.csv / <segment>_NE_Relative_Factors.csv. CMS's own raw
  column names for these vary cosmetically by package vintage (e.g. "CE_NonLow_Aged" in the 2026
  packages vs "CE_NonLowAged" in the 2027 ones) -- normalized here to a stable repo naming
  convention (CE_NONLOW_AGED, etc.) regardless of source spelling.
- No HCC-count/payment-count categories: CMS's own utils.py computes RXHCC_COUNT5-10P columns,
  but no segment's coefficient file actually scores them (confirmed across all 5 segments) --
  omitted from category_definition.json/weights.csv entirely.
- File layout differs between package vintages: the 2026 T/X packages nest their coefficient
  CSVs under a per-segment subfolder (data/input/internal/T/T_CE_Relative_Factors.csv), while the
  2027 T2/Y1/Y2 packages have them directly under data/input/internal/ -- this script checks both.

Usage:
    poetry run python scripts/build_medicare_rxhcc_reference_data.py \\
        --segment T --year 2026 \\
        --cms-package-dir /path/to/extracted/RxHCC_v8_2026_T_package_v5/software/RxHCC
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

CE_COLUMN_ALIASES = {
    "cenonlowaged": "CE_NONLOW_AGED",
    "cenonlownonaged": "CE_NONLOW_NONAGED",
    "celowaged": "CE_LOW_AGED",
    "celownonaged": "CE_LOW_NONAGED",
    "celti": "CE_LTI",
}
NE_COLUMN_ALIASES = {
    "nenonlowcommunity": "NE_NONLOW_COMMUNITY",
    "nelowcommunity": "NE_LOW_COMMUNITY",
    "nelti": "NE_LTI",
}
ALL_WEIGHT_COLUMNS = list(CE_COLUMN_ALIASES.values()) + list(NE_COLUMN_ALIASES.values())

# The 7 NONAGED_RXHCC{n} disease interactions, hardcoded identically across all 5 segments in
# CMS's own transform.py (nonaged_hcc_flags). No other disease-disease interactions exist.
NONAGED_RXHCCS = ["1", "130", "131", "132", "133", "159", "163"]


def normalize_col(col: str) -> str:
    return col.replace("_", "").strip().lower()


def find_internal_file(cms_dir: Path, segment: str, filename: str) -> Path:
    nested = cms_dir / "data/input/internal" / segment / filename
    if nested.exists():
        return nested
    flat = cms_dir / "data/input/internal" / filename
    if flat.exists():
        return flat
    raise FileNotFoundError(
        f"Could not find {filename} under {cms_dir}/data/input/internal"
    )


def read_cms_csv(path: Path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_definitions(cms_dir: Path, segment: str, repo_target: Path):
    hierarchy_rows = read_cms_csv(
        find_internal_file(cms_dir, segment, "HCC_Hierarchies.csv")
    )
    hierarchy = {}
    disease_rxhccs = set()
    for row in hierarchy_rows:
        rxhcc = f"RXHCC{row['RXHCC'].strip()}"
        disease_rxhccs.add(rxhcc)
        secondaries = [
            f"RXHCC{row[f'SecondaryRxHCC_{i}'].strip()}"
            for i in range(1, 7)
            if row.get(f"SecondaryRxHCC_{i}", "").strip()
        ]
        if secondaries:
            hierarchy[rxhcc] = {"descr": None, "remove_code": secondaries}

    ce_rows = read_cms_csv(
        find_internal_file(cms_dir, segment, f"{segment}_CE_Relative_Factors.csv")
    )
    labels = {row["Variable"].strip(): row["Label"].strip() for row in ce_rows}

    categories = {}
    for rxhcc in disease_rxhccs:
        categories[rxhcc] = {
            "descr": labels.get(rxhcc, rxhcc),
            "type": "disease",
            "number": int(rxhcc.replace("RXHCC", "")),
        }
        if rxhcc in hierarchy:
            hierarchy[rxhcc]["descr"] = labels.get(rxhcc, rxhcc)

    for row in ce_rows:
        var = row["Variable"].strip()
        if var in ("M65OD", "F65OD", "OD65"):
            categories[var] = {
                "descr": labels[var].strip(),
                "type": "demographic_interaction",
            }
        elif var[0] in "FM" and var[1:2].isdigit():
            categories[var] = {"descr": labels[var].strip(), "type": "demographic"}

    for n in NONAGED_RXHCCS:
        name = f"NONAGED_RXHCC{n}"
        categories[name] = {
            "descr": labels.get(name, name),
            "type": "disease_interaction",
        }

    ne_rows = read_cms_csv(
        find_internal_file(cms_dir, segment, f"{segment}_NE_Relative_Factors.csv")
    )
    for row in ne_rows:
        variable = row["Variable"].strip()
        if variable not in categories:
            categories[variable] = {
                "descr": row["Label"].strip(),
                "type": "demographic",
            }

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


def build_weights(cms_dir: Path, segment: str, categories: dict, repo_target: Path):
    weights = defaultdict(lambda: {col: 0.0 for col in ALL_WEIGHT_COLUMNS})

    ce_rows = read_cms_csv(
        find_internal_file(cms_dir, segment, f"{segment}_CE_Relative_Factors.csv")
    )
    ce_col_map = {}
    for raw_col in ce_rows[0].keys():
        alias = CE_COLUMN_ALIASES.get(normalize_col(raw_col))
        if alias:
            ce_col_map[raw_col] = alias
    for row in ce_rows:
        category = row["Variable"].strip()
        if category not in categories:
            continue
        for raw_col, repo_col in ce_col_map.items():
            raw = row.get(raw_col, "").strip()
            weights[category][repo_col] = float(raw) if raw else 0.0

    ne_rows = read_cms_csv(
        find_internal_file(cms_dir, segment, f"{segment}_NE_Relative_Factors.csv")
    )
    ne_col_map = {}
    for raw_col in ne_rows[0].keys():
        alias = NE_COLUMN_ALIASES.get(normalize_col(raw_col))
        if alias:
            ne_col_map[raw_col] = alias
    for row in ne_rows:
        category = row["Variable"].strip()
        if category not in categories:
            continue
        for raw_col, repo_col in ne_col_map.items():
            raw = row.get(raw_col, "").strip()
            weights[category][repo_col] = float(raw) if raw else 0.0

    with open(repo_target / "weights.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["category"] + ALL_WEIGHT_COLUMNS)
        for category, pop_weight in weights.items():
            writer.writerow(
                [category] + [pop_weight[col] for col in ALL_WEIGHT_COLUMNS]
            )
    print(f"  Wrote weights.csv ({len(weights)} data rows)")


def build_diag_map(cms_dir: Path, segment: str, year: int, repo_target: Path):
    rows = read_cms_csv(
        find_internal_file(cms_dir, segment, f"ICD10_CC_mappings_RxHCC_{year}.csv")
    )
    # No AGE_EDIT_CONDITION/SEX_EDIT_CONDITION columns exist for RxHCC -- a plain reshape, one
    # row per distinct (ICD10, CC) pair, no stability-check/grid analysis needed.
    rows_by_code = defaultdict(set)
    for row in rows:
        rows_by_code[row["ICD10"].strip()].add(str(int(float(row["CC"]))))

    out_lines = []
    for code in sorted(rows_by_code):
        ccs = sorted(rows_by_code[code], key=int)
        for i, cc in enumerate(ccs):
            flag = ["D"] if i > 0 else []
            out_lines.append([code, cc] + flag)

    with open(repo_target / "diag_to_category_map.txt", "w") as f:
        for parts in out_lines:
            f.write("\t".join(parts) + "\n")
    print(
        f"  Wrote diag_to_category_map.txt ({len(out_lines)} lines, {len(rows_by_code)} codes)"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--segment", required=True, choices=["T", "X", "T2", "Y1", "Y2"]
    )
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--cms-package-dir", required=True, type=Path)
    args = parser.parse_args()

    repo_target = (
        REPO_ROOT
        / "src/risk_adjustment_model/reference_data/medicare"
        / f"v08_rxhcc_{args.segment.lower()}"
        / str(args.year)
    )

    print(
        f"Building hierarchy_definition.json / category_definition.json for {args.segment}..."
    )
    categories = build_definitions(args.cms_package_dir, args.segment, repo_target)

    print("Building weights.csv...")
    build_weights(args.cms_package_dir, args.segment, categories, repo_target)

    print("Building diag_to_category_map.txt...")
    build_diag_map(args.cms_package_dir, args.segment, args.year, repo_target)

    print("Done.")


if __name__ == "__main__":
    main()

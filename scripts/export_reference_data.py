"""
Exports this repo's already-built, already-cross-validated reference data (everything under
src/risk_adjustment_model/reference_data/) into a small, uniform set of flat CSV tables -- one
shape across every model family (Commercial v07/v08, Medicare Community v22/v24/v28, ESRD
v24_esrd/v21_esrd, RxHCC v08_rxhcc_t/x/t2/y1/y2) -- for bulk-loading into any SQL warehouse.

This reuses ReferenceFilesLoader (the same class every model's score() runs on), not a fresh parse
of the raw reference files, so the export is always consistent with actual scoring behavior and
needs no CMS package download to run -- just a checkout of this repo.

Usage:
    poetry run python scripts/export_reference_data.py --out-dir ./export
    poetry run python scripts/export_reference_data.py --out-dir ./export --lob commercial
    poetry run python scripts/export_reference_data.py --out-dir ./export --lob medicare --model-version v28 --year 2026

With no filters, walks every (lob, model_version, benefit_year) combination this repo ships and
accumulates rows from all of them into one set of CSVs (so e.g. category_definitions_*.csv holds
every benefit_year/model_version this repo supports in one table, distinguished by its lob/
model_version/benefit_year columns) -- matching a typical dbt-seed-style table shape.

Output tables (one CSV per entity, written under --out-dir). Every row also carries an
`extracted_at` timestamp (when this export was generated), appended as the last column. That same
timestamp (as UTC, filesystem-safe YYYYMMDDTHHMMSSZ) is also stamped into each file's name, e.g.
`category_definitions_20260812T140512Z.csv`, so repeated runs never silently clobber a prior export.
If `--lob` and/or `--year` were passed, they're inserted into the filename too (in that order,
between the entity name and the timestamp), e.g. `--lob medicare --year 2026` produces
`category_definitions_medicare_2026_20260812T140512Z.csv`. `--model-version` is not included in
the filename since it's typically used alongside `--lob`/`--year` to narrow further, not to
distinguish separate output sets:

    category_definitions_<extracted_at>.csv                 lob, model_version, benefit_year, category, category_number, category_type, description
    category_coefficients_<extracted_at>.csv                 lob, model_version, benefit_year, rate_group, category, population, coefficient
    hierarchy_definitions_<extracted_at>.csv                 lob, model_version, benefit_year, dominant_category, description, subordinate_category
    diagnosis_code_to_category_<extracted_at>.csv            lob, model_version, benefit_year, diagnosis_code, category
    ndc_to_category_<extracted_at>.csv                       lob, model_version, benefit_year, ndc, category                              (Commercial only)
    procedure_code_to_category_<extracted_at>.csv            lob, model_version, benefit_year, procedure_code, category                   (Commercial only)
    acf_eligible_codes_<extracted_at>.csv                    lob, model_version, benefit_year, code, code_type, category                  (Commercial only, BY2026+)
    category_groups_<extracted_at>.csv                       lob, model_version, benefit_year, rate_group, group_category, dropped_category  (Commercial only)
    esrd_flat_score_tables_<extracted_at>.csv                lob, model_version, benefit_year, score_table, key, score                    (ESRD only)
    infant_severity_categories_<extracted_at>.csv            lob, model_version, benefit_year, category, infant_severity_level            (Commercial only)
    severe_illness_transplant_categories_<extracted_at>.csv  lob, model_version, benefit_year, category, is_severe_illness, is_transplant (Commercial only)
    model_adjustment_factors_<extracted_at>.csv              lob, model_version, benefit_year, factor_type, population_group, value

`model_adjustment_factors.csv` consolidates normalization factors, coding-intensity adjusters, and
Commercial's CSR adjuster -- these have zero file-based representation anywhere else in this repo
(they're hardcoded Python dicts scattered across a dozen model files), so this table is this
export's one genuine gap-fill rather than just a reshape of an existing file. `population_group`
is blank except where the factor genuinely varies by group within a single benefit_year (ESRD's
dialysis/graft split, RxHCC X's MAPD/PDP channel split, Commercial's CSR indicator). Values are
read directly out of each model class's source via a small AST-based literal reader (see
`_extract_dict_literal`/`_extract_list_literals` below) rather than re-derived by hand, so this
stays correct even if the underlying dicts change -- but it does mean this script must be re-run
against a matching checkout of this repo if those methods are ever restructured; the extractors
assert on the shape they expect and fail loudly rather than silently exporting nothing/wrong data.

Deliberately NOT exported: the code lists that feed hardcoded Python business rules with no
CMS-published tabular equivalent (age/sex diagnosis-code edits, disease-interaction triggers, ACF
eligibility age-gating, infant maturity status) -- seemed better to leave those as pure code than
invent a table schema that doesn't correspond to anything CMS actually ships.
"""

import argparse
import ast
import csv
import inspect
import textwrap
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DATA_ROOT = REPO_ROOT / "src/risk_adjustment_model/reference_data"

import sys  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "src"))
from risk_adjustment_model.reference_files_loader import ReferenceFilesLoader  # noqa: E402

MODEL_CLASS_NAMES = {
    "v07": "CommercialModelV07",
    "v08": "CommercialModelV08",
    "v22": "MedicareModelV22",
    "v24": "MedicareModelV24",
    "v28": "MedicareModelV28",
    "v24_esrd": "MedicareModelESRDv24",
    "v21_esrd": "MedicareModelESRDv21",
    "v08_rxhcc_t": "MedicareModelRxHCCv08T",
    "v08_rxhcc_x": "MedicareModelRxHCCv08X",
    "v08_rxhcc_t2": "MedicareModelRxHCCv08T2",
    "v08_rxhcc_y1": "MedicareModelRxHCCv08Y1",
    "v08_rxhcc_y2": "MedicareModelRxHCCv08Y2",
}
COMMERCIAL_VERSIONS = {"v07", "v08"}
ESRD_VERSIONS = {"v24_esrd", "v21_esrd"}
RXHCC_VERSIONS = {
    "v08_rxhcc_t",
    "v08_rxhcc_x",
    "v08_rxhcc_t2",
    "v08_rxhcc_y1",
    "v08_rxhcc_y2",
}
RXHCC_X_VERSIONS = {"v08_rxhcc_x"}


def get_model_class(model_version: str):
    import risk_adjustment_model

    return getattr(risk_adjustment_model, MODEL_CLASS_NAMES[model_version])


# --- AST-based literal extraction, for the hardcoded-in-Python constants (see module docstring) ---


def _extract_dict_literal(method, var_name: str) -> dict:
    source = textwrap.dedent(inspect.getsource(method))
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == var_name
        ):
            return ast.literal_eval(node.value)
    raise ValueError(
        f"Could not find dict literal {var_name!r} in {method.__qualname__}"
    )


def _extract_list_literals(method) -> list:
    source = textwrap.dedent(inspect.getsource(method))
    tree = ast.parse(source)
    return [
        ast.literal_eval(node) for node in ast.walk(tree) if isinstance(node, ast.List)
    ]


# --- discovery ---


def discover_combinations(lob_filter, version_filter, year_filter) -> list:
    combos = []
    for lob_dir in sorted(p for p in REFERENCE_DATA_ROOT.iterdir() if p.is_dir()):
        lob = lob_dir.name
        if lob_filter and lob != lob_filter:
            continue
        for version_dir in sorted(p for p in lob_dir.iterdir() if p.is_dir()):
            model_version = version_dir.name
            if version_filter and model_version != version_filter:
                continue
            for year_dir in sorted(p for p in version_dir.iterdir() if p.is_dir()):
                try:
                    year = int(year_dir.name)
                except ValueError:
                    continue
                if year_filter and year != year_filter:
                    continue
                combos.append((lob, model_version, year, year_dir))
    return combos


# --- per-entity row generators (from ReferenceFilesLoader's already-loaded attributes) ---


def rows_category_definitions(lob, mv, year, loader):
    for category, info in loader.category_definitions.items():
        yield {
            "lob": lob,
            "model_version": mv,
            "benefit_year": year,
            "category": category,
            "category_number": info.get("number", ""),
            "category_type": info.get("type", ""),
            "description": info.get("descr", ""),
        }


def rows_category_coefficients(lob, mv, year, loader):
    for key, pop_weights in loader.category_weights.items():
        if lob == "commercial":
            rate_group, category = key.split("_", 1)
        else:
            rate_group, category = "", key
        for population, coefficient in pop_weights.items():
            yield {
                "lob": lob,
                "model_version": mv,
                "benefit_year": year,
                "rate_group": rate_group,
                "category": category,
                "population": population,
                "coefficient": coefficient,
            }


def rows_hierarchy_definitions(lob, mv, year, loader):
    for category, info in loader.hierarchy_definitions.items():
        remove_codes = info.get("remove_code") or []
        if not remove_codes:
            yield {
                "lob": lob,
                "model_version": mv,
                "benefit_year": year,
                "dominant_category": category,
                "description": info.get("descr", ""),
                "subordinate_category": "",
            }
            continue
        for subordinate in remove_codes:
            yield {
                "lob": lob,
                "model_version": mv,
                "benefit_year": year,
                "dominant_category": category,
                "description": info.get("descr", ""),
                "subordinate_category": subordinate,
            }


def _rows_code_to_category(lob, mv, year, mapping, code_column):
    for code, categories in mapping.items():
        for category in categories:
            yield {
                "lob": lob,
                "model_version": mv,
                "benefit_year": year,
                code_column: code,
                "category": category,
            }


def rows_diagnosis_code_to_category(lob, mv, year, loader):
    yield from _rows_code_to_category(
        lob, mv, year, loader.category_map.get("diag", {}), "diagnosis_code"
    )


def rows_ndc_to_category(lob, mv, year, loader):
    yield from _rows_code_to_category(
        lob, mv, year, loader.category_map.get("ndc", {}), "ndc"
    )


def rows_procedure_code_to_category(lob, mv, year, loader):
    yield from _rows_code_to_category(
        lob, mv, year, loader.category_map.get("proc", {}), "procedure_code"
    )


def rows_acf_eligible_codes(lob, mv, year, loader):
    for code, categories in loader.category_map.get("acf", {}).items():
        code_type = "ndc" if code.isdigit() else "hcpcs"
        for category in categories:
            yield {
                "lob": lob,
                "model_version": mv,
                "benefit_year": year,
                "code": code,
                "code_type": code_type,
                "category": category,
            }


def rows_category_groups(lob, mv, year, loader):
    group_definitions = getattr(loader, "group_definitions", None)
    if not group_definitions:
        return
    for rate_group, mapping in group_definitions.items():
        for dropped_category, group_category in mapping.items():
            yield {
                "lob": lob,
                "model_version": mv,
                "benefit_year": year,
                "rate_group": rate_group,
                "group_category": group_category,
                "dropped_category": dropped_category,
            }


def rows_esrd_flat_score_tables(lob, mv, year, loader):
    for attr, label in (
        ("graft_duration_scores", "graft_duration"),
        ("institutional_graft_scores", "institutional_graft"),
        ("transplant_scores", "transplant"),
    ):
        table = getattr(loader, attr, None)
        if not table:
            continue
        for key, score in table.items():
            yield {
                "lob": lob,
                "model_version": mv,
                "benefit_year": year,
                "score_table": label,
                "key": key,
                "score": score,
            }


def rows_infant_severity_categories(lob, mv, year, model_class):
    lists = _extract_list_literals(model_class._determine_infant_severity_level)
    assert len(lists) == 5, (
        f"Expected 5 severity HCC lists in {model_class.__name__}._determine_infant_severity_level, "
        f"found {len(lists)} -- source shape may have changed, update the extractor"
    )
    for level, hccs in zip((5, 4, 3, 2, 1), lists):
        for hcc in hccs:
            yield {
                "lob": lob,
                "model_version": mv,
                "benefit_year": year,
                "category": hcc,
                "infant_severity_level": level,
            }


def rows_severe_illness_transplant_categories(lob, mv, year, model_class):
    lists = _extract_list_literals(
        model_class._determine_severe_illness_transplant_status
    )
    assert len(lists) == 2, (
        f"Expected 2 HCC lists (severe_illness, transplant) in "
        f"{model_class.__name__}._determine_severe_illness_transplant_status, found {len(lists)} "
        f"-- source shape may have changed, update the extractor"
    )
    severe_codes, transplant_codes = set(lists[0]), set(lists[1])
    for category in sorted(severe_codes | transplant_codes):
        yield {
            "lob": lob,
            "model_version": mv,
            "benefit_year": year,
            "category": category,
            "is_severe_illness": category in severe_codes,
            "is_transplant": category in transplant_codes,
        }


# --- model_adjustment_factors.csv: consolidates the hardcoded normalization/coding-intensity/CSR dicts ---


def rows_model_adjustment_factors(lob, mv, year):
    def row(factor_type, population_group, value):
        return {
            "lob": lob,
            "model_version": mv,
            "benefit_year": year,
            "factor_type": factor_type,
            "population_group": population_group,
            "value": value,
        }

    if lob == "commercial":
        from risk_adjustment_model.commercial_model import CommercialModel

        csr_dict = _extract_dict_literal(
            CommercialModel._get_csr_adjuster, "csr_adjuster_dict"
        )
        if year in csr_dict:
            for indicator, value in csr_dict[year].items():
                yield row("csr_adjuster", indicator, value)
        return

    from risk_adjustment_model.medicare_model import MedicareModel

    model_class = get_model_class(mv)

    if mv in RXHCC_VERSIONS:
        yield row("coding_intensity", "", 1)
        if mv in RXHCC_X_VERSIONS:
            norm_dict = _extract_dict_literal(
                model_class._get_normalization_factor, "norm_factor_dict"
            )
            if year in norm_dict:
                for channel, value in norm_dict[year].items():
                    yield row("normalization", channel, value)
        else:
            norm_dict = _extract_dict_literal(
                model_class._get_normalization_factor, "norm_factor_dict"
            )
            if year in norm_dict:
                yield row("normalization", "", norm_dict[year])
        return

    coding_intensity_dict = _extract_dict_literal(
        MedicareModel._get_coding_intensity_adjuster, "coding_intensity_dict"
    )
    if year in coding_intensity_dict:
        yield row("coding_intensity", "", coding_intensity_dict[year])

    if mv in ESRD_VERSIONS:
        dialysis_dict = _extract_dict_literal(
            model_class._get_normalization_factor, "dialysis_group_norm_factor_dict"
        )
        graft_dict = _extract_dict_literal(
            model_class._get_normalization_factor, "graft_group_norm_factor_dict"
        )
        if year in dialysis_dict:
            yield row("normalization", "dialysis", dialysis_dict[year])
        if year in graft_dict:
            yield row("normalization", "graft", graft_dict[year])
    else:
        norm_dict = _extract_dict_literal(
            model_class._get_normalization_factor, "norm_factor_dict"
        )
        if year in norm_dict:
            yield row("normalization", "", norm_dict[year])


ENTITY_FIELDNAMES = {
    "category_definitions": [
        "lob",
        "model_version",
        "benefit_year",
        "category",
        "category_number",
        "category_type",
        "description",
    ],
    "category_coefficients": [
        "lob",
        "model_version",
        "benefit_year",
        "rate_group",
        "category",
        "population",
        "coefficient",
    ],
    "hierarchy_definitions": [
        "lob",
        "model_version",
        "benefit_year",
        "dominant_category",
        "description",
        "subordinate_category",
    ],
    "diagnosis_code_to_category": [
        "lob",
        "model_version",
        "benefit_year",
        "diagnosis_code",
        "category",
    ],
    "ndc_to_category": ["lob", "model_version", "benefit_year", "ndc", "category"],
    "procedure_code_to_category": [
        "lob",
        "model_version",
        "benefit_year",
        "procedure_code",
        "category",
    ],
    "acf_eligible_codes": [
        "lob",
        "model_version",
        "benefit_year",
        "code",
        "code_type",
        "category",
    ],
    "category_groups": [
        "lob",
        "model_version",
        "benefit_year",
        "rate_group",
        "group_category",
        "dropped_category",
    ],
    "esrd_flat_score_tables": [
        "lob",
        "model_version",
        "benefit_year",
        "score_table",
        "key",
        "score",
    ],
    "infant_severity_categories": [
        "lob",
        "model_version",
        "benefit_year",
        "category",
        "infant_severity_level",
    ],
    "severe_illness_transplant_categories": [
        "lob",
        "model_version",
        "benefit_year",
        "category",
        "is_severe_illness",
        "is_transplant",
    ],
    "model_adjustment_factors": [
        "lob",
        "model_version",
        "benefit_year",
        "factor_type",
        "population_group",
        "value",
    ],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--lob", choices=["commercial", "medicare"], default=None)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()

    combos = discover_combinations(args.lob, args.model_version, args.year)
    if not combos:
        raise SystemExit(
            "No matching (lob, model_version, benefit_year) combinations found"
        )

    extracted_at_dt = datetime.now(timezone.utc)
    extracted_at = extracted_at_dt.isoformat()
    extracted_at_tag = extracted_at_dt.strftime("%Y%m%dT%H%M%SZ")
    tables = {entity: [] for entity in ENTITY_FIELDNAMES}

    for lob, mv, year, path in combos:
        category_prefix = "RXHCC" if mv in RXHCC_VERSIONS else "HCC"
        loader = ReferenceFilesLoader(path, lob=lob, category_prefix=category_prefix)

        tables["category_definitions"].extend(
            rows_category_definitions(lob, mv, year, loader)
        )
        tables["category_coefficients"].extend(
            rows_category_coefficients(lob, mv, year, loader)
        )
        tables["hierarchy_definitions"].extend(
            rows_hierarchy_definitions(lob, mv, year, loader)
        )
        tables["diagnosis_code_to_category"].extend(
            rows_diagnosis_code_to_category(lob, mv, year, loader)
        )
        tables["ndc_to_category"].extend(rows_ndc_to_category(lob, mv, year, loader))
        tables["procedure_code_to_category"].extend(
            rows_procedure_code_to_category(lob, mv, year, loader)
        )
        tables["acf_eligible_codes"].extend(
            rows_acf_eligible_codes(lob, mv, year, loader)
        )
        tables["category_groups"].extend(rows_category_groups(lob, mv, year, loader))
        tables["esrd_flat_score_tables"].extend(
            rows_esrd_flat_score_tables(lob, mv, year, loader)
        )
        tables["model_adjustment_factors"].extend(
            rows_model_adjustment_factors(lob, mv, year)
        )

        if mv in COMMERCIAL_VERSIONS:
            model_class = get_model_class(mv)
            tables["infant_severity_categories"].extend(
                rows_infant_severity_categories(lob, mv, year, model_class)
            )
            tables["severe_illness_transplant_categories"].extend(
                rows_severe_illness_transplant_categories(lob, mv, year, model_class)
            )

    filter_tag = "_".join(
        str(part) for part in (args.lob, args.year) if part is not None
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for entity, fieldnames in ENTITY_FIELDNAMES.items():
        rows = tables[entity]
        if not rows:
            continue
        name_parts = [entity]
        if filter_tag:
            name_parts.append(filter_tag)
        name_parts.append(extracted_at_tag)
        out_path = args.out_dir / f"{'_'.join(name_parts)}.csv"
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames + ["extracted_at"])
            writer.writeheader()
            for row in rows:
                row["extracted_at"] = extracted_at
                writer.writerow(row)
        print(f"{out_path.name}: {len(rows)} rows")


if __name__ == "__main__":
    main()

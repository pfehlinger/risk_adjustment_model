import importlib
import json
from pathlib import Path


def determine_age_band(age: int, age_ranges: list):
    range = None

    for age_range in age_ranges:
        age_band = age_range.split("_")
        lower, upper = 0, 999
        if len(age_band) == 1:
            lower = int(age_band[0])
            upper = lower + 1
        elif age_band[1] == "GT":
            lower = int(age_band[0])
        else:
            lower = int(age_band[0])
            upper = int(age_band[1]) + 1
        if lower <= age < upper:
            range = age_range
            break

    return range


def nvl(value, default):
    if value is not None:
        return value
    else:
        return default


def import_function(module_name, function_name):
    module = importlib.import_module(module_name, package="risk_adjustment_model")
    func = getattr(module, function_name)
    return func


def _get_data_directory(lob, version, model_year) -> Path:
    """
    Get the directory path to the reference data for the Medicare model.

    Returns:
        Path: The directory path to the reference data.
    """
    data_dir = importlib.resources.files(
        "risk_adjustment_model.reference_data"
    ).joinpath(f"{lob}")
    data_directory = data_dir / version / str(model_year)

    return data_directory


def _get_code_to_category_mapping(filepath, type) -> dict:
    """
    Retrieve diagnosis code to category mappings from a text file. It expects the file
    to be a csv in the layout of diag,category_nbr.

    Returns:
        dict: A dictionary mapping diagnosis codes to categories.
    """
    diag_to_category_map = {}
    with open(filepath / f"{type}_to_category_map.txt", "r") as file:
        for line in file:
            # Split the line based on the delimiter
            parts = line.strip().split("\t")
            diag = parts[0].strip()
            category = "HCC" + parts[1].strip()
            if diag not in diag_to_category_map:
                diag_to_category_map[diag] = []
            diag_to_category_map[diag].append(category)

    return diag_to_category_map


def _get_category_definitions(filepath) -> dict:
    """
    Retrieve category definitions from a JSON file.

    Returns:
        dict: A dictionary containing the category definitions.
    """
    with open(filepath / "category_definition.json") as file:
        category_definitions = json.load(file)

    return category_definitions


def _get_category_weights(filepath) -> dict:
    """
    Retrieve category weights from a CSV file.

    Returns:
        dict: A dictionary containing category weights.

    Notes:
        The CSV file is expected to have a header row specifying column
        names, and subsequent rows representing category weights. Each row should
        contain values separated by a delimiter, with one column representing
        the category and others representing different weights. The function constructs
        a nested dictionary where each category is mapped to a dictionary of weights.
    """
    weights = {}
    col_map = {}
    with open(filepath / "weights.csv", "r") as file:
        for i, line in enumerate(file):
            parts = line.strip().split(",")
            if i == 0:
                # Validate column order OR create column map
                for x, col in enumerate(parts):
                    col_map[col] = x
            else:
                pop_weight = {}
                category = parts[col_map["category"]]
                for key in col_map.keys():
                    if key != "category":
                        pop_weight[key] = float(parts[col_map[key]])
                weights[category] = pop_weight

    return weights

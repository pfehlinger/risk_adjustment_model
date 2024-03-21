import json
import importlib.resources
import os
from pathlib import Path


class Config:
    def __init__(self, version, year=None):
        self.version = version
        self.year = year
        self.model_year = self._get_model_year()
        self.data_directory = self._get_data_directory()
        self.hierarchy_definitions = self._get_hierarchy_definitions()
        self.category_definitions = self._get_category_definitions()
        self.diag_to_category_map = self._get_diagnosis_code_to_category_mapping()
        self.category_weights = self._get_category_weights()

    def _get_model_year(self) -> int:
        """
        The CMS Medicare Risk Adjustment model is implemented on an annual basis, and sometimes
        even if the categories do not change, weights, diagnosis code mappings, etc. can change.
        Therefore, to account for this, a year can be passed in to specify which mappings and weights
        to use. If nothing is passed in, the code will by default use the most recent valid year.

        Returns:
            int: The model year.

        Raises:
            FileNotFoundError: If the specified version directory or reference data
                            directory does not exist.

        """
        if not self.year:
            data_dir = importlib.resources.files(
                "risk_adjustment_model.reference_data"
            ).joinpath("medicare")
            dirs = os.listdir(data_dir / self.version)
            years = [int(dir) for dir in dirs]
            max_year = max(years)
        else:
            max_year = self.year

        return max_year

    def _get_data_directory(self) -> Path:
        """
        Get the directory path to the reference data for the Medicare model.

        Returns:
            Path: The directory path to the reference data.
        """
        data_dir = importlib.resources.files(
            "risk_adjustment_model.reference_data"
        ).joinpath("medicare")
        data_directory = data_dir / self.version / str(self.model_year)

        return data_directory

    def _get_hierarchy_definitions(self) -> dict:
        """
        Retrieve the hierarchy definitions from a JSON file.

        Returns:
            dict: A dictionary containing the hierarchy definitions.
        """
        with open(self.data_directory / "hierarchy_definition.json") as file:
            hierarchy_definitions = json.load(file)

        return hierarchy_definitions

    def _get_category_definitions(self) -> dict:
        """
        Retrieve category definitions from a JSON file.

        Returns:
            dict: A dictionary containing the category definitions.
        """
        with open(self.data_directory / "category_definition.json") as file:
            category_definitions = json.load(file)

        return category_definitions

    def _get_diagnosis_code_to_category_mapping(self) -> dict:
        """
        Retrieve diagnosis code to category mappings from a text file. It expects the file
        to be a csv in the layout of diag,category_nbr.

        Returns:
            dict: A dictionary mapping diagnosis codes to categories.
        """
        diag_to_category_map = {}
        with open(self.data_directory / "diag_to_category_map.txt", "r") as file:
            for line in file:
                # Split the line based on the delimiter
                parts = line.strip().split("|")
                diag = parts[0].strip()
                category = "HCC" + parts[1].strip()
                if diag not in diag_to_category_map:
                    diag_to_category_map[diag] = []
                diag_to_category_map[diag].append(category)

        return diag_to_category_map

    def _get_category_weights(self) -> dict:
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
        with open(self.data_directory / "weights.csv", "r") as file:
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

import json
import importlib.resources
import os
from pathlib import Path


class BaseModel:
    def __init__(self, lob, version, year=None):
        self.lob = lob
        self.version = version
        self.year = year
        self.model_year = self._get_model_year()
        self.data_directory = self._get_data_directory()
        self.hierarchy_definitions = self._get_hierarchy_definitions()

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
            ).joinpath(f"{self.lob}")
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
        ).joinpath(f"{self.lob}")
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

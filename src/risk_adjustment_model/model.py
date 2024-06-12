import importlib.resources
import os
from pathlib import Path
from typing import Union
from .reference_files_loader import ReferenceFilesLoader


class BaseModel:
    """
    Represents a base model for healthcare Risk Adjustment models. This should not be
    called directly.

    Attributes:
        lob (str): Line of Business (LOB) for the model.
        version (str): Version of the model.
        year (int): Year for which the model is implemented (default is None).
        model_year (int): The actual year of the model.
        data_directory (Path): Path to the directory containing model data.
        reference_files (ReferenceFilesLoader): Loader for reference files.
    """

    def __init__(self, lob: str, version: str, year: Union[int, None] = None):
        """
        Initializes a BaseModel with the provided parameters.

        Args:
            lob (str): Line of Business (LOB) for the model.
            version (str): Version of the model.
            year (int, optional): Year for which the model is implemented (default is None).
        """
        self.lob = lob
        self.version = version
        self.year = year
        self.model_year = self._get_model_year()
        self.data_directory = self._get_data_directory()
        self.reference_files = ReferenceFilesLoader(self.data_directory, lob)

    def _get_model_year(self) -> int:
        """
        Determine the model year based on the provided year or the most recent available year.
        If the year passed in is invalid, it raises a value error.

        Returns:
            int: The model year.

        Raises:
            FileNotFoundError: If the specified version directory or reference data
                                directory does not exist.
            ValueError: If the year passed in is not valid for the Line of Business (LOB) and version,
                        or if no year is passed and there are no valid years available.
        """
        data_dir = importlib.resources.files(
            "risk_adjustment_model.reference_data"
        ).joinpath(f"{self.lob}")
        dirs = os.listdir(data_dir / self.version)
        years = [int(dir) for dir in dirs]

        if not self.year:
            max_year = max(years)
        elif self.year not in years:
            raise ValueError(
                f"Input year is not valid for LOB: {self.lob}, version: {self.version}. Valid years are {years}"
            )
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

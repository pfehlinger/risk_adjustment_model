from typing import Type, Union, List
from .reference_files_loader import ReferenceFilesLoader


class Category:
    """
    Encapsulates metadata for a single category.

    This class represents a category with its metadata and the coefficient assigned to it
    for a specific model population.

    Attributes:
        reference_files: An instantiated ReferenceFilesLoader class containing category definitions and coefficients.
        risk_model_population (str): The population type of the beneficiary used for scoring.
        category (str): The name of the category, e.g. "HCC1", "F0_34".
        mapper_codes (list, optional): Mapping codes associated with the category (default is None).
        dropped_categories (list, optional): List of dropped categories (default is None).
        type (str):
        description (str):
        coefficient (float):
        number (int):

    """

    def __init__(
        self,
        reference_files: Type[ReferenceFilesLoader],
        risk_model_population: str,
        category: str,
        mapper_codes: Union[None, List[str]] = None,
        dropped_categories: Union[None, List[str]] = None,
    ):
        """
        Initialize a Category object.

        Args:
            reference_files: An instantiated ReferenceFilesLoader class containing category definitions and coefficients.
            risk_model_population (str): The population type of the beneficiary used for scoring.
            category (str): The name of the category, e.g. "HCC1", "F0_34".
            mapper_codes (list, optional): Mapping codes associated with the category (default is None).
            dropped_categories (list, optional): List of dropped categories (default is None)..

        """
        self.reference_files = reference_files
        self.risk_model_population = risk_model_population
        self.category = category
        self.mapper_codes = mapper_codes
        self.dropped_categories = dropped_categories
        self.type = self._get_type(category)
        self.description = self._get_description(category)
        self.coefficient = self._get_coefficient(category, risk_model_population)
        self.number = self._get_number(category)

    def _get_type(self, category: str):
        """
        Retrieve the type of the category from the reference files.

        Args:
            category (str): The name of the category.

        Returns:
            str: The type of the category.

        """
        return self.reference_files.category_definitions[category]["type"]

    def _get_description(self, category: str):
        """
        Retrieve the description of the category from the reference files.

        Args:
            category (str): The name of the category.

        Returns:
            str: The description of the category.

        """
        return self.reference_files.category_definitions[category]["descr"]

    def _get_coefficient(self, category: str, risk_model_population: str):
        """
        Retrieve the coefficient of the category for the given population from the reference files.

        Args:
            category (str): The name of the category.
            risk_model_population (str): The population type for the risk model.

        Returns:
            float: The coefficient of the category for the given population.

        """
        return self.reference_files.category_weights[category][risk_model_population]

    def _get_number(self, category: str):
        """
        Retrieve the number associated with the category from the reference files.
        For medicare this will be an integer, for commercial it will be a string due to
        some categories have 87_2.

        Args:
            category (str): The name of the category.

        Returns:
            int or str or None: The number associated with the category, or None if not found.

        """
        return self.reference_files.category_definitions[category].get("number", None)

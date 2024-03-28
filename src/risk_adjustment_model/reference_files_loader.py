import json
import os


class ReferenceFilesLoader:
    """
    A utility class for loading reference files necessary for risk adjustment models to run.
    This is needed from a code performance standpoint to read in files once, and then use
    across various classes.

    This class provides methods to load various reference files such as hierarchy definitions,
    category definitions, category weights, and category mappings from JSON and CSV files.

    Attributes:
        data_directory (str or Path): The directory path containing the reference files.
        hierarchy_definitions (dict): A dictionary containing the hierarchy definitions loaded
                                      from a JSON file.
        category_definitions (dict): A dictionary containing the category definitions loaded
                                     from a JSON file.
        category_weights (dict): A dictionary containing the category weights loaded from a CSV file.
                                 Each category is mapped to a dictionary of weights.
        category_map (dict): A dictionary containing various category mappings loaded from
                             different types of files.

    Methods:
        _get_hierarchy_definitions: Retrieve the hierarchy definitions from a JSON file.
        _get_category_definitions: Retrieve category definitions from a JSON file.
        _get_category_weights: Retrieve category weights from a CSV file.
        _get_category_mapping: Retrieve various category mappings from files in the data directory.
        _get_diag_code_to_category_mapping: Retrieve diagnosis code to category mappings from a text file.
        _get_ndc_code_to_category_mapping: Retrieve ndc code to category mappings from a text file.
        _get_proc_code_to_category_mapping: Retrieve procedure code to category mappings from a text file.
    """

    def __init__(self, filepath):
        self.data_directory = filepath
        self.hierarchy_definitions = self._get_hierarchy_definitions()
        self.category_definitions = self._get_category_definitions()
        self.category_weights = self._get_category_weights()
        self.category_map = self._get_category_mapping()

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

    def _get_category_mapping(self) -> dict:
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
        category_map = {}

        for filename in os.listdir(self.data_directory):
            if "category_map" in filename:
                file_type = filename.split("_")[0]

                if file_type == "diag":
                    category_map[file_type] = self._get_diag_code_to_category_mapping()
                elif file_type == "ndc":
                    category_map[file_type] = self._get_ndc_code_to_category_mapping()
                elif file_type == "proc":
                    category_map[file_type] = self._get_proc_code_to_category_mapping()

        return category_map

    def _get_diag_code_to_category_mapping(self) -> dict:
        """
        Retrieve diagnosis code to category mappings from a text file. It expects the file
        to be a text file in the layout of diag-category_nbr where they are separated by
        a tab character.

        Returns:
            dict: A dictionary mapping diagnosis codes to categories.
        """
        diag_to_category_map = {}
        with open(self.data_directory / "diag_to_category_map.txt", "r") as file:
            for line in file:
                # Split the line based on the delimiter
                parts = line.strip().split("\t")
                diag = parts[0].strip()
                category = "HCC" + parts[1].strip()
                if diag not in diag_to_category_map:
                    diag_to_category_map[diag] = []
                diag_to_category_map[diag].append(category)

        return diag_to_category_map

    def _get_ndc_code_to_category_mapping(self) -> dict:
        """
        Retrieve ndc code to category mappings from a text file. This is used by the
        ACA (Commercial) Models.

        Returns:
            dict: A dictionary mapping ndc codes to categories.
        """
        return None

    def _get_proc_code_to_category_mapping(self) -> dict:
        """
        Retrieve procedure code to category mappings from a text file. This is used by the
        ACA (Commercial) Models.

        Returns:
            dict: A dictionary mapping diagnosis codes to categories.
        """
        return None

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
        _get_acf_code_to_category_mapping: Retrieve ACF code to category mappings from a text file.
    """

    def __init__(self, filepath, lob=None, category_prefix="HCC"):
        self.data_directory = filepath
        self.hierarchy_definitions = self._get_hierarchy_definitions()
        self.category_definitions = self._get_category_definitions()
        self.category_weights = self._get_category_weights(lob)
        self.category_map = self._get_category_mapping(lob, category_prefix)
        if lob == "commercial":
            self.group_definitions = self._get_group_definitions()
        # ESRD-only flat lookup tables: these don't fit weights.csv's category-by-population
        # shape (they're small, single-value tables applied as scoring-time adjustments on top
        # of the normal category sum, not per-category coefficients -- see v24_esrd.py). Gated
        # on file presence rather than lob, since ESRD stays under lob="medicare".
        for attr, filename in (
            ("graft_duration_scores", "graft_duration_scores.csv"),
            ("institutional_graft_scores", "institutional_graft_scores.csv"),
            ("transplant_scores", "transplant_scores.csv"),
        ):
            if (self.data_directory / filename).exists():
                setattr(self, attr, self._get_flat_score_table(filename))

    def _get_hierarchy_definitions(self) -> dict:
        """
        Retrieve the hierarchy definitions from a JSON file.

        Returns:
            dict: A dictionary containing the hierarchy definitions.
        """
        with open(self.data_directory / "hierarchy_definition.json") as file:
            hierarchy_definitions = json.load(file)

        return hierarchy_definitions

    def _get_group_definitions(self) -> dict:
        """
        Retrieve the group definitions from a JSON file. This is applicable to Commercial
        only.

        Returns:
            dict: A dictionary containing the hierarchy definitions.
        """
        with open(self.data_directory / "group_definition.json") as file:
            group_definitions = json.load(file)

        return group_definitions

    def _get_category_definitions(self) -> dict:
        """
        Retrieve category definitions from a JSON file.

        Returns:
            dict: A dictionary containing the category definitions.
        """
        with open(self.data_directory / "category_definition.json") as file:
            category_definitions = json.load(file)

        return category_definitions

    def _get_category_weights(self, lob) -> dict:
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
        if lob == "commercial":
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
                        model_group = parts[col_map["model"]]
                        for key in col_map.keys():
                            if key not in ["category", "model"]:
                                pop_weight[key] = float(parts[col_map[key]])
                        weights[model_group + "_" + category] = pop_weight
        else:
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

    def _get_flat_score_table(self, filename: str) -> dict:
        """
        Retrieve a flat key->score lookup table from a two-column CSV file (key, score), used
        for ESRD's graft-duration, institutional-graft-duration, and flat transplant-month score
        tables.

        Args:
            filename (str): Name of the CSV file within data_directory, e.g. "transplant_scores.csv".

        Returns:
            dict: A dictionary mapping the key column (e.g. "GE65_DUR4_9_FBD",
                 "TRANSPLANT_KIDNEY_ONLY_1M") to its float score.
        """
        table = {}
        with open(self.data_directory / filename, "r") as file:
            for i, line in enumerate(file):
                if i == 0:
                    continue
                key, score = line.strip().split(",")
                table[key] = float(score)

        return table

    def _get_category_mapping(self, lob, category_prefix="HCC") -> dict:
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
                    category_map[file_type] = self._get_diag_code_to_category_mapping(
                        lob, category_prefix
                    )
                elif file_type == "ndc":
                    category_map[file_type] = self._get_ndc_code_to_category_mapping()
                elif file_type == "proc":
                    category_map[file_type] = self._get_proc_code_to_category_mapping()
                elif file_type == "acf":
                    category_map[file_type] = self._get_acf_code_to_category_mapping()

        return category_map

    def _get_diag_code_to_category_mapping(self, lob, category_prefix="HCC") -> dict:
        """
        Retrieve diagnosis code to category mappings from a text file. It expects the file
        to be a text file in the layout of diag-category_nbr where they are separated by
        a tab character.

        Args:
            lob (str): Line of Business, "commercial" builds "HHS_HCC..." names regardless
                       of category_prefix; any other LOB uses category_prefix.
            category_prefix (str): Prefix prepended to the bare category number for non-Commercial
                                    LOBs, e.g. "HCC" for CMS-HCC/ESRD, "RXHCC" for RxHCC.

        Returns:
            dict: A dictionary mapping diagnosis codes to categories.
        """
        diag_to_category_map = {}
        with open(self.data_directory / "diag_to_category_map.txt", "r") as file:
            for line in file:
                # Split the line based on the delimiter
                parts = line.strip().split("\t")
                diag = parts[0].strip()
                if lob == "commercial":
                    if "." in parts[1]:
                        category = "HHS_HCC" + parts[1].strip().replace(".", "_").zfill(
                            5
                        )
                    else:
                        category = "HHS_HCC" + parts[1].strip().zfill(3)
                else:
                    category = category_prefix + parts[1].strip()
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
        ndc_to_category_map = {}
        with open(self.data_directory / "ndc_to_category_map.txt", "r") as file:
            for line in file:
                # Split the line based on the delimiter
                parts = line.strip().split("\t")
                ndc = parts[0].strip()
                category = "RXC_" + parts[1].strip().zfill(2)

                if ndc not in ndc_to_category_map:
                    ndc_to_category_map[ndc] = []
                ndc_to_category_map[ndc].append(category)
        return ndc_to_category_map

    def _get_proc_code_to_category_mapping(self) -> dict:
        """
        Retrieve procedure code to category mappings from a text file. This is used by the
        ACA (Commercial) Models.

        Returns:
            dict: A dictionary mapping diagnosis codes to categories.
        """
        proc_to_category_map = {}
        with open(self.data_directory / "proc_to_category_map.txt", "r") as file:
            for line in file:
                # Split the line based on the delimiter
                parts = line.strip().split("\t")
                proc = parts[0].strip()
                category = "RXC_" + parts[1].strip().zfill(2)

                if proc not in proc_to_category_map:
                    proc_to_category_map[proc] = []
                proc_to_category_map[proc].append(category)
        return proc_to_category_map

    def _get_acf_code_to_category_mapping(self) -> dict:
        """
        Retrieve Affiliated Cost Factor (ACF) code to category mappings from a text file.
        This is used by the ACA (Commercial) Models, and was introduced starting with the
        2026 benefit year, so older model years won't have this file (it's optional).

        Returns:
            dict: A dictionary mapping NDC/HCPCS codes to categories.
        """
        acf_to_category_map = {}
        with open(self.data_directory / "acf_to_category_map.txt", "r") as file:
            for line in file:
                parts = line.strip().split("\t")
                code = parts[0].strip()
                category = parts[1].strip()

                if code not in acf_to_category_map:
                    acf_to_category_map[code] = []
                acf_to_category_map[code].append(category)
        return acf_to_category_map

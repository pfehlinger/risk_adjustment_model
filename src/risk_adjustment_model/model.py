import importlib.resources
import os
from pathlib import Path
from .reference_files_loader import ReferenceFilesLoader
from .utilities import determine_age_band
from .beneficiary import MedicareBeneficiary
from .category import Category
from .result import ScoringResult
from .mapper import DxCodeCategory


class BaseModel:
    def __init__(self, lob, version, year=None):
        self.lob = lob
        self.version = version
        self.year = year
        self.model_year = self._get_model_year()
        self.data_directory = self._get_data_directory()
        self.reference_files = ReferenceFilesLoader(self.data_directory)

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


class MedicareModel(BaseModel):
    """
    This is the foundation for Medicare Models. It is not to be called directly. It loads all relevant information for that model
    and year as class attributes.


    How this class works:
    1. Instantiate the class with set up information: model version, year optional if same model version has multiple years and differences
    between years. If year is null, going to pull the most recent
    2. Instantiating the class loads all reference information into memory and it is ready to go.
    3. Call the score method passing in necessary values
    4. Since each model may have its own nuances, want to put each model in its own class that then handles certain category stuff
    """

    def __init__(self, version: str, year=None):
        super().__init__("medicare", version, year)
        self.coding_intensity_adjuster = self._get_coding_intensity_adjuster(
            self.model_year
        )
        self.normalization_factor = self._get_normalization_factor(self.model_year)

    def score(
        self,
        gender: str,
        orec: str,
        medicaid: bool,
        diagnosis_codes=[],
        age=None,
        dob=None,
        population="CNA",
        verbose=False,
    ) -> dict:
        """
        Determines the risk score for the inputs. Entry point for end users.
        Steps:
        1. Use beneficiary information to get the demographic categories
        2. Using diagnosis code inputs and beneficiary information get the diagnosis code to
           category relationship
        3. Get the unique set of categories from diagnosis codes
        4. Apply hierarchies
        5. Determine disease interactions


        Args:
            gender (str): Gender of the beneficiary being scored, valid values M or F.
            orec (str): Original Entitlement Reason Code of the beneficiary. See: https://bluebutton.cms.gov/assets/ig/ValueSet-orec.html for valid values
            medicaid (bool): Beneficiary medicaid status, True or False
            diagnosis_codes (list): List of the diagnosis codes associated with the beneficiary
            age (int): Age of the beneficiary, can be None.
            dob (str): Date of birth of the beneficiary, can be None
            population (str): Population of beneficiary being scored, valid values are CNA, CND, CPA, CPD, CFA, CFD, INS, NE
            verbose (bool): Indicates if trimmed output or full output is desired

        Returns:
            dict: A dictionary containing the score information.
        """

        beneficiary = MedicareBeneficiary(gender, orec, medicaid, population, age, dob)
        demo_categories = self.determine_demographic_cats(beneficiary)

        if diagnosis_codes:
            cat_dict = {}
            dx_categories = self._get_dx_categories(diagnosis_codes, beneficiary)
            # Some diagnosis codes go to more than one category thus the category is a list
            # and it is a two step process to unpack them
            unique_disease_cats = set(
                category
                for dx_code in dx_categories
                for category in dx_code.category
                if category is not None and category != "NA"
            )

            for category in unique_disease_cats:
                # This is done to obtain a consistent output for diagnosis map
                # If there are no diagnosis codes mapping to the category it should
                # return None, as opposed to an empty list. The below statement making
                # the map would create an empty list, thus the if statement following
                # to catch that and modify it
                diagnosis_map = [
                    dx_code.mapper_code
                    for dx_code in dx_categories
                    if category in dx_code.category
                ]
                cat_dict[category] = diagnosis_map
        else:
            cat_dict = {}
            unique_disease_cats = None

        if unique_disease_cats:
            unique_categories = demo_categories + list(unique_disease_cats)
        else:
            unique_categories = demo_categories

        categories = [
            Category(
                self.reference_files,
                beneficiary.risk_model_population,
                category,
                cat_dict.get(category),
            )
            for category in unique_categories
        ]
        categories = self._apply_hierarchies(categories)
        categories = self._determine_disease_interactions(categories, beneficiary)

        score_raw = sum([category.coefficient for category in categories])
        disease_score_raw = sum(
            [
                category.coefficient
                for category in categories
                if "disease" in category.type
            ]
        )
        demographic_score_raw = sum(
            [
                category.coefficient
                for category in categories
                if "demographic" in category.type
            ]
        )

        category_details = self._build_category_details(categories, verbose)

        output_dict = ScoringResult(
            gender=beneficiary.gender,
            orec=beneficiary.orec,
            medicaid=beneficiary.medicaid,
            age=beneficiary.age,
            dob=beneficiary.dob,
            diagnosis_codes=diagnosis_codes,
            year=self.year,
            population=beneficiary.population,
            risk_model_age=beneficiary.risk_model_age,
            risk_model_population=beneficiary.risk_model_population,
            model_version=self.version,
            model_year=self.model_year,
            coding_intensity_adjuster=self.coding_intensity_adjuster,
            normalization_factor=self.normalization_factor,
            score_raw=score_raw,
            disease_score_raw=disease_score_raw,
            demographic_score_raw=demographic_score_raw,
            score=self._apply_norm_factor_coding_adj(score_raw),
            disease_score=self._apply_norm_factor_coding_adj(disease_score_raw),
            demographic_score=self._apply_norm_factor_coding_adj(demographic_score_raw),
            category_list=[category.category for category in categories],
            category_details=category_details,
        )

        return output_dict

    def determine_demographic_cats(self, beneficiary) -> list:
        """Need to do the static typing stuff above for gender, age, orec"""
        # NEED TO DO LTIMEDICAID
        demo_cats = []
        demo_cats.append(
            self._determine_demographic_cats(
                beneficiary.age, beneficiary.gender, beneficiary.population
            )
        )
        demo_int = self._determine_demographic_interactions(
            beneficiary.gender, beneficiary.orig_disabled, beneficiary.medicaid
        )
        if demo_int:
            demo_cats.extend(demo_int)

        return demo_cats

    def _apply_hierarchies(self, categories: list) -> dict:
        """
        Takes in a list containing category objects and removes categories that fall
        into hierarchies as outlined in the hierarchy_definition file.

        Returns:
            list a of category objects
        """
        category_list = [category.category for category in categories]
        dropped_codes_total = []

        for category in categories:
            dropped_codes = []
            if category.category in self.reference_files.hierarchy_definitions.keys():
                for remove_category in self.reference_files.hierarchy_definitions[
                    category.category
                ]["remove_code"]:
                    if remove_category in category_list:
                        dropped_codes.append(remove_category)
                        dropped_codes_total.append(remove_category)

            if dropped_codes:
                category.dropped_categories = dropped_codes

        # Remove objects from list
        final_categories = [
            category
            for category in categories
            if category.category not in dropped_codes_total
        ]

        return final_categories

    def _build_category_details(self, categories, verbose):
        # Combine the dictionaries to make output
        category_details = {}
        for category in categories:
            if verbose:
                category_details[category.category] = {
                    "coefficient": category.coefficient,
                    "type": category.type,
                    "category_number": category.number,
                    "category_description": category.description,
                    "dropped_categories": category.dropped_categories,
                    "diagnosis_map": category.mapper_codes,
                }
            else:
                category_details[category.category] = {
                    "coefficient": category.coefficient,
                    "diagnosis_map": category.mapper_codes,
                }

        return category_details

    # --- Helper methods which should not be overwritten ---

    def _apply_norm_factor_coding_adj(self, score: float) -> float:
        return round(
            round(score * self.coding_intensity_adjuster, 4)
            / self.normalization_factor,
            4,
        )

    def _get_coding_intensity_adjuster(self, year) -> float:
        """

        Returns:
            float: The coding intensity adjuster.
        """
        coding_intensity_dict = {
            2020: 0.941,
            2021: 0.941,
            2022: 0.941,
            2023: 0.941,
            2024: 0.941,
            2025: 0.941,
        }
        if coding_intensity_dict.get(year):
            coding_intensity_adjuster = coding_intensity_dict.get(year)
        else:
            coding_intensity_adjuster = 1

        return coding_intensity_adjuster

    def _get_normalization_factor(self, version, year, model_group="C") -> float:
        """

        C = Commmunity
        D = Dialysis
        G = Graft

        Returns:
            float: The normalization factor.
        """
        norm_factor_dict = {
            "v24": {
                2020: {"C": 1.069},
                2021: {"C": 1.097},
                2022: {"C": 1.118},
                2023: {"C": 1.127},
                2024: {"C": 1.146},
                2025: {"C": 1.153},
            },
            "v28": {
                2024: {"C": 1.015},
                2025: {"C": 1.045},
            },
        }
        try:
            normalization_factor = norm_factor_dict[version][year][model_group]
        except KeyError:
            normalization_factor = 1

        return normalization_factor

    def _get_dx_categories(self, diagnosis_codes, beneficiary):
        dx_categories = [
            DxCodeCategory(self.reference_files.category_map, diagnosis_code)
            for diagnosis_code in diagnosis_codes
        ]

        for dx in dx_categories:
            edit_category = self.age_sex_edits(
                beneficiary.gender, beneficiary.age, dx.mapper_code
            )
            if edit_category:
                dx.category = edit_category

        return dx_categories

    # -- To be overwritten by each model class as need
    def _determine_disease_interactions(self, categories: list, beneficiary) -> list:
        interaction_list = []
        category_count = self._get_payment_count_categories(categories)
        if category_count:
            interaction_list.append(category_count)

        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]

        interactions.append(categories)

        return interactions

    def _get_payment_count_categories(self, categories: list):
        """"""
        category_count = len(categories)
        category = None
        if category_count > 9:
            category = "D10P"
        elif category_count > 0:
            category = f"D{category_count}"

        return category

    def _determine_demographic_cats(self, age, gender, population):
        """
        This may need to be overwritten depending on the mechanices of the model.
        Ranges may change, the population may change, etc.
        """
        if population[:2] == "NE":
            demo_category_ranges = [
                "0_34",
                "35_44",
                "45_54",
                "55_59",
                "60_64",
                "65",
                "66",
                "67",
                "68",
                "69",
                "70_74",
                "75_79",
                "80_84",
                "85_89",
                "90_94",
                "95_GT",
            ]
        else:
            demo_category_ranges = [
                "0_34",
                "35_44",
                "45_54",
                "55_59",
                "60_64",
                "65_69",
                "70_74",
                "75_79",
                "80_84",
                "85_89",
                "90_94",
                "95_GT",
            ]

        demographic_category_range = determine_age_band(age, demo_category_ranges)

        if population[:2] == "NE":
            demographic_category = f"NE{gender}{demographic_category_range}"
        else:
            demographic_category = f"{gender}{demographic_category_range}"

        return demographic_category

    def _determine_demographic_interactions(self, gender, orig_disabled, medicaid):
        """
        Depending on model this may change
        """
        demo_interactions = []
        if gender == "F" and orig_disabled == 1:
            demo_interactions.append("OriginallyDisabled_Female")
        elif gender == "M" and orig_disabled == 1:
            demo_interactions.append("OriginallyDisabled_Male")

        if medicaid:
            demo_interactions.append("LTIMCAID")

        return demo_interactions

    def age_sex_edits(self, gender, age, diagnosis_code):
        return ["NA"]

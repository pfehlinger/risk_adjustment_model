from .config import Config
from .beneficiary import MedicareBeneficiary
from .category import Category
from .output import ScoringResults
from .diagnosis_code import MedicareDxCodeCategory
from .utilities import import_function


class MedicareModel:
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
        self.config = Config(version, year)
        self.coding_intensity_adjuster = self._get_coding_intensity_adjuster(
            self.config.model_year
        )
        # PF: This will break for the models that have different normalization factors, will have to refactor once implemented
        self.normalization_factor = self._get_normalization_factor(
            version, self.config.model_year
        )
        self._determine_demographic_cats = import_function(
            "." + self.config.version, "determine_demographic_cats"
        )
        self._determine_demographic_interactions = import_function(
            "." + self.config.version, "determine_demographic_interactions"
        )
        self._determine_disease_interactions = import_function(
            "." + self.config.version, "determine_disease_interactions"
        )

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
            dx_categories = [
                MedicareDxCodeCategory(self.config, diagnosis_code, beneficiary)
                for diagnosis_code in diagnosis_codes
            ]
            # Some diagnosis codes go to more than one category thus the category is a list
            # and it is a two step process to unpack them
            unique_disease_cats = set(
                category
                for dx_code in dx_categories
                for category in dx_code.category
                if category != "NA"
            )
            hier_category_dict, disease_categories = self._apply_hierarchies(
                unique_disease_cats
            )
            interactions = self._determine_disease_interactions(
                disease_categories, beneficiary.disabled
            )
            if interactions:
                disease_categories.extend(interactions)

            for category in disease_categories:
                cat_dict[category] = {
                    "dropped_categories": hier_category_dict.get(category, None),
                    "diagnosis_map": [
                        dx_code.diagnosis_code
                        for dx_code in dx_categories
                        if dx_code.category == category
                    ],
                }
        else:
            disease_categories = None
            cat_dict = {}

        if disease_categories:
            unique_categories = demo_categories + disease_categories
        else:
            unique_categories = demo_categories
        categories = [
            Category(self.config, beneficiary.risk_model_population, category)
            for category in unique_categories
        ]

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

        category_details = self._build_category_details(categories, cat_dict, verbose)

        output_dict = ScoringResults(
            gender=beneficiary.gender,
            orec=beneficiary.orec,
            medicaid=beneficiary.medicaid,
            age=beneficiary.age,
            dob=beneficiary.dob,
            diagnosis_codes=diagnosis_codes,
            year=self.config.year,
            population=beneficiary.population,
            risk_model_age=beneficiary.risk_model_age,
            risk_model_population=beneficiary.risk_model_population,
            model_version=self.config.version,
            model_year=self.config.model_year,
            coding_intensity_adjuster=self.coding_intensity_adjuster,
            normalization_factor=self.normalization_factor,
            score_raw=score_raw,
            disease_score_raw=disease_score_raw,
            demographic_score_raw=demographic_score_raw,
            score=self._apply_norm_factor_coding_adj(score_raw),
            disease_score=self._apply_norm_factor_coding_adj(disease_score_raw),
            demographic_score=self._apply_norm_factor_coding_adj(demographic_score_raw),
            category_list=unique_categories,
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
            beneficiary.gender, beneficiary.orig_disabled
        )
        if demo_int:
            demo_cats.append(demo_int)

        return demo_cats

    def _apply_hierarchies(self, categories: set) -> dict:
        """
        Takes in a unique set of categories and removes categories that fall into
        hierarchies as outlined in the hierarchy_definition file.

        Returns:
            dict containing the remaining categories and any categories "dropped"
            by that category.

        """
        category_list = list(categories)
        categories_dict = {}
        dropped_codes_total = []

        # Patch for V28 Heart Conditions
        if self.config.version == "v28":
            if "HCC223" in category_list and not any(
                category in category_list
                for category in ["HCC221", "HCC222", "HCC224", "HCC225", "HCC226"]
            ):
                category_list.remove("HCC223")

        for category in category_list:
            dropped_codes = []
            if category in self.config.hierarchy_definitions.keys():
                for remove_category in self.config.hierarchy_definitions[category][
                    "remove_code"
                ]:
                    try:
                        category_list.remove(remove_category)
                    except ValueError:
                        pass
                    else:
                        dropped_codes.append(remove_category)
                        dropped_codes_total.append(remove_category)
                if not dropped_codes:
                    categories_dict[category] = None
                else:
                    categories_dict[category] = dropped_codes

        # Fill in remaining categories
        for category in category_list:
            if category not in dropped_codes_total:
                categories_dict[category] = None

        return categories_dict, category_list

    def _build_category_details(self, categories, category_dict, verbose):
        # Combine the dictionaries to make output
        category_details = {}
        for category in categories:
            if verbose:
                category_details[category.category] = {
                    "coefficient": category.coefficient,
                    "type": category.type,
                    "category_number": category.number,
                    "category_description": category.description,
                    "dropped_categories": category_dict.get(category, None),
                    "diagnosis_map": category_dict.get(category, None),
                }
            else:
                category_details[category.category] = {
                    "coefficient": category.coefficient,
                    "diagnosis_map": category_dict.get(category, None),
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

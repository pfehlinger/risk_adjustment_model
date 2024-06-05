import importlib.resources
import os
from pathlib import Path
from typing import Union, Type, List
from .reference_files_loader import ReferenceFilesLoader
from .utilities import determine_age_band
from .beneficiary import MedicareBeneficiary, CommercialBeneficiary
from .category import Category
from .result import CommercialScoringResult
from .mapper import DxCodeCategory


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


class CommercialModel(BaseModel):
    """
    This is the foundation class for Medicare Models. It is not to be called directly. It loads all
    relevant information for that model and year as class attributes.

    How this class works:
    1.  Instantiate the class with set up information: model version and year (optional).
        If year is None, the code will determine the most recent year and use that.
    2.  Instantiating the class loads all reference information into memory for performance purposes.
    3.  The entry point is the "score" method.
    4.  Since each model has its own nuances, each model is its own class inheriting from this class.

    Attributes:


    Notes:
        In terms of inheritance for child classes and how it relates to methods, the code is
        organizaed in the following fashion:

        Methods strongly advised against overwriting:
            score
            _build_category_details
        Methods unlikely needing overwriting but could happen based on needs:
            _apply_hierarchies
            _determine_demographic_categories
            _get_dx_categories
            _get_coding_intensity_adjuster
        Methods likely needing overwriting, e.g.:
            _determine_age_gender_category
            _determine_disease_interactions
            _age_sex_edits
            _get_normalization_factor
        Helper methods to not override, e.g.: _apply_norm_factor_coding_adj
    """

    def __init__(self, version: str, year: Union[int, None] = None):
        super().__init__(lob="commercial", version=version, year=year)

    def score(
        self,
        gender: str,
        metal_level: str,
        csr_indicator: int,
        enrollment_months: int,
        diagnosis_codes: Union[List[str], None] = None,
        age: Union[int, None] = None,
        dob: Union[str, None] = None,
        last_enrollment_date: Union[str, None] = None,
        verbose: bool = False,
    ) -> Type[CommercialScoringResult]:
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
            ScoringResult: An instantiated object of ScoringResult class.
        """
        beneficiary = CommercialBeneficiary(
            gender,
            metal_level,
            enrollment_months,
            csr_indicator,
            age,
            dob,
            self.model_year,
            last_enrollment_date,
        )
        # PF: Don't love this here, will want to refactor
        self.csr_adjuster = self._get_csr_adjuster(self.model_year, csr_indicator)

        # The way the Commercial Model is designed is that the model determines categories
        # and score is based on the age group in addition to the diagnosis codes.
        # To handle this the category map contains as a key agegroup_hcc, this map now
        # needs to be pared down to the relevant model now that we know the age group
        # associated with the scoring run
        self.reference_files.category_weights = {
            key.split("_", 1)[1]: self.reference_files.category_weights[key]
            for key in self.reference_files.category_weights.keys()
            if key.startswith(beneficiary.risk_model_age_group)
        }

        demo_categories = self._determine_demographic_categories(beneficiary)

        if diagnosis_codes:
            cat_dict = {}
            dx_categories = self._get_dx_categories(diagnosis_codes, beneficiary)
            # Some diagnosis codes go to more than one category thus the category is a list
            # and it is a two step process to unpack them
            unique_disease_cats = set(
                category
                for dx_code in dx_categories
                for category in dx_code.categories
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
                    if category in dx_code.categories
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
        categories = self._apply_groups(categories, beneficiary)

        # There is a scenario in the model where the age of an infant is 0, but the infant
        # has a maturity level of Age1. In this case, the infant is supposed to get the
        # Age1_Male demographic category. This breaks the assumed convention of demographic
        # categories being indepedent of the disease categories. The code here addresses
        # This scenario
        if beneficiary.risk_model_age_group == "Infant":
            category_list = [category.category for category in categories]
            maturity_status = self._determine_infant_maturity_status(category_list)

            if beneficiary.age == 0 and maturity_status == "Age1":
                # Append Age1_Male to category list
                categories.append(
                    Category(
                        self.reference_files,
                        beneficiary.risk_model_population,
                        "Age1_Male",
                        cat_dict.get("Age1_Male"),
                    )
                )
                # Remove Age0_Male from list
                categories = [
                    category
                    for category in categories
                    if category.category not in "Age0_Male"
                ]

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

        results = CommercialScoringResult(
            gender=beneficiary.gender,
            metal_level=beneficiary.metal_level,
            enrollment_months=beneficiary.enrollment_months,
            csr_indicator=beneficiary.csr_indicator,
            age=beneficiary.age,
            dob=beneficiary.dob,
            last_enrollment_date=beneficiary.last_enrollment_date,
            diagnosis_codes=diagnosis_codes,
            year=self.year,
            risk_model_age=beneficiary.risk_model_age,
            risk_model_population=beneficiary.risk_model_population,
            model_version=self.version,
            model_year=self.model_year,
            csr_adjuster=self.csr_adjuster,
            score_raw=score_raw,
            disease_score_raw=disease_score_raw,
            demographic_score_raw=demographic_score_raw,
            score=self._apply_csr_adj(score_raw),
            disease_score=self._apply_csr_adj(disease_score_raw),
            demographic_score=self._apply_csr_adj(demographic_score_raw),
            category_list=[category.category for category in categories],
            category_details=category_details,
        )

        return results

    def _build_category_details(
        self, categories: List[Type[Category]], verbose: bool
    ) -> dict:
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

    # --- Methods which may need to be overwritten but unlikely to be overwritten ---

    def _determine_demographic_categories(
        self, beneficiary: Type[CommercialBeneficiary]
    ) -> List[str]:
        """
        Determine demographic categories based on beneficiary attributes.

        Args:
            beneficiary (Type[CommercialBeneficiary]): An instance of CommercialBeneficiary.

        Returns:
            list: A list containing demographic categories.
        """
        demo_cats = []
        demo_cats.append(
            self._determine_age_gender_category(beneficiary.age, beneficiary.gender)
        )
        return demo_cats

    def _apply_hierarchies(
        self, categories: List[Type[Category]]
    ) -> List[Type[Category]]:
        """
        Filters out categories falling into hierarchies per the model hierarchy_definition file.

        Args:
            categories (List[Type[Category]]): List of category objects to process.

        Returns:
            List[Type[Category]]: List of category objects after filtering.

        Notes:
            For each category, the codes dropped are tracked and assigned to the
            attribute "dropped_categories" of the category object.
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

    def _apply_groups(
        self, categories: List[Type[Category]], beneficiary
    ) -> List[Type[Category]]:
        """
        Assigns groups based on the "remove_codes" the member has and
        adds the group category and filters out the normal categories per the model
        group_definition file.

        Args:
            categories (List[Type[Category]]): List of category objects to process.

        Returns:
            List[Type[Category]]: List of category objects after filtering.

        Notes:
            For each category, the codes dropped are tracked and assigned to the
            attribute "dropped_categories" of the category object.
        """
        category_list = [category.category for category in categories]
        dropped_codes_total = []
        group_categories = []

        for category in categories:
            dropped_codes = []
            if category.category in self.reference_files.group_definitions.keys():
                dropped_codes.append(category.category)
                group_category = Category(
                    self.reference_files,
                    beneficiary.risk_model_population,
                    self.reference_files.group_definitions[category.category],
                    dropped_categories=dropped_codes,
                )
                group_categories.append(group_category)

        # Remove objects from list
        final_categories = [
            category
            for category in categories
            if category.category not in dropped_codes_total
        ]
        # Add the group categories
        final_categories.extend(group_categories)

        return final_categories

    def _get_dx_categories(
        self, diagnosis_codes: List[str], beneficiary: Type[MedicareBeneficiary]
    ) -> List[Type[DxCodeCategory]]:
        """
        Generates diagnosis code to categories relationships based on provided diagnosis codes
        and beneficiary information.

        Args:
            diagnosis_codes (List[str]): List of diagnosis codes.
            beneficiary (Type[MedicareBeneficiary]): Instance of MedicareBeneficiary representing the beneficiary information.

        Returns:
            List[Type[DxCodeCategory]]: List of DxCodeCategory objects representing the diagnosis code categories.
        """
        dx_categories = [
            DxCodeCategory(self.reference_files.category_map, diagnosis_code)
            for diagnosis_code in diagnosis_codes
        ]

        for dx in dx_categories:
            edit_category = self._age_sex_edits(
                beneficiary.gender, beneficiary.age, dx.mapper_code
            )
            if edit_category:
                dx.categories = edit_category

        return dx_categories

    def _get_csr_adjuster(self, year: int, csr_indicator: int) -> float:
        """
        Gets the appropriate coding intensity adjuster for the model year as outlined by
        CMS in their annual Annoucements:
        https://www.cms.gov/medicare/payment/medicare-advantage-rates-statistics/announcements-and-documents

        Returns:
            float: The coding intensity adjuster.

        Notes:
            In the documents, the coding intensity adjuster is listed as a small decimal, e.g.
            .059. In scoring calculations, the adjuster is applied by doing score * (1-.059).
            Thus, the below already represents the 1-.059 for convenience.
            Most years, the coding intensity adjuster is the statuatory minimum of .059.
        """
        csr_adjuster_dict = {
            2019: {1: 1.00, 2: 1.07, 3: 1.12, 4: 1.15},
            2020: {1: 1.00, 2: 1.07, 3: 1.12, 4: 1.15},
            2021: {1: 1.00, 2: 1.07, 3: 1.12, 4: 1.15},
            2022: {1: 1.00, 2: 1.07, 3: 1.12, 4: 1.15},
            2023: {1: 1.00, 2: 1.07, 3: 1.12, 4: 1.15},
            2024: {1: 1.00, 2: 1.07, 3: 1.12, 4: 1.15},
            2025: {1: 1.00, 2: 1.07, 3: 1.12, 4: 1.15},
        }

        if csr_adjuster_dict.get(year):
            csr_adjuster = csr_adjuster_dict[year].get(csr_indicator, 1.00)
        else:
            csr_adjuster = 1.00

        return csr_adjuster

    # --- Methods likely to be overwritten by each model class ---

    # def _apply_groups():

    def _determine_age_gender_category(self, age: int, gender: str) -> str:
        """
        Determines the demographic category based on age, gender, and population.

        Args:
            age (int): Age of the individual.
            gender (str): Gender of the individual ('M' for male, 'F' for female).

        Returns:
            str: Demographic category based on age and gender.
        """

        if age < 2:
            # Infants all are consider "Male" from a model standpoint
            demographic_category = f"Age{age}_Male"
        else:
            demo_category_ranges = [
                "2_4",
                "5_9",
                "10_14",
                "15_20",
                "21_24",
                "25_29",
                "30_34",
                "35_39",
                "40_44",
                "45_49",
                "50_54",
                "55_59",
                "60_GT",
            ]

            demographic_category_range = determine_age_band(age, demo_category_ranges)
            demographic_category = f"{gender}AGE_LAST_{demographic_category_range}"

        return demographic_category

    def _determine_disease_interactions(
        self, categories: List[Type[Category]], beneficiary: Type[MedicareBeneficiary]
    ) -> List[Type[Category]]:
        """
        Determines disease interactions based on provided Category objects and beneficiary information.
        Placeholder to be overwritten by child classes.

        Args:
            categories (List[Type[Category]]): List of Category objects representing disease categories.
            beneficiary (Type[MedicareBeneficiary]): Instance of MedicareBeneficiary representing the beneficiary information.

        Returns:
            List[Type[Category]]: List of Category objects representing the disease interactions.
        """
        interaction_list = []

        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]

        interactions.append(categories)

        return interactions

    def _age_sex_edits(
        self, gender: str, age: int, diagnosis_code: str
    ) -> Union[List[str], None]:
        """
        Placeholder function to be overwritten by child clasess. This to encapsulate
        the age sex edits for a model that are to be performed on the
        DxCodeCategory objects in the _get_dx_categories method.

        Returns:
            List[str]: List of categories based on input gender, age, diagnosis code
        """
        return ["NA"]

    def _determine_infant_maturity_status(self, category_list, beneficiary):
        maturity_status = None

        # If infant is 1, then maturity status is Age1
        # else it checks the categories associated with birth to determine status
        if beneficiary.age == 1:
            maturity_status = "Age1"
        else:
            if any(
                category in category_list
                for category in ["HHS_HCC242", "HHS_HCC243", "HHS_HCC244"]
            ):
                maturity_status = "Extremely_Immature"
            elif any(
                category in category_list for category in ["HHS_HCC245", "HHS_HCC246"]
            ):
                maturity_status = "Immature"
            elif any(
                category in category_list for category in ["HHS_HCC247", "HHS_HCC248"]
            ):
                maturity_status = "Premature_Multiples"
            elif "HHS_HCC249" in category_list:
                maturity_status = "Term"
            elif all(
                category not in category_list
                for category in [
                    "HHS_HCC242",
                    "HHS_HCC243",
                    "HHS_HCC244",
                    "HHS_HCC245",
                    "HHS_HCC246",
                    "HHS_HCC247",
                    "HHS_HCC248",
                    "HHS_HCC249",
                ]
            ):
                maturity_status = "Age1"

        return maturity_status

    # --- Helper methods which should not be overwritten ---

    def _apply_csr_adj(self, score: float) -> float:
        """
        Applies normalization factor and coding intensity adjustment to the score.
        Per CMS documentation, rounding happens at each step. Technically, it should
        be to the third decmial, but rounding to the 4th for greater precision.

        Args:
            score (float): The score to be adjusted.

        Returns:
            float: The adjusted score.
        """
        return round(score * self.csr_adjuster, 3)

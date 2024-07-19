from typing import Union, Type, List
from .utilities import determine_age_band
from .beneficiary import MedicareBeneficiary
from .category import Category
from .result import MedicareScoringResult
from .mapper import DxCodeCategory
from .model import BaseModel


class MedicareModel(BaseModel):
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
        coding_intensity_adjuster (float): CMS is required by law to adjust Medicare Advantage risk scores
                                           using this value. See:
                                           https://bettermedicarealliance.org/wp-content/uploads/2022/06/BMA-Fact-Sheet-Coding-Practices-and-Adjustments-in-Medicare-Advantage-1.pdf
        normalization_factor (float): CMS updates normalization factor each year to apply to the risk scores. See:
                                      https://www.commonwealthfund.org/publications/explainer/2024/mar/how-government-updates-payment-rates-medicare-advantage-plans

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
        super().__init__(lob="medicare", version=version, year=year)
        self.coding_intensity_adjuster = self._get_coding_intensity_adjuster(
            self.model_year
        )
        self.normalization_factor = self._get_normalization_factor(self.model_year)

    def score(
        self,
        gender: str,
        orec: str,
        medicaid: bool,
        diagnosis_codes: Union[List[str], None] = None,
        age: Union[int, None] = None,
        dob: Union[str, None] = None,
        population: str = "CNA",
        verbose: bool = False,
    ) -> Type[MedicareScoringResult]:
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
            MedicareScoringResult: An instantiated object of ScoringResult class.
        """
        beneficiary = MedicareBeneficiary(
            gender, orec, medicaid, population, age, dob, self.model_year
        )
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

        results = MedicareScoringResult(
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
        self, beneficiary: Type[MedicareBeneficiary]
    ) -> List[str]:
        """
        Determine demographic categories based on beneficiary attributes.

        Args:
            beneficiary (Type[MedicareBeneficiary]): An instance of MedicareBeneficiary.

        Returns:
            list: A list containing demographic categories.
        """
        demo_cats = []
        demo_cats.append(
            self._determine_age_gender_category(
                beneficiary.age, beneficiary.gender, beneficiary.population
            )
        )
        demo_int = self._determine_demographic_interactions(
            beneficiary.gender, beneficiary.orig_disabled, beneficiary.medicaid
        )
        if demo_int:
            demo_cats.extend(demo_int)

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

    def _get_coding_intensity_adjuster(self, year: int) -> float:
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

    # --- Methods likely to be overwritten by each model class ---

    def _determine_age_gender_category(
        self, age: int, gender: str, population: str
    ) -> str:
        """
        Determines the demographic category based on age, gender, and population.

        Args:
            age (int): Age of the individual.
            gender (str): Gender of the individual ('M' for male, 'F' for female).
            population (str): Beneficiary model population used for scoring

        Returns:
            str: Demographic category based on age, gender, and population.
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

    def _determine_demographic_interactions(
        self, gender: str, orig_disabled: bool, medicaid: bool
    ) -> List[str]:
        """
        Determines demographic interactions based on gender, disability status, and Medicaid enrollment.

        Args:
            gender (str): Gender of the individual ('M' for male, 'F' for female).
            orig_disabled (bool): Indicates if the individual was originally disabled.
            medicaid (bool): Indicates if the individual is enrolled in Medicaid.

        Returns:
            List[str]: List of demographic interaction labels.
        """
        demo_interactions = []
        if gender == "F" and orig_disabled:
            demo_interactions.append("OriginallyDisabled_Female")
        elif gender == "M" and orig_disabled:
            demo_interactions.append("OriginallyDisabled_Male")

        if medicaid:
            demo_interactions.append("LTIMCAID")

        return demo_interactions

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
        category_count = self._determine_payment_count_category(categories)
        if category_count:
            interaction_list.append(category_count)

        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]

        interactions.append(categories)

        return interactions

    def _determine_payment_count_category(self, categories: list) -> str:
        """
        Determines the payment count category based on the number of categories provided.

        Args:
            categories (list): List of categories.

        Returns:
            str: Payment count category.
        """
        category_count = len(categories)
        category = None
        if category_count > 9:
            category = "D10P"
        elif category_count > 0:
            category = f"D{category_count}"

        return category

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

    def _get_normalization_factor(self, year: int) -> float:
        """
        Placeholder function to be overwritten by child class to return the normalization
        factor for model and year combination.

        Returns:
            float: The normalization factor.
        """
        normalization_factor = 1

        return normalization_factor

    # --- Helper methods which should not be overwritten ---

    def _apply_norm_factor_coding_adj(self, score: float) -> float:
        """
        Applies normalization factor and coding intensity adjustment to the score.
        Per CMS documentation, rounding happens at each step. Technically, it should
        be to the third decmial, but rounding to the 4th for greater precision.

        Args:
            score (float): The score to be adjusted.

        Returns:
            float: The adjusted score.
        """
        return round(
            round(score * self.coding_intensity_adjuster, 4)
            / self.normalization_factor,
            4,
        )

import copy
from typing import Union, Type, List
from .utilities import determine_age_band
from .beneficiary import CommercialBeneficiary
from .category import Category
from .result import CommercialScoringResult
from .mapper import DxCodeCategory, NDCCodeCategory, ProcCodeCategory
from .model import BaseModel


class CommercialModel(BaseModel):
    """
    This is the foundation class for Commercial Models. It is not to be called directly. It loads all
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
        # The way the Commercial Model is designed is that the model determines categories
        # and score is based on the age group in addition to the diagnosis codes.
        # To handle this the category map contains as a key agegroup_hcc, this map now
        # needs to be pared down to the relevant model now that we know the age group
        # associated with the scoring run
        self.model_group_reference_files = copy.deepcopy(self.reference_files)

    def score(
        self,
        gender: str,
        metal_level: str,
        csr_indicator: int,
        enrollment_days: int,
        diagnosis_codes: Union[List[str], None] = None,
        ndc_codes: Union[List[str], None] = None,
        proc_codes: Union[List[str], None] = None,
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
            enrollment_days,
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
        self.model_group_reference_files.category_weights = {
            key.split("_", 1)[1]: self.reference_files.category_weights[key]
            for key in self.reference_files.category_weights.keys()
            if key.startswith(beneficiary.risk_model_age_group)
        }
        self.model_group_reference_files.group_definitions = (
            self.reference_files.group_definitions.get(beneficiary.risk_model_age_group)
        )

        demo_categories = self._determine_demographic_categories(beneficiary)

        if diagnosis_codes or ndc_codes or proc_codes:
            mapper_categories = []
            cat_dict = {}
            if diagnosis_codes:
                dx_categories = self._get_dx_categories(diagnosis_codes, beneficiary)
                mapper_categories.extend(dx_categories)
            if ndc_codes:
                ndc_categories = self._get_ndc_categories(ndc_codes, beneficiary)
                mapper_categories.extend(ndc_categories)
            if proc_codes:
                proc_categories = self._get_proc_categories(proc_codes, beneficiary)
                mapper_categories.extend(proc_categories)

            # Some diagnosis codes go to more than one category thus the category is a list
            # and it is a two step process to unpack them
            unique_disease_cats = set(
                category
                for mapper_code in mapper_categories
                for category in mapper_code.categories
                if category is not None and category != "NA"
            )

            for category in unique_disease_cats:
                # This is done to obtain a consistent output for diagnosis map
                # If there are no diagnosis codes mapping to the category it should
                # return None, as opposed to an empty list. The below statement making
                # the map would create an empty list, thus the if statement following
                # to catch that and modify it
                mapper_map = [
                    mapper_code.mapper_code
                    for mapper_code in mapper_categories
                    if category in mapper_code.categories
                ]
                cat_dict[category] = mapper_map
        else:
            cat_dict = {}
            unique_disease_cats = None

        if unique_disease_cats:
            unique_categories = demo_categories + list(unique_disease_cats)
        else:
            unique_categories = demo_categories

        # At this point the model groups start diverging thus a separate method for
        # infants
        if beneficiary.risk_model_age_group == "Infant":
            # Since the infant model does not have HHS_HCCs with weights, not instantiating
            # categories yet
            categories = self._determine_infant_categories(
                unique_categories, beneficiary
            )
        else:
            # Adult and Child both apply hierarchies and groups and have
            # interactions. Children do not have RX categories, and interactions
            # are different per group and will need to be handled in other methods
            if beneficiary.risk_model_age_group == "Child":
                categories = [
                    Category(
                        self.model_group_reference_files,
                        beneficiary.risk_model_population,
                        category,
                        cat_dict.get(category),
                    )
                    for category in unique_categories
                    if "RX" not in category
                ]
            else:
                categories = [
                    Category(
                        self.model_group_reference_files,
                        beneficiary.risk_model_population,
                        category,
                        cat_dict.get(category),
                    )
                    for category in unique_categories
                ]
            categories = self._apply_hierarchies(categories)
            categories = self._determine_interactions(categories, beneficiary)
            categories = self._apply_groups(categories, beneficiary)

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
            enrollment_days=beneficiary.enrollment_days,
            csr_indicator=beneficiary.csr_indicator,
            age=beneficiary.age,
            dob=beneficiary.dob,
            last_enrollment_date=beneficiary.last_enrollment_date,
            enrollment_months=beneficiary.enrollment_months,
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
        demo_cat = self._determine_age_gender_category(
            beneficiary.age, beneficiary.gender
        )
        # Infant females do not have a weighted demographic category thus this check is needed
        if demo_cat:
            demo_cats.append(demo_cat)
        return demo_cats

    def _determine_infant_categories(self, unique_categories, beneficiary):
        """
        This combines multiple steps in the other models into one as the Infant model
        doesn't follow the same steps as the other models. An infant has a
        demographic component and then an "interaction category" that is based on
        the severity level and maturity status based on the categories their diagnosis
        codes map to.
        """

        # If infants don't have disease categories, can't compute the maturity and
        # severity level, so first build the categories list based on demographic
        # then consider the ones based on categories
        categories = [
            Category(
                self.model_group_reference_files,
                beneficiary.risk_model_population,
                category,
            )
            for category in unique_categories
            if not category.startswith("HHS_HCC")
        ]

        maturity_status = self._determine_infant_maturity_status(
            unique_categories, beneficiary
        )
        severity_level = self._determine_infant_severity_level(unique_categories)
        if maturity_status and severity_level:
            interaction_category = f"{maturity_status}_x_{severity_level}"

            categories.append(
                Category(
                    self.model_group_reference_files,
                    beneficiary.risk_model_population,
                    interaction_category,
                )
            )

        # There is a scenario in the model where the age of an infant is 0, but the infant
        # has a maturity level of Age1. In this case, the infant is supposed to get the
        # Age1_Male demographic category.

        if (
            beneficiary.age == 0
            and beneficiary.gender == "M"
            and maturity_status == "Age1"
        ):
            # Append Age1_Male to category list
            categories.append(
                Category(
                    self.model_group_reference_files,
                    beneficiary.risk_model_population,
                    "Age1_Male",
                )
            )
            # Remove Age0_Male from list
            categories = [
                category
                for category in categories
                if category.category not in "Age0_Male"
            ]

        return categories

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
            if (
                category.category
                in self.model_group_reference_files.hierarchy_definitions.keys()
            ):
                for (
                    remove_category
                ) in self.model_group_reference_files.hierarchy_definitions[
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

            It is possible for a group to drop two categories that are not in a
            hierarchy. As such it needs to be treated similarly to how applying
            hierarchies work.
        """
        category_list = [category.category for category in categories]
        dropped_codes_total = []
        group_dict = {}

        for category in category_list:
            if category in self.model_group_reference_files.group_definitions.keys():
                # At this point need to add the Group code and the code it drops
                # to a dictionary, and then check if that group code exists
                # if it does, then update the value, else add a new value
                dropped_codes_total.append(category)
                group_category = self.model_group_reference_files.group_definitions[
                    category
                ]

                if group_category in group_dict:
                    group_dict[group_category].append(category)
                else:
                    group_dict[group_category] = [category]

        # Remove objects from list
        final_categories = [
            category
            for category in categories
            if category.category not in dropped_codes_total
        ]

        # Add groups to the list
        group_categories = [
            Category(
                self.model_group_reference_files,
                beneficiary.risk_model_population,
                category,
                dropped_categories=dropped_codes,
            )
            for category, dropped_codes in group_dict.items()
        ]

        if group_categories:
            final_categories.extend(group_categories)

        return final_categories

    def _get_dx_categories(
        self, diagnosis_codes: List[str], beneficiary: Type[CommercialBeneficiary]
    ) -> List[Type[DxCodeCategory]]:
        """
        Generates diagnosis code to categories relationships based on provided diagnosis codes
        and beneficiary information.

        Args:
            diagnosis_codes (List[str]): List of diagnosis codes.
            beneficiary (Type[CommercialBeneficiary]): Instance of CommercialBeneficiary representing the beneficiary information.

        Returns:
            List[Type[DxCodeCategory]]: List of DxCodeCategory objects representing the diagnosis code categories.
        """
        dx_categories = [
            DxCodeCategory(
                self.model_group_reference_files.category_map, diagnosis_code
            )
            for diagnosis_code in diagnosis_codes
        ]

        for dx in dx_categories:
            edit_category = self._age_sex_edits(
                beneficiary.gender, beneficiary.age, dx.mapper_code
            )
            if edit_category:
                dx.categories = edit_category

        return dx_categories

    def _get_ndc_categories(
        self, ndc_codes: List[str], beneficiary: Type[CommercialBeneficiary]
    ) -> List[Type[NDCCodeCategory]]:
        """
        Generates diagnosis code to categories relationships based on provided diagnosis codes
        and beneficiary information.

        Args:
            diagnosis_codes (List[str]): List of diagnosis codes.
            beneficiary (Type[CommercialBeneficiary]): Instance of CommercialBeneficiary representing the beneficiary information.

        Returns:
            List[Type[DxCodeCategory]]: List of DxCodeCategory objects representing the diagnosis code categories.
        """
        ndc_categories = [
            NDCCodeCategory(self.model_group_reference_files.category_map, ndc_code)
            for ndc_code in ndc_codes
        ]

        return ndc_categories

    def _get_proc_categories(
        self, proc_codes: List[str], beneficiary: Type[CommercialBeneficiary]
    ) -> List[Type[ProcCodeCategory]]:
        """
        Generates diagnosis code to categories relationships based on provided diagnosis codes
        and beneficiary information.

        Args:
            diagnosis_codes (List[str]): List of diagnosis codes.
            beneficiary (Type[CommercialBeneficiary]): Instance of CommercialBeneficiary representing the beneficiary information.

        Returns:
            List[Type[DxCodeCategory]]: List of DxCodeCategory objects representing the diagnosis code categories.
        """
        proc_code_categories = [
            ProcCodeCategory(self.model_group_reference_files.category_map, proc_code)
            for proc_code in proc_codes
        ]

        return proc_code_categories

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
            2019: {"1": 1.00, "2": 1.07, "3": 1.12, "4": 1.15},
            2020: {"1": 1.00, "2": 1.07, "3": 1.12, "4": 1.15},
            2021: {"1": 1.00, "2": 1.07, "3": 1.12, "4": 1.15},
            2022: {"1": 1.00, "2": 1.07, "3": 1.12, "4": 1.15},
            2023: {"1": 1.00, "2": 1.07, "3": 1.12, "4": 1.15},
            2024: {"1": 1.00, "2": 1.07, "3": 1.12, "4": 1.15},
            2025: {"1": 1.00, "2": 1.07, "3": 1.12, "4": 1.15},
        }

        if csr_adjuster_dict.get(year):
            csr_adjuster = csr_adjuster_dict[year].get(csr_indicator, 1.00)
        else:
            csr_adjuster = 1.00

        return csr_adjuster

    # --- Methods likely to be overwritten by each model class ---

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
            if gender == "F":
                demographic_category = None
            else:
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

    def _determine_interactions(
        self, categories: List[Type[Category]], beneficiary: Type[CommercialBeneficiary]
    ) -> List[Type[Category]]:
        """
        Determines disease interactions based on provided Category objects and beneficiary information.
        Placeholder to be overwritten by child classes.

        Args:
            categories (List[Type[Category]]): List of Category objects representing disease categories.
            beneficiary (Type[CommercialBeneficiary]): Instance of CommercialBeneficiary representing the beneficiary information.

        Returns:
            List[Type[Category]]: List of Category objects representing the disease interactions.
        """
        interaction_list = []

        interactions = [
            Category(
                self.model_group_reference_files,
                beneficiary.risk_model_population,
                beneficiary.risk_model_age_group,
                category,
            )
            for category in interaction_list
        ]

        interactions.append(categories)

        return interactions

    def _determine_child_interactions(
        self, categories: List[Type[Category]], beneficiary: Type[CommercialBeneficiary]
    ) -> List[Type[Category]]:
        """
        Determines disease interactions based on provided Category objects and beneficiary information.
        Placeholder to be overwritten by child classes.

        Args:
            categories (List[Type[Category]]): List of Category objects representing disease categories.
            beneficiary (Type[CommercialBeneficiary]): Instance of CommercialBeneficiary representing the beneficiary information.

        Returns:
            List[Type[Category]]: List of Category objects representing the disease interactions.
        """
        interaction_list = []

        interactions = [
            Category(
                self.model_group_reference_files,
                beneficiary.risk_model_population,
                beneficiary.risk_model_age_group,
                category,
            )
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

    def _determine_infant_severity_level(self, category_list):
        severity_5_hccs = [
            "HHS_HCC008",
            "HHS_HCC018",
            "HHS_HCC034",
            "HHS_HCC041",
            "HHS_HCC042",
            "HHS_HCC125",
            "HHS_HCC128",
            "HHS_HCC129",
            "HHS_HCC130",
            "HHS_HCC137",
            "HHS_HCC158",
            "HHS_HCC183",
            "HHS_HCC184",
            "HHS_HCC251",
        ]

        severity_4_hccs = [
            "HHS_HCC002",
            "HHS_HCC009",
            "HHS_HCC026",
            "HHS_HCC030",
            "HHS_HCC035_1",
            "HHS_HCC035_2",
            "HHS_HCC064",
            "HHS_HCC067",
            "HHS_HCC068",
            "HHS_HCC073",
            "HHS_HCC106",
            "HHS_HCC107",
            "HHS_HCC111",
            "HHS_HCC112",
            "HHS_HCC115",
            "HHS_HCC122",
            "HHS_HCC126",
            "HHS_HCC127",
            "HHS_HCC131",
            "HHS_HCC135",
            "HHS_HCC138",
            "HHS_HCC145",
            "HHS_HCC146",
            "HHS_HCC154",
            "HHS_HCC156",
            "HHS_HCC163",
            "HHS_HCC187",
            "HHS_HCC253",
        ]

        severity_3_hccs = [
            "HHS_HCC001",
            "HHS_HCC003",
            "HHS_HCC006",
            "HHS_HCC010",
            "HHS_HCC011",
            "HHS_HCC012",
            "HHS_HCC027",
            "HHS_HCC045",
            "HHS_HCC054",
            "HHS_HCC055",
            "HHS_HCC061",
            "HHS_HCC063",
            "HHS_HCC066",
            "HHS_HCC074",
            "HHS_HCC075",
            "HHS_HCC081",
            "HHS_HCC082",
            "HHS_HCC083",
            "HHS_HCC084",
            "HHS_HCC096",
            "HHS_HCC108",
            "HHS_HCC109",
            "HHS_HCC110",
            "HHS_HCC113",
            "HHS_HCC114",
            "HHS_HCC117",
            "HHS_HCC119",
            "HHS_HCC121",
            "HHS_HCC132",
            "HHS_HCC139",
            "HHS_HCC142",
            "HHS_HCC149",
            "HHS_HCC150",
            "HHS_HCC159",
            "HHS_HCC218",
            "HHS_HCC223",
            "HHS_HCC226",
            "HHS_HCC228",
        ]

        severity_2_hccs = [
            "HHS_HCC004",
            "HHS_HCC013",
            "HHS_HCC019",
            "HHS_HCC020",
            "HHS_HCC021",
            "HHS_HCC023",
            "HHS_HCC028",
            "HHS_HCC029",
            "HHS_HCC036",
            "HHS_HCC046",
            "HHS_HCC047",
            "HHS_HCC048",
            "HHS_HCC056",
            "HHS_HCC057",
            "HHS_HCC062",
            "HHS_HCC069",
            "HHS_HCC070",
            "HHS_HCC097",
            "HHS_HCC120",
            "HHS_HCC151",
            "HHS_HCC153",
            "HHS_HCC160",
            "HHS_HCC161_1",
            "HHS_HCC162",
            "HHS_HCC188",
            "HHS_HCC217",
            "HHS_HCC219",
        ]

        severity_1_hccs = [
            "HHS_HCC037_1",
            "HHS_HCC037_2",
            "HHS_HCC071",
            "HHS_HCC102",
            "HHS_HCC103",
            "HHS_HCC118",
            "HHS_HCC161_2",
            "HHS_HCC234",
            "HHS_HCC254",
        ]

        # This is the default Severity Status
        severity_status = "Severity1"

        if any(category in category_list for category in severity_5_hccs):
            severity_status = "Severity5"
        elif any(category in category_list for category in severity_4_hccs):
            severity_status = "Severity4"
        elif any(category in category_list for category in severity_3_hccs):
            severity_status = "Severity3"
        elif any(category in category_list for category in severity_2_hccs):
            severity_status = "Severity2"
        elif any(category in category_list for category in severity_1_hccs):
            severity_status = "Severity1"

        return severity_status

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

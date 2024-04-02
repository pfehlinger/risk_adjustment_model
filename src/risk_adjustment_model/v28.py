from typing import List, Union, Type
from .utilities import determine_age_band
from .model import MedicareModel
from .category import Category
from .beneficiary import MedicareBeneficiary


class MedicareModelV28(MedicareModel):
    """
    This class represents the V28 Community Model for Medicare. It inherits from the MedicareModel class.

    Methods:
        __init__: Initializes the MedicareModelV24 instance.

        Overwrites:
            _get_normalization_factor: Retrieves the normalization factor based on the model year.
            _age_sex_edits: Applies age and sex edits to diagnosis codes.
            _determine_disease_interactions: Determines disease interactions based on Category objects and beneficiary information.

        Included for clarity:
            _determine_payment_count_category: Determines the payment count category based on the number of categories provided.
            _determine_age_gender_category: Determines the demographic category based on age, gender, and population.
            _determine_demographic_interactions: Determines demographic interactions based on gender, disability status, and Medicaid enrollment.

        New:
            _age_sex_edit_1: Applies age and sex edit 1 to a diagnosis code.
            _age_sex_edit_2: Applies age and sex edit 2 to a diagnosis code.
            _age_sex_edit_3: Applies age and sex edit 3 to a diagnosis code.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v28", year)
        self.normalization_factor = self._get_normalization_factor(self.model_year)

    def _get_normalization_factor(self, year: int) -> float:
        """
        CMS updates normalization factor each year to apply to the risk scores. See:
        https://www.commonwealthfund.org/publications/explainer/2024/mar/how-government-updates-payment-rates-medicare-advantage-plans

        This dictionary is updated each year to include the normalization factor from the final announcement.

        Returns:
            float: The normalization factor.
        """
        norm_factor_dict = {
            2024: 1.015,
            2025: 1.045,
        }
        try:
            normalization_factor = norm_factor_dict[year]
        except KeyError:
            normalization_factor = 1

        return normalization_factor

    def _apply_hierarchies(
        self, categories: List[Type[Category]]
    ) -> List[Type[Category]]:
        """
        Filters out categories falling into hierarchies per the model hierarchy_definition file.
        In V28 there is a "heart interaction patch" in the file V283T3M which is easily
        applied in the hierachy step, thus this method is overwritten here.

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

        # Patch for V28 Heart Conditions
        if "HCC223" in category_list and not any(
            category in category_list
            for category in ["HCC221", "HCC222", "HCC224", "HCC225", "HCC226"]
        ):
            dropped_codes_total.append("HCC223")

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

    def _age_sex_edits(
        self, gender: str, age: int, diagnosis_code: str
    ) -> Union[List[str], None]:
        """
        Wrapper method to apply all model specific age and sex edits for a diagnosis code to
        category mapping. These are found in the model software file named something like
        "V28I0ED1".

        Args:
            gender (str): Gender of the individual ('M' for male, 'F' for female).
            age (int): Age of the individual.
            diagnosis_code (str): Diagnosis code to apply edits.

        Returns:
            Union[List[str], None]: List of categories after applying edits, or None if no edits applied.
        """
        new_category = self._age_sex_edit_1(gender, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_2(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_3(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_4(age, diagnosis_code)
        if new_category:
            return new_category

    def _age_sex_edit_1(self, gender: str, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 1 to a diagnosis code.

        Args:
            gender (str): Gender of the individual ('M' for male, 'F' for female).
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if gender == "F" and dx_code in ["D66", "D67"]:
            return ["HCC112"]

    def _age_sex_edit_2(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 2 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if age < 18 and dx_code in [
            "J410",
            "J411",
            "J418",
            "J42",
            "J430",
            "J431",
            "J432",
            "J438",
            "J439",
            "J440",
            "J441",
            "J449",
            "J982",
            "J983",
        ]:
            return ["NA"]

    def _age_sex_edit_3(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 3 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if age < 50 and dx_code in [
            "C50011",
            "C50012",
            "C50019",
            "C50021",
            "C50022",
            "C50029",
            "C50111",
            "C50112",
            "C50119",
            "C50121",
            "C50122",
            "C50129",
            "C50211",
            "C50212",
            "C50219",
            "C50221",
            "C50222",
            "C50229",
            "C50311",
            "C50312",
            "C50319",
            "C50321",
            "C50322",
            "C50329",
            "C50411",
            "C50412",
            "C50419",
            "C50421",
            "C50422",
            "C50429",
            "C50511",
            "C50512",
            "C50519",
            "C50521",
            "C50522",
            "C50529",
            "C50611",
            "C50612",
            "C50619",
            "C50621",
            "C50622",
            "C50629",
            "C50811",
            "C50812",
            "C50819",
            "C50821",
            "C50822",
            "C50829",
            "C50911",
            "C50912",
            "C50919",
            "C50921",
            "C50922",
            "C50929",
        ]:
            return ["HCC22"]

    def _age_sex_edit_4(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 4 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if age >= 2 and dx_code in [
            "P040",
            "P041",
            "P0411",
            "P0412",
            "P0413",
            "P0414",
            "P0415",
            "P0416",
            "P0417",
            "P0418",
            "P0419",
            "P041A",
            "P042",
            "P043",
            "P0440",
            "P0441",
            "P0442",
            "P0449",
            "P045",
            "P046",
            "P048",
            "P0481",
            "P0489",
            "P049",
            "P270",
            "P271",
            "P278",
            "P279",
            "P930",
            "P938",
            "P961",
            "P962",
        ]:
            return ["NA"]

    def _determine_disease_interactions(
        self, categories: List[Type[Category]], beneficiary: Type[MedicareBeneficiary]
    ) -> List[Type[Category]]:
        """
        Determines disease interactions based on provided Category objects and beneficiary information.

        Args:
            categories (List[Type[Category]]): List of Category objects representing disease categories.
            beneficiary (Type[MedicareBeneficiary]): Instance of MedicareBeneficiary representing the beneficiary information.

        Returns:
            List[Type[Category]]: List of Category objects representing the disease interactions.
        """
        category_list = [
            category.category for category in categories if category.type == "disease"
        ]
        cancer_list = ["HCC17", "HCC18", "HCC19", "HCC20", "HCC21", "HCC22", "HCC23"]
        diabetes_list = ["HCC35", "HCC36", "HCC37", "HCC38"]
        card_resp_fail_list = ["HCC211", "HCC212", "HCC213"]
        hf_list = ["HCC221", "HCC222", "HCC223", "HCC224", "HCC225", "HCC226"]
        chr_lung_list = ["HCC276", "HCC277", "HCC278", "HCC279", "HCC280"]
        kidney_v28_list = ["HCC326", "HCC327", "HCC328", "HCC329"]
        g_substance_use_disorder_v28_list = [
            "HCC135",
            "HCC136",
            "HCC137",
            "HCC138",
            "HCC139",
        ]
        g_pyshiatric_v28_list = ["HCC151", "HCC152", "HCC153", "HCC154", "HCC155"]
        neuro_v28_list = [
            "HCC180",
            "HCC181",
            "HCC182",
            "HCC190",
            "HCC191",
            "HCC192",
            "HCC195",
            "HCC196",
            "HCC198",
            "HCC199",
        ]
        ulcer_v28_list = ["HCC379", "HCC380", "HCC381", "HCC382"]

        cancer = any(category in category_list for category in cancer_list)
        diabetes = any(category in category_list for category in diabetes_list)
        card_resp_fail = any(
            category in category_list for category in card_resp_fail_list
        )
        hf = any(category in category_list for category in hf_list)
        chr_lung = any(category in category_list for category in chr_lung_list)
        kidney_v28 = any(category in category_list for category in kidney_v28_list)
        g_substance_use_disorder_v28 = any(
            category in category_list for category in g_substance_use_disorder_v28_list
        )
        g_pyshiatric_v28 = any(
            category in category_list for category in g_pyshiatric_v28_list
        )
        neuro_v28 = any(category in category_list for category in neuro_v28_list)
        ulcer_v28 = any(category in category_list for category in ulcer_v28_list)
        hcc238 = "HCC238" in category_list

        interactions_dict = {
            "DIABETES_HF_V28": all([diabetes, hf]),
            "HF_CHR_LUNG_V28": all([hf, chr_lung]),
            "HF_KIDNEY_V28": all([hf, kidney_v28]),
            "CHR_LUNG_CARD_RESP_FAIL_V28": all([chr_lung, card_resp_fail]),
            "HF_HCC238_V28": all([hf, hcc238]),
            "gSubUseDisorder_gPsych_V28": all(
                [g_substance_use_disorder_v28, g_pyshiatric_v28]
            ),
            "DISABLED_CANCER_V28": all([beneficiary.disabled, cancer]),
            "DISABLED_NEURO_V28": all([beneficiary.disabled, neuro_v28]),
            "DISABLED_HF_V28": all([beneficiary.disabled, hf]),
            "DISABLED_CHR_LUNG_V28": all([beneficiary.disabled, chr_lung]),
            "DISABLED_ULCER_V28": all([beneficiary.disabled, ulcer_v28]),
        }
        interaction_list = [key for key, value in interactions_dict.items() if value]

        category_count = self._determine_payment_count_category(category_list)
        if category_count:
            interaction_list.append(category_count)
        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]
        interactions.extend(categories)

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

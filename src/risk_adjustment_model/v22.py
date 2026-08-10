from typing import List, Union, Type
from .medicare_model import MedicareModel
from .category import Category
from .beneficiary import MedicareBeneficiary


class MedicareModelV22(MedicareModel):
    """
    This class represents the V22 Community Model for Medicare. It inherits from the MedicareModel
    class. V22 is a legacy model version -- CMS has fully retired V22 alongside V24 as of PY2026 in
    favor of V28, but continues to publish it for transition/blending purposes.

    Methods:
        __init__: Initializes the MedicareModelV22 instance.

        Overwrites:
            _get_normalization_factor: Retrieves the normalization factor based on the model year.
            _age_sex_edits: Applies age and sex edits to diagnosis codes.
            _determine_disease_interactions: Determines disease interactions based on Category objects and beneficiary information.

        Included for clarity:
            _determine_age_gender_category: Determines the demographic category based on age, gender, and population.
            _determine_demographic_interactions: Determines demographic interactions based on gender, disability status, and Medicaid enrollment.

        New:
            _age_sex_edit_1: Applies age and sex edit 1 to a diagnosis code.
            _age_sex_edit_2: Applies age and sex edit 2 to a diagnosis code.
            _age_sex_edit_3: Applies age and sex edit 3 to a diagnosis code.

    Notes:
        Unlike V24/V28, V22 has no HCC-count ("payment count") interaction variables -- CMS's own
        V22_CE_Relative_Factors.csv has no D1-D10P-style rows, and this feature is absent from the
        V22 transform.py entirely, so `_determine_disease_interactions` does not call
        `_determine_payment_count_category` the way V24/V28 do.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v22", year)
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
            2026: 1.187,
            2027: 1.202,
        }
        try:
            normalization_factor = norm_factor_dict[year]
        except KeyError:
            normalization_factor = 1

        return normalization_factor

    def _age_sex_edits(
        self, gender: str, age: int, diagnosis_code: str
    ) -> Union[List[str], None]:
        """
        Wrapper method to apply all model specific age and sex edits for a diagnosis code to
        category mapping. These are found in the model software file named something like
        "V22I0ED1".

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
            return ["HCC48"]

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
            "J4481",
            "J4489",
            "J449",
            "J982",
            "J983",
        ]:
            return ["HCC112"]

    def _age_sex_edit_3(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 3 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age < 6 or age > 18) and dx_code == "F3481":
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

        Notes:
            Some interaction pairs share the exact same underlying condition but are scored under
            two different category names for Community vs. Institutional populations (CMS's own
            sparse per-population coefficients -- e.g. "HCC85_gCopdCF" is Community-only and
            "CHF_gCopdCF" is Institutional-only, both triggered by the same HCC85 x gCopdCF
            condition). Both are added when the condition is met; the irrelevant population's copy
            simply has a 0/blank coefficient and contributes nothing.
        """
        category_list = [
            category.category for category in categories if category.type == "disease"
        ]
        cancer_list = ["HCC8", "HCC9", "HCC10", "HCC11", "HCC12"]
        diabetes_list = ["HCC17", "HCC18", "HCC19"]
        card_resp_fail_list = ["HCC82", "HCC83", "HCC84"]
        g_copd_cf_list = ["HCC110", "HCC111", "HCC112"]
        renal_list = ["HCC134", "HCC135", "HCC136", "HCC137"]
        g_substance_abuse_list = ["HCC54", "HCC55"]
        g_psychiatric_list = ["HCC57", "HCC58"]
        pressure_ulcer_list = ["HCC157", "HCC158"]

        cancer = any(category in category_list for category in cancer_list)
        diabetes = any(category in category_list for category in diabetes_list)
        chf = "HCC85" in category_list
        card_resp_fail = any(
            category in category_list for category in card_resp_fail_list
        )
        g_copd_cf = any(category in category_list for category in g_copd_cf_list)
        renal = any(category in category_list for category in renal_list)
        sepsis = "HCC2" in category_list
        g_substance_abuse = any(
            category in category_list for category in g_substance_abuse_list
        )
        g_psychiatric = any(
            category in category_list for category in g_psychiatric_list
        )
        pressure_ulcer = any(
            category in category_list for category in pressure_ulcer_list
        )
        hcc47 = "HCC47" in category_list
        hcc96 = "HCC96" in category_list
        hcc188 = "HCC188" in category_list
        hcc114 = "HCC114" in category_list
        hcc57 = "HCC57" in category_list
        hcc79 = "HCC79" in category_list

        interactions_dict = {
            "HCC47_gCancer": all([hcc47, cancer]),
            "HCC85_gDiabetesMellit": all([chf, diabetes]),
            "HCC85_gCopdCF": all([chf, g_copd_cf]),
            "HCC85_gRenal": all([chf, renal]),
            "gRespDepandArre_gCopdCF": all([card_resp_fail, g_copd_cf]),
            "HCC85_HCC96": all([chf, hcc96]),
            "gSubstanceAbuse_gPsychiatric": all([g_substance_abuse, g_psychiatric]),
            "CHF_gCopdCF": all([chf, g_copd_cf]),
            "gCopdCF_CARD_RESP_FAIL": all([g_copd_cf, card_resp_fail]),
            "SEPSIS_PRESSURE_ULCER": all([sepsis, pressure_ulcer]),
            "SEPSIS_ARTIF_OPENINGS": all([sepsis, hcc188]),
            "ART_OPENINGS_PRESSURE_ULCER": all([hcc188, pressure_ulcer]),
            "DIABETES_CHF": all([diabetes, chf]),
            "gCopdCF_ASP_SPEC_BACT_PNEUM": all([g_copd_cf, hcc114]),
            "ASP_SPEC_BACT_PNEUM_PRES_ULC": all([hcc114, pressure_ulcer]),
            "SEPSIS_ASP_SPEC_BACT_PNEUM": all([sepsis, hcc114]),
            "SCHIZOPHRENIA_gCopdCF": all([hcc57, g_copd_cf]),
            "SCHIZOPHRENIA_CHF": all([hcc57, chf]),
            "SCHIZOPHRENIA_SEIZURES": all([hcc57, hcc79]),
            "DISABLED_HCC85": all([beneficiary.disabled, chf]),
            "DISABLED_PRESSURE_ULCER": all([beneficiary.disabled, pressure_ulcer]),
            "DISABLED_HCC161": all([beneficiary.disabled, "HCC161" in category_list]),
            "DISABLED_HCC39": all([beneficiary.disabled, "HCC39" in category_list]),
            "DISABLED_HCC77": all([beneficiary.disabled, "HCC77" in category_list]),
            "DISABLED_HCC6": all([beneficiary.disabled, "HCC6" in category_list]),
        }
        interaction_list = [key for key, value in interactions_dict.items() if value]

        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]
        interactions.extend(categories)

        return interactions

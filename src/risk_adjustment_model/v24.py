from .utilities import determine_age_band
from .model import MedicareModel
from .category import Category


class MedicareModelV24(MedicareModel):
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

    def __init__(self, year=None):
        super().__init__("v24", year)
        self.normalization_factor = self._get_normalization_factor(self.model_year)

    def _get_normalization_factor(self, year) -> float:
        """

        Returns:
            float: The normalization factor.
        """
        norm_factor_dict = {
            2020: 1.069,
            2021: 1.097,
            2022: 1.118,
            2023: 1.127,
            2024: 1.146,
            2025: 1.153,
        }
        try:
            normalization_factor = norm_factor_dict[year]
        except KeyError:
            normalization_factor = 1

        return normalization_factor

    def age_sex_edits(self, gender, age, diagnosis_code):
        new_category = self._age_sex_edit_1(gender, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_2(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_3(age, diagnosis_code)
        if new_category:
            return new_category

    def _age_sex_edit_1(self, gender, dx_code):
        if gender == "F" and dx_code in ["D66", "D67"]:
            return ["HCC48"]

    def _age_sex_edit_2(self, age, dx_code):
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
            return ["HCC112"]

    def _age_sex_edit_3(self, age, dx_code):
        if (age < 6 or age > 18) and dx_code == "F3481":
            return ["NA"]

    def _determine_disease_interactions(self, categories: list, beneficiary) -> list:
        category_list = [
            category.category for category in categories if category.type == "disease"
        ]
        cancer_list = ["HCC8", "HCC9", "HCC10", "HCC11", "HCC12"]
        diabetes_list = ["HCC17", "HCC18", "HCC19"]
        card_resp_fail_list = ["HCC82", "HCC83", "HCC84"]
        g_copd_cf_list = ["HCC110", "HCC111", "HCC112"]
        renal_v24_list = ["HCC134", "HCC135", "HCC136", "HCC137", "HCC138"]
        g_substance_use_disorder_v24_list = ["HCC54", "HCC55", "HCC56"]
        g_pyshiatric_v24_list = ["HCC57", "HCC58", "HCC59", "HCC60"]
        pressure_ulcer_list = ["HCC157", "HCC158", "HCC159"]

        cancer = any(category in category_list for category in cancer_list)
        diabetes = any(category in category_list for category in diabetes_list)
        card_resp_fail = any(
            category in category_list for category in card_resp_fail_list
        )
        chf = "HCC85" in category_list
        g_copd_cf = any(category in category_list for category in g_copd_cf_list)
        renal_v24 = any(category in category_list for category in renal_v24_list)
        sepsis = "HCC2" in category_list
        g_substance_use_disorder_v24 = any(
            category in category_list for category in g_substance_use_disorder_v24_list
        )
        g_pyshiatric_v24 = any(
            category in category_list for category in g_pyshiatric_v24_list
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
            "HCC47_gCancer": all([cancer, hcc47]),
            "DIABETES_CHF": all([diabetes, chf]),
            "CHF_gCopdCF": all([chf, g_copd_cf]),
            "HCC85_gRenal_V24": all([chf, renal_v24]),
            "gCopdCF_CARD_RESP_FAIL": all([g_copd_cf, card_resp_fail]),
            "HCC85_HCC96": all([chf, hcc96]),
            "gSubstanceUseDisorder_gPsych": all(
                [g_pyshiatric_v24, g_substance_use_disorder_v24]
            ),
            "SEPSIS_PRESSURE_ULCER": all([sepsis, pressure_ulcer]),
            "SEPSIS_ARTIF_OPENINGS": all([sepsis, hcc188]),
            "ART_OPENINGS_PRESS_ULCER": all([hcc188, pressure_ulcer]),
            "gCopdCF_ASP_SPEC_B_PNEUM": all([g_copd_cf, hcc114]),
            "ASP_SPEC_B_PNEUM_PRES_ULC": all([hcc114, pressure_ulcer]),
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

        category_count = self._get_payment_count_categories(category_list)
        if category_count:
            interaction_list.append(category_count)

        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]
        interactions.extend(categories)

        return interactions

    def _get_payment_count_categories(self, categories: list):
        """ """
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

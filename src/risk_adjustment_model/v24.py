from .utilities import determine_age_band
from .medicare_model import MedicareModel
from .diagnosis_code import MedicareDxCodeCategoryV24


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
        self.coding_intensity_adjuster = self._get_coding_intensity_adjuster(
            self.model_year
        )
        # PF: This will break for the models that have different normalization factors, will have to refactor once implemented
        self.normalization_factor = self._get_normalization_factor(
            self.version, self.model_year
        )

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
            MedicareDxCodeCategoryV24(self.data_directory, diagnosis_code, beneficiary)
            for diagnosis_code in diagnosis_codes
        ]

        return dx_categories

    def _determine_disease_interactions(self, categories: list, disabled: bool) -> list:
        cancer_list = ["HCC8", "HCC9", "HCC10", "HCC11", "HCC12"]
        diabetes_list = ["HCC17", "HCC18", "HCC19"]
        card_resp_fail_list = ["HCC82", "HCC83", "HCC84"]
        g_copd_cf_list = ["HCC110", "HCC111", "HCC112"]
        renal_v24_list = ["HCC134", "HCC135", "HCC136", "HCC137", "HCC138"]
        g_substance_use_disorder_v24_list = ["HCC54", "HCC55", "HCC56"]
        g_pyshiatric_v24_list = ["HCC57", "HCC58", "HCC59", "HCC60"]
        pressure_ulcer_list = ["HCC157", "HCC158", "HCC159"]

        cancer = any(category in categories for category in cancer_list)
        diabetes = any(category in categories for category in diabetes_list)
        card_resp_fail = any(category in categories for category in card_resp_fail_list)
        chf = "HCC85" in categories
        g_copd_cf = any(category in categories for category in g_copd_cf_list)
        renal_v24 = any(category in categories for category in renal_v24_list)
        sepsis = "HCC2" in categories
        g_substance_use_disorder_v24 = any(
            category in categories for category in g_substance_use_disorder_v24_list
        )
        g_pyshiatric_v24 = any(
            category in categories for category in g_pyshiatric_v24_list
        )
        pressure_ulcer = any(category in categories for category in pressure_ulcer_list)
        hcc47 = "HCC47" in categories
        hcc96 = "HCC96" in categories
        hcc188 = "HCC188" in categories
        hcc114 = "HCC114" in categories
        hcc57 = "HCC57" in categories
        hcc79 = "HCC79" in categories

        interactions = {
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
            "DISABLED_HCC85": all([disabled, chf]),
            "DISABLED_PRESSURE_ULCER": all([disabled, pressure_ulcer]),
            "DISABLED_HCC161": all([disabled, "HCC161" in categories]),
            "DISABLED_HCC39": all([disabled, "HCC39" in categories]),
            "DISABLED_HCC77": all([disabled, "HCC77" in categories]),
            "DISABLED_HCC6": all([disabled, "HCC6" in categories]),
        }
        interaction_list = [key for key, value in interactions.items() if value]

        category_count = self._get_payment_count_categories(categories)
        if category_count:
            interaction_list.append(category_count)

        return interaction_list

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

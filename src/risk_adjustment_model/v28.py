from .utilities import determine_age_band
from .medicare_model import MedicareModel
from .diagnosis_code import MedicareDxCodeCategoryV28


class MedicareModelV28(MedicareModel):
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
        super().__init__("v28", year)
        self.coding_intensity_adjuster = self._get_coding_intensity_adjuster(
            self.model_year
        )
        # PF: This will break for the models that have different normalization factors, will have to refactor once implemented
        self.normalization_factor = self._get_normalization_factor(
            self.version, self.model_year
        )

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
        if "HCC223" in category_list and not any(
            category in category_list
            for category in ["HCC221", "HCC222", "HCC224", "HCC225", "HCC226"]
        ):
            category_list.remove("HCC223")

        for category in category_list:
            dropped_codes = []
            if category in self.hierarchy_definitions.keys():
                for remove_category in self.hierarchy_definitions[category][
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
            MedicareDxCodeCategoryV28(self.data_directory, diagnosis_code, beneficiary)
            for diagnosis_code in diagnosis_codes
        ]

        return dx_categories

    def _determine_disease_interactions(self, categories: list, disabled: bool) -> list:
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

        cancer = any(category in categories for category in cancer_list)
        diabetes = any(category in categories for category in diabetes_list)
        card_resp_fail = any(category in categories for category in card_resp_fail_list)
        hf = any(category in categories for category in hf_list)
        chr_lung = any(category in categories for category in chr_lung_list)
        kidney_v28 = any(category in categories for category in kidney_v28_list)
        g_substance_use_disorder_v28 = any(
            category in categories for category in g_substance_use_disorder_v28_list
        )
        g_pyshiatric_v28 = any(
            category in categories for category in g_pyshiatric_v28_list
        )
        neuro_v28 = any(category in categories for category in neuro_v28_list)
        ulcer_v28 = any(category in categories for category in ulcer_v28_list)
        hcc238 = "HCC238" in categories

        interactions = {
            "DIABETES_HF_V28": all([diabetes, hf]),
            "HF_CHR_LUNG_V28": all([hf, chr_lung]),
            "HF_KIDNEY_V28": all([hf, kidney_v28]),
            "CHR_LUNG_CARD_RESP_FAIL_V28": all([chr_lung, card_resp_fail]),
            "HF_HCC238_V28": all([hf, hcc238]),
            "gSubUseDisorder_gPsych_V28": all(
                [g_substance_use_disorder_v28, g_pyshiatric_v28]
            ),
            "DISABLED_CANCER_V28": all([disabled, cancer]),
            "DISABLED_NEURO_V28": all([disabled, neuro_v28]),
            "DISABLED_HF_V28": all([disabled, hf]),
            "DISABLED_CHR_LUNG_V28": all([disabled, chr_lung]),
            "DISABLED_ULCER_V28": all([disabled, ulcer_v28]),
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

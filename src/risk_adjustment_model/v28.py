from .utilities import determine_age_band
from .model import MedicareModel
from .category import Category


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
        self.normalization_factor = self._get_normalization_factor(self.model_year)

    def _apply_hierarchies(self, categories: list) -> dict:
        """
        Takes in a list containing category objects and removes categories that fall
        into hierarchies as outlined in the hierarchy_definition file.

        Returns:
            list a of category objects
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

    def _get_normalization_factor(self, year) -> float:
        """

        C = Commmunity
        D = Dialysis
        G = Graft

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
        new_category = self._age_sex_edit_4(age, diagnosis_code)
        if new_category:
            return new_category

    def _age_sex_edit_1(self, gender, dx_code):
        if gender == "F" and dx_code in ["D66", "D67"]:
            return ["HCC112"]

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
            return ["NA"]

    def _age_sex_edit_3(self, age, dx_code):
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

    def _age_sex_edit_4(self, age, dx_code):
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

    def _determine_disease_interactions(self, categories: list, beneficiary) -> list:
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

        category_count = self._get_payment_count_categories(category_list)
        if category_count:
            interaction_list.append(category_count)
        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]
        interactions.extend(categories)

        return interactions

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

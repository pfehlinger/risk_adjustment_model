from .utilities import determine_age_band


def age_sex_edits(gender, age, diagnosis_code):
    new_category = _age_sex_edit_1(gender, diagnosis_code)
    if new_category:
        return new_category
    new_category = _age_sex_edit_2(age, diagnosis_code)
    if new_category:
        return new_category
    new_category = _age_sex_edit_3(age, diagnosis_code)
    if new_category:
        return new_category
    new_category = _age_sex_edit_4(age, diagnosis_code)
    if new_category:
        return new_category


def _age_sex_edit_1(gender, dx_code):
    if gender == "F" and dx_code in ["D66", "D67"]:
        return ["HCC112"]


def _age_sex_edit_2(age, dx_code):
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


def _age_sex_edit_3(age, dx_code):
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


def _age_sex_edit_4(age, dx_code):
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


def determine_disease_interactions(categories: list, disabled: bool) -> list:
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
    g_pyshiatric_v28 = any(category in categories for category in g_pyshiatric_v28_list)
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

    category_count = get_payment_count_categories(categories)
    if category_count:
        interaction_list.append(category_count)

    return interaction_list


def get_payment_count_categories(categories: list):
    """ """
    category_count = len(categories)
    category = None
    if category_count > 9:
        category = "D10P"
    elif category_count > 0:
        category = f"D{category_count}"

    return category


def determine_demographic_cats(age, gender, population):
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


def determine_demographic_interactions(gender, orig_disabled, medicaid):
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

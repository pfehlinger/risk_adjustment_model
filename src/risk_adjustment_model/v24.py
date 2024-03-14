from src.risk_adjustment_model.utilities import nvl, determine_age_band


def age_sex_edits(gender, age, dx_categories):
    for diagnosis_code in dx_categories.keys():
        new_category = _age_sex_edit_1(gender, diagnosis_code)
        if new_category:
            dx_categories[diagnosis_code] = new_category
            break
        new_category = _age_sex_edit_2(age, diagnosis_code)
        if new_category:
            dx_categories[diagnosis_code] = new_category
            break
        new_category = _age_sex_edit_3(age, diagnosis_code)
        if new_category:
            dx_categories[diagnosis_code] = new_category
            break

    return dx_categories

def _age_sex_edit_1(gender, dx_code):
    if gender == 'F' and dx_code in ['D66', 'D67']:
        return ['HCC48']


def _age_sex_edit_2(age, dx_code):
    if age < 18 and dx_code in ['J410', 'J411', 'J418',
                            'J42', 'J430', 'J431', 'J432',
                            'J438', 'J439', 'J440',
                            'J441', 'J449', 'J982', 'J983']:
        return ['HCC112']


def _age_sex_edit_3(age, dx_code):
    if (age < 6 or age > 18) and dx_code=='F3481':
        return ['NA']


def determine_disease_interactions(categories: list) -> list:
    cancer = False
    cancer_list = ['HCC8', 'HCC9', 'HCC10', 'HCC11', 'HCC12']
    diabetes = False
    diabetes_list = ['HCC17', 'HCC18', 'HCC19']
    card_resp_fail = False
    card_resp_fail_list = ['HCC82', 'HCC83', 'HCC84']
    chf = False
    chf_list = ['HCC85']
    g_copd_cf = False
    g_copd_cf_list = ['HCC110', 'HCC111', 'HCC112']
    renal_v24 = False
    renal_v24_list = ['HCC134', 'HCC135', 'HCC136', 'HCC137', 'HCC138']
    sepsis = False
    sepsis_list = ['HCC2']
    g_substance_use_disorder_v24 = False
    g_substance_use_disorder_v24_list = ['HCC54', 'HCC55', 'HCC56']
    g_pyshiatric_v24 = False
    g_pyshiatric_v24_list = ['HCC57', 'HCC58', 'HCC59', 'HCC60']
    
    for category in cancer_list:
        if category in categories:
            cancer = True
            break
    for category in diabetes_list:
        if category in categories:
            diabetes = True
            break
    for category in card_resp_fail_list:
        if category in categories:
            card_resp_fail = True
            break
    for category in chf_list:
        if category in categories:
            chf = True
            break
    for category in g_copd_cf_list:
        if category in categories:
            g_copd_cf = True
            break
    for category in renal_v24_list:
        if category in categories:
            renal_v24 = True
            break
    for category in sepsis_list:
        if category in categories:
            sepsis = True
            break
    for category in g_substance_use_disorder_v24_list:
        if category in categories:
            g_substance_use_disorder_v24 = True
            break
    for category in g_pyshiatric_v24_list:
        if category in categories:
            g_pyshiatric_v24 = True
            break
    if 'HCC47' in categories:
        hcc47 = True
    else:
        hcc47 = False    
    if 'HCC85' in categories:
        hcc85 = True
    else:
        hcc85 = False
    if 'HCC96' in categories:
        hcc96 = True
    else:
        hcc96 = False

    interactions = {
        'HCC47_gCancer': bool(cancer*hcc47),
        'DIABETES_CHF': bool(diabetes*chf),
        'CHF_gCopdCF': bool(chf*g_copd_cf),
        'HCC85_gRenal_V24': bool(hcc85*renal_v24),
        'gCopdCF_CARD_RESP_FAIL': bool(g_copd_cf*card_resp_fail),
        'HCC85_HCC96': bool(hcc85*hcc96),
        'gSubstanceUseDisorder_gPsych': bool(g_pyshiatric_v24*g_substance_use_disorder_v24)
    }
    interaction_list = [key for key, value in interactions.items() if value]

    category_count = get_payment_count_categories(categories)
    if category_count:
        interaction_list.append(category_count)

    return interaction_list


def get_payment_count_categories(categories: list):
    """
    """
    category_count = len(categories)
    category = None
    if category_count > 9:
        category = 'D10P'
    elif category_count > 0:
        category = f'D{category_count}'

    return category


def determine_demographic_cats(age, gender, population):
    """
    This may need to be overwritten depending on the mechanices of the model.
    Ranges may change, the population may change, etc.
    """
    if population[:2] == 'NE':
        demo_category_ranges = [
            '0_34', '35_44', '45_54', '55_59', '60_64',
            '65', '66', '67', '68', '69', '70_74', 
            '75_79', '80_84', '85_89', '90_94', '95_GT',
        ]
    else:
        demo_category_ranges = [
            '0_34', '35_44', '45_54', '55_59', '60_64',
            '65_69', '70_74', '75_79', '80_84', '85_89', 
            '90_94', '95_GT',
        ]
    
    demographic_category_range = determine_age_band(age, demo_category_ranges)

    if population[:2] == 'NE':
        demographic_category = f'NE{gender}{demographic_category_range}'
    else:
        demographic_category = f'{gender}{demographic_category_range}'

    return demographic_category


def determine_demographic_interactions(gender, orig_disabled):
    """
    Depending on model this may change
    """
    demo_interaction = None
    if gender == 'F' and orig_disabled == 1:
        demo_interaction = 'OriginallyDisabled_Female'
    elif gender == 'M' and orig_disabled == 1:
        demo_interaction = 'OriginallyDisabled_Male'

    return demo_interaction
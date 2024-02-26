import pandas as pd
import logging
import os
import yaml

from pathlib import Path
from src.config import Config

log = logging.getLogger(__name__)


CMS_VARIABLES_V24 = {
    'coding_intensity_adjuster': 0.059,
    'normalization_factor': 1.146
}

def age_sex_edits_v24(gender, age, dx_code, category):
        category = _age_sex_edit_1(gender, age, dx_code)
        category = _age_sex_edit_2(gender, age, dx_code)
        category = _age_sex_edit_3(gender, age, dx_code)

        return category

def _age_sex_edit_1(gender, age, dx_code):
    if gender == 'F' and dx_code in ['D66', 'D67']:
        return '48'


def _age_sex_edit_2(gender, age, dx_code):
    if age < 18 and dx_code in ['J410', 'J411', 'J418',
                            'J42', 'J430', 'J431', 'J432',
                            'J438', 'J439', 'J440',
                            'J441', 'J449', 'J982', 'J983']:
        return '112'


def _age_sex_edit_3(gender, age, dx_code):
    if (age < 6 or age > 18) and dx_code=='F3481':
        return 'NA'


def get_disease_interactions_v24(categories: list) -> list:
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

    return interaction_list
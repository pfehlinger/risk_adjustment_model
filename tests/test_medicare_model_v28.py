from risk_adjustment_model import MedicareModel
from math import isclose

def test_category_mapping():
    model = MedicareModel('v28')
    results = model.score(gender='M', orec='1', medicaid=False, diagnosis_codes=['E08311'], age=67, population='CNA', verbose=False)
    assert 'HCC37' in results.category_list
    results = model.score(gender='M', orec='1', medicaid=False, diagnosis_codes=['D8687'], age=67, population='CNA', verbose=False)
    assert 'HCC93' in results.category_list
    # Check the Heart Patch works, diag goes to HCC223 and since it is the only one present, it should be removed
    results = model.score(gender='M', orec='0', medicaid=False, diagnosis_codes=['T82522A'], age=67, population='CNA', verbose=False)
    assert len(results.category_list)==1
    # Now see if HCC223 is present when HCC224 existed thus heart patch shouldn't do anything
    results = model.score(gender='M', orec='0', medicaid=False, diagnosis_codes=['T82522A', 'I5023'], age=67, population='CNA', verbose=False)
    assert 'HCC223' in results.category_list


def test_demo_category_mapping():
    model = MedicareModel('v28')
    results = model.score(gender='M', orec='1', medicaid=False, diagnosis_codes=['E1169'], age=67, population='CNA', verbose=False)
    assert 'M65_69' in results.category_list
    assert 'OriginallyDisabled_Male' in results.category_list
    results = model.score(gender='F', orec='0', medicaid=True, diagnosis_codes=['I209'], age=86, population='CNA', verbose=False)
    assert 'F85_89' in results.category_list


def test_age_sex_edits():
    model = MedicareModel('v28')
    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['D66'], age=67, population='CNA', verbose=False)
    assert 'HCC112' in results.category_list

    # The edit should result in no disease categories just a demographic category
    results = model.score(gender='M', orec='0', medicaid=True, diagnosis_codes=['J430'], age=17, population='CPD', verbose=False)
    assert len(results.category_list)==1

    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['C50229'], age=47, population='CPD', verbose=False)
    assert 'HCC22' in results.category_list

    # The edit should result in no disease categories just a demographic category
    results = model.score(gender='M', orec='0', medicaid=True, diagnosis_codes=['P0449'], age=5, population='CPD', verbose=False)
    assert len(results.category_list)==1


def test_category_interactions():
    model = MedicareModel('v28')

    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['E0810', 'I5084'], age=67, population='CNA', verbose=False)
    assert 'DIABETES_HF_V28' in results.category_list

    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['T8620', 'J84112'], age=67, population='CNA', verbose=False)
    assert 'HF_CHR_LUNG_V28' in results.category_list

    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['I0981', 'N184'], age=67, population='CNA', verbose=False)
    assert 'HF_KIDNEY_V28' in results.category_list

    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['E8419', 'P2881'], age=67, population='CNA', verbose=False)
    assert 'CHR_LUNG_CARD_RESP_FAIL_V28' in results.category_list

    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['I0981', 'I470'], age=67, population='CNA', verbose=False)
    assert 'HF_HCC238_V28' in results.category_list

    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['F10132', 'F28'], age=67, population='CNA', verbose=False)
    assert 'gSubUseDisorder_gPsych_V28' in results.category_list


def test_new_enrollee():
    model = MedicareModel('v28')
    # NE_NMCAID_NORIGDIS
    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=[], age=67, population='NE', verbose=False)
    assert results.risk_model_population == 'NE_NMCAID_NORIGDIS'
    assert 'NEF67' in results.category_list
    # NE_MCAID_NORIGDIS
    results = model.score(gender='F', orec='0', medicaid=True, diagnosis_codes=[], age=67, population='NE', verbose=False)
    assert results.risk_model_population == 'NE_MCAID_NORIGDIS'
    assert 'NEF67' in results.category_list
    # NE_NMCAID_ORIGDIS
    results = model.score(gender='F', orec='1', medicaid=False, diagnosis_codes=[], age=67, population='NE', verbose=False)
    assert results.risk_model_population == 'NE_NMCAID_ORIGDIS'
    assert 'NEF67' in results.category_list
    # NE_MCAID_ORIGDIS
    results = model.score(gender='F', orec='1', medicaid=True, diagnosis_codes=[], age=67, population='NE', verbose=False)
    assert results.risk_model_population == 'NE_MCAID_ORIGDIS'
    assert 'NEF67' in results.category_list


def test_raw_score():
    model = MedicareModel('v28')
    results = model.score(gender='M', orec='0', medicaid=False, diagnosis_codes=['E1169', 'I509'], age=70, population='CNA')
    assert isclose(results.score_raw, 1.034)
    results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['E1169', 'I5030', 'I509', 'I211', 'I209', 'R05'], age=45, population='CND')
    assert isclose(results.score_raw, 0.996)

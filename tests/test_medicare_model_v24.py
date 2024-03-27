from risk_adjustment_model import MedicareModelV24
from math import isclose


def test_category_mapping():
    model = MedicareModelV24()
    results = model.score(
        gender="M",
        orec="1",
        medicaid=False,
        diagnosis_codes=["E1169"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC18" in results.category_list
    results = model.score(
        gender="M",
        orec="1",
        medicaid=False,
        diagnosis_codes=["I209"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC88" in results.category_list


def test_demo_category_mapping():
    model = MedicareModelV24()
    results = model.score(
        gender="M",
        orec="1",
        medicaid=False,
        diagnosis_codes=["E1169"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "M65_69" in results.category_list
    assert "OriginallyDisabled_Male" in results.category_list
    results = model.score(
        gender="F",
        orec="0",
        medicaid=True,
        diagnosis_codes=["I209"],
        age=86,
        population="CNA",
        verbose=False,
    )
    assert "F85_89" in results.category_list


def test_age_sex_edits():
    model = MedicareModelV24()
    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["D66"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC48" in results.category_list
    results = model.score(
        gender="M",
        orec="0",
        medicaid=True,
        diagnosis_codes=["J430"],
        age=17,
        population="CPD",
        verbose=False,
    )
    assert "HCC112" in results.category_list
    results = model.score(
        gender="M",
        orec="0",
        medicaid=True,
        diagnosis_codes=["F3481"],
        age=25,
        population="CPD",
        verbose=False,
    )
    # LTIMCAID shows in addition to the demographic
    assert len(results.category_list) == 2


def test_category_interactions():
    model = MedicareModelV24()

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["D61811", "C4010"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC47_gCancer" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["E1169", "A3681"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "DIABETES_CHF" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["A3681", "J410"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "CHF_gCopdCF" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["A3681", "I120"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC85_gRenal_V24" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["J410", "R092"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "gCopdCF_CARD_RESP_FAIL" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["A3681", "I442"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC85_HCC96" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["F10120", "F28"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "gSubstanceUseDisorder_gPsych" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["A021", "L89000"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "SEPSIS_PRESSURE_ULCER" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["A021", "Z432"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "SEPSIS_ARTIF_OPENINGS" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["Z432", "L89000"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "ART_OPENINGS_PRESS_ULCER" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["J410", "A481"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "gCopdCF_ASP_SPEC_B_PNEUM" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["A481", "L89000"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "ASP_SPEC_B_PNEUM_PRES_ULC" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["A021", "A481"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "SEPSIS_ASP_SPEC_BACT_PNEUM" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["F200", "J410"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "SCHIZOPHRENIA_gCopdCF" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["F200", "A3681"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "SCHIZOPHRENIA_CHF" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["F200", "G40009"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "SCHIZOPHRENIA_SEIZURES" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["A3681"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_HCC85" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["L89000"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_PRESSURE_ULCER" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["L97101"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_HCC161" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["M0000"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_HCC39" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["G360"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_HCC77" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["A072"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_HCC6" in results.category_list


def test_new_enrollee():
    model = MedicareModelV24()
    # NE_NMCAID_NORIGDIS
    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=[],
        age=67,
        population="NE",
        verbose=False,
    )
    assert results.risk_model_population == "NE_NMCAID_NORIGDIS"
    assert "NEF67" in results.category_list
    # NE_MCAID_NORIGDIS
    results = model.score(
        gender="F",
        orec="0",
        medicaid=True,
        diagnosis_codes=[],
        age=67,
        population="NE",
        verbose=False,
    )
    assert results.risk_model_population == "NE_MCAID_NORIGDIS"
    assert "NEF67" in results.category_list
    # NE_NMCAID_ORIGDIS
    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=[],
        age=67,
        population="NE",
        verbose=False,
    )
    assert results.risk_model_population == "NE_NMCAID_ORIGDIS"
    assert "NEF67" in results.category_list
    # NE_MCAID_ORIGDIS
    results = model.score(
        gender="F",
        orec="1",
        medicaid=True,
        diagnosis_codes=[],
        age=67,
        population="NE",
        verbose=False,
    )
    assert results.risk_model_population == "NE_MCAID_ORIGDIS"
    assert "NEF67" in results.category_list


def test_raw_score():
    model = MedicareModelV24()
    results = model.score(
        gender="M",
        orec="0",
        medicaid=False,
        diagnosis_codes=["E1169", "I509"],
        age=70,
        population="CNA",
    )
    assert isclose(results.score_raw, 1.148)
    results = model.score(
        gender="M",
        orec="0",
        medicaid=False,
        diagnosis_codes=["E1169", "I5030", "I509", "I2111", "I209"],
        age=70,
        population="CNA",
    )
    assert isclose(results.score_raw, 1.343)
    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["E1169", "I5030", "I509", "I2111", "I209"],
        age=45,
        population="CND",
    )
    assert isclose(results.score_raw, 1.434)

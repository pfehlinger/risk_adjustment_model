from risk_adjustment_model import MedicareModelV28
from math import isclose


def test_category_mapping():
    model = MedicareModelV28()
    results = model.score(
        gender="M",
        orec="1",
        medicaid=False,
        diagnosis_codes=["E08311"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC37" in results.category_list
    results = model.score(
        gender="M",
        orec="1",
        medicaid=False,
        diagnosis_codes=["D8687"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC93" in results.category_list
    # Check the Heart Patch works, diag goes to HCC223 and since it is the only one present, it should be removed
    results = model.score(
        gender="M",
        orec="0",
        medicaid=False,
        diagnosis_codes=["T82522A"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert len(results.category_list) == 1
    # Now see if HCC223 is present when HCC224 existed thus heart patch shouldn't do anything
    results = model.score(
        gender="M",
        orec="0",
        medicaid=False,
        diagnosis_codes=["T82522A", "I5023"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC223" in results.category_list


def test_demo_category_mapping():
    model = MedicareModelV28()
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
        diagnosis_codes=["I2109"],
        age=86,
        population="CNA",
        verbose=False,
    )
    assert "F85_89" in results.category_list


def test_age_sex_edits():
    model = MedicareModelV28()
    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["D66"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC112" in results.category_list

    # The edit should result in no disease categories just a demographic category
    results = model.score(
        gender="M",
        orec="0",
        medicaid=True,
        diagnosis_codes=["J430"],
        age=17,
        population="CPD",
        verbose=False,
    )
    # LTIMCAID shows in addition to the demographic
    assert len(results.category_list) == 2

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["C50229"],
        age=47,
        population="CPD",
        verbose=False,
    )
    assert "HCC22" in results.category_list

    # The edit should result in no disease categories just a demographic category
    results = model.score(
        gender="M",
        orec="0",
        medicaid=True,
        diagnosis_codes=["P0449"],
        age=5,
        population="CPD",
        verbose=False,
    )
    # LTIMCAID shows in addition to the demographic
    assert len(results.category_list) == 2


def test_category_interactions():
    model = MedicareModelV28()

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["E0810", "I5084"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "DIABETES_HF_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["T8620", "J84112"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HF_CHR_LUNG_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["I0981", "N184"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HF_KIDNEY_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["E8419", "P2881"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "CHR_LUNG_CARD_RESP_FAIL_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["I0981", "I470"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HF_HCC238_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["F10132", "F28"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "gSubUseDisorder_gPsych_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["C772"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_CANCER_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["G1220"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_NEURO_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["I5084"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_HF_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["E8419"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_CHR_LUNG_V28" in results.category_list

    results = model.score(
        gender="F",
        orec="1",
        medicaid=False,
        diagnosis_codes=["L89003"],
        age=60,
        population="INS",
        verbose=False,
    )
    assert "DISABLED_ULCER_V28" in results.category_list


def test_new_enrollee():
    model = MedicareModelV28()
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


def test_new_enrollee_medicaid_is_independent_of_ne_medicaid():
    # CMS's beneficiary file has two separate Medicaid columns -- LTIMCAID (continuing-enrollee
    # scoring, `medicaid`) and NEMCAID (new-enrollee population resolution, `ne_medicaid`) --
    # which are not guaranteed to agree for a given beneficiary. `ne_medicaid` must drive NE
    # population resolution, not `medicaid`.
    model = MedicareModelV28()
    results = model.score(
        gender="F",
        orec="0",
        medicaid=True,
        ne_medicaid=False,
        diagnosis_codes=[],
        age=67,
        population="NE",
        verbose=False,
    )
    assert results.risk_model_population == "NE_NMCAID_NORIGDIS"

    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        ne_medicaid=True,
        diagnosis_codes=[],
        age=67,
        population="NE",
        verbose=False,
    )
    assert results.risk_model_population == "NE_MCAID_NORIGDIS"

    # ne_medicaid defaults to medicaid when not passed, preserving prior behavior.
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
    assert results.ne_medicaid is True


def test_orig_disabled_only_applies_to_orec_1_not_orec_3():
    # CMS's own current source (CMS_HCC_utils.py) only sets ORIGDIS for orec == "1", not "3"
    # (both DIB and ESRD) -- despite `disabled` itself keying off any non-"0" orec while under 65.
    model = MedicareModelV28()
    results = model.score(
        gender="M", orec="1", medicaid=False, age=68, population="CNA"
    )
    assert "OriginallyDisabled_Male" in results.category_list

    results = model.score(
        gender="M", orec="3", medicaid=False, age=68, population="CNA"
    )
    assert "OriginallyDisabled_Male" not in results.category_list


def test_dob_input_does_not_crash():
    # MedicareBeneficiary previously used the raw `age` input (None when dob was passed
    # instead) in several places that need the resolved risk_model_age, crashing unconditionally
    # for any dob-based scoring call.
    model = MedicareModelV28(year=2026)
    results = model.score(
        gender="M", orec="0", medicaid=False, dob="1956-01-15", population="CNA"
    )
    assert results.risk_model_age == 70
    assert "M70_74" in results.category_list


def test_new_enrollee_age_64_orec_0_recodes_to_65():
    # Per CMS (CMS_HCC_utils.py's get_ne_bene_age_sex_vars), a New Enrollee exactly age 64 with
    # orec == "0" is recoded into the single-year "65" band, not "60_64".
    model = MedicareModelV28()
    results = model.score(gender="F", orec="0", medicaid=False, age=64, population="NE")
    assert "NEF65" in results.category_list
    assert "NEF60_64" not in results.category_list

    results = model.score(gender="F", orec="1", medicaid=False, age=64, population="NE")
    assert "NEF60_64" in results.category_list


def test_raw_score():
    model = MedicareModelV28(year=2024)
    results = model.score(
        gender="M",
        orec="0",
        medicaid=False,
        diagnosis_codes=["E1169", "I509"],
        age=70,
        population="CNA",
    )
    assert isclose(results.score_raw, 1.034)
    results = model.score(
        gender="F",
        orec="0",
        medicaid=False,
        diagnosis_codes=["E1169", "I5030", "I509", "I2111", "I2109"],
        age=45,
        population="CND",
    )
    assert isclose(results.score_raw, 1.250)


def test_year_2026_and_2027_of_model():
    # Golden value cross-validated directly against CMS's own PY2026 transform.py
    # (SCORE_COMMUNITY_NA = 1.286 for this exact beneficiary/diagnosis combination).
    for year in (2026, 2027):
        model = MedicareModelV28(year=year)
        results = model.score(
            gender="M",
            orec="0",
            medicaid=False,
            diagnosis_codes=["E1169", "I5030", "I509", "I2111"],
            age=70,
            population="CNA",
            verbose=False,
        )
        assert isclose(results.score_raw, 1.286)
        assert set(results.category_list) == {
            "HCC37",
            "HCC226",
            "HCC228",
            "M70_74",
            "D3",
            "DIABETES_HF_V28",
        }

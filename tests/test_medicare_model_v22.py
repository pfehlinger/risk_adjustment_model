from risk_adjustment_model import MedicareModelV22
from math import isclose


def test_category_mapping():
    model = MedicareModelV22()
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


def test_demo_category_mapping():
    model = MedicareModelV22()
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
        diagnosis_codes=[],
        age=86,
        population="CNA",
        verbose=False,
    )
    assert "F85_89" in results.category_list


def test_age_sex_edits():
    model = MedicareModelV22()
    # Female -> override to HCC48
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
    # Male -> static default HCC46
    results = model.score(
        gender="M",
        orec="0",
        medicaid=False,
        diagnosis_codes=["D66"],
        age=67,
        population="CNA",
        verbose=False,
    )
    assert "HCC46" in results.category_list
    # age < 18 -> override to HCC112
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
    # age >= 18 -> static default HCC111
    results = model.score(
        gender="M",
        orec="0",
        medicaid=True,
        diagnosis_codes=["J430"],
        age=30,
        population="CPD",
        verbose=False,
    )
    assert "HCC111" in results.category_list
    # age 6-18 -> static default HCC58
    results = model.score(
        gender="M",
        orec="0",
        medicaid=True,
        diagnosis_codes=["F3481"],
        age=10,
        population="CPD",
        verbose=False,
    )
    assert "HCC58" in results.category_list
    # outside age 6-18 -> rejected (no HCC/"NA" category), only demographic + LTIMCAID remain
    results = model.score(
        gender="M",
        orec="0",
        medicaid=True,
        diagnosis_codes=["F3481"],
        age=25,
        population="CPD",
        verbose=False,
    )
    assert not any(c.startswith("HCC") for c in results.category_list)


def test_category_interactions():
    model = MedicareModelV22()

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
    assert "HCC85_gDiabetesMellit" in results.category_list
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
    assert "HCC85_gCopdCF" in results.category_list
    assert "CHF_gCopdCF" in results.category_list

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
    # beneficiary is also disabled (orec=1, age<65) so the disabled interaction triggers too
    assert "DISABLED_PRESSURE_ULCER" in results.category_list

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
    model = MedicareModelV22()
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


def test_year_2026_and_2027_of_model():
    # Golden value cross-validated directly against CMS's own PY2026/2027 transform.py
    # (SCORE_COMMUNITY_NA = 1.407 for this exact beneficiary/diagnosis combination, both years).
    for year in (2026, 2027):
        model = MedicareModelV22(year=year)
        results = model.score(
            gender="M",
            orec="0",
            medicaid=False,
            diagnosis_codes=["E1169", "I5030", "I509", "I2111"],
            age=70,
            population="CNA",
            verbose=False,
        )
        assert isclose(results.score_raw, 1.407)
        assert set(results.category_list) == {
            "HCC18",
            "HCC85",
            "HCC86",
            "M70_74",
            "HCC85_gDiabetesMellit",
            "DIABETES_CHF",
        }


def test_normalization_and_coding_intensity_2026_2027():
    # Published CMS PY2026/2027 figures for V22.
    expected = {2026: 1.187, 2027: 1.202}
    for year, norm_factor in expected.items():
        model = MedicareModelV22(year=year)
        assert isclose(model.coding_intensity_adjuster, 0.941)
        assert isclose(model.normalization_factor, norm_factor)

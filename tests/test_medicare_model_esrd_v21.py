from risk_adjustment_model import MedicareModelESRDv21
from math import isclose


def test_dial_category_mapping():
    model = MedicareModelESRDv21()
    results = model.score(
        gender="M",
        orec="0",
        diagnosis_codes=["E1169"],
        age=67,
        population="DIAL",
        verbose=False,
    )
    assert "HCC18" in results.category_list
    assert "M65_69" in results.category_list


def test_renal_categories_are_scored():
    # Unlike V24, V21 does not zero renal categories -- N185 (CKD stage 5) should score normally.
    model = MedicareModelESRDv21()
    results = model.score(
        gender="M",
        orec="0",
        diagnosis_codes=["N185"],
        age=50,
        population="DIAL",
        verbose=False,
    )
    assert "HCC136" in results.category_list


def test_demographic_interactions():
    model = MedicareModelESRDv21()
    results = model.score(
        gender="F",
        orec="0",
        mcaid=True,
        diagnosis_codes=[],
        age=70,
        population="DIAL",
        verbose=False,
    )
    assert "MCAID" in results.category_list
    # DISABL == 0 (not disabled) is labeled "Aged" in CMS's source -- age 70 with orec "0" is
    # not disabled, so this is the "Aged" bucket despite being a chronological match too.
    assert "MCAID_Female_Aged" in results.category_list

    # orec == "1" and age >= 65 -> "originally disabled"
    results = model.score(
        gender="F", orec="1", diagnosis_codes=[], age=70, population="DIAL"
    )
    assert "OriginallyDisabled_Female" in results.category_list

    # orec == "2"/"3" (originally entitled due to ESRD) and aged -> Originally_ESRD_*
    results = model.score(
        gender="M", orec="2", diagnosis_codes=[], age=70, population="DIAL"
    )
    assert "Originally_ESRD_Male" in results.category_list


def test_mcaid_vs_ne_mcaid_are_independent():
    # CMS's beneficiary file has two separate dual-status columns (MCAID for continuing
    # enrollees, NEMCAID for new enrollees) -- confirm this repo doesn't conflate them.
    model = MedicareModelESRDv21()
    r1 = model.score(
        gender="F", orec="0", mcaid=True, ne_mcaid=False, age=67, population="NE_DIAL"
    )
    r2 = model.score(
        gender="F", orec="0", mcaid=False, ne_mcaid=True, age=67, population="NE_DIAL"
    )
    assert r1.risk_model_population == "NE_DIAL_NMCAID_NORIGDIS"
    assert r2.risk_model_population == "NE_DIAL_MCAID_NORIGDIS"
    assert not isclose(r1.score_raw, r2.score_raw)


def test_age_sex_edits():
    model = MedicareModelESRDv21()
    results = model.score(
        gender="F", orec="0", diagnosis_codes=["D66"], age=67, population="DIAL"
    )
    assert "HCC48" in results.category_list
    results = model.score(
        gender="M", orec="0", diagnosis_codes=["D66"], age=67, population="DIAL"
    )
    assert "HCC46" in results.category_list

    results = model.score(
        gender="M", orec="0", diagnosis_codes=["J430"], age=10, population="DIAL"
    )
    assert "HCC112" in results.category_list
    results = model.score(
        gender="M", orec="0", diagnosis_codes=["J430"], age=30, population="DIAL"
    )
    assert "HCC111" in results.category_list

    # F3481 targets HCC58 in V21 (not HCC59, unlike V22/V24 Community); no static default row.
    results = model.score(
        gender="M", orec="0", diagnosis_codes=["F3481"], age=10, population="DIAL"
    )
    assert "HCC58" in results.category_list
    results = model.score(
        gender="M", orec="0", diagnosis_codes=["F3481"], age=25, population="DIAL"
    )
    assert not any(c.startswith("HCC") for c in results.category_list)


def test_disease_interactions():
    model = MedicareModelESRDv21()
    results = model.score(
        gender="F",
        orec="0",
        diagnosis_codes=["E1169", "A3681"],
        age=67,
        population="DIAL",
        verbose=False,
    )
    assert "DIABETES_CHF" in results.category_list

    # CHF_RENAL is reachable in V21 (unlike V24's omitted HCC85_gRenal_V24)
    results = model.score(
        gender="F",
        orec="0",
        diagnosis_codes=["A3681", "N185"],
        age=67,
        population="DIAL",
        verbose=False,
    )
    assert "CHF_RENAL" in results.category_list

    # NONAGED_* is keyed off DISABL (age < 65 and orec-conditioned), not plain age
    results = model.score(
        gender="F", orec="0", diagnosis_codes=["A3681"], age=40, population="DIAL"
    )
    assert "NONAGED_HCC85" not in results.category_list  # orec "0" -> not disabled
    results = model.score(
        gender="F", orec="1", diagnosis_codes=["A3681"], age=40, population="DIAL"
    )
    assert "NONAGED_HCC85" in results.category_list


def test_graft_community_and_institutional():
    model = MedicareModelESRDv21()
    # cross-validated directly against CMS's own PY2026 transform.py.
    results = model.score(
        gender="F",
        orec="0",
        mcaid=True,
        diagnosis_codes=["D66"],
        age=67,
        population="GRAFT_COMM",
        graft_duration_months=6,
        verbose=False,
    )
    assert results.risk_model_population == "GRAFT_COMM"
    assert isclose(results.score_raw, 3.362)

    results = model.score(
        gender="M",
        orec="0",
        mcaid=True,
        diagnosis_codes=[],
        age=40,
        population="GRAFT_INST",
        graft_duration_months=12,
        verbose=False,
    )
    assert isclose(results.score_raw, 1.87)


def test_new_enrollee_dialysis_and_graft():
    model = MedicareModelESRDv21()
    results = model.score(
        gender="F", orec="0", age=40, population="NE_DIAL", verbose=False
    )
    assert results.risk_model_population == "NE_DIAL_NMCAID_NORIGDIS"
    assert isclose(results.score_raw, 0.793)

    # No actuarial adjustment for NE_GRAFT in V21, unlike V24.
    results = model.score(
        gender="F",
        orec="0",
        ne_mcaid=True,
        age=67,
        population="NE_GRAFT",
        graft_duration_months=6,
        verbose=False,
    )
    assert results.risk_model_population == "NE_GRAFT_MCAID_NORIGDIS"
    assert isclose(results.score_raw, 3.481)


def test_transplant_flat_scores():
    model = MedicareModelESRDv21()
    r1 = model.score(gender="M", orec="0", age=50, population="TRANSPLANT_1M")
    r2 = model.score(gender="M", orec="0", age=50, population="TRANSPLANT_2M")
    r3 = model.score(gender="M", orec="0", age=50, population="TRANSPLANT_3M")
    assert isclose(r1.score_raw, 6.03)
    assert isclose(r2.score_raw, 0.895)
    assert isclose(r3.score_raw, 0.895)
    assert r1.category_list == []


def test_normalization_factor_is_population_group_dependent():
    # CMS publishes a distinct normalization factor for the "Dialysis CMS-HCC" series (DIAL,
    # NE_DIAL, TRANSPLANT_*M) vs. the "Functioning Graft CMS-HCC" series (GRAFT_COMM, GRAFT_INST,
    # NE_GRAFT) -- not one flat value per year.
    model = MedicareModelESRDv21(year=2026)
    assert isclose(model.coding_intensity_adjuster, 0.941)

    dial = model.score(gender="M", orec="0", age=50, population="DIAL")
    assert isclose(dial.normalization_factor, 1.129)

    graft_comm = model.score(
        gender="M", orec="0", age=50, population="GRAFT_COMM", graft_duration_months=6
    )
    assert isclose(graft_comm.normalization_factor, 1.203)

    # 2027 figures -- checked directly via _get_normalization_factor, since this repo doesn't
    # have 2027 ESRD reference data built yet (a separate, tracked gap; see README) and so can't
    # instantiate a 2027 model to score through.
    assert isclose(model._get_normalization_factor(2027, "DIAL"), 1.145)
    assert isclose(model._get_normalization_factor(2027, "GRAFT_COMM"), 1.209)

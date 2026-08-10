from risk_adjustment_model import MedicareModelESRDv24
from math import isclose


def test_dial_category_mapping():
    model = MedicareModelESRDv24()
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


def test_renal_categories_excluded():
    # N185 (CKD stage 5) would map to a renal HCC in Community, but ESRD forcibly zeroes renal
    # categories -- an ESRD beneficiary is definitionally already on dialysis/graft-dependent.
    model = MedicareModelESRDv24()
    results = model.score(
        gender="M",
        orec="0",
        diagnosis_codes=["N185"],
        age=50,
        population="DIAL",
        verbose=False,
    )
    assert not any(c.startswith("HCC") for c in results.category_list)


def test_demographic_interactions():
    model = MedicareModelESRDv24()
    results = model.score(
        gender="F",
        orec="0",
        fbdual=True,
        lti=True,
        diagnosis_codes=[],
        age=70,
        population="DIAL",
        verbose=False,
    )
    assert "FBDual_Female_Aged" in results.category_list
    assert "LTI_Aged" in results.category_list

    results = model.score(
        gender="M",
        orec="0",
        pbdual=True,
        diagnosis_codes=[],
        age=40,
        population="DIAL",
        verbose=False,
    )
    assert "PBDual_Male_NonAged" in results.category_list

    # orec == "1" and age >= 65 -> "originally disabled"
    results = model.score(
        gender="F",
        orec="1",
        diagnosis_codes=[],
        age=70,
        population="DIAL",
        verbose=False,
    )
    assert "OriginallyDisabled_Female" in results.category_list

    # orec == "2"/"3" (originally entitled due to ESRD) and aged -> Originally_ESRD_*
    results = model.score(
        gender="M",
        orec="2",
        diagnosis_codes=[],
        age=70,
        population="DIAL",
        verbose=False,
    )
    assert "Originally_ESRD_Male" in results.category_list


def test_age_sex_edits():
    model = MedicareModelESRDv24()
    # D66/D67: female overrides to HCC48, male keeps static default HCC46
    results = model.score(
        gender="F", orec="0", diagnosis_codes=["D66"], age=67, population="DIAL"
    )
    assert "HCC48" in results.category_list
    results = model.score(
        gender="M", orec="0", diagnosis_codes=["D66"], age=67, population="DIAL"
    )
    assert "HCC46" in results.category_list

    # J-codes: age < 18 -> HCC112, age >= 18 -> static default HCC111
    results = model.score(
        gender="M", orec="0", diagnosis_codes=["J430"], age=10, population="DIAL"
    )
    assert "HCC112" in results.category_list
    results = model.score(
        gender="M", orec="0", diagnosis_codes=["J430"], age=30, population="DIAL"
    )
    assert "HCC111" in results.category_list

    # F3481: no static default in ESRD's crosswalk (unlike Community) -- only maps within 6-18
    results = model.score(
        gender="M", orec="0", diagnosis_codes=["F3481"], age=10, population="DIAL"
    )
    assert "HCC59" in results.category_list
    results = model.score(
        gender="M", orec="0", diagnosis_codes=["F3481"], age=25, population="DIAL"
    )
    assert not any(c.startswith("HCC") for c in results.category_list)


def test_disease_interactions():
    model = MedicareModelESRDv24()
    results = model.score(
        gender="F",
        orec="0",
        diagnosis_codes=["E1169", "A3681"],
        age=67,
        population="DIAL",
        verbose=False,
    )
    assert "DIABETES_CHF" in results.category_list

    # NONAGED_* interactions only trigger under 65
    results = model.score(
        gender="F",
        orec="0",
        diagnosis_codes=["A3681"],
        age=40,
        population="DIAL",
        verbose=False,
    )
    assert "NONAGED_HCC85" in results.category_list
    results = model.score(
        gender="F",
        orec="0",
        diagnosis_codes=["A3681"],
        age=70,
        population="DIAL",
        verbose=False,
    )
    assert "NONAGED_HCC85" not in results.category_list


def test_graft_community():
    model = MedicareModelESRDv24()
    # cross-validated directly against CMS's own PY2026 transform.py:
    # SCORE_G_COMM_FBD_GE65_DUR4_9 = 3.247 for this exact beneficiary/diagnosis combination.
    results = model.score(
        gender="F",
        orec="0",
        fbdual=True,
        diagnosis_codes=["D66"],
        age=67,
        population="GRAFT_COMM",
        graft_duration_months=6,
        verbose=False,
    )
    assert results.risk_model_population == "GRAFT_COMM_FBD_GE65"
    assert isclose(results.score_raw, 3.247)

    # under 4 months has no bonus bucket -- score is just the base category sum
    results_no_bonus = model.score(
        gender="F",
        orec="0",
        fbdual=True,
        diagnosis_codes=["D66"],
        age=67,
        population="GRAFT_COMM",
        graft_duration_months=2,
        verbose=False,
    )
    assert results_no_bonus.graft_duration_months == 2
    assert results_no_bonus.score_raw < results.score_raw


def test_graft_institutional():
    model = MedicareModelESRDv24()
    # cross-validated: SCORE_GRAFT_INST_ND_PBD_GE65_DUR10PL = 3.287 (PBDual + LTI both add bonus
    # terms on top of the base GRAFT_INST coefficient, which itself doesn't vary by dual/aged).
    results = model.score(
        gender="M",
        orec="0",
        pbdual=True,
        lti=True,
        diagnosis_codes=[],
        age=70,
        population="GRAFT_INST",
        graft_duration_months=12,
        verbose=False,
    )
    assert isclose(results.score_raw, 3.287)


def test_new_enrollee_dialysis():
    model = MedicareModelESRDv24()
    # cross-validated: SCORE_DIAL_NE = 0.747
    results = model.score(
        gender="F", orec="0", age=40, population="NE_DIAL", verbose=False
    )
    assert results.risk_model_population == "NE_DIAL_ND_PBD_NORIGDIS"
    assert isclose(results.score_raw, 0.747)
    assert "NEF35_44" in results.category_list


def test_new_enrollee_graft():
    model = MedicareModelESRDv24()
    # cross-validated: SCORE_GRAFT_NE_GE65_DUR4_9_FBD = 3.979 (includes the mandatory actuarial
    # adjustment division by 0.905 for the 4-9 month bucket).
    results = model.score(
        gender="F",
        orec="0",
        fbdual=True,
        age=67,
        population="NE_GRAFT",
        graft_duration_months=6,
        verbose=False,
    )
    assert results.risk_model_population == "NE_GRAFT_FBD_NORIGDIS"
    assert isclose(results.score_raw, 3.979)


def test_transplant_flat_scores():
    model = MedicareModelESRDv24()
    # Flat CMS constants -- no dependence on diagnosis codes or demographics at all.
    r1 = model.score(gender="M", orec="0", age=50, population="TRANSPLANT_1M")
    r2 = model.score(gender="M", orec="0", age=50, population="TRANSPLANT_2M")
    r3 = model.score(gender="M", orec="0", age=50, population="TRANSPLANT_3M")
    assert isclose(r1.score_raw, 5.985)
    assert isclose(r2.score_raw, 0.941)
    assert isclose(r3.score_raw, 0.941)
    assert r1.category_list == []


def test_normalization_factor_is_population_group_dependent():
    # CMS publishes a distinct normalization factor for the "Dialysis CMS-HCC" series (DIAL,
    # NE_DIAL, TRANSPLANT_*M) vs. the "Functioning Graft CMS-HCC" series (GRAFT_COMM, GRAFT_INST,
    # NE_GRAFT) -- not one flat value per year.
    model = MedicareModelESRDv24(year=2026)
    assert isclose(model.coding_intensity_adjuster, 0.941)

    dial = model.score(gender="M", orec="0", age=50, population="DIAL")
    assert isclose(dial.normalization_factor, 1.062)

    ne_dial = model.score(gender="M", orec="0", age=50, population="NE_DIAL")
    assert isclose(ne_dial.normalization_factor, 1.062)

    transplant = model.score(gender="M", orec="0", age=50, population="TRANSPLANT_1M")
    assert isclose(transplant.normalization_factor, 1.062)

    graft_comm = model.score(
        gender="M", orec="0", age=50, population="GRAFT_COMM", graft_duration_months=6
    )
    assert isclose(graft_comm.normalization_factor, 1.104)

    graft_inst = model.score(
        gender="M", orec="0", age=50, population="GRAFT_INST", graft_duration_months=6
    )
    assert isclose(graft_inst.normalization_factor, 1.104)

    ne_graft = model.score(
        gender="M", orec="0", age=50, population="NE_GRAFT", graft_duration_months=6
    )
    assert isclose(ne_graft.normalization_factor, 1.104)

    # 2027 figures -- checked directly via _get_normalization_factor, since this repo doesn't
    # have 2027 ESRD reference data built yet (a separate, tracked gap; see README) and so can't
    # instantiate a 2027 model to score through.
    assert isclose(model._get_normalization_factor(2027, "DIAL"), 1.072)
    assert isclose(model._get_normalization_factor(2027, "GRAFT_COMM"), 1.119)

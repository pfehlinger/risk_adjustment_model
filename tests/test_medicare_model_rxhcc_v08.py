import pytest
from math import isclose
from risk_adjustment_model import (
    MedicareModelRxHCCv08T,
    MedicareModelRxHCCv08X,
    MedicareModelRxHCCv08T2,
    MedicareModelRxHCCv08Y1,
    MedicareModelRxHCCv08Y2,
)

SEGMENT_CLASSES = [
    MedicareModelRxHCCv08T,
    MedicareModelRxHCCv08X,
    MedicareModelRxHCCv08T2,
    MedicareModelRxHCCv08Y1,
    MedicareModelRxHCCv08Y2,
]


@pytest.mark.parametrize("model_class", SEGMENT_CLASSES)
def test_ce_category_mapping(model_class):
    model = model_class()
    results = model.score(
        gender="M",
        orec="0",
        diagnosis_codes=["E1169"],
        age=67,
        population="CE_NONLOW_AGED",
        verbose=False,
    )
    assert "RXHCC30" in results.category_list
    assert "M65_69" in results.category_list


@pytest.mark.parametrize("model_class", SEGMENT_CLASSES)
def test_originally_disabled_interactions(model_class):
    model = model_class()
    # orec == "1" and age >= 65 -> "originally disabled": both gendered and ungendered flags
    results = model.score(
        gender="F", orec="1", age=70, population="CE_LOW_AGED", verbose=False
    )
    assert "F65OD" in results.category_list
    assert "OD65" in results.category_list

    # not originally disabled -- neither flag present
    results = model.score(
        gender="F", orec="0", age=70, population="CE_LOW_AGED", verbose=False
    )
    assert "F65OD" not in results.category_list
    assert "OD65" not in results.category_list


@pytest.mark.parametrize("model_class", SEGMENT_CLASSES)
def test_nonaged_disease_interaction(model_class):
    model = model_class()
    # RXHCC1 is one of the 7 NONAGED_RXHCC{n} codes -- only triggers under 65
    results = model.score(
        gender="F",
        orec="0",
        diagnosis_codes=["B20"],
        age=40,
        population="CE_NONLOW_NONAGED",
        verbose=False,
    )
    assert "RXHCC1" in results.category_list
    assert "NONAGED_RXHCC1" in results.category_list

    results = model.score(
        gender="F",
        orec="0",
        diagnosis_codes=["B20"],
        age=70,
        population="CE_NONLOW_AGED",
        verbose=False,
    )
    assert "NONAGED_RXHCC1" not in results.category_list


@pytest.mark.parametrize("model_class", SEGMENT_CLASSES)
def test_ce_lti_is_single_population(model_class):
    model = model_class()
    results = model.score(
        gender="M", orec="0", age=50, population="CE_LTI", verbose=False
    )
    assert results.risk_model_population == "CE_LTI"


@pytest.mark.parametrize("model_class", SEGMENT_CLASSES)
def test_new_enrollee_ignores_diagnosis_codes(model_class):
    # CMS's own NE coefficient files have no disease/HCC columns at all -- an RXHCC category
    # can still appear in category_list/category_details (this repo's usual "include it at its
    # population-specific coefficient, even when 0" philosophy), but it must never affect score.
    model = model_class()
    with_dx = model.score(
        gender="M",
        orec="0",
        diagnosis_codes=["E1169"],
        age=40,
        population="NE_NONLOW_COMMUNITY",
    )
    without_dx = model.score(
        gender="M", orec="0", age=40, population="NE_NONLOW_COMMUNITY"
    )
    assert isclose(with_dx.score_raw, without_dx.score_raw)
    assert with_dx.category_details["RXHCC30"]["coefficient"] == 0.0


@pytest.mark.parametrize("model_class", SEGMENT_CLASSES)
def test_new_enrollee_esrd_and_origdis_category(model_class):
    model = model_class()
    results = model.score(
        gender="M", orec="0", esrd=True, age=40, population="NE_NONLOW_COMMUNITY"
    )
    assert results.category_list == ["ESRD_NORIGDIS_X_M35_44"]

    # origdis only applies at age >= 65
    results = model.score(
        gender="M", orec="1", esrd=False, age=70, population="NE_LOW_COMMUNITY"
    )
    assert results.category_list == ["NESRD_ORIGDIS_X_M70_74"]

    # age 64 with orec == "0" recodes to age 65 for NE band selection
    results = model.score(gender="F", orec="0", esrd=False, age=64, population="NE_LTI")
    assert results.category_list == ["NESRD_NORIGDIS_X_F65"]


def test_t_segment_golden_values():
    # cross-validated directly against CMS's own PY2026 T-segment transform.py.
    model = MedicareModelRxHCCv08T(year=2026)
    results = model.score(
        gender="M",
        orec="0",
        esrd=False,
        diagnosis_codes=["E1169"],
        age=67,
        population="CE_NONLOW_AGED",
    )
    assert isclose(results.score_raw, 0.663)

    results = model.score(
        gender="M",
        orec="0",
        esrd=True,
        diagnosis_codes=["J449"],
        age=40,
        population="NE_NONLOW_COMMUNITY",
    )
    assert isclose(results.score_raw, 1.139)


def test_y1_segment_golden_values():
    # cross-validated directly against CMS's own PY2027 Y1-segment (MAPD-only) transform.py.
    model = MedicareModelRxHCCv08Y1(year=2027)
    results = model.score(
        gender="M", orec="0", esrd=False, age=68, population="NE_NONLOW_COMMUNITY"
    )
    assert isclose(results.score_raw, 0.669)


@pytest.mark.parametrize("model_class", SEGMENT_CLASSES)
def test_coding_intensity_is_always_one(model_class):
    # Part D has no statutory coding-intensity adjustment the way Part C does.
    model = model_class()
    assert isclose(model.coding_intensity_adjuster, 1)


def test_t_x_t2_y1_y2_each_apply_their_own_normalization_factor():
    # Published CMS figures -- each segment differs from every other, even within the same
    # payment year (T2/Y1/Y2 are all 2027), so normalization can't live in the shared base class.
    assert isclose(MedicareModelRxHCCv08T(year=2026).normalization_factor, 1.202)
    assert isclose(MedicareModelRxHCCv08T2(year=2027).normalization_factor, 1.237)
    assert isclose(MedicareModelRxHCCv08Y1(year=2027).normalization_factor, 1.109)
    assert isclose(MedicareModelRxHCCv08Y2(year=2027).normalization_factor, 1.005)


def test_x_segment_channel_affects_normalization_not_score_raw():
    # X's regression is calibrated on pooled PDP+MAPD data (score_raw doesn't vary by channel),
    # but CMS publishes a different normalization factor for each -- 1.194 MAPD vs. 0.887 PDP.
    model = MedicareModelRxHCCv08X(year=2026)
    kwargs = dict(
        gender="M",
        orec="0",
        esrd=False,
        diagnosis_codes=["E1169"],
        age=67,
        population="CE_NONLOW_AGED",
    )
    mapd = model.score(**kwargs, channel="MAPD")
    pdp = model.score(**kwargs, channel="PDP")

    assert isclose(mapd.score_raw, pdp.score_raw)
    assert not isclose(mapd.score, pdp.score)
    assert isclose(mapd.normalization_factor, 1.194)
    assert isclose(pdp.normalization_factor, 0.887)
    assert mapd.channel == "MAPD"
    assert pdp.channel == "PDP"

    # channel defaults to MAPD when not passed.
    default = model.score(**kwargs)
    assert isclose(default.score, mapd.score)
    assert default.channel == "MAPD"

    # Non-X segments don't have a channel concept -- always None.
    t = MedicareModelRxHCCv08T(year=2026)
    t_result = t.score(**kwargs)
    assert t_result.channel is None

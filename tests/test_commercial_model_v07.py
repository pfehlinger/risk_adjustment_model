from risk_adjustment_model import CommercialModelV07


def test_category_mapping():
    model = CommercialModelV07(year=2023)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["A064"],
        age=35,
        verbose=False,
    )
    assert "HHS_HCC035_1" in results.category_list

    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=None,
        ndc_codes=["00069080860"],
        age=35,
        verbose=False,
    )
    assert "RXC_01" in results.category_list

    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=None,
        proc_codes=["J1817"],
        age=35,
        verbose=False,
    )
    assert "RXC_06" in results.category_list

    # Effective 2023-2024
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["I4719"],
        age=35,
        verbose=False,
    )
    assert "HHS_HCC142" in results.category_list

    # Effective 2022-2023
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["I471"],
        age=35,
        verbose=False,
    )
    assert "HHS_HCC142" in results.category_list


def test_category_groups():
    model = CommercialModelV07(year=2023)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E1169"],
        age=35,
        verbose=False,
    )
    assert "G01" in results.category_list

    # Test child only group, confirm in child
    # and not in adult
    # model = CommercialModelV07(year=2023)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E771"],
        age=12,
        verbose=False,
    )
    assert "G02D" in results.category_list
    assert "HHS_HCC028" not in results.category_list

    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E8029"],
        age=35,
        verbose=False,
    )
    assert "G02D" not in results.category_list
    assert "HHS_HCC029" in results.category_list


def test_demo_category_mapping():
    model = CommercialModelV07(year=2023)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E1169"],
        age=35,
        verbose=False,
    )
    assert "MAGE_LAST_35_39" in results.category_list

    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E1169"],
        age=12,
        verbose=False,
    )
    assert "FAGE_LAST_10_14" in results.category_list

    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E1169"],
        age=1,
        verbose=False,
    )
    assert "Age1_Male" in results.category_list

    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E1169"],
        age=1,
        verbose=False,
    )
    assert "Age1_Male" not in results.category_list


def test_age_sex_edits():
    model = CommercialModelV07(year=2023)

    # Test _age_sex_edit_1
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["C9100"],
        age=17,
        verbose=False,
    )
    assert "HHS_HCC009" in results.category_list

    # Test _age_sex_edit_2
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["J410"],
        age=17,
        verbose=False,
    )
    assert "HHS_HCC161_1" in results.category_list

    # Test _age_sex_edit_3
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["K55011"],
        age=1,
        verbose=False,
    )
    assert "Age1_x_Severity5" in results.category_list

    # Test _age_sex_edit_4
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["C50011"],
        age=45,
        verbose=False,
    )
    assert "HHS_HCC011" in results.category_list

    # Test _age_sex_edit_5
    # Should only have a demographic category
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["J430"],
        age=1,
        verbose=False,
    )
    assert "Age1_x_Severity2" not in results.category_list
    assert "Age1_x_Severity1" in results.category_list

    # Test _age_sex_edit_6
    # Should only have demographic category
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["H353210"],
        age=20,
        verbose=False,
    )
    assert len(results.category_list) == 1

    # Test _age_sex_edit_7
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["P0500"],
        age=1,
        verbose=False,
    )
    assert "Age1_x_Severity1" in results.category_list

    # Test _age_sex_edit_8
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["Q894"],
        age=1,
        verbose=False,
    )
    assert "Age1_x_Severity2" in results.category_list

    # Test _age_sex_edit_9
    # Should only have a demographic category
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["K551"],
        age=2,
        verbose=False,
    )
    assert len(results.category_list) == 1

    # Test _age_sex_edit_10
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["P270"],
        age=2,
        verbose=False,
    )
    assert "HHS_HCC162" in results.category_list

    # Test _age_sex_edit_11
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["F3481"],
        age=5,
        verbose=False,
    )
    assert len(results.category_list) == 1

    # Test _age_sex_edit_12
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E700"],
        age=21,
        verbose=False,
    )
    assert len(results.category_list) == 1

    # Test _age_sex_edit_13
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["D66"],
        age=25,
        verbose=False,
    )
    assert "HHS_HCC075" in results.category_list

    # Test _age_sex_edit_14
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E10641"],
        age=20,
        verbose=False,
    )
    assert "HHS_HCC019" not in results.category_list
    assert "G01" in results.category_list

    # Test _age_sex_edit_15
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E1022"],
        age=20,
        verbose=False,
    )
    assert "HHS_HCC020" not in results.category_list
    assert "G01" in results.category_list

    # Test _age_sex_edit_16
    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=12,
        diagnosis_codes=["E108"],
        age=20,
        verbose=False,
    )
    assert "HHS_HCC021" not in results.category_list
    assert "G01" in results.category_list


def test_enrollment_duraction():
    model = CommercialModelV07(year=2023)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=5,
        diagnosis_codes=["A064"],
        age=35,
        verbose=False,
    )
    assert "HCC_ED5" in results.category_list

    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=10,
        diagnosis_codes=["A064"],
        age=35,
        verbose=False,
    )
    assert not any(category.startswith("HCC_ED") for category in results.category_list)


def test_infant_severity():
    model = CommercialModelV07(year=2023)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_months=2,
        diagnosis_codes=["Z051", "Z23", "Z3800"],
        age=0,
        verbose=False,
    )
    assert "Term_x_Severity1" in results.category_list

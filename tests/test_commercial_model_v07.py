from risk_adjustment_model import CommercialModelV07


def test_category_mapping():
    model = CommercialModelV07(year=2023)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["A064"],
        age=35,
        verbose=False,
    )
    assert "HHS_HCC035_1" in results.category_list

    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
        diagnosis_codes=["E8029"],
        age=35,
        verbose=False,
    )
    assert "G02D" not in results.category_list
    assert "HHS_HCC029" in results.category_list

    # Test that two HCCs not in a hierachy
    # that trigger a group are captured in the dropped
    # codes. As such need verbose output
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["E71311", "E71448"],
        age=18,
        verbose=True,
    )
    assert "G02D" in results.category_list
    assert "HHS_HCC028" in results.category_details["G02D"]["dropped_categories"]
    assert "HHS_HCC029" in results.category_details["G02D"]["dropped_categories"]

    # Starting in 2024, a new group exists G24 for adult model
    # it is for HCC18 and 183
    model = CommercialModelV07(year=2024)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["Z940"],
        age=57,
        verbose=True,
    )
    assert "G24" in results.category_list
    assert "HHS_HCC183" not in results.category_list
    assert "HHS_HCC183" in results.category_details["G24"]["dropped_categories"]

    # Test that if both 18 and 183 are present, doesn't lead to double counting of
    # categories
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["B3781", "D84821", "Z9483", "T8610"],
        age=57,
        verbose=True,
    )
    assert "HHS_HCC006" in results.category_list
    assert "G08" in results.category_list
    assert "G24" in results.category_list
    assert "SEVERE_HCC_COUNT3" in results.category_list
    assert "HHS_HCC183" not in results.category_list
    assert "HHS_HCC183" in results.category_details["G24"]["dropped_categories"]
    assert "HHS_HCC018" not in results.category_list
    assert "HHS_HCC018" in results.category_details["G24"]["dropped_categories"]
    assert "HHS_HCC074" not in results.category_list
    assert "HHS_HCC074" in results.category_details["G08"]["dropped_categories"]

    model = CommercialModelV07(year=2025)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["Z940"],
        age=57,
        verbose=True,
    )
    assert "G24" in results.category_list
    assert "HHS_HCC183" not in results.category_list
    assert "HHS_HCC183" in results.category_details["G24"]["dropped_categories"]

    # In 2025 G07A is no longer group
    # First test it is still exists for 2024
    model = CommercialModelV07(year=2024)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["D5700"],
        age=57,
        verbose=True,
    )
    assert "G07A" in results.category_list
    assert "HHS_HCC070" not in results.category_list
    assert "HHS_HCC070" in results.category_details["G07A"]["dropped_categories"]

    model = CommercialModelV07(year=2025)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["D5700"],
        age=57,
        verbose=True,
    )
    assert "G07A" not in results.category_list
    assert "HHS_HCC070" in results.category_list


def test_demo_category_mapping():
    model = CommercialModelV07(year=2023)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["E1169"],
        age=35,
        verbose=False,
    )
    assert "MAGE_LAST_35_39" in results.category_list

    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["E1169"],
        age=12,
        verbose=False,
    )
    assert "FAGE_LAST_10_14" in results.category_list

    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["E1169"],
        age=1,
        verbose=False,
    )
    assert "Age1_Male" in results.category_list

    results = model.score(
        gender="F",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=365,
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
        enrollment_days=150,
        diagnosis_codes=["A064"],
        age=35,
        verbose=False,
    )
    assert "HCC_ED5" in results.category_list

    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=300,
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
        enrollment_days=38,
        diagnosis_codes=["Z3800"],
        age=0,
        verbose=False,
    )
    assert "Term_x_Severity1" in results.category_list

    # In 2025, HCC071 moved up severity level
    # Test it is level 1 prior
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=38,
        diagnosis_codes=[
            "Z3800",
            "D562",  # HCC071
        ],
        age=0,
        verbose=False,
    )
    assert "Term_x_Severity1" in results.category_list

    model = CommercialModelV07(year=2025)
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=38,
        diagnosis_codes=[
            "Z3800",
            "D562",  # HCC071
        ],
        age=0,
        verbose=False,
    )
    assert "Term_x_Severity2" in results.category_list


def test_infant_age():
    model = CommercialModelV07(year=2024)

    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=38,
        diagnosis_codes=[
            "A0101",
        ],
        age=0,
        verbose=False,
    )
    assert "Age1_Male" in results.category_list
    assert results.risk_model_age == 1


def test_interactions():
    model = CommercialModelV07(year=2023)

    # RXC_05_x_HCC048_041
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=68,
        diagnosis_codes=["K50011"],
        ndc_codes=["70710154302"],
        age=54,
        verbose=False,
    )
    assert "RXC_05_x_HCC048_041" in results.category_list
    assert (
        "HHS_HCC048"
        in results.category_details["RXC_05_x_HCC048_041"]["trigger_code_map"]
    )

    # Test RXC_07_x_HCC018_019_020_021
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=68,
        diagnosis_codes=["E119"],
        ndc_codes=["00002147180"],
        age=54,
        verbose=False,
    )
    assert "RXC_07_x_HCC018_019_020_021" in results.category_list
    assert "G01" in results.category_list

    # "RXC_09_x_HCC056_057_and_048_041"
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=68,
        diagnosis_codes=["K50011", "M05019"],
        ndc_codes=["72606003003"],
        age=54,
        verbose=False,
    )
    assert "HHS_HCC056" in results.category_list
    assert "HHS_HCC048" in results.category_list
    assert "RXC_09_x_HCC056_057_and_048_041" in results.category_list

    # "RXC_04_x_HCC184_183_187_188"
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=68,
        diagnosis_codes=["I120"],
        ndc_codes=["00004040109"],
        age=54,
        verbose=False,
    )
    assert "G16" in results.category_list
    assert "HHS_HCC187" not in results.category_list
    assert "RXC_04_x_HCC184_183_187_188" in results.category_list


def test_dropped_categories():
    model = CommercialModelV07(year=2023)

    # Check Group dropping category
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["E119"],
        age=54,
        verbose=False,
    )
    assert "G01" in results.category_list
    assert "HHS_HCC021" in results.dropped_category_list

    # Check hierarchy dropping category
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["A0101", "A871"],
        age=54,
        verbose=False,
    )
    assert "HHS_HCC003" in results.category_list
    assert "HHS_HCC004" in results.dropped_category_list

    # Check hierarchy and group dropping categories
    # HCC020 should drop HCC021 and then the group
    # should drop HCC020
    results = model.score(
        gender="M",
        metal_level="Silver",
        csr_indicator=1,
        enrollment_days=365,
        diagnosis_codes=["E119", "E11610"],
        age=54,
        verbose=False,
    )
    assert "G01" in results.category_list
    assert "HHS_HCC021" in results.dropped_category_list
    assert "HHS_HCC020" in results.dropped_category_list


def test_refernce_files_version():
    model = CommercialModelV07(year=2023)
    assert "3.0" == model.reference_files_version

    model = CommercialModelV07(year=2024)
    assert "1.0" == model.reference_files_version

    model = CommercialModelV07(year=2025)
    assert "0.0" == model.reference_files_version

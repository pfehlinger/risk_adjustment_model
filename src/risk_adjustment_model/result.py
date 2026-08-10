from dataclasses import dataclass
from typing import List, Union, Dict


@dataclass
class BaseScoringResult:
    """
    Represents the scoring result for a specific individual in a population.

    Attributes:
        gender (str): The gender of the individual.
        age (int, optional): The age of the individual.
        dob (str, optional): The date of birth of the individual.
        diagnosis_codes (List[str], optional): A list of diagnosis codes associated with the individual.
        year (int, optional): The year passed into the model.
        risk_model_age (int): The age used in the risk model calculation.
        risk_model_population (str): The population group used in the risk model calculation.
        model_version (str): The version of the scoring model used.
        model_year (int): The year of the scoring model.
        score_raw (float): The raw score before any adjustments.
        disease_score_raw (float): The raw disease score before any adjustments.
        demographic_score_raw (float): The raw demographic score before any adjustments.
        score (float): The final score after adjustments.
        disease_score (float): The final disease score after adjustments.
        demographic_score (float): The final demographic score after adjustments.
        category_list (List[str]): A list of categories associated with the individual.
        category_details (Dict[str, str]): A dictionary containing details about each category.

    Notes:
        - The 'dob' attribute is expected to be in the format 'YYYY-MM-DD'.
        - The 'category_details' dictionary should contain category names as keys
          and corresponding details as values.
    """

    gender: str
    age: Union[int, None]
    dob: Union[str, None]
    diagnosis_codes: Union[List[str], None]
    year: Union[int, None]
    risk_model_age: int
    risk_model_population: str
    model_version: str
    model_year: int
    score_raw: float
    disease_score_raw: float
    demographic_score_raw: float
    score: float
    disease_score: float
    demographic_score: float
    category_list: List[str]
    category_details: Dict[str, str]


@dataclass
class MedicareScoringResult(BaseScoringResult):
    """
    Represents the scoring result for a Medicare beneficiary.

    Attributes:
        gender (str): The gender of the individual.
        orec (str): The OREC (original reason for entitlement category) of the individual.
        medicaid (bool): Indicates whether the individual has Medicaid coverage.
        age (int, optional): The age of the individual.
        dob (str, optional): The date of birth of the individual.
        diagnosis_codes (List[str], optional): A list of diagnosis codes associated with the individual.
        year (int, optional): The year passed into the model.
        risk_model_age (int): The age used in the risk model calculation.
        risk_model_population (str): The population group used in the risk model calculation.
        model_version (str): The version of the scoring model used.
        model_year (int): The year of the scoring model.
        score_raw (float): The raw score before any adjustments.
        disease_score_raw (float): The raw disease score before any adjustments.
        demographic_score_raw (float): The raw demographic score before any adjustments.
        score (float): The final score after adjustments.
        disease_score (float): The final disease score after adjustments.
        demographic_score (float): The final demographic score after adjustments.
        category_list (List[str]): A list of categories associated with the individual.
        category_details (Dict[str, str]): A dictionary containing details about each category.
        orec (str): The OREC (original reason for entitlement category) of the individual.
        medicaid (bool): Indicates whether the individual has Medicaid coverage.
        ne_medicaid (bool): Indicates Medicaid coverage used for new-enrollee population
                            resolution -- a separate CMS input from `medicaid`, see
                            MedicareBeneficiary's docstring.
        population (str): The population group to which the individual belongs.
        coding_intensity_adjuster (float): The coding intensity adjuster applied to the score.
        normalization_factor (float): The normalization factor applied to the score.

    Notes:
        - The 'dob' attribute is expected to be in the format 'YYYY-MM-DD'.
        - The 'category_details' dictionary should contain category names as keys
          and corresponding details as values.
    """

    orec: str
    medicaid: bool
    population: str
    coding_intensity_adjuster: float
    normalization_factor: float
    ne_medicaid: bool


@dataclass
class ESRDScoringResult(BaseScoringResult):
    """
    Represents the scoring result for a Medicare ESRD (End-Stage Renal Disease) beneficiary.

    Attributes:
        (see BaseScoringResult for the common fields)
        orec (str): The OREC (original reason for entitlement category) of the individual.
        fbdual (bool): Full Benefit Dual status.
        pbdual (bool): Partial Benefit Dual status.
        lti (bool): Long-Term Institutional status.
        population (str): The ESRD population passed in (DIAL, GRAFT_COMM, GRAFT_INST, NE_DIAL,
                          NE_GRAFT, or one of the flat TRANSPLANT_*M populations).
        graft_duration_months (int, optional): Months since transplant, used to select the
                                               graft-duration bonus bucket for GRAFT_COMM/
                                               GRAFT_INST/NE_GRAFT populations. None for
                                               DIAL/TRANSPLANT_*M, or a functioning-graft
                                               population with duration under 4 months (no bonus
                                               bucket applies yet -- see TRANSPLANT_*M instead).
        coding_intensity_adjuster (float): The coding intensity adjuster applied to the score.
        normalization_factor (float): The normalization factor applied to the score.
    """

    orec: str
    fbdual: bool
    pbdual: bool
    lti: bool
    population: str
    graft_duration_months: Union[int, None]
    coding_intensity_adjuster: float
    normalization_factor: float


@dataclass
class ESRDv21ScoringResult(BaseScoringResult):
    """
    Represents the scoring result for a Medicare ESRD V21 (legacy) beneficiary.

    Attributes:
        (see BaseScoringResult for the common fields)
        orec (str): The OREC (original reason for entitlement category) of the individual.
        mcaid (bool): Medicaid dual status used for continuing-enrollee scoring.
        ne_mcaid (bool): Medicaid dual status used for new-enrollee population resolution -- a
                         separate CMS input from `mcaid`, see ESRDv21Beneficiary.
        population (str): The ESRD population passed in (DIAL, GRAFT_COMM, GRAFT_INST, NE_DIAL,
                          NE_GRAFT, or one of the flat TRANSPLANT_*M populations).
        graft_duration_months (int, optional): Months since transplant, used to select the
                                               graft-duration bonus bucket for GRAFT_COMM/
                                               GRAFT_INST/NE_GRAFT populations.
        coding_intensity_adjuster (float): The coding intensity adjuster applied to the score.
        normalization_factor (float): The normalization factor applied to the score.
    """

    orec: str
    mcaid: bool
    ne_mcaid: bool
    population: str
    graft_duration_months: Union[int, None]
    coding_intensity_adjuster: float
    normalization_factor: float


@dataclass
class RxHCCScoringResult(BaseScoringResult):
    """
    Represents the scoring result for a Medicare RxHCC (Part D) beneficiary.

    Attributes:
        (see BaseScoringResult for the common fields)
        orec (str): The OREC (original reason for entitlement category) of the individual.
        esrd (bool): End-Stage Renal Disease status.
        population (str): The RxHCC population passed in -- see RxHCCBeneficiary.
        coding_intensity_adjuster (float): The coding intensity adjuster applied to the score.
        normalization_factor (float): The normalization factor applied to the score.
        channel (str, optional): Enrollment channel ("MAPD" or "PDP") used to select the
                                 normalization factor. Only meaningful for MedicareModelRxHCCv08X,
                                 whose regression is calibrated on pooled PDP+MAPD data but whose
                                 published normalization factor differs by channel -- see
                                 MedicareModelRxHCCv08X's docstring. None for every other segment.
    """

    orec: str
    esrd: bool
    population: str
    coding_intensity_adjuster: float
    normalization_factor: float
    channel: Union[str, None] = None


@dataclass
class CommercialScoringResult(BaseScoringResult):
    """
    Represents the scoring result for a commercial insurance beneficiary.

    Attributes:
        gender (str): The gender of the individual.
        age (int, optional): The age of the individual.
        dob (str, optional): The date of birth of the individual.
        diagnosis_codes (List[str], optional): A list of diagnosis codes associated with the individual.
        year (int, optional): The year passed into the model.
        risk_model_age (int): The age used in the risk model calculation.
        risk_model_population (str): The population group used in the risk model calculation.
        model_version (str): The version of the scoring model used.
        model_year (int): The year of the scoring model.
        score_raw (float): The raw score before any adjustments.
        disease_score_raw (float): The raw disease score before any adjustments.
        demographic_score_raw (float): The raw demographic score before any adjustments.
        score (float): The final score after adjustments.
        disease_score (float): The final disease score after adjustments.
        demographic_score (float): The final demographic score after adjustments.
        category_list (List[str]): A list of categories associated with the individual.
        category_details (Dict[str, str]): A dictionary containing details about each category.
        metal_level (str): The metal level of the individual's insurance plan.
        csr_indicator (int): The cost-sharing reduction indicator.
        enrollment_days (int): The number of days the individual has been enrolled.
        last_enrollment_date (str, optional): The last enrollment date of the individual.
        enrollment_months (float): The number of months the individual has been enrolled.
        csr_adjuster (float): The cost-sharing reduction adjuster applied to the score.
        dropped_category_list (List[str], optional): A list of categories dropped from the scoring.
        dropped_category_details (Dict[str, str], optional): A dictionary containing details about each dropped category.

    Notes:
        - The 'dob' attribute is expected to be in the format 'YYYY-MM-DD'.
        - The 'category_details' and 'dropped_category_details' dictionaries should contain category names as keys
          and corresponding details as values.
    """

    metal_level: str
    csr_indicator: int
    enrollment_days: int
    last_enrollment_date: Union[str, None]
    enrollment_months: float
    csr_adjuster: float
    dropped_category_list: Union[List[str], None]
    dropped_category_details: Union[Dict[str, str], None]

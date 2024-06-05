from dataclasses import dataclass
from typing import List, Union, Dict


@dataclass
class BaseScoringResult:
    """
    Represents the scoring result for a specific individual in a population.

    Attributes:
        gender (str): The gender of the individual.
        orec (str): The OREC (original reason for entitlement category) of the individual.
        medicaid (bool): Indicates whether the individual has Medicaid coverage.
        age (int): The age of the individual.
        dob (str): The date of birth of the individual.
        diagnosis_codes (List[str]): A list of diagnosis codes associated with the individual.
        year (int): The year passed into the model. None if no year was passed in.
        population (str): The population group to which the individual belongs.
        risk_model_age (int): The age used in the risk model calculation.
        risk_model_population (str): The population group used in the risk model calculation.
        model_version (str): The version of the scoring model used.
        model_year (int): The year of the scoring model.
        coding_intensity_adjuster (float): The coding intensity adjuster applied to the score.
        normalization_factor (float): The normalization factor applied to the score.
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
    Represents the scoring result for a specific individual in a population.

    Attributes:
        gender (str): The gender of the individual.
        orec (str): The OREC (original reason for entitlement category) of the individual.
        medicaid (bool): Indicates whether the individual has Medicaid coverage.
        age (int): The age of the individual.
        dob (str): The date of birth of the individual.
        diagnosis_codes (List[str]): A list of diagnosis codes associated with the individual.
        year (int): The year passed into the model. None if no year was passed in.
        population (str): The population group to which the individual belongs.
        risk_model_age (int): The age used in the risk model calculation.
        risk_model_population (str): The population group used in the risk model calculation.
        model_version (str): The version of the scoring model used.
        model_year (int): The year of the scoring model.
        coding_intensity_adjuster (float): The coding intensity adjuster applied to the score.
        normalization_factor (float): The normalization factor applied to the score.
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

    orec: str
    medicaid: bool
    population: str
    coding_intensity_adjuster: float
    normalization_factor: float


@dataclass
class CommercialScoringResult(BaseScoringResult):
    """
    Represents the scoring result for a specific individual in a population.

    Attributes:
        gender (str): The gender of the individual.
        orec (str): The OREC (original reason for entitlement category) of the individual.
        medicaid (bool): Indicates whether the individual has Medicaid coverage.
        age (int): The age of the individual.
        dob (str): The date of birth of the individual.
        diagnosis_codes (List[str]): A list of diagnosis codes associated with the individual.
        year (int): The year passed into the model. None if no year was passed in.
        population (str): The population group to which the individual belongs.
        risk_model_age (int): The age used in the risk model calculation.
        risk_model_population (str): The population group used in the risk model calculation.
        model_version (str): The version of the scoring model used.
        model_year (int): The year of the scoring model.
        coding_intensity_adjuster (float): The coding intensity adjuster applied to the score.
        normalization_factor (float): The normalization factor applied to the score.
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

    metal_level: str
    csr_indicator: int
    enrollment_months: int
    last_enrollment_date: Union[str, None]
    csr_adjuster: float

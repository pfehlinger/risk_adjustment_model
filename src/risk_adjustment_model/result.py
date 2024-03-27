from dataclasses import dataclass


# PF: This could be refactored to use inheritance or have one per LOB I think
@dataclass
class ScoringResult:
    gender: str
    orec: str
    medicaid: bool
    age: int
    dob: str
    diagnosis_codes: list
    year: int
    population: str
    risk_model_age: int
    risk_model_population: str
    model_version: str
    model_year: int
    coding_intensity_adjuster: float
    normalization_factor: float
    score_raw: float
    disease_score_raw: float
    demographic_score_raw: float
    score: float
    disease_score: float
    demographic_score: float
    category_list: list
    category_details: dict

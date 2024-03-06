from dataclasses import dataclass

@dataclass
class ScoringResults:
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
    beneficiary_score_profile: dict


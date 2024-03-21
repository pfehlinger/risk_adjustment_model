from .config import Config
from .beneficiary import MedicareBeneficiary
from .category import MedicareCategory
from .output import ScoringResults


class MedicareModel:
    """
    This is the foundation for Medicare Models. It is not to be called directly. It loads all relevant information for that model
    and year as class attributes.


    How this class works:
    1. Instantiate the class with set up information: model version, year optional if same model version has multiple years and differences
    between years. If year is null, going to pull the most recent
    2. Instantiating the class loads all reference information into memory and it is ready to go.
    3. Call the score method passing in necessary values
    4. Since each model may have its own nuances, want to put each model in its own class that then handles certain category stuff
    """

    def __init__(self, version: str, year=None):
        self.config = Config(version, year)
        self.coding_intensity_adjuster = self._get_coding_intensity_adjuster(
            self.config.model_year
        )
        # PF: This will break for the models that have different normalization factors, will have to refactor once implemented
        self.normalization_factor = self._get_normalization_factor(
            version, self.config.model_year
        )

    def score(
        self,
        gender: str,
        orec: str,
        medicaid: bool,
        diagnosis_codes=[],
        age=None,
        dob=None,
        population="CNA",
        verbose=False,
    ) -> dict:
        """
        Determines the risk score for the inputs. Entry point for end users.

        Args:
            gender (str): Gender of the beneficiary being scored, valid values M or F.
            orec (str): Original Entitlement Reason Code of the beneficiary. See: https://bluebutton.cms.gov/assets/ig/ValueSet-orec.html for valid values
            medicaid (bool): Beneficiary medicaid status, True or False
            diagnosis_codes (list): List of the diagnosis codes associated with the beneficiary
            age (int): Age of the beneficiary, can be None.
            dob (str): Date of birth of the beneficiary, can be None
            population (str): Population of beneficiary being scored, valid values are CNA, CND, CPA, CPD, CFA, CFD, INS, NE
            verbose (bool): Indicates if trimmed output or full output is desired

        Returns:
            dict: A dictionary containing the score information.
        """
        beneficiary = MedicareBeneficiary(
            gender, orec, medicaid, population, age, dob, diagnosis_codes
        )
        categories = MedicareCategory(self.config, beneficiary)
        score_dict = self.get_weights(
            categories.category_list, beneficiary.risk_model_population
        )

        combine_dict = {}
        # Combine the dictionaries to make output
        for key, value in score_dict["categories"].items():
            if categories.category_details.get(key):
                value.update(categories.category_details.get(key))
                combine_dict[key] = value
            else:
                combine_dict[key] = value

        if not verbose:
            self._trim_output(combine_dict)

        output_dict = ScoringResults(
            gender=beneficiary.gender,
            orec=beneficiary.orec,
            medicaid=beneficiary.medicaid,
            age=beneficiary.age,
            dob=beneficiary.dob,
            diagnosis_codes=beneficiary.diagnosis_codes,
            year=self.config.year,
            population=beneficiary.population,
            risk_model_age=beneficiary.risk_model_age,
            risk_model_population=beneficiary.risk_model_population,
            model_version=self.config.version,
            model_year=self.config.model_year,
            coding_intensity_adjuster=self.coding_intensity_adjuster,
            normalization_factor=self.normalization_factor,
            score_raw=score_dict["score_raw"],
            disease_score_raw=score_dict["disease_score_raw"],
            demographic_score_raw=score_dict["demographic_score_raw"],
            score=score_dict["score"],
            disease_score=score_dict["disease_score"],
            demographic_score=score_dict["demographic_score"],
            category_list=categories.category_list,
            category_details=combine_dict,
        )

        return output_dict

    def get_weights(self, categories: list, population: str):
        """
        Returns:
            {'categories': {'HCC1': {'weight': 0.6,
                'type': 'disease',
                'category_number': 1,
                'category_description': 'HIV/AIDS'},
                'F65_69': {'weight': 0.6,
                'type': 'demographic',
                'category_number': None,
                'category_description': 'Female, 65 to 69 Years Old'}},
                'score_raw': 1.2,
                'disease_score_raw': 0.6,
                'demographic_score_raw': 0.6,
                'score': 0.9853,
                'disease_score': 0.4927,
                'demographic_score': 0.4927}
        """
        category_dict = {}
        cat_output = {}
        score = 0
        disease_score = 0
        demographic_score = 0
        for cat in categories:
            for key, value in self.config.category_definitions.items():
                if cat == key:
                    weight = self.config.category_weights[cat][population]
                    score += weight
                    if (
                        value["type"] == "disease"
                        or value["type"] == "disease_interaction"
                    ):
                        disease_score += weight
                    if (
                        value["type"] == "demographic"
                        or value["type"] == "demographic_interaction"
                    ):
                        demographic_score += weight
                    category_dict[key] = {
                        "weight": weight,
                        "type": value["type"],
                        "category_number": value.get("number", None),
                        "category_description": value["descr"],
                    }
        cat_output["categories"] = category_dict
        cat_output["score_raw"] = score
        cat_output["disease_score_raw"] = disease_score
        cat_output["demographic_score_raw"] = demographic_score

        # Now apply coding intensity and normalization to scores
        cat_output["score"] = self._apply_norm_factor_coding_adj(score)
        cat_output["disease_score"] = self._apply_norm_factor_coding_adj(disease_score)
        cat_output["demographic_score"] = self._apply_norm_factor_coding_adj(
            demographic_score
        )

        return cat_output

    # --- Helper methods which should not be overwritten ---

    def _apply_norm_factor_coding_adj(self, score: float) -> float:
        return round(
            round(score * self.coding_intensity_adjuster, 4)
            / self.normalization_factor,
            4,
        )

    def _trim_output(self, score_dict: dict) -> dict:
        """Takes in the verbose output and trims to the smaller output"""
        for key, value in score_dict.items():
            del value["type"]
            del value["category_number"]
            del value["category_description"]
            try:
                del value["dropped_categories"]
            except KeyError:
                pass

    def _get_coding_intensity_adjuster(self, year) -> float:
        """

        Returns:
            float: The coding intensity adjuster.
        """
        coding_intensity_dict = {
            2020: 0.941,
            2021: 0.941,
            2022: 0.941,
            2023: 0.941,
            2024: 0.941,
            2025: 0.941,
        }
        if coding_intensity_dict.get(year):
            coding_intensity_adjuster = coding_intensity_dict.get(year)
        else:
            coding_intensity_adjuster = 1

        return coding_intensity_adjuster

    def _get_normalization_factor(self, version, year, model_group="C") -> float:
        """

        C = Commmunity
        D = Dialysis
        G = Graft

        Returns:
            float: The normalization factor.
        """
        norm_factor_dict = {
            "v24": {
                2020: {"C": 1.069},
                2021: {"C": 1.097},
                2022: {"C": 1.118},
                2023: {"C": 1.127},
                2024: {"C": 1.146},
                2025: {"C": 1.153},
            },
            "v28": {
                2024: {"C": 1.015},
                2025: {"C": 1.045},
            },
        }
        try:
            normalization_factor = norm_factor_dict[version][year][model_group]
        except KeyError:
            normalization_factor = 1

        return normalization_factor

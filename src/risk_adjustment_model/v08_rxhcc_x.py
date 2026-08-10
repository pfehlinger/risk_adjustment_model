from typing import List, Union, Type
from .rxhcc_model import RxHCCModel
from .beneficiary import RxHCCBeneficiary
from .category import Category
from .result import RxHCCScoringResult


class MedicareModelRxHCCv08X(RxHCCModel):
    """
    RxHCC V08, "X" segment: calibrated on HCPCS-filtered diagnoses (2022) and payment data
    (2023), PDP+MAPD combined (i.e. one regression, not split by channel). Published by CMS for
    PY2026, for all non-PACE Part D beneficiaries plus the current-model 10% component of PACE's
    blend (see v08_rxhcc_t.py for the other 90%).

    Unlike every other RxHCC segment, X's *normalization* factor (unlike its regression
    coefficients) is published separately for MA-PD vs. PDP enrollment -- 1.194 vs. 0.887 for
    PY2026. Since `population` doesn't capture this (it's an orthogonal fact: Low/NonLow-Income-
    Subsidy status and Aged/NonAged/institutional setting don't say anything about which channel
    a beneficiary's drug coverage comes through, and X's own category weights don't vary by
    channel at all -- only this downstream normalization step does), `score()` takes an explicit
    `channel` parameter, used only to select which normalization value applies. Two calls with
    the same inputs except `channel` produce the same `score_raw` but a different `score`.

    See RxHCCModel's module docstring for the full segment lineup and design.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v08_rxhcc_x", year)
        self.normalization_factor = self._get_normalization_factor(self.model_year)

    def _get_normalization_factor(self, year: int, channel: str = "MAPD") -> float:
        """
        Returns:
            float: The normalization factor for the given year and enrollment channel.
        """
        norm_factor_dict = {
            2026: {"MAPD": 1.194, "PDP": 0.887},
        }
        try:
            normalization_factor = norm_factor_dict[year][channel]
        except KeyError:
            normalization_factor = 1
        return normalization_factor

    def score(
        self,
        gender: str,
        orec: str,
        esrd: bool = False,
        diagnosis_codes: Union[List[str], None] = None,
        age: Union[int, None] = None,
        dob: Union[str, None] = None,
        population: str = "CE_NONLOW_AGED",
        verbose: bool = False,
        channel: str = "MAPD",
    ) -> Type[RxHCCScoringResult]:
        """
        Determines the RxHCC risk score for the inputs. Entry point for end users.

        Args:
            gender (str): Gender of the beneficiary being scored, valid values M or F.
            orec (str): Original Entitlement Reason Code of the beneficiary.
            esrd (bool): End-Stage Renal Disease status.
            diagnosis_codes (list): List of diagnosis codes. Ignored for NE_* populations --
                                    see RxHCCModel's class docstring.
            age (int): Age of the beneficiary, can be None.
            dob (str): Date of birth of the beneficiary, can be None.
            population (str): CE_NONLOW_AGED, CE_NONLOW_NONAGED, CE_LOW_AGED, CE_LOW_NONAGED,
                              CE_LTI, NE_NONLOW_COMMUNITY, NE_LOW_COMMUNITY, or NE_LTI (default
                              "CE_NONLOW_AGED").
            verbose (bool): Indicates if trimmed output or full output is desired.
            channel (str): "MAPD" or "PDP" -- the beneficiary's enrollment channel, used only to
                           select the normalization factor (does not affect score_raw at all).
                           See class docstring.

        Returns:
            RxHCCScoringResult: An instantiated object of RxHCCScoringResult class.
        """
        # X's normalization factor depends on enrollment channel, not just year -- see class
        # docstring and _get_normalization_factor.
        self.normalization_factor = self._get_normalization_factor(
            self.model_year, channel
        )

        beneficiary = RxHCCBeneficiary(
            gender, orec, esrd, population, age, dob, self.model_year
        )
        demo_categories = self._determine_demographic_categories(beneficiary)

        if diagnosis_codes:
            cat_dict = {}
            dx_categories = self._get_dx_categories(diagnosis_codes, beneficiary)
            unique_disease_cats = set(
                category
                for dx_code in dx_categories
                for category in dx_code.categories
                if category is not None and category != "NA"
            )
            for category in unique_disease_cats:
                diagnosis_map = [
                    dx_code.mapper_code
                    for dx_code in dx_categories
                    if category in dx_code.categories
                ]
                cat_dict[category] = diagnosis_map
        else:
            cat_dict = {}
            unique_disease_cats = None

        if unique_disease_cats:
            unique_categories = demo_categories + list(unique_disease_cats)
        else:
            unique_categories = demo_categories

        categories = [
            Category(
                self.reference_files,
                beneficiary.risk_model_population,
                category,
                cat_dict.get(category),
            )
            for category in unique_categories
        ]
        categories = self._apply_hierarchies(categories)
        categories = self._determine_disease_interactions(categories, beneficiary)

        score_raw = sum(category.coefficient for category in categories)
        disease_score_raw = sum(
            category.coefficient
            for category in categories
            if "disease" in category.type
        )
        demographic_score_raw = sum(
            category.coefficient
            for category in categories
            if "demographic" in category.type
        )

        category_details = self._build_category_details(categories, verbose)

        return RxHCCScoringResult(
            gender=beneficiary.gender,
            orec=beneficiary.orec,
            esrd=beneficiary.esrd,
            age=beneficiary.age,
            dob=beneficiary.dob,
            diagnosis_codes=diagnosis_codes,
            year=self.year,
            risk_model_age=beneficiary.risk_model_age,
            risk_model_population=beneficiary.risk_model_population,
            model_version=self.version,
            model_year=self.model_year,
            population=population,
            channel=channel,
            coding_intensity_adjuster=self.coding_intensity_adjuster,
            normalization_factor=self.normalization_factor,
            score_raw=score_raw,
            disease_score_raw=disease_score_raw,
            demographic_score_raw=demographic_score_raw,
            score=self._apply_norm_factor_coding_adj(score_raw),
            disease_score=self._apply_norm_factor_coding_adj(disease_score_raw),
            demographic_score=self._apply_norm_factor_coding_adj(demographic_score_raw),
            category_list=[category.category for category in categories],
            category_details=category_details,
        )

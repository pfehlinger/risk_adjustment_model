from typing import List, Union, Type
from .utilities import determine_age_band
from .medicare_model import MedicareModel
from .category import Category
from .beneficiary import RxHCCBeneficiary
from .result import RxHCCScoringResult


class RxHCCModel(MedicareModel):
    """
    Shared base class for CMS's RxHCC (Part D) risk-adjustment model, V08. Like ESRD, RxHCC is a
    Medicare model variant, not a separate line of business -- lob="medicare", imported from the
    top-level risk_adjustment_model package.

    CMS publishes RxHCC as several independently-calibrated "segments" per payment year, not one
    model per year the way Community/ESRD are:

        2026: T  (Specialty-filtered diagnoses/2018, payment/2019 calibration, PDP+MAPD combined)
              X  (HCPCS-filtered diagnoses/2022, payment/2023 calibration, PDP+MAPD combined)
        2027: T2 (same calibration approach as T, one year later)
              Y1 (HCPCS-filtered/2023-2024 calibration, MAPD-only)
              Y2 (HCPCS-filtered/2023-2024 calibration, PDP-only)

    T vs X vs T2 differ by *which data the regression was calibrated on* -- the same kind of
    distinction that separates MedicareModelV22 from V24 from V28, not a population fact about
    any individual beneficiary. Y1 vs Y2 *are* a population fact (which channel, MAPD or PDP, the
    beneficiary is enrolled through). Since these don't reduce to one consistent axis, each
    segment gets its own thin class (MedicareModelRxHCCv08T, ...v08X, ...v08T2, ...v08Y1,
    ...v08Y2, one per v08_rxhcc_*.py file) sharing this base -- mirroring how MedicareModelV22/
    V24/V28 are separate classes despite being "the same kind of model" architecturally.

    Population values (passed directly by the caller, exactly like Community's CNA/CFA/etc --
    unlike Community's "NE" shortcut or ESRD's population resolution, RxHCCBeneficiary does no
    derivation at all, since none of these are computable from other beneficiary attributes):

        CE_NONLOW_AGED, CE_NONLOW_NONAGED, CE_LOW_AGED, CE_LOW_NONAGED
            Continuing enrollee, community, split by Low-Income-Subsidy status and aged/nonaged.
        CE_LTI
            Continuing enrollee, institutional. Single population -- doesn't split by LIS/aged.
        NE_NONLOW_COMMUNITY, NE_LOW_COMMUNITY
            New enrollee, community, split by Low-Income-Subsidy status.
        NE_LTI
            New enrollee, institutional.

    New-enrollee populations get diagnosis_codes ignored -- CMS's own NE coefficient files have
    no disease/HCC columns at all (NE scoring is driven entirely by age, sex, ESRD, and
    "originally disabled" status). Unlike ESRD, this doesn't need a bespoke score() short-circuit
    per population: RXHCC* categories simply carry a 0.0 coefficient for every NE population in
    weights.csv, so if a caller passes diagnosis_codes anyway for an NE population, the resulting
    categories are included in category_list/category_details at their natural 0 contribution --
    consistent with this repo's existing "include categories at their population-specific
    coefficient, even when 0" philosophy (see README).

    RxHCC has none of ESRD's bespoke scoring-time arithmetic -- no duration buckets, no actuarial
    adjustment, no flat constant-score populations. It's a plain category-coefficient sum for
    every population, so `score()` is the only thing that needs overriding at all (to swap in
    RxHCCBeneficiary/`esrd` for MedicareBeneficiary/`medicaid`); every other override below is
    exactly the kind of hook MedicareModel's own docstring already calls out as "likely needing
    overwriting".

    Notes on what's *not* modeled, matching this repo's established Medicare precedent:
        - MCE (Medicare Code Editor) age-condition filtering is out of scope -- RxHCC's crosswalk
          only has an MCE_AGE_CONDITION column (no AGE_EDIT_CONDITION/SEX_EDIT_CONDITION at all,
          so _age_sex_edits is overridden to always return None -- MedicareModel's own base
          placeholder returns ["NA"], which would incorrectly reject every diagnosis code if left
          un-overridden here).
        - HCC-count/payment-count categories: CMS's own utils.py computes RXHCC_COUNT5-10P
          columns, but no segment's CE/NE coefficient file actually scores them (confirmed empty
          across all 5 segments) -- omitted entirely rather than implemented as always-zero.

    Attributes:
        category_prefix (str): "RXHCC" (not "HCC") -- see model.py/reference_files_loader.py's
                                category_prefix generalization.

    Methods:
        Overwrites:
            score, _determine_demographic_categories, _determine_disease_interactions,
            _age_sex_edits, _get_normalization_factor.

        New:
            _ce_age_gender_category, _ne_age_gender_category, _determine_demographic_interactions.
    """

    category_prefix = "RXHCC"

    def _get_normalization_factor(self, year: int) -> float:
        """
        No published RxHCC normalization factor has been sourced yet (Part D's own normalization
        comes from CMS's annual Rate Announcement, a different figure than Community's) -- falls
        back to the base class default of 1 until a real value is added here. Coding intensity
        similarly falls back to MedicareModel's shared Part-C-derived adjuster, for consistency
        with how V22/ESRD handle the same gap, until an RxHCC-specific figure is sourced.
        """
        norm_factor_dict = {}
        try:
            normalization_factor = norm_factor_dict[year]
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
    ) -> Type[RxHCCScoringResult]:
        """
        Determines the RxHCC risk score for the inputs. Entry point for end users.

        Args:
            gender (str): Gender of the beneficiary being scored, valid values M or F.
            orec (str): Original Entitlement Reason Code of the beneficiary.
            esrd (bool): End-Stage Renal Disease status.
            diagnosis_codes (list): List of diagnosis codes. Ignored for NE_* populations --
                                    see class docstring.
            age (int): Age of the beneficiary, can be None.
            dob (str): Date of birth of the beneficiary, can be None.
            population (str): CE_NONLOW_AGED, CE_NONLOW_NONAGED, CE_LOW_AGED, CE_LOW_NONAGED,
                              CE_LTI, NE_NONLOW_COMMUNITY, NE_LOW_COMMUNITY, or NE_LTI (default
                              "CE_NONLOW_AGED").
            verbose (bool): Indicates if trimmed output or full output is desired.

        Returns:
            RxHCCScoringResult: An instantiated object of RxHCCScoringResult class.
        """
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

    # --- Demographic categories ---

    def _determine_demographic_categories(
        self, beneficiary: Type[RxHCCBeneficiary]
    ) -> List[str]:
        """
        Determine demographic categories. NE_* populations get a single age/sex category and
        nothing else (CMS's NE coefficient files have no interaction variables at all);
        CE_* populations get an age/sex-band category plus the M65OD/F65OD/OD65 "originally
        disabled" interaction categories when applicable.
        """
        if beneficiary.population.startswith("NE_"):
            return [
                self._ne_age_gender_category(
                    beneficiary.risk_model_age,
                    beneficiary.gender,
                    beneficiary.orec,
                    beneficiary.esrd,
                    beneficiary.origdis,
                )
            ]

        demo_cats = [
            self._ce_age_gender_category(beneficiary.risk_model_age, beneficiary.gender)
        ]
        demo_cats.extend(self._determine_demographic_interactions(beneficiary))

        return demo_cats

    def _ce_age_gender_category(self, age: int, gender: str) -> str:
        """Age/sex band for continuing enrollees. Same band structure as Community/ESRD."""
        bands = [
            "0_34",
            "35_44",
            "45_54",
            "55_59",
            "60_64",
            "65_69",
            "70_74",
            "75_79",
            "80_84",
            "85_89",
            "90_94",
            "95_GT",
        ]
        band = determine_age_band(age, bands)
        return f"{gender}{band}"

    def _ne_age_gender_category(
        self, age: int, gender: str, orec: str, esrd: bool, origdis: bool
    ) -> str:
        """
        Age/sex/ESRD/originally-disabled category for new enrollees, e.g.
        "NESRD_NORIGDIS_X_M0_34" or "ESRD_ORIGDIS_X_F70_74". Per CMS (RxHCC/utils.py's
        get_ne_bene_age_sex_vars), age 64 with orec == "0" is recoded to 65 for band selection
        (same special case as Community/ESRD's NE age handling). `origdis` is only ever True
        for age >= 65 (see RxHCCBeneficiary), so the ESRD/ORIGDIS-vs-NORIGDIS combination below
        naturally collapses to CMS's "origdis only applies at 65+" rule without a separate branch.
        """
        recoded_age = 65 if (age == 64 and orec == "0") else age
        bands = [
            "0_34",
            "35_44",
            "45_54",
            "55_59",
            "60_64",
            "65",
            "66",
            "67",
            "68",
            "69",
            "70_74",
            "75_79",
            "80_84",
            "85_89",
            "90_94",
            "95_GT",
        ]
        band = determine_age_band(recoded_age, bands)
        esrd_label = "ESRD" if esrd else "NESRD"
        origdis_label = "ORIGDIS" if origdis else "NORIGDIS"
        return f"{esrd_label}_{origdis_label}_X_{gender}{band}"

    def _determine_demographic_interactions(
        self, beneficiary: Type[RxHCCBeneficiary]
    ) -> List[str]:
        """
        Determines RxHCC demographic interaction categories for continuing enrollees: when the
        beneficiary is both aged (>= 65) and "originally disabled" (orec == "1"), CMS scores both
        a gender-specific flag (M65OD/F65OD) and a gender-agnostic flag (OD65) together -- not
        mutually exclusive with each other or with the base age/sex band category.
        """
        if beneficiary.origdis:
            return [f"{beneficiary.gender}65OD", "OD65"]
        return []

    # --- Disease interactions ---

    def _determine_disease_interactions(
        self, categories: List[Type[Category]], beneficiary: Type[RxHCCBeneficiary]
    ) -> List[Type[Category]]:
        """
        Determines RxHCC disease interactions: the 7 NONAGED_RXHCC{n} flags (nonaged == age < 65,
        no orec condition at all -- unlike ESRD's disabled/nonaged concepts). No other
        disease-disease interactions and no HCC-count/payment-count category exist in RxHCC V08 --
        see class docstring.

        Args:
            categories (List[Type[Category]]): List of Category objects.
            beneficiary (Type[RxHCCBeneficiary]): Instance of RxHCCBeneficiary.

        Returns:
            List[Type[Category]]: List of Category objects representing the disease interactions.
        """
        category_list = [
            category.category for category in categories if category.type == "disease"
        ]
        nonaged_rxhccs = ["1", "130", "131", "132", "133", "159", "163"]
        nonaged = not beneficiary.aged

        interaction_list = [
            f"NONAGED_RXHCC{n}"
            for n in nonaged_rxhccs
            if nonaged and f"RXHCC{n}" in category_list
        ]

        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]
        interactions.extend(categories)

        return interactions

    # --- Age/sex edits ---

    def _age_sex_edits(
        self, gender: str, age: int, diagnosis_code: str
    ) -> Union[List[str], None]:
        """
        RxHCC's ICD10-to-CC crosswalk has no AGE_EDIT_CONDITION/SEX_EDIT_CONDITION columns at
        all (only MCE_AGE_CONDITION, which is out of scope -- see class docstring), so there are
        no age/sex edits to apply. Overriding this to return None is required: MedicareModel's
        own placeholder returns ["NA"] unconditionally, which would reject every diagnosis code
        if left un-overridden.
        """
        return None

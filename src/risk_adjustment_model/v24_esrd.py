from typing import List, Union, Type
from .utilities import determine_age_band
from .medicare_model import MedicareModel
from .category import Category
from .beneficiary import ESRDBeneficiary
from .result import ESRDScoringResult


# CMS's transplant_scores.csv keys its rows "TRANSPLANT_KIDNEY_ONLY_1M" etc; this repo's
# `population` values are the shorter "TRANSPLANT_1M" etc for symmetry with DIAL/GRAFT_COMM/...
TRANSPLANT_SCORE_KEYS = {
    "TRANSPLANT_1M": "TRANSPLANT_KIDNEY_ONLY_1M",
    "TRANSPLANT_2M": "TRANSPLANT_KIDNEY_ONLY_2M",
    "TRANSPLANT_3M": "TRANSPLANT_KIDNEY_ONLY_3M",
}

# CMS publishes ESRD normalization factors as two series, "Dialysis CMS-HCC" and "Functioning
# Graft CMS-HCC" -- these populations belong to the former; everything else (GRAFT_COMM,
# GRAFT_INST, NE_GRAFT) belongs to the latter. See _get_normalization_factor.
DIALYSIS_GROUP_POPULATIONS = {
    "DIAL",
    "NE_DIAL",
    "TRANSPLANT_1M",
    "TRANSPLANT_2M",
    "TRANSPLANT_3M",
}


class MedicareModelESRDv24(MedicareModel):
    """
    This class represents the V24 ESRD (End-Stage Renal Disease) Model for Medicare. ESRD is a
    variant of the Medicare Community model family, not a separate line of business -- it stays
    under lob="medicare" with its own version namespace ("v24_esrd") and reference data
    directory, and is imported from the top-level risk_adjustment_model package alongside
    MedicareModelV22/V24/V28.

    Design notes (why this class overrides `score` entirely rather than reusing MedicareModel's):

    CMS's own ESRD DIY software doesn't compute one score per beneficiary -- it computes every
    possible score variant (dialysis, community-graft, institutional-graft, new enrollee
    dialysis/graft, flat transplant-month scores) and leaves it to the downstream payment process
    to pick the one that matches the beneficiary's actual, externally-tracked ESRD status
    (dialysis vs. functioning graft vs. recent transplant, and graft duration), none of which is
    part of this software's own input. Consistent with how this repo already requires the caller
    to pass `population` explicitly for Community (CNA vs CND vs ...) rather than computing every
    population, ESRD follows the same philosophy: the caller passes one `population` value and
    gets back one score for it. Valid values:

        DIAL         - Continuing enrollee, dialysis
        GRAFT_COMM   - Continuing enrollee, community, functioning graft
        GRAFT_INST   - Continuing enrollee, institutional, functioning graft
        NE_DIAL      - New enrollee, dialysis
        NE_GRAFT     - New enrollee, functioning graft
        TRANSPLANT_1M, TRANSPLANT_2M, TRANSPLANT_3M
                     - Flat kidney-transplant-month scores. These don't depend on diagnosis
                       codes or beneficiary demographics at all -- CMS publishes them as flat
                       constants for months 1-3 post-transplant (functioning-graft scoring, via
                       GRAFT_COMM/GRAFT_INST/NE_GRAFT, only starts at month 4).

    Unlike Community, dual status is not folded into `population` for every variant: FBDual and
    PBDual are explicit boolean inputs (matching the beneficiary file's own FBDual/PBDual
    columns), since ESRD's institutional and new-enrollee graft scoring needs them directly in
    scoring-time arithmetic (see below), not just as a category lookup key. `population="GRAFT_COMM"`
    still resolves its dual+aged sub-variant internally (via ESRDBeneficiary), since that
    sub-variant genuinely is just a weights.csv column selector there -- see beneficiary.py.

    Score composition:

    - DIAL: a plain sum of category coefficients (demographic + disease + disease interactions),
      identical in shape to Community's scoring -- no special-case math needed.
    - GRAFT_COMM / GRAFT_INST: the same category-coefficient sum for demographic + disease +
      disease interactions, PLUS an additive "graft duration bonus" layered on top when
      `graft_duration_months` is given (4-9 months or 10+ months; under 4 months has no bonus
      bucket at all -- use the flat TRANSPLANT_1M/2M/3M populations instead). The bonus itself
      isn't expressible as a weights.csv category coefficient (it depends on FBDual/PBDual/LTI
      status multiplicatively, not as independent additive category flags), so it's computed
      directly from the graft_duration_scores/institutional_graft_scores reference tables. This
      matches CMS's own transform.py math (see V24_Graft_Duration_Scores.csv /
      V24_CE_Institutional_Graft_Scores.csv), just evaluated for one population per call instead
      of vectorized across every population at once.
    - NE_DIAL / NE_GRAFT: purely demographic -- CMS's own NE dialysis/graft coefficient files
      have no disease/HCC columns at all, so diagnosis_codes are accepted but ignored for these
      two populations (mirrors CMS's software, which never looks up HCCs for ESRD new enrollees).
      NE_GRAFT additionally gets the graft duration bonus (using CMS's separate "NE_Aged" age
      rule -- age >= 65, or age == 64 with orec == "0" -- rather than the plain age >= 65 used
      elsewhere) followed by CMS's mandatory actuarial adjustment: dividing by 0.905 (4-9 months)
      or 0.698 (10+ months).
    - TRANSPLANT_1M/2M/3M: a flat constant from transplant_scores.csv, no scoring pipeline at all.

    Renal categories (HCC134-138) are permanently excluded from this model's reference data
    (never appear in category_definition.json, hierarchy_definition.json, or
    diag_to_category_map.txt). CMS's own software forcibly zeroes these CCs for every ESRD
    beneficiary before scoring (an ESRD beneficiary is definitionally already on dialysis or
    graft-dependent, so scoring renal failure again would double-count) -- since the result is
    identical either way, omitting the mappings entirely is simpler than reproducing an
    always-true rejection rule in Python for every one of the ~40 diagnosis codes that would
    otherwise map to them.

    Like the rest of this repo's Medicare models, MCE (Medicare Code Editor) age-condition
    filtering is out of scope -- only the AGE_EDIT_CONDITION/SEX_EDIT_CONDITION columns are
    modeled (via _age_sex_edits below), not MCE_AGE_CONDITION.

    Attributes:
        category_prefix (str): "HCC", same convention as Community.

    Methods:
        Overwrites:
            score: Entry point -- see design notes above for why this doesn't reuse MedicareModel.score.
            _get_normalization_factor: Retrieves the normalization factor based on the model year.
            _determine_demographic_categories: ESRD-specific demographic category resolution
                                               (population-dependent age bands + interactions).
            _determine_disease_interactions: The 26 scored ESRD V24 disease interactions (no
                                             HCC-count/payment-count interaction, unlike Community).
            _age_sex_edits: Applies age and sex edits to diagnosis codes.

        New:
            _age_sex_edit_1, _age_sex_edit_2, _age_sex_edit_3: The 19 genuinely age/sex-conditional
                diagnosis codes (identical set to V22/V24 Community: D66/D67, 16 J-codes, F3481).
            _get_graft_duration_bucket: Converts months-since-transplant into "DUR4_9"/"DUR10PL"/None.
            _get_community_graft_bonus, _get_institutional_graft_bonus, _get_ne_graft_bonus,
                _get_ne_actuarial_adjuster: Graft duration/actuarial-adjustment scoring-time math.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v24_esrd", year)
        self.normalization_factor = self._get_normalization_factor(self.model_year)

    def _get_normalization_factor(self, year: int, population: str = "DIAL") -> float:
        """
        CMS publishes ESRD normalization factors as two distinct series per year -- "Dialysis
        CMS-HCC" (covers DIAL, NE_DIAL, and the TRANSPLANT_*M populations) and "Functioning Graft
        CMS-HCC" (covers GRAFT_COMM, GRAFT_INST, and NE_GRAFT) -- not one flat value per year the
        way Community is. `population` selects which series applies; see score(), which resolves
        this per call (self.normalization_factor is not a fixed per-instance value for ESRD).

        Returns:
            float: The normalization factor for the given year and population's group.
        """
        dialysis_group_norm_factor_dict = {
            2026: 1.062,
            2027: 1.072,
        }
        graft_group_norm_factor_dict = {
            2026: 1.104,
            2027: 1.119,
        }
        norm_factor_dict = (
            dialysis_group_norm_factor_dict
            if population in DIALYSIS_GROUP_POPULATIONS
            else graft_group_norm_factor_dict
        )
        try:
            normalization_factor = norm_factor_dict[year]
        except KeyError:
            normalization_factor = 1
        return normalization_factor

    def score(
        self,
        gender: str,
        orec: str,
        fbdual: bool = False,
        pbdual: bool = False,
        lti: bool = False,
        diagnosis_codes: Union[List[str], None] = None,
        age: Union[int, None] = None,
        dob: Union[str, None] = None,
        population: str = "DIAL",
        graft_duration_months: Union[int, None] = None,
        verbose: bool = False,
    ) -> Type[ESRDScoringResult]:
        """
        Determines the ESRD risk score for the inputs. Entry point for end users.

        Args:
            gender (str): Gender of the beneficiary being scored, valid values M or F.
            orec (str): Original Entitlement Reason Code of the beneficiary.
            fbdual (bool): Full Benefit Dual status.
            pbdual (bool): Partial Benefit Dual status.
            lti (bool): Long-Term Institutional status.
            diagnosis_codes (list): List of the diagnosis codes associated with the beneficiary.
                                    Ignored for population NE_DIAL/NE_GRAFT and TRANSPLANT_*M --
                                    see class docstring.
            age (int): Age of the beneficiary, can be None.
            dob (str): Date of birth of the beneficiary, can be None.
            population (str): DIAL, GRAFT_COMM, GRAFT_INST, NE_DIAL, NE_GRAFT, TRANSPLANT_1M,
                              TRANSPLANT_2M, or TRANSPLANT_3M (default "DIAL"). See class docstring.
            graft_duration_months (int, optional): Months since transplant. Only used for
                                                   GRAFT_COMM/GRAFT_INST/NE_GRAFT populations, to
                                                   select the 4-9-month or 10-plus-month bonus
                                                   bucket. None (the default) means no bonus is
                                                   applied -- correct for DIAL/NE_DIAL/TRANSPLANT_*M,
                                                   and also correct for a functioning graft under 4
                                                   months old (use TRANSPLANT_*M instead for that case).
            verbose (bool): Indicates if trimmed output or full output is desired.

        Returns:
            ESRDScoringResult: An instantiated object of ESRDScoringResult class.
        """
        # ESRD's normalization factor depends on which population is being scored (dialysis-group
        # vs. functioning-graft-group series), not just year -- see _get_normalization_factor.
        self.normalization_factor = self._get_normalization_factor(
            self.model_year, population
        )
        beneficiary = ESRDBeneficiary(
            gender, orec, fbdual, pbdual, lti, population, age, dob, self.model_year
        )
        duration_bucket = self._get_graft_duration_bucket(graft_duration_months)

        if population.startswith("TRANSPLANT_"):
            score_raw = round(
                self.reference_files.transplant_scores[
                    TRANSPLANT_SCORE_KEYS[population]
                ],
                3,
            )
            return self._build_result(
                beneficiary,
                diagnosis_codes,
                population,
                None,
                score_raw,
                0.0,
                score_raw,
                [],
                {},
            )

        if population in ("NE_DIAL", "NE_GRAFT"):
            demo_category = self._determine_demographic_categories(beneficiary)[0]
            category = Category(
                self.reference_files, beneficiary.risk_model_population, demo_category
            )
            demographic_score_raw = category.coefficient
            if population == "NE_GRAFT" and duration_bucket:
                demographic_score_raw += self._get_ne_graft_bonus(
                    beneficiary, duration_bucket
                )
                demographic_score_raw = (
                    demographic_score_raw
                    / self._get_ne_actuarial_adjuster(duration_bucket)
                )
            score_raw = round(demographic_score_raw, 3)
            category_details = self._build_category_details([category], verbose)
            return self._build_result(
                beneficiary,
                diagnosis_codes,
                population,
                graft_duration_months if population == "NE_GRAFT" else None,
                score_raw,
                0.0,
                score_raw,
                [category.category],
                category_details,
            )

        # CE: DIAL, GRAFT_COMM, GRAFT_INST
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

        if population == "GRAFT_COMM" and duration_bucket:
            demographic_score_raw += self._get_community_graft_bonus(
                beneficiary, duration_bucket
            )
        elif population == "GRAFT_INST" and duration_bucket:
            demographic_score_raw += self._get_institutional_graft_bonus(
                beneficiary, duration_bucket
            )

        score_raw = round(disease_score_raw + demographic_score_raw, 3)
        disease_score_raw = round(disease_score_raw, 3)
        demographic_score_raw = round(demographic_score_raw, 3)
        category_details = self._build_category_details(categories, verbose)

        return self._build_result(
            beneficiary,
            diagnosis_codes,
            population,
            graft_duration_months
            if population in ("GRAFT_COMM", "GRAFT_INST")
            else None,
            score_raw,
            disease_score_raw,
            demographic_score_raw,
            [category.category for category in categories],
            category_details,
        )

    def _build_result(
        self,
        beneficiary: Type[ESRDBeneficiary],
        diagnosis_codes: Union[List[str], None],
        population: str,
        graft_duration_months: Union[int, None],
        score_raw: float,
        disease_score_raw: float,
        demographic_score_raw: float,
        category_list: List[str],
        category_details: dict,
    ) -> Type[ESRDScoringResult]:
        """
        Assembles an ESRDScoringResult. Factored out of `score` since all four population
        branches (transplant, new enrollee, and the shared continuing-enrollee path) build the
        same result shape from different intermediate values.
        """
        return ESRDScoringResult(
            gender=beneficiary.gender,
            orec=beneficiary.orec,
            fbdual=beneficiary.fbdual,
            pbdual=beneficiary.pbdual,
            lti=beneficiary.lti,
            age=beneficiary.age,
            dob=beneficiary.dob,
            diagnosis_codes=diagnosis_codes,
            year=self.year,
            risk_model_age=beneficiary.risk_model_age,
            risk_model_population=beneficiary.risk_model_population,
            model_version=self.version,
            model_year=self.model_year,
            population=population,
            graft_duration_months=graft_duration_months,
            coding_intensity_adjuster=self.coding_intensity_adjuster,
            normalization_factor=self.normalization_factor,
            score_raw=score_raw,
            disease_score_raw=disease_score_raw,
            demographic_score_raw=demographic_score_raw,
            score=self._apply_norm_factor_coding_adj(score_raw),
            disease_score=self._apply_norm_factor_coding_adj(disease_score_raw),
            demographic_score=self._apply_norm_factor_coding_adj(demographic_score_raw),
            category_list=category_list,
            category_details=category_details,
        )

    # --- Demographic categories ---

    def _determine_demographic_categories(
        self, beneficiary: Type[ESRDBeneficiary]
    ) -> List[str]:
        """
        Determine demographic categories based on beneficiary attributes. Population-dependent:
        NE_DIAL/NE_GRAFT get a single age/sex-band category and nothing else (CMS's NE
        coefficient files have no interaction variables at all); DIAL/GRAFT_COMM/GRAFT_INST get
        an age/sex-band category plus whichever demographic interactions apply. All possible
        interactions are included regardless of which CE population is being scored (rather than
        filtering by population in Python) -- weights.csv naturally zeroes out the ones that
        don't apply to a given population, matching how this repo already handles
        population-conditional category applicability elsewhere.

        Args:
            beneficiary (Type[ESRDBeneficiary]): An instance of ESRDBeneficiary.

        Returns:
            list: A list containing demographic categories.
        """
        if beneficiary.population == "NE_DIAL":
            return [
                self._ne_dial_age_gender_category(
                    beneficiary.risk_model_age, beneficiary.gender, beneficiary.orec
                )
            ]
        if beneficiary.population == "NE_GRAFT":
            return [
                self._ne_graft_age_gender_category(
                    beneficiary.risk_model_age, beneficiary.gender, beneficiary.orec
                )
            ]

        demo_cats = [
            self._ce_age_gender_category(beneficiary.risk_model_age, beneficiary.gender)
        ]
        demo_cats.extend(self._determine_demographic_interactions(beneficiary))

        return demo_cats

    def _ce_age_gender_category(self, age: int, gender: str) -> str:
        """
        Age/sex band for continuing enrollee (DIAL/GRAFT_COMM/GRAFT_INST) populations. Same
        band structure as Community.
        """
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

    def _ne_dial_age_gender_category(self, age: int, gender: str, orec: str) -> str:
        """
        Age/sex band for the NE_DIAL population. Per CMS (ESRD_utils.py's
        get_ne_bene_age_sex_vars), a beneficiary who is exactly age 64 is recoded into the 65-69
        band if orec == "0" (aged in this cycle), otherwise into the 60-64 band -- CMS's own
        Community V28 software has this identical special case (CMS_HCC_utils.py's
        get_ne_bene_age_sex_vars), though this repo's existing Community NE implementation
        doesn't currently replicate it; not addressed here since that's Community's own gap, not
        ESRD's, and out of scope for this change.
        """
        if age == 64:
            band = "65_69" if orec == "0" else "60_64"
        else:
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
                "85_GT",
            ]
            band = determine_age_band(age, bands)
        return f"NE{gender}{band}"

    def _ne_graft_age_gender_category(self, age: int, gender: str, orec: str) -> str:
        """
        Age/sex band for the NE_GRAFT population. Finer-grained than NE_DIAL near 65 (individual
        years 65-69), since graft duration/actuarial adjustment math needs single-year precision
        there. Age 64 is recoded to a single-year "65" band if orec == "0", otherwise 60-64 --
        same CMS special case as NE_DIAL, adapted to NE_GRAFT's band structure (see
        ESRD_utils.py's get_ne_bene_graft_age_sex_vars).
        """
        if age == 64:
            band = "65" if orec == "0" else "60_64"
        else:
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
            band = determine_age_band(age, bands)
        return f"NE{gender}{band}"

    def _determine_demographic_interactions(
        self, beneficiary: Type[ESRDBeneficiary]
    ) -> List[str]:
        """
        Determines ESRD demographic interaction categories. Distinct from Community's version --
        ESRD scores dual status (FBDual/PBDual, split by gender and aged/nonaged), LTI status
        (split by aged/nonaged), "originally disabled" status, and "originally ESRD" status
        (aged only) directly as demographic interaction categories, rather than the single
        LTIMCAID flag Community uses.

        Args:
            beneficiary (Type[ESRDBeneficiary]): Instance of ESRDBeneficiary.

        Returns:
            List[str]: List of demographic interaction category names.
        """
        interactions = []
        sex_label = "Female" if beneficiary.gender == "F" else "Male"
        aged_label = "Aged" if beneficiary.aged else "NonAged"

        if beneficiary.ce_orig_disabled:
            interactions.append(f"OriginallyDisabled_{sex_label}")
        if beneficiary.origesrd and beneficiary.aged:
            interactions.append(f"Originally_ESRD_{sex_label}")
        if beneficiary.lti:
            interactions.append(f"LTI_{aged_label}")
        if beneficiary.fbdual:
            interactions.append(f"FBDual_{sex_label}_{aged_label}")
        if beneficiary.pbdual:
            interactions.append(f"PBDual_{sex_label}_{aged_label}")

        return interactions

    # --- Disease interactions ---

    def _determine_disease_interactions(
        self, categories: List[Type[Category]], beneficiary: Type[ESRDBeneficiary]
    ) -> List[Type[Category]]:
        """
        Determines disease interactions based on provided Category objects and beneficiary
        information. Unlike Community, ESRD V24 has no HCC-count/payment-count interaction
        variable, and omits CMS's HCC85_gRenal_V24 interaction entirely -- it can never trigger,
        since renal categories (HCC134-138) are excluded from this model's reference data
        altogether (see class docstring).

        Args:
            categories (List[Type[Category]]): List of Category objects representing disease categories.
            beneficiary (Type[ESRDBeneficiary]): Instance of ESRDBeneficiary.

        Returns:
            List[Type[Category]]: List of Category objects representing the disease interactions.
        """
        category_list = [
            category.category for category in categories if category.type == "disease"
        ]
        cancer_list = ["HCC8", "HCC9", "HCC10", "HCC11", "HCC12"]
        diabetes_list = ["HCC17", "HCC18", "HCC19"]
        card_resp_fail_list = ["HCC82", "HCC83", "HCC84"]
        g_copd_cf_list = ["HCC110", "HCC111", "HCC112"]
        g_substance_use_disorder_list = ["HCC54", "HCC55", "HCC56"]
        g_psychiatric_list = ["HCC57", "HCC58", "HCC59", "HCC60"]
        pressure_ulcer_list = ["HCC157", "HCC158", "HCC159"]

        cancer = any(category in category_list for category in cancer_list)
        diabetes = any(category in category_list for category in diabetes_list)
        card_resp_fail = any(
            category in category_list for category in card_resp_fail_list
        )
        chf = "HCC85" in category_list
        g_copd_cf = any(category in category_list for category in g_copd_cf_list)
        sepsis = "HCC2" in category_list
        g_substance_use_disorder = any(
            category in category_list for category in g_substance_use_disorder_list
        )
        g_psychiatric = any(
            category in category_list for category in g_psychiatric_list
        )
        pressure_ulcer = any(
            category in category_list for category in pressure_ulcer_list
        )
        hcc6 = "HCC6" in category_list
        hcc34 = "HCC34" in category_list
        hcc39 = "HCC39" in category_list
        hcc46 = "HCC46" in category_list
        hcc47 = "HCC47" in category_list
        hcc57 = "HCC57" in category_list
        hcc77 = "HCC77" in category_list
        hcc79 = "HCC79" in category_list
        hcc96 = "HCC96" in category_list
        hcc110 = "HCC110" in category_list
        hcc114 = "HCC114" in category_list
        hcc161 = "HCC161" in category_list
        hcc176 = "HCC176" in category_list
        hcc188 = "HCC188" in category_list

        g_sub_use_ds_g_psych = all([g_substance_use_disorder, g_psychiatric])
        nonaged = not beneficiary.aged

        interactions_dict = {
            "HCC47_gCancer": all([hcc47, cancer]),
            "DIABETES_CHF": all([diabetes, chf]),
            "CHF_gCopdCF": all([chf, g_copd_cf]),
            "gCopdCF_CARD_RESP_FAIL": all([g_copd_cf, card_resp_fail]),
            "HCC85_HCC96": all([chf, hcc96]),
            "gSubUseDs_gPsych_V24": g_sub_use_ds_g_psych,
            "SEPSIS_PRESSURE_ULCER_V24": all([sepsis, pressure_ulcer]),
            "SEPSIS_ARTIF_OPENINGS": all([sepsis, hcc188]),
            "ART_OPENINGS_PRESSURE_ULCER_V24": all([hcc188, pressure_ulcer]),
            "gCopdCF_ASP_SPEC_B_PNEUM": all([g_copd_cf, hcc114]),
            "ASP_SPEC_B_PNEUM_PRES_ULC_V24": all([hcc114, pressure_ulcer]),
            "SEPSIS_ASP_SPEC_BACT_PNEUM": all([sepsis, hcc114]),
            "SCHIZOPHRENIA_gCopdCF": all([hcc57, g_copd_cf]),
            "SCHIZOPHRENIA_CHF": all([hcc57, chf]),
            "SCHIZOPHRENIA_SEIZURES": all([hcc57, hcc79]),
            "NONAGED_gSubUseDs_gPsych": all([nonaged, g_sub_use_ds_g_psych]),
            "NONAGED_HCC6": all([nonaged, hcc6]),
            "NONAGED_HCC34": all([nonaged, hcc34]),
            "NONAGED_HCC46": all([nonaged, hcc46]),
            "NONAGED_HCC110": all([nonaged, hcc110]),
            "NONAGED_HCC176": all([nonaged, hcc176]),
            "NONAGED_HCC85": all([nonaged, chf]),
            "NONAGED_PRESSURE_ULCER_V24": all([nonaged, pressure_ulcer]),
            "NONAGED_HCC161": all([nonaged, hcc161]),
            "NONAGED_HCC39": all([nonaged, hcc39]),
            "NONAGED_HCC77": all([nonaged, hcc77]),
        }
        interaction_list = [key for key, value in interactions_dict.items() if value]

        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]
        interactions.extend(categories)

        return interactions

    # --- Graft duration / actuarial adjustment math ---

    def _get_graft_duration_bucket(
        self, graft_duration_months: Union[int, None]
    ) -> Union[str, None]:
        """
        Converts months-since-transplant into the CMS duration bucket used to key into
        graft_duration_scores/institutional_graft_scores. Under 4 months has no bucket at all --
        CMS scores that window with the flat TRANSPLANT_1M/2M/3M populations instead.

        Returns:
            Union[str, None]: "DUR4_9", "DUR10PL", or None.
        """
        if graft_duration_months is None:
            return None
        if 4 <= graft_duration_months <= 9:
            return "DUR4_9"
        if graft_duration_months >= 10:
            return "DUR10PL"
        return None

    def _get_community_graft_bonus(
        self, beneficiary: Type[ESRDBeneficiary], duration_bucket: str
    ) -> float:
        """
        Additive graft-duration bonus for the GRAFT_COMM population, from
        graft_duration_scores.csv. Aged/dual tier is read straight off the beneficiary object
        (already resolved from population="GRAFT_COMM" + actual age/fbdual by ESRDBeneficiary),
        matching CMS's `graft_dur_coef_score * aged` / `* pbdual * aged` terms with aged/dual
        implicitly 1 given the population already selected that tier.
        """
        aged_key = "GE65" if beneficiary.aged else "LT65"
        dual_key = "FBD" if beneficiary.fbdual else "ND_PBD"
        dur_key = "DUR4_9" if duration_bucket == "DUR4_9" else "DUR10PL"

        bonus = self.reference_files.graft_duration_scores[
            f"{aged_key}_{dur_key}_{dual_key}"
        ]
        if not beneficiary.fbdual and beneficiary.pbdual:
            bonus += self.reference_files.graft_duration_scores[f"PBD_{aged_key}_flag"]

        return bonus

    def _get_institutional_graft_bonus(
        self, beneficiary: Type[ESRDBeneficiary], duration_bucket: str
    ) -> float:
        """
        Additive graft-duration bonus for the GRAFT_INST population, from
        institutional_graft_scores.csv. Unlike GRAFT_COMM, GRAFT_INST's base category
        coefficients don't vary by dual/aged status at all, so aged comes from the beneficiary's
        actual age and dual comes directly from fbdual/pbdual; LTI (Long-Term Institutional)
        status adds a further additive bonus, only relevant to this population.
        """
        aged_key = "GE65" if beneficiary.aged else "LT65"
        dual_key = "FBD" if beneficiary.fbdual else "ND_PBD"
        dur_key = "DUR4_9" if duration_bucket == "DUR4_9" else "DUR10PL"

        bonus = self.reference_files.institutional_graft_scores[
            f"FGI_{aged_key}_{dur_key}_{dual_key}"
        ]
        if not beneficiary.fbdual and beneficiary.pbdual:
            bonus += self.reference_files.institutional_graft_scores[
                f"FGI_PBD_{aged_key}_flag"
            ]
        if beneficiary.lti:
            bonus += self.reference_files.institutional_graft_scores[f"LTI_{aged_key}"]

        return bonus

    def _get_ne_graft_bonus(
        self, beneficiary: Type[ESRDBeneficiary], duration_bucket: str
    ) -> float:
        """
        Additive graft-duration bonus for the NE_GRAFT population, from
        graft_duration_scores.csv (the same table GRAFT_COMM uses). Aged tier uses CMS's
        NE-specific "NE_Aged" rule (beneficiary.ne_aged) rather than the plain age >= 65 used
        elsewhere -- see ESRDBeneficiary. The actuarial adjustment division is applied separately
        by the caller (score()), not here, matching CMS's own two-step formula.
        """
        aged_key = "GE65" if beneficiary.ne_aged else "LT65"
        dual_key = "FBD" if beneficiary.fbdual else "ND_PBD"
        dur_key = "DUR4_9" if duration_bucket == "DUR4_9" else "DUR10PL"

        return self.reference_files.graft_duration_scores[
            f"{aged_key}_{dur_key}_{dual_key}"
        ]

    def _get_ne_actuarial_adjuster(self, duration_bucket: str) -> float:
        """
        CMS's mandatory NE graft actuarial adjustment divisor: 0.905 for the 4-9 month bucket,
        0.698 for the 10-plus month bucket. Specific to ESRD V24 new enrollees -- no other model
        in this repo has an equivalent adjustment.
        """
        return 0.905 if duration_bucket == "DUR4_9" else 0.698

    # --- Age/sex edits ---

    def _age_sex_edits(
        self, gender: str, age: int, diagnosis_code: str
    ) -> Union[List[str], None]:
        """
        Wrapper method to apply all model specific age and sex edits for a diagnosis code to
        category mapping. Same 19-code set as V22/V24 Community (D66/D67, 16 J-codes, F3481) --
        CMS reuses this edit list across model families.
        """
        new_category = self._age_sex_edit_1(gender, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_2(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_3(age, diagnosis_code)
        if new_category:
            return new_category

    def _age_sex_edit_1(self, gender: str, dx_code: str) -> Union[List[str], None]:
        """D66/D67: static default (male) is HCC46; female overrides to HCC48."""
        if gender == "F" and dx_code in ["D66", "D67"]:
            return ["HCC48"]

    def _age_sex_edit_2(self, age: int, dx_code: str) -> Union[List[str], None]:
        """The 16 J-codes: static default (age >= 18) is HCC111; under 18 overrides to HCC112."""
        if age < 18 and dx_code in [
            "J410",
            "J411",
            "J418",
            "J42",
            "J430",
            "J431",
            "J432",
            "J438",
            "J439",
            "J440",
            "J441",
            "J4481",
            "J4489",
            "J449",
            "J982",
            "J983",
        ]:
            return ["HCC112"]

    def _age_sex_edit_3(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        F3481: unlike V22/V24 Community, ESRD's crosswalk has no unconditional default row for
        this code at all -- it maps to HCC59 only within age 6-18, and to nothing outside that
        range. So there's no static row to cancel; this edit *adds* the category when the
        condition is met, rather than rejecting a default outside it.
        """
        if 6 <= age <= 18 and dx_code == "F3481":
            return ["HCC59"]

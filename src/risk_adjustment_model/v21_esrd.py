from typing import List, Union, Type
from .utilities import determine_age_band
from .medicare_model import MedicareModel
from .category import Category
from .beneficiary import ESRDv21Beneficiary
from .result import ESRDv21ScoringResult

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


class MedicareModelESRDv21(MedicareModel):
    """
    This class represents the V21 ESRD (End-Stage Renal Disease) Model for Medicare -- CMS's
    legacy ESRD model, retained alongside V24 for transition/blending purposes the same way
    MedicareModelV22 is retained alongside V24/V28 for Community. Like MedicareModelESRDv24,
    this is a Medicare model variant, not a separate line of business -- lob="medicare",
    version="v21_esrd", imported from the top-level risk_adjustment_model package.

    V21 is structurally simpler than V24 in three ways that matter for this implementation:

    1. A Medicaid dual-status flag (`mcaid`), not V24's Full/Partial Benefit Dual split -- see
       ESRDv21Beneficiary, which is its own class rather than reusing ESRDBeneficiary's
       fbdual/pbdual/lti fields (V21 has no LTI concept at all). Note CMS's beneficiary file
       actually has *two* separate dual-status columns (MCAID, NEMCAID) -- `mcaid` drives
       continuing-enrollee scoring and `ne_mcaid` independently drives new-enrollee population
       resolution; see ESRDv21Beneficiary's docstring for why these aren't conflated.
    2. GRAFT_COMM and GRAFT_INST are each a single population column with no dual/aged
       sub-variant (unlike V24's GRAFT_COMM_{ND_PBD,FBD}_{GE65,LT65} / dual-and-aged-dependent
       GRAFT_INST bonus) -- population="GRAFT_COMM"/"GRAFT_INST" pass straight through to
       weights.csv unchanged. The graft-duration bonus itself is correspondingly simpler: one
       shared table (graft_duration_scores.csv) with no dual axis and no separate institutional
       table, used identically for GRAFT_COMM, GRAFT_INST, and NE_GRAFT, and no PBD-flag or LTI
       additive terms.
    3. V21's own software applies no actuarial adjustment to NE_GRAFT scores at all (V24 divides
       by 0.905/0.698) and does *not* zero out renal categories (HCC134-141 are scored normally
       here, unlike V24 where they're forcibly zeroed and excluded from this repo's reference
       data entirely -- see MedicareModelESRDv24's docstring for why V24 does that).

    One more subtlety carried over faithfully from CMS's source: V21's MCAID_*_Aged/NonAged
    demographic interactions and its NONAGED_* disease interactions are keyed off `disabled`
    (age < 65 *and* orec-conditioned) rather than plain age >= 65 -- see
    ESRDv21Beneficiary.disabled vs .aged, and _determine_demographic_interactions /
    _determine_disease_interactions below.

    Population values (same top-level vocabulary as V24, see MedicareModelESRDv24's docstring
    for the full design rationale): DIAL, GRAFT_COMM, GRAFT_INST, NE_DIAL, NE_GRAFT,
    TRANSPLANT_1M, TRANSPLANT_2M, TRANSPLANT_3M.

    Like the rest of this repo's Medicare models, MCE (Medicare Code Editor) age-condition
    filtering is out of scope -- only AGE_EDIT_CONDITION/SEX_EDIT_CONDITION are modeled.

    Attributes:
        category_prefix (str): "HCC", same convention as Community/V24.

    Methods:
        Overwrites:
            score, _get_normalization_factor, _determine_demographic_categories,
            _determine_disease_interactions, _age_sex_edits (see MedicareModelESRDv24 for the
            equivalent V24 methods -- shapes match, values/formulas differ per this docstring).

        New:
            _age_sex_edit_1/2/3, _get_graft_duration_bucket, _get_graft_bonus,
            _get_ne_actuarial_adjuster.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v21_esrd", year)
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
            2026: 1.129,
            2027: 1.145,
        }
        graft_group_norm_factor_dict = {
            2026: 1.203,
            2027: 1.209,
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
        mcaid: bool = False,
        ne_mcaid: bool = False,
        diagnosis_codes: Union[List[str], None] = None,
        age: Union[int, None] = None,
        dob: Union[str, None] = None,
        population: str = "DIAL",
        graft_duration_months: Union[int, None] = None,
        verbose: bool = False,
    ) -> Type[ESRDv21ScoringResult]:
        """
        Determines the ESRD V21 risk score for the inputs. Entry point for end users.

        Args:
            gender (str): Gender of the beneficiary being scored, valid values M or F.
            orec (str): Original Entitlement Reason Code of the beneficiary.
            mcaid (bool): Medicaid dual status used for continuing-enrollee (DIAL/GRAFT_COMM/
                         GRAFT_INST) scoring.
            ne_mcaid (bool): Medicaid dual status used for new-enrollee (NE_DIAL/NE_GRAFT)
                             population resolution -- a separate CMS input from `mcaid`, not a
                             duplicate of it; see ESRDv21Beneficiary's docstring.
            diagnosis_codes (list): List of diagnosis codes. Ignored for population
                                    NE_DIAL/NE_GRAFT/TRANSPLANT_*M -- see class docstring.
            age (int): Age of the beneficiary, can be None.
            dob (str): Date of birth of the beneficiary, can be None.
            population (str): DIAL, GRAFT_COMM, GRAFT_INST, NE_DIAL, NE_GRAFT, TRANSPLANT_1M,
                              TRANSPLANT_2M, or TRANSPLANT_3M (default "DIAL").
            graft_duration_months (int, optional): Months since transplant. Only used for
                                                   GRAFT_COMM/GRAFT_INST/NE_GRAFT populations.
            verbose (bool): Indicates if trimmed output or full output is desired.

        Returns:
            ESRDv21ScoringResult: An instantiated object of ESRDv21ScoringResult class.
        """
        # ESRD's normalization factor depends on which population is being scored (dialysis-group
        # vs. functioning-graft-group series), not just year -- see _get_normalization_factor.
        self.normalization_factor = self._get_normalization_factor(
            self.model_year, population
        )
        beneficiary = ESRDv21Beneficiary(
            gender, orec, mcaid, ne_mcaid, population, age, dob, self.model_year
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
                demographic_score_raw += self._get_graft_bonus(
                    beneficiary.ne_aged, duration_bucket
                )
                # Unlike V24, V21 applies no actuarial adjustment division to NE_GRAFT.
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

        if population in ("GRAFT_COMM", "GRAFT_INST") and duration_bucket:
            demographic_score_raw += self._get_graft_bonus(
                beneficiary.aged, duration_bucket
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
        beneficiary: Type[ESRDv21Beneficiary],
        diagnosis_codes: Union[List[str], None],
        population: str,
        graft_duration_months: Union[int, None],
        score_raw: float,
        disease_score_raw: float,
        demographic_score_raw: float,
        category_list: List[str],
        category_details: dict,
    ) -> Type[ESRDv21ScoringResult]:
        """Assembles an ESRDv21ScoringResult. See MedicareModelESRDv24._build_result."""
        return ESRDv21ScoringResult(
            gender=beneficiary.gender,
            orec=beneficiary.orec,
            mcaid=beneficiary.mcaid,
            ne_mcaid=beneficiary.ne_mcaid,
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
        self, beneficiary: Type[ESRDv21Beneficiary]
    ) -> List[str]:
        """
        Determine demographic categories. Same population-dependent structure as
        MedicareModelESRDv24 (NE_DIAL/NE_GRAFT get one age/sex-band category and nothing else;
        DIAL/GRAFT_COMM/GRAFT_INST get an age/sex-band category plus whichever interactions
        apply, unconditionally -- weights.csv zeroes out the ones that don't apply to a given
        population).
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
        """Age/sex band for DIAL/GRAFT_COMM/GRAFT_INST. Same band structure as Community/V24."""
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
        """Age/sex band for NE_DIAL. See MedicareModelESRDv24._ne_dial_age_gender_category."""
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
        """Age/sex band for NE_GRAFT. See MedicareModelESRDv24._ne_graft_age_gender_category."""
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
        self, beneficiary: Type[ESRDv21Beneficiary]
    ) -> List[str]:
        """
        Determines V21 demographic interaction categories. Note MCAID_*_Aged/NonAged is keyed
        off `beneficiary.disabled` (CMS's DISABL, age < 65 *and* orec-conditioned), not plain
        `beneficiary.aged` -- see class docstring. The flat "MCAID" category (no gender/aged
        split) is scored only for GRAFT_INST in weights.csv, but included unconditionally here
        like the rest, matching this repo's usual population-agnostic category inclusion pattern.

        Args:
            beneficiary (Type[ESRDv21Beneficiary]): Instance of ESRDv21Beneficiary.

        Returns:
            List[str]: List of demographic interaction category names.
        """
        interactions = []
        sex_label = "Female" if beneficiary.gender == "F" else "Male"
        # CMS's CE source labels DISABL == 0 as "Aged" and DISABL == 1 as "NonAged" here --
        # counterintuitive naming, faithfully reproduced.
        disabl_aged_label = "NonAged" if beneficiary.disabled else "Aged"

        if beneficiary.ce_orig_disabled:
            interactions.append(f"OriginallyDisabled_{sex_label}")
        if beneficiary.origesrd and beneficiary.aged:
            interactions.append(f"Originally_ESRD_{sex_label}")
        if beneficiary.mcaid:
            interactions.append("MCAID")
            interactions.append(f"MCAID_{sex_label}_{disabl_aged_label}")

        return interactions

    # --- Disease interactions ---

    def _determine_disease_interactions(
        self, categories: List[Type[Category]], beneficiary: Type[ESRDv21Beneficiary]
    ) -> List[Type[Category]]:
        """
        Determines V21 disease interactions. Unlike V24: no HCC-count/payment-count
        interaction; renal categories are real and scored (CHF_RENAL is reachable, unlike V24's
        omitted HCC85_gRenal_V24); NONAGED_* is keyed off `beneficiary.disabled`, matching CMS's
        var_1="DISABL" (not plain NonAged/age < 65 the way V24's NONAGED_* interactions are).

        Args:
            categories (List[Type[Category]]): List of Category objects.
            beneficiary (Type[ESRDv21Beneficiary]): Instance of ESRDv21Beneficiary.

        Returns:
            List[Type[Category]]: List of Category objects representing the disease interactions.
        """
        category_list = [
            category.category for category in categories if category.type == "disease"
        ]
        cancer_list = ["HCC8", "HCC9", "HCC10", "HCC11", "HCC12"]
        diabetes_list = ["HCC17", "HCC18", "HCC19"]
        card_resp_fail_list = ["HCC82", "HCC83", "HCC84"]
        copd_list = ["HCC110", "HCC111"]
        renal_list = [
            "HCC134",
            "HCC135",
            "HCC136",
            "HCC137",
            "HCC138",
            "HCC139",
            "HCC140",
            "HCC141",
        ]
        pressure_ulcer_list = ["HCC157", "HCC158", "HCC159", "HCC160"]

        cancer = any(category in category_list for category in cancer_list)
        diabetes = any(category in category_list for category in diabetes_list)
        card_resp_fail = any(
            category in category_list for category in card_resp_fail_list
        )
        chf = "HCC85" in category_list
        copd = any(category in category_list for category in copd_list)
        renal = any(category in category_list for category in renal_list)
        sepsis = "HCC2" in category_list
        pressure_ulcer = any(
            category in category_list for category in pressure_ulcer_list
        )
        hcc6 = "HCC6" in category_list
        hcc34 = "HCC34" in category_list
        hcc39 = "HCC39" in category_list
        hcc46 = "HCC46" in category_list
        hcc47 = "HCC47" in category_list
        hcc54 = "HCC54" in category_list
        hcc55 = "HCC55" in category_list
        hcc57 = "HCC57" in category_list
        hcc77 = "HCC77" in category_list
        hcc79 = "HCC79" in category_list
        hcc110 = "HCC110" in category_list
        hcc114 = "HCC114" in category_list
        hcc161 = "HCC161" in category_list
        hcc176 = "HCC176" in category_list
        hcc188 = "HCC188" in category_list

        disabled = beneficiary.disabled

        interactions_dict = {
            "SEPSIS_CARD_RESP_FAIL": all([sepsis, card_resp_fail]),
            "CANCER_IMMUNE": all([cancer, hcc47]),
            "DIABETES_CHF": all([diabetes, chf]),
            "CHF_COPD": all([chf, copd]),
            "CHF_RENAL": all([chf, renal]),
            "COPD_CARD_RESP_FAIL": all([copd, card_resp_fail]),
            "SEPSIS_PRESSURE_ULCER": all([sepsis, pressure_ulcer]),
            "SEPSIS_ARTIF_OPENINGS": all([sepsis, hcc188]),
            "ART_OPENINGS_PRESSURE_ULCER": all([hcc188, pressure_ulcer]),
            "COPD_ASP_SPEC_BACT_PNEUM": all([copd, hcc114]),
            "ASP_SPEC_BACT_PNEUM_PRES_ULC": all([hcc114, pressure_ulcer]),
            "SEPSIS_ASP_SPEC_BACT_PNEUM": all([sepsis, hcc114]),
            "SCHIZOPHRENIA_COPD": all([hcc57, copd]),
            "SCHIZOPHRENIA_CHF": all([hcc57, chf]),
            "SCHIZOPHRENIA_SEIZURES": all([hcc57, hcc79]),
            "NONAGED_HCC6": all([disabled, hcc6]),
            "NONAGED_HCC34": all([disabled, hcc34]),
            "NONAGED_HCC46": all([disabled, hcc46]),
            "NONAGED_HCC54": all([disabled, hcc54]),
            "NONAGED_HCC55": all([disabled, hcc55]),
            "NONAGED_HCC110": all([disabled, hcc110]),
            "NONAGED_HCC176": all([disabled, hcc176]),
            "NONAGED_HCC85": all([disabled, chf]),
            "NONAGED_PRESSURE_ULCER": all([disabled, pressure_ulcer]),
            "NONAGED_HCC161": all([disabled, hcc161]),
            "NONAGED_HCC39": all([disabled, hcc39]),
            "NONAGED_HCC77": all([disabled, hcc77]),
        }
        interaction_list = [key for key, value in interactions_dict.items() if value]

        interactions = [
            Category(self.reference_files, beneficiary.risk_model_population, category)
            for category in interaction_list
        ]
        interactions.extend(categories)

        return interactions

    # --- Graft duration math ---

    def _get_graft_duration_bucket(
        self, graft_duration_months: Union[int, None]
    ) -> Union[str, None]:
        """See MedicareModelESRDv24._get_graft_duration_bucket -- identical rule."""
        if graft_duration_months is None:
            return None
        if 4 <= graft_duration_months <= 9:
            return "DUR4_9"
        if graft_duration_months >= 10:
            return "DUR10PL"
        return None

    def _get_graft_bonus(self, aged: bool, duration_bucket: str) -> float:
        """
        Additive graft-duration bonus, from graft_duration_scores.csv. Unlike V24, the same
        table and formula apply to GRAFT_COMM, GRAFT_INST, and NE_GRAFT alike -- no dual axis,
        no PBD-flag or LTI additive terms. `aged` should be beneficiary.aged for
        GRAFT_COMM/GRAFT_INST, or beneficiary.ne_aged for NE_GRAFT (see score()).
        """
        aged_key = "GE65" if aged else "LT65"
        dur_key = "DUR4_9" if duration_bucket == "DUR4_9" else "DUR10PL"
        return self.reference_files.graft_duration_scores[f"{dur_key}_{aged_key}"]

    # --- Age/sex edits ---

    def _age_sex_edits(
        self, gender: str, age: int, diagnosis_code: str
    ) -> Union[List[str], None]:
        """Same 19-code edit set as V22/V24 Community and ESRD V24 -- see class docstring."""
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
        F3481: no unconditional default row (same shape as ESRD V24, but the target HCC differs
        -- HCC58 here, not HCC59). Maps to HCC58 only within age 6-18, and to nothing outside it.
        """
        if 6 <= age <= 18 and dx_code == "F3481":
            return ["HCC58"]

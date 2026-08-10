import datetime
from typing import Union, Tuple


class Beneficiary:
    """
    Represents a beneficiary. As to why there is age and DOB: DOB is considered PHI.
    Thus to comply with HIPPA rules, it can be excluded and age used instead. However,
    one of the two is required.

    Attributes:
        gender (str): The gender of the beneficiary.
        age (int, optional): The age of the beneficiary.
        dob (str, optional): The date of birth of the beneficiary in ISO format.

    """

    def __init__(
        self, gender: str, age: Union[None, int] = None, dob: Union[None, str] = None
    ):
        """
        Initialize a Beneficiary object.

        Args:
            gender (str): The gender of the beneficiary.
            age (int, optional): The age of the beneficiary.
            dob (str, optional): The date of birth of the beneficiary in ISO format.

        """
        if age is None and dob is None:
            raise ValueError("Either age or dob must be provided.")
        self.gender = gender
        self.age = age
        self.dob = dob


class MedicareBeneficiary(Beneficiary):
    """
    Represents a Medicare beneficiary which expands upon the Beneficiary class and
    requires additional Medicare specific attributes: orec, medicaid, and population.
    See __init__ for more detailed description of these attributes

    Attributes:
        gender (str): The gender of the Medicare beneficiary.
        orec (str): The original reason for entitlement code.
        medicaid (bool): Indicates whether the beneficiary has Medicaid, for continuing-enrollee
                         (LTIMCAID demographic interaction) scoring purposes.
        ne_medicaid (bool): Indicates whether the beneficiary has Medicaid, for new-enrollee
                            population resolution purposes. CMS's own beneficiary file has two
                            separate columns for this -- LTIMCAID and NEMCAID -- which are not
                            guaranteed to agree for a given beneficiary (see
                            CMS_HCC_utils.py's get_bene_info_df, which reads NEMCAID for the NE
                            population split and LTIMCAID separately for the CE interaction).
                            Defaults to `medicaid` when not passed explicitly, preserving prior
                            behavior for callers who only ever tracked one dual-status flag.
        population (str, optional): The Medicare population type (default is "CNA").
        age (int, optional): The age of the Medicare beneficiary.
        dob (str, optional): The date of birth of the Medicare beneficiary in ISO format.
        disabled (bool): Indicates if the beneficiary is disabled.
        orig_disabled (bool): Indiciates if the beneficiary was originally disabled.
        risk_model_age (int): Age of the benficiary used in the model scoring calculations.
                              Per CMS, it is age of the beneficiary as of February 1st of
                              the payment year.
        risk_model_population (str): The derived population for the beneficiary based on all
                                     beneficiary attributes. This is necessary as in the
                                     Community model, CMS New Enrollees are broken into four
                                     subpopulations based on Medicaid status and whether or
                                     not the beneficiary was "originally disabled". By only
                                     requiring "NE" to be passed in for a population value,
                                     users do not need to know how to determine the four
                                     additional subpopulations and the code does it for
                                     them. See _get_new_enrollee_population for more details.

    """

    def __init__(
        self,
        gender: str,
        orec: str,
        medicaid: bool,
        population="CNA",
        age: Union[None, int] = None,
        dob: Union[None, str] = None,
        model_year: Union[None, int] = None,
        ne_medicaid: Union[None, bool] = None,
    ):
        """
        Initialize a MedicareBeneficiary object.

        Args:
            gender (str): The gender of the Medicare beneficiary.
            orec (str): The original reason entitlement code. See the below link for more information:
                        https://resdac.org/cms-data/variables/medicare-original-reason-entitlement-code-orec
            medicaid (bool): A boolean indicating whether the beneficiary has Medicaid, used for
                             continuing-enrollee (LTIMCAID) scoring.
            population (str, optional): The Medicare population type which the benficiary is
                                        associated with and the score is being computed for.
                                        Valid values are:
                                        CNA - Community, Non Dual, Aged (default)
                                        CND - Community, Non Dual, Disabled
                                        CPA - Community, Partial Dual, Aged
                                        CPD - Community, Partial Dual, Disabled
                                        CFA - Community, Full Dual, Aged
                                        CFD - Community, Full Dual, Disabled
                                        INS - Institutional
                                        NE - CMS New Enrollee
            age (int, optional): The age of the Medicare beneficiary.
            dob (str, optional): The date of birth of the Medicare beneficiary in ISO format.
            model_year (int, optional): The model year which this beneficiary object is associated with.
                              It is necessary to determine the age of the beneficiary if dob is passed in.
            ne_medicaid (bool, optional): A boolean indicating whether the beneficiary has
                                          Medicaid, used for new-enrollee population resolution
                                          (population="NE") -- CMS tracks this as a separate
                                          input (NEMCAID) from the continuing-enrollee `medicaid`
                                          flag (LTIMCAID). Defaults to `medicaid` when None.
        """
        super().__init__(gender, age, dob)
        self.orec = orec
        self.medicaid = medicaid
        self.ne_medicaid = medicaid if ne_medicaid is None else ne_medicaid
        self.population = population
        self.model_year = model_year
        self.risk_model_age = self._determine_age(self.age, self.dob)
        self.disabled, self.orig_disabled = self._determine_disabled(
            self.age, self.orec
        )
        if self.population == "NE":
            self.risk_model_population = self._get_new_enrollee_population(
                self.risk_model_age, self.orec, self.ne_medicaid
            )
        else:
            self.risk_model_population = population

    def _determine_age(self, age: int, dob: str) -> int:
        """
        Determine the age of the beneficiary based on either age or date of birth (DOB).

        This function addresses two design considerations:
        1. Date of birth (DOB) is considered Protected Health Information (PHI), thus
           allowing flexibility in handling PHI by accepting either age or DOB.
        2. The CMS Risk Adjustment Model uses age as of February 1st of the payment year.
           If DOB is provided, age needs to be computed relative to that date. That payment year
           must also be provided.

        Args:
            age (int): The age of the beneficiary.
            dob (str): The date of birth of the beneficiary in ISO format.

        Returns:
            int: The age of the beneficiary as of February 1st of the payment year.

        If age is provided, it is assumed to be correct as of February 1st of the payment year.
        If DOB is provided, it computes the age relative to February 1st of the payment year.
        """
        if dob:
            if self.model_year is None:
                raise ValueError(
                    "When date of birth is provided, model year must also be provided"
                )
            reference_date = datetime.datetime.fromisoformat(f"{self.model_year}-02-01")
            dt_dob = datetime.datetime.fromisoformat(dob)
            age = (
                reference_date.year
                - dt_dob.year
                - (
                    (reference_date.month, reference_date.day)
                    < (dt_dob.month, dt_dob.day)
                )
            )
        elif age:
            age = age

        return age

    def _determine_disabled(self, age: int, orec: str) -> Tuple[bool, bool]:
        """
        Determine disability status and original disability status based on age and
        original entitlement reason code.

        Args:
            age (int): The age of the individual.
            orec (str): The original reason for entitlement code.

        Returns:
            tuple: A tuple containing two boolean elements:
                - A bool indicating if the individual is disabled (True if disabled, False otherwise).
                - A bool indicating the original disability status (True if originally disabled, False otherwise).
        """
        if age < 65 and orec != "0":
            disabled = True
        else:
            disabled = False

        if orec in ("1", "3") and disabled == 0:
            orig_disabled = True
        else:
            orig_disabled = False

        return disabled, orig_disabled

    def _get_new_enrollee_population(self, age: int, orec: str, medicaid: bool):
        """
        Compute the new enrollee population for the Community model based on Medicaid status
        and whether or not the beneficiary was originally disabled.

        Args:
            age (int): The age of the beneficiary.
            orec (str): The original reason for entitlement category.
            medicaid (bool): A boolean indicating whether the beneficiary has Medicaid.

        Returns:
            str: The new enrollee population type.

        New enrollee populations:
            - NMCAID_NORIGDIS: Non-Medicaid and not Originally Disabled
            - MCAID_NORIGDIS: Medicaid and not Originally Disabled
            - NMCAID_ORIGDIS: Non-Medicaid and Originally Disabled
            - MCAID_ORIGDIS: Medicaid and Originally Disabled
        """
        ne_population = None

        if age >= 65 and orec == "1":
            ne_originally_disabled = True
        else:
            ne_originally_disabled = False
        if not ne_originally_disabled and not medicaid:
            ne_population = "NE_NMCAID_NORIGDIS"
        if not ne_originally_disabled and medicaid:
            ne_population = "NE_MCAID_NORIGDIS"
        if ne_originally_disabled and not medicaid:
            ne_population = "NE_NMCAID_ORIGDIS"
        if ne_originally_disabled and medicaid:
            ne_population = "NE_MCAID_ORIGDIS"

        if ne_population is None:
            raise ValueError(
                "Population value NE passed in, but unable to determine corresponding risk model population for associated beneficiary attributes"
            )

        return ne_population


class ESRDBeneficiary(Beneficiary):
    """
    Represents a Medicare ESRD (End-Stage Renal Disease) beneficiary. Expands upon the
    Beneficiary class with ESRD-specific attributes: orec, fbdual, pbdual, lti, and population.

    Unlike MedicareBeneficiary, there is no single "medicaid" flag -- ESRD's own beneficiary
    file distinguishes Full Benefit Dual (fbdual) from Partial Benefit Dual (pbdual), and both
    feed directly into scoring (as opposed to Community, where dual status is folded entirely
    into the population choice, e.g. CFA vs CPA). See v24_esrd.py's module docstring for the
    full population/scoring design this supports.

    Attributes:
        gender (str): The gender of the beneficiary.
        orec (str): The original reason for entitlement code.
        fbdual (bool): Full Benefit Dual (Medicare + full Medicaid) status.
        pbdual (bool): Partial Benefit Dual status.
        lti (bool): Long-Term Institutional status.
        population (str, optional): The ESRD population the score is being computed for. Valid
                                    values are DIAL, GRAFT_COMM, GRAFT_INST, NE_DIAL, NE_GRAFT,
                                    TRANSPLANT_1M, TRANSPLANT_2M, TRANSPLANT_3M (default "DIAL").
        age (int, optional): The age of the beneficiary.
        dob (str, optional): The date of birth of the beneficiary in ISO format.
        disabled (bool): Indicates if the beneficiary is disabled (age < 65 and orec in [1,2,3]).
        aged (bool): Indicates if the beneficiary is 65 or older.
        ce_orig_disabled (bool): Continuing-enrollee "originally disabled" status -- true only
                                 when orec == "1" and the beneficiary is not currently disabled
                                 (i.e. age >= 65 and orec == "1"). Distinct from Community's
                                 orig_disabled, which also treats orec == "3" as originally
                                 disabled; ESRD's CE model does not.
        origesrd (bool): Indicates the beneficiary's original entitlement reason was ESRD
                         (orec in ["2", "3"]).
        ne_dial_origdis (bool): New enrollee dialysis "originally disabled" status -- true
                                whenever orec == "1", with no age gate.
        ne_graft_origdis (bool): New enrollee graft "originally disabled" status -- true only
                                 when age >= 65 and orec == "1" (unlike ne_dial_origdis, this one
                                 is age-gated, matching CMS's NE_ORIGDIS vs NE_ORIGDIS_G split).
        ne_aged (bool): New enrollee "aged" status used only for NE graft duration/actuarial
                        adjustment math -- true when age >= 65, or age == 64 with orec == "0".
        risk_model_age (int): Age of the beneficiary used in the model scoring calculations.
        risk_model_population (str): The fully-qualified weights.csv population column resolved
                                     from population + fbdual/pbdual/age, e.g. "GRAFT_COMM_FBD_GE65"
                                     or "NE_DIAL_ND_PBD_ORIGDIS". DIAL, GRAFT_INST, and the flat
                                     TRANSPLANT_*M populations pass through unchanged since their
                                     weights.csv columns don't vary by dual/origdis status.
    """

    def __init__(
        self,
        gender: str,
        orec: str,
        fbdual: bool = False,
        pbdual: bool = False,
        lti: bool = False,
        population: str = "DIAL",
        age: Union[None, int] = None,
        dob: Union[None, str] = None,
        model_year: Union[None, int] = None,
    ):
        """
        Initialize an ESRDBeneficiary object.

        Args:
            gender (str): The gender of the beneficiary.
            orec (str): The original reason entitlement code.
            fbdual (bool): Full Benefit Dual status (default False).
            pbdual (bool): Partial Benefit Dual status (default False).
            lti (bool): Long-Term Institutional status (default False).
            population (str, optional): The ESRD population the score is being computed for
                                        (default "DIAL"). See class docstring for valid values.
            age (int, optional): The age of the beneficiary.
            dob (str, optional): The date of birth of the beneficiary in ISO format.
            model_year (int, optional): The model year associated with the beneficiary. Necessary
                                        to determine age when dob is passed in.
        """
        super().__init__(gender, age, dob)
        self.orec = orec
        self.fbdual = fbdual
        self.pbdual = pbdual
        self.lti = lti
        self.population = population
        self.model_year = model_year
        self.risk_model_age = self._determine_age(self.age, self.dob)
        self.disabled = self.risk_model_age < 65 and self.orec in ("1", "2", "3")
        self.aged = self.risk_model_age >= 65
        self.ce_orig_disabled = self.orec == "1" and not self.disabled
        self.origesrd = self.orec in ("2", "3")
        self.ne_dial_origdis = self.orec == "1"
        self.ne_graft_origdis = self.risk_model_age >= 65 and self.orec == "1"
        self.ne_aged = self.risk_model_age >= 65 or (
            self.risk_model_age == 64 and self.orec == "0"
        )
        self.risk_model_population = self._get_risk_model_population(population)

    def _determine_age(self, age: int, dob: str) -> int:
        """
        Determine the age of the beneficiary based on either age or date of birth (DOB), as of
        February 1st of the payment year. See MedicareBeneficiary._determine_age for the full
        rationale; the calculation is identical for ESRD.
        """
        if dob:
            if self.model_year is None:
                raise ValueError(
                    "When date of birth is provided, model year must also be provided"
                )
            reference_date = datetime.datetime.fromisoformat(f"{self.model_year}-02-01")
            dt_dob = datetime.datetime.fromisoformat(dob)
            age = (
                reference_date.year
                - dt_dob.year
                - (
                    (reference_date.month, reference_date.day)
                    < (dt_dob.month, dt_dob.day)
                )
            )
        elif age:
            age = age

        return age

    def _get_risk_model_population(self, population: str) -> str:
        """
        Resolve the caller-facing population choice into the fully-qualified weights.csv
        population column, mirroring how MedicareBeneficiary resolves population="NE" into one
        of four NE_* sub-populations. DIAL, GRAFT_INST, and the flat TRANSPLANT_*M populations
        pass through unchanged -- their base category coefficients don't vary by dual/origdis
        status (GRAFT_INST's duration-bonus math still uses fbdual/pbdual/lti directly, applied
        as a scoring-time adjustment in v24_esrd.py rather than a population axis).

        Args:
            population (str): DIAL, GRAFT_COMM, GRAFT_INST, NE_DIAL, NE_GRAFT, or one of
                              TRANSPLANT_1M/TRANSPLANT_2M/TRANSPLANT_3M.

        Returns:
            str: The fully-qualified weights.csv population column.
        """
        dual = "FBD" if self.fbdual else "ND_PBD"

        if population in ("DIAL", "GRAFT_INST") or population.startswith("TRANSPLANT_"):
            return population
        if population == "GRAFT_COMM":
            aged = "GE65" if self.aged else "LT65"
            return f"GRAFT_COMM_{dual}_{aged}"
        if population == "NE_DIAL":
            origdis = "ORIGDIS" if self.ne_dial_origdis else "NORIGDIS"
            return f"NE_DIAL_{dual}_{origdis}"
        if population == "NE_GRAFT":
            origdis = "ORIGDIS" if self.ne_graft_origdis else "NORIGDIS"
            return f"NE_GRAFT_{dual}_{origdis}"

        raise ValueError(
            f"Unrecognized ESRD population: {population}. Valid values are DIAL, GRAFT_COMM, "
            "GRAFT_INST, NE_DIAL, NE_GRAFT, TRANSPLANT_1M, TRANSPLANT_2M, TRANSPLANT_3M"
        )


class ESRDv21Beneficiary(Beneficiary):
    """
    Represents a Medicare ESRD V21 (legacy) beneficiary. V21 is structurally simpler than V24:
    a Medicaid dual-status flag (no Full/Partial Benefit Dual split) and no Long-Term
    Institutional concept at all -- CMS's own V21 beneficiary file is just ID,DOB,SEX,OREC,
    MCAID,NEMCAID. Kept as its own class rather than reusing ESRDBeneficiary's fbdual/pbdual/lti
    fields, since those don't apply to V21 at all and would be misleading to expose.

    Note CMS's beneficiary file has *two separate* dual-status columns, not one: `mcaid` drives
    the continuing-enrollee (DIAL/GRAFT_COMM/GRAFT_INST) demographic interactions, while
    `ne_mcaid` is an independent flag that drives new-enrollee (NE_DIAL/NE_GRAFT) population
    resolution -- confirmed directly from CMS's transform.py, which reads `row['MCAID']` for the
    CE MCAID_*_Aged/NonAged interactions and `row['NEMCAID']` for the NE population split. Unlike
    V24 (where the same fbdual/pbdual values feed both CE and NE), these are not the same
    real-world fact necessarily -- do not default one from the other.

    Attributes:
        gender (str): The gender of the beneficiary.
        orec (str): The original reason for entitlement code.
        mcaid (bool): Medicaid dual status, used for continuing-enrollee scoring.
        ne_mcaid (bool): Medicaid dual status, used for new-enrollee population resolution. A
                         separate CMS input from `mcaid` -- see class docstring.
        population (str, optional): The ESRD population the score is being computed for. Valid
                                    values are DIAL, GRAFT_COMM, GRAFT_INST, NE_DIAL, NE_GRAFT,
                                    TRANSPLANT_1M, TRANSPLANT_2M, TRANSPLANT_3M (default "DIAL").
        age (int, optional): The age of the beneficiary.
        dob (str, optional): The date of birth of the beneficiary in ISO format.
        disabled (bool): age < 65 and orec in [1,2,3]. Distinct from `aged` (plain age >= 65) --
                         V21's own MCAID_*_Aged/NonAged and NONAGED_* interaction categories are
                         keyed off `disabled` (matching CMS's DISABL variable), not plain age.
        aged (bool): age >= 65. Used for Originally_ESRD_*, and the graft-duration bonus's
                    aged/nonaged bucket.
        ce_orig_disabled (bool): orec == "1" and not disabled (i.e. age >= 65 and orec == "1").
        origesrd (bool): orec in ["2", "3"].
        ne_dial_origdis (bool): orec == "1", no age gate.
        ne_graft_origdis (bool): age >= 65 and orec == "1".
        ne_aged (bool): age >= 65, or age == 64 with orec == "0". Used only for NE_GRAFT's
                        graft-duration bonus.
        risk_model_age (int): Age of the beneficiary used in the model scoring calculations.
        risk_model_population (str): The fully-qualified weights.csv population column. DIAL,
                                     GRAFT_COMM, GRAFT_INST, and the TRANSPLANT_*M populations
                                     pass through unchanged -- unlike V24, V21's GRAFT_COMM/
                                     GRAFT_INST base coefficients don't vary by dual status at
                                     all. Only NE_DIAL/NE_GRAFT resolve to a dual+origdis
                                     sub-population, e.g. "NE_DIAL_MCAID_ORIGDIS".
    """

    def __init__(
        self,
        gender: str,
        orec: str,
        mcaid: bool = False,
        ne_mcaid: bool = False,
        population: str = "DIAL",
        age: Union[None, int] = None,
        dob: Union[None, str] = None,
        model_year: Union[None, int] = None,
    ):
        super().__init__(gender, age, dob)
        self.orec = orec
        self.mcaid = mcaid
        self.ne_mcaid = ne_mcaid
        self.population = population
        self.model_year = model_year
        self.risk_model_age = self._determine_age(self.age, self.dob)
        self.disabled = self.risk_model_age < 65 and self.orec in ("1", "2", "3")
        self.aged = self.risk_model_age >= 65
        self.ce_orig_disabled = self.orec == "1" and not self.disabled
        self.origesrd = self.orec in ("2", "3")
        self.ne_dial_origdis = self.orec == "1"
        self.ne_graft_origdis = self.risk_model_age >= 65 and self.orec == "1"
        self.ne_aged = self.risk_model_age >= 65 or (
            self.risk_model_age == 64 and self.orec == "0"
        )
        self.risk_model_population = self._get_risk_model_population(population)

    def _determine_age(self, age: int, dob: str) -> int:
        """
        Determine the age of the beneficiary based on either age or date of birth (DOB), as of
        February 1st of the payment year. See MedicareBeneficiary._determine_age for the full
        rationale; the calculation is identical for ESRD.
        """
        if dob:
            if self.model_year is None:
                raise ValueError(
                    "When date of birth is provided, model year must also be provided"
                )
            reference_date = datetime.datetime.fromisoformat(f"{self.model_year}-02-01")
            dt_dob = datetime.datetime.fromisoformat(dob)
            age = (
                reference_date.year
                - dt_dob.year
                - (
                    (reference_date.month, reference_date.day)
                    < (dt_dob.month, dt_dob.day)
                )
            )
        elif age:
            age = age

        return age

    def _get_risk_model_population(self, population: str) -> str:
        """
        Resolve the caller-facing population choice into the fully-qualified weights.csv
        population column. DIAL, GRAFT_COMM, GRAFT_INST, and the flat TRANSPLANT_*M populations
        pass through unchanged (V21's base category coefficients for all three don't vary by
        dual/origdis status at all -- see v21_esrd.py). Only NE_DIAL/NE_GRAFT resolve further.

        Args:
            population (str): DIAL, GRAFT_COMM, GRAFT_INST, NE_DIAL, NE_GRAFT, or one of
                              TRANSPLANT_1M/TRANSPLANT_2M/TRANSPLANT_3M.

        Returns:
            str: The fully-qualified weights.csv population column.
        """
        if population in ("DIAL", "GRAFT_COMM", "GRAFT_INST") or population.startswith(
            "TRANSPLANT_"
        ):
            return population

        # NE population resolution uses ne_mcaid, not mcaid -- see class docstring.
        dual = "MCAID" if self.ne_mcaid else "NMCAID"
        if population == "NE_DIAL":
            origdis = "ORIGDIS" if self.ne_dial_origdis else "NORIGDIS"
            return f"NE_DIAL_{dual}_{origdis}"
        if population == "NE_GRAFT":
            origdis = "ORIGDIS" if self.ne_graft_origdis else "NORIGDIS"
            return f"NE_GRAFT_{dual}_{origdis}"

        raise ValueError(
            f"Unrecognized ESRD population: {population}. Valid values are DIAL, GRAFT_COMM, "
            "GRAFT_INST, NE_DIAL, NE_GRAFT, TRANSPLANT_1M, TRANSPLANT_2M, TRANSPLANT_3M"
        )


class RxHCCBeneficiary(Beneficiary):
    """
    Represents a Medicare RxHCC (Part D) beneficiary. Expands upon the Beneficiary class with
    RxHCC-specific attributes: orec, esrd, and population.

    Unlike Community/ESRD, `population` needs no derivation at all -- CMS's own RxHCC software
    outputs 8 population columns (5 continuing-enrollee, 3 new-enrollee) that don't vary by any
    beneficiary attribute other than the caller's direct choice, so `risk_model_population` is
    always just `population` passed straight through. See v08_rxhcc_t.py (and its sibling
    segment classes)'s module docstring for the full population list and design rationale.

    Attributes:
        gender (str): The gender of the beneficiary.
        orec (str): The original reason for entitlement code.
        esrd (bool): Indicates End-Stage Renal Disease status (dialysis, transplant, or post
                     graft) -- RxHCC's beneficiary file has no dual/LIS status field at all;
                     Low/NonLow-Income-Subsidy status is instead part of `population` itself,
                     chosen directly by the caller like Community's CNA vs CFA.
        population (str, optional): The RxHCC population the score is being computed for (default
                                    "CE_NONLOW_AGED"). Valid values: CE_NONLOW_AGED,
                                    CE_NONLOW_NONAGED, CE_LOW_AGED, CE_LOW_NONAGED, CE_LTI,
                                    NE_NONLOW_COMMUNITY, NE_LOW_COMMUNITY, NE_LTI.
        age (int, optional): The age of the beneficiary.
        dob (str, optional): The date of birth of the beneficiary in ISO format.
        disabled (bool): age < 65 and orec != "0" (matches CMS's DISABLED variable -- note this
                         is broader than ESRD's, which further restricts orec to [1,2,3]).
        aged (bool): age >= 65.
        origdis (bool): "Originally disabled" -- orec == "1" and not disabled (i.e. age >= 65 and
                        orec == "1"). Drives the M65OD/F65OD/OD65 demographic interaction
                        categories for continuing enrollees, and the ESRD/NORIGDIS axis of new
                        enrollee age/sex category resolution.
        risk_model_age (int): Age of the beneficiary used in the model scoring calculations.
        risk_model_population (str): Always equal to `population` -- see class docstring.
    """

    def __init__(
        self,
        gender: str,
        orec: str,
        esrd: bool = False,
        population: str = "CE_NONLOW_AGED",
        age: Union[None, int] = None,
        dob: Union[None, str] = None,
        model_year: Union[None, int] = None,
    ):
        super().__init__(gender, age, dob)
        self.orec = orec
        self.esrd = esrd
        self.population = population
        self.model_year = model_year
        self.risk_model_age = self._determine_age(self.age, self.dob)
        self.disabled = self.risk_model_age < 65 and self.orec != "0"
        self.aged = self.risk_model_age >= 65
        self.origdis = self.orec == "1" and not self.disabled
        self.risk_model_population = population

    def _determine_age(self, age: int, dob: str) -> int:
        """
        Determine the age of the beneficiary based on either age or date of birth (DOB), as of
        February 1st of the payment year. See MedicareBeneficiary._determine_age for the full
        rationale; the calculation is identical for RxHCC.
        """
        if dob:
            if self.model_year is None:
                raise ValueError(
                    "When date of birth is provided, model year must also be provided"
                )
            reference_date = datetime.datetime.fromisoformat(f"{self.model_year}-02-01")
            dt_dob = datetime.datetime.fromisoformat(dob)
            age = (
                reference_date.year
                - dt_dob.year
                - (
                    (reference_date.month, reference_date.day)
                    < (dt_dob.month, dt_dob.day)
                )
            )
        elif age:
            age = age

        return age


class CommercialBeneficiary(Beneficiary):
    """
    Represents a Commercial beneficiary which expands upon the Beneficiary class and
    requires additional Commercial-specific attributes: metal level, enrollment days,
    CSR indicator, and last enrollment date.

    Attributes:
        gender (str): The gender of the Commercial beneficiary.
        metal_level (str): The metal level of the beneficiary's insurance plan (e.g., Bronze, Silver).
        enrollment_days (int): The number of days the beneficiary has been enrolled.
        csr_indicator (int): The cost-sharing reduction indicator. Values are 1, 2, 3, 4
        age (int, optional): The age of the Commercial beneficiary.
        dob (str, optional): The date of birth of the Commercial beneficiary in ISO format.
        model_year (int, optional): The model year associated with the beneficiary.
        last_enrollment_date (str, optional): The last enrollment date of the beneficiary in ISO format.
        risk_model_age (int): The age of the beneficiary used in model scoring calculations.
        risk_model_age_group (str): The age group of the beneficiary (Infant, Child, Adult).
        risk_model_population (str): The derived population for the beneficiary.
        enrollment_months (int): The number of months the beneficiary has been enrolled.

    See __init__ for more detailed descriptions of these attributes.
    """

    def __init__(
        self,
        gender: str,
        metal_level: str = "Bronze",
        enrollment_days: int = 365,
        csr_indicator: int = 1,
        age: Union[None, int] = None,
        dob: Union[None, str] = None,
        model_year: Union[None, int] = None,
        last_enrollment_date: Union[None, str] = None,
    ):
        """
        Initialize a CommercialBeneficiary object.

        Args:
            gender (str): The gender of the Commercial beneficiary.
            metal_level (str): The metal level of the beneficiary's insurance plan (default is "Bronze").
            enrollment_days (int): The number of days the beneficiary has been enrolled (default is 365).
            csr_indicator (int): The cost-sharing reduction indicator (default is 1).
            age (int, optional): The age of the Commercial beneficiary.
            dob (str, optional): The date of birth of the Commercial beneficiary in ISO format.
            model_year (int, optional): The model year associated with the beneficiary.
            last_enrollment_date (str, optional): The last enrollment date of the beneficiary in ISO format.
        """
        super().__init__(gender, age, dob)
        self.metal_level = metal_level
        self.enrollment_days = enrollment_days
        self.csr_indicator = csr_indicator
        self.model_year = model_year
        self.last_enrollment_date = last_enrollment_date
        self.risk_model_age = self._determine_age(self.age, self.dob)
        self.risk_model_age_group = self._determine_age_group(self.risk_model_age)
        self.risk_model_population = self.metal_level
        self.enrollment_months = self._determine_enrollment_months(self.enrollment_days)

    def _determine_age(
        self, age: Union[None, int] = None, dob: Union[None, str] = None
    ) -> int:
        """
        Determine the age of the beneficiary based on either age or date of birth (DOB).

        This function addresses two design considerations:
        1. Date of birth (DOB) is considered Protected Health Information (PHI), thus
           allowing flexibility in handling PHI by accepting either age or DOB.
        2. The HHS Risk Adjustment Model uses age as of the last eligibility date of that
           beneficiary for that benefit year. If DOB is provided, age needs to be computed
           relative to that date. That benefit year must also be provided.

        Args:
            age (int, optional): The age of the beneficiary.
            dob (str, optional): The date of birth of the beneficiary in ISO format.

        Returns:
            int: The age of the beneficiary as of the last enrollment date of the benefit year.

        Raises:
            ValueError: If DOB is provided but the last enrollment date is not provided.
        """
        if dob:
            if self.last_enrollment_date is None:
                raise ValueError(
                    "When date of birth is provided, last enrollment date must also be provided"
                )
            reference_date = datetime.datetime.fromisoformat(self.last_enrollment_date)
            dt_dob = datetime.datetime.fromisoformat(dob)
            model_age = (
                reference_date.year
                - dt_dob.year
                - (
                    (reference_date.month, reference_date.day)
                    < (dt_dob.month, dt_dob.day)
                )
            )
        elif age is not None:
            model_age = age

        return model_age

    def _determine_age_group(self, age: int) -> str:
        """
        Determine the age group of the beneficiary based on their age.

        Args:
            age (int): The age of the beneficiary.

        Returns:
            str: The age group of the beneficiary. Possible values are "Infant", "Child", "Adult".
        """
        if age < 2:
            return "Infant"
        elif 2 <= age < 21:
            return "Child"
        else:
            return "Adult"

    def _determine_enrollment_months(self, enrollment_days: int) -> int:
        """
        Determine the enrollment duration in months based on the number of enrollment days.

        Args:
            enrollment_days (int): The number of days the beneficiary has been enrolled.

        Returns:
            int: The number of months the beneficiary has been enrolled.
        """
        if 1 <= enrollment_days <= 31:
            return 1
        elif 32 <= enrollment_days <= 62:
            return 2
        elif 63 <= enrollment_days <= 92:
            return 3
        elif 93 <= enrollment_days <= 123:
            return 4
        elif 124 <= enrollment_days <= 153:
            return 5
        elif 154 <= enrollment_days <= 184:
            return 6
        elif 185 <= enrollment_days <= 214:
            return 7
        elif 215 <= enrollment_days <= 245:
            return 8
        elif 246 <= enrollment_days <= 275:
            return 9
        elif 276 <= enrollment_days <= 306:
            return 10
        elif 307 <= enrollment_days <= 335:
            return 11
        elif 336 <= enrollment_days <= 366:
            return 12
        else:
            return 0

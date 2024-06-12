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
        medicaid (bool): Indicates whether the beneficiary has Medicaid.
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
    ):
        """
        Initialize a MedicareBeneficiary object.

        Args:
            gender (str): The gender of the Medicare beneficiary.
            orec (str): The original reason entitlement code. See the below link for more information:
                        https://resdac.org/cms-data/variables/medicare-original-reason-entitlement-code-orec
            medicaid (bool): A boolean indicating whether the beneficiary has Medicaid.
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
        """
        super().__init__(gender, age, dob)
        self.orec = orec
        self.medicaid = medicaid
        self.population = population
        self.model_year = model_year
        self.risk_model_age = self._determine_age(self.age, self.dob)
        self.disabled, self.orig_disabled = self._determine_disabled(
            self.age, self.orec
        )
        if self.population == "NE":
            self.risk_model_population = self._get_new_enrollee_population(
                self.risk_model_age, self.orec, self.medicaid
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


class CommercialBeneficiary(Beneficiary):
    """
    Represents a Commercial beneficiary which expands upon the Beneficiary class and
    requires additional Commercial specific attributes: metal level, and population.
    See __init__ for more detailed description of these attributes

    Attributes:
        gender (str): The gender of the Medicare beneficiary.
        metal_level (str):
        medicaid (bool): Indicates whether the beneficiary has Medicaid.
        population (str, optional): The Medicare population type (default is "CNA").
        age (int, optional): The age of the Commercial beneficiary.
        dob (str, optional): The date of birth of the Commercial beneficiary in ISO format.
        disabled (bool): Indicates if the beneficiary is disabled.
        orig_disabled (bool): Indiciates if the beneficiary was originally disabled.
        risk_model_age (int): Age of the benficiary used in the model scoring calculations.
                              Per HHS, it is age of the beneficiary as of the last day of
                              the enrollment period of that beneficiary.
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
        metal_level: str = "Bronze",
        enrollment_months: int = 12,
        csr_indicator: int = 1,
        age: Union[None, int] = None,
        dob: Union[None, str] = None,
        model_year: Union[None, int] = None,
        last_enrollement_date: Union[None, str] = None,
    ):
        """
        Initialize a CommercialBeneficiary object.

        Args:
            gender (str): The gender of the Medicare beneficiary.
            orec (str): The original reason entitlement code. See the below link for more information:
                        https://resdac.org/cms-data/variables/medicare-original-reason-entitlement-code-orec
            medicaid (bool): A boolean indicating whether the beneficiary has Medicaid.
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
        """
        super().__init__(gender, age, dob)
        self.metal_level = metal_level
        self.enrollment_months = enrollment_months
        self.csr_indicator = csr_indicator
        self.model_year = model_year
        self.last_enrollment_date = last_enrollement_date
        self.risk_model_age = self._determine_age(self.age, self.dob)
        self.risk_model_age_group = self._determine_age_group(self.risk_model_age)
        self.risk_model_population = self.metal_level

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
            age (int): The age of the beneficiary.
            dob (str): The date of birth of the beneficiary in ISO format.

        Returns:
            int: The age of the beneficiary as of February 1st of the payment year.

        If age is provided, it is assumed to be correct as of February 1st of the payment year.
        If DOB is provided, it computes the age relative to February 1st of the payment year.
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

    def _determine_age_group(self, age: int):
        age_group = None

        if age < 2:
            age_group = "Infant"
        elif 2 <= age < 21:
            age_group = "Child"
        else:
            age_group = "Adult"

        return age_group

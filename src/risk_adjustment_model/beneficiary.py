import datetime


class Beneficiary:
    def __init__(self, gender: str, age=None, dob=None):
        self.gender = gender
        self.age = age
        self.dob = dob


class MedicareBeneficiary(Beneficiary):
    def __init__(
        self,
        gender: str,
        orec: str,
        medicaid: bool,
        population="CNA",
        age=None,
        dob=None,
    ):
        super().__init__(gender, age, dob)
        self.orec = orec
        self.medicaid = medicaid
        self.population = population
        self.risk_model_age = self._determine_age(self.age, self.dob)
        self.disabled, self.orig_disabled = self._determine_disabled(
            self.age, self.orec
        )
        if self.population == "NE":  # Tim why just NE? what does NE mean?
            self.risk_model_population = self._get_new_enrollee_population(
                self.risk_model_age, self.orec, self.medicaid
            )
        else:
            # CNA, CND, CFA, CFD, CPA, CPD
            self.risk_model_population = population

    def _determine_age(self, age: int, dob: str) -> int:
        """
        This code is meant to address two design considerations:
        1.  Date of birth (DOB) is PHI, thus the code allows for either age or DOB to create flexibility
            around the handling of PHI.
        2.  The CMS Risk Adjustment Model uses age as of February 1st of the payment year. Thus if DOB
            is passed in, age needs to be computed relative to that date.

        It checks that one of DOB or age is passed in, then determines age if DOB is given. If age is given
        it returns that age and assumes that is the correct age as of February 1st of the payment year.

        """
        if dob is None and age is None:
            raise ValueError("Need a DOB or an Age passed in")
        elif dob:
            reference_date = datetime.fromisoformat(f"{self.model_year}-02-01")
            age = (
                reference_date.year
                - dob.year
                - ((reference_date.month, reference_date.day) < (dob.month, dob.day))
            )
        elif age:
            age = age

        return age

    def _determine_disabled(self, age, orec):
        """
        Determine disability status and original disability status based on age and original entitlement reason code.

        Args:
            age (int): The age of the individual.
            orec (str): The original reason for entitlement category.

        Returns:
            tuple: A tuple containing two elements:
                - A flag indicating if the individual is disabled (1 if disabled, 0 otherwise).
                - A flag indicating the original disability status (1 if originally disabled, 0 otherwise).

        Notes:
            This function determines the disability status of an individual based on their age and original entitlement
            reason code (orec). If the individual is under 65 years old and orec is not '0', they are considered disabled.
            Additionally, if orec is '1' or '3' and the individual is not disabled, they are marked as originally disabled.

            Original disability status is determined based on whether the individual was initially considered disabled,
            regardless of their current status.
        """
        if age < 65 and orec != "0":
            disabled = True
        else:
            disabled = False

        # Should it be this: orig_disabled = (orec == '1') * (disabled == 0)
        if orec in ("1", "3") and disabled == 0:
            orig_disabled = True
        else:
            orig_disabled = False

        return disabled, orig_disabled

    def _get_new_enrollee_population(self, age, orec, medicaid):
        """
        Depending on the model, new enrollee population may be identified
        differently. This default is the CMS Community Model

        NE_ORIGDS       = (AGEF>=65)*(OREC='1');
        NMCAID_NORIGDIS = (NEMCAID <=0 and NE_ORIGDS <=0);
        MCAID_NORIGDIS  = (NEMCAID > 0 and NE_ORIGDS <=0);
        NMCAID_ORIGDIS  = (NEMCAID <=0 and NE_ORIGDS > 0);
        MCAID_ORIGDIS   = (NEMCAID > 0 and NE_ORIGDS > 0);
        """
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

        return ne_population

import pandas as pd
import logging
from datetime import datetime

from pathlib import Path
# from risk_adjustment_scoring.src.config import Config

log = logging.getLogger(__name__)

class Beneficiary:
    """
    This encapsulates key attributes of a Person needed for risk scoring:
    Age
    Gender
    OREC
    ID
    """

    def __init__(self, id, gender, orec, medicaid, diagnosis_codes=[], age=None, dob=None, **kwargs):
        # To do: add method to maintain mapping of internal id to input id
        self.id = id
        self.gender = gender
        self.orec = orec
        self.age = self._determine_age(age, dob)
        self.medicaid = medicaid
        # Add in information about the below, should consider if I want all optional
        # OR consider if I want two classes, Person and PersonAttributes or something like that
        # self.first_name
        # self.last_name
        # self.dob
        # self.middle_name
        # self.middle_initial
        # self.email
        # self.address1
        # self.address2
        # self.city
        # self.state
        # self.zip
        # self.mbi
        # PF: DO I WANT THIS HERE
        self.diagnosis_codes = diagnosis_codes
        
    
    def _determine_age(self, person_age, person_dob):
        # Since the Medicare model uses Age as of February first want the ability to take in DOB and determine age as of February first
        if person_dob == None and person_age == None:
            raise ValueError('Need a DOB or an Age passed in')
        elif person_dob:      
            person_dob = datetime.strptime(person_dob, "%Y-%m-%d")
            reference_date = datetime.strptime(reference_date, "%Y-%m-%d")

            # Calculate the age
            age = reference_date.year - person_dob.year - ((reference_date.month, reference_date.day) < (person_dob.month, person_dob.day))
        elif person_age:
            age = person_age

        return age
   
    

import datetime
#PF: Is dob a string or datetime being passed in?
def determine_age(age: int, dob: str) -> int:
    # Since the Medicare model uses Age as of February first want the ability to take in DOB and determine age as of February first
    if dob == None and age == None:
            raise ValueError('Need a DOB or an Age passed in')
    elif dob:      
        dob = datetime.strptime(dob, "%Y-%m-%d")
        # PF: What is reference date??
        reference_date = datetime.strptime(reference_date, "%Y-%m-%d")

        # Calculate the age
        age = reference_date.year - dob.year - ((reference_date.month, reference_date.day) < (dob.month, dob.day))
    elif age:
        age = age

    return age
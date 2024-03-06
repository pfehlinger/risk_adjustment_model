import datetime
#PF: Is dob a string or datetime being passed in?
def determine_age(age: int, dob: str) -> int:
    # Since the Medicare model uses Age as of February first want the ability to take in DOB and determine age as of February first
    if dob == None and age == None:
            raise ValueError('Need a DOB or an Age passed in')
    elif dob:      
        # PF: What is reference date??
        reference_date = dob = datetime.fromisoformat(dob) # tim try using fromisoformat

        # Calculate the age
        age = reference_date.year - dob.year - ((reference_date.month, reference_date.day) < (dob.month, dob.day))
    elif age:
        age = age

    return age

def determine_age_band(age: int, age_ranges: list):
    
    range = None
    
    for age_range in age_ranges:
        age_band = age_range.split('_') 
        lower, upper = 0, 999
        if len(age_band) == 1:
            lower = int(age_band[0])
            upper = lower + 1
        elif age_band[1] == 'GT':
            lower = int(age_band[0])
        else: 
            lower = int(age_band[0])
            upper = int(age_band[1]) + 1
        if lower <= age < upper:
            range = age_range
            break
    
    return range
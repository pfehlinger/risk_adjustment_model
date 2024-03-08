import datetime
#PF: Is dob a string or datetime being passed in?


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
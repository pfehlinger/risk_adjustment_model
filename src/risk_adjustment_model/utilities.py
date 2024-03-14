import importlib


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


def nvl(value, default):
    if value is not None:
        return value
    else:
        return default
    
def import_function(module_name, function_name):
    module = importlib.import_module(module_name, package='src.risk_adjustment_model')
    func = getattr(module, function_name)
    return func
from typing import List


def determine_age_band(age: int, age_ranges: List[str]):
    """
    Determine the age band of a given age based on a list of age ranges.

    Args:
        age (int): The age to determine the age band for.
        age_ranges (list): A list of age ranges represented as strings in the format
                           "lower_upper" or "lower_GT" where "lower" is the lower
                           bound of the age range, "upper" is the upper bound (exclusive)
                           if provided, and "GT" signifies greater than.

    Returns:
        str: The age band that the given age falls into. Returns None if no matching
             age band is found in the provided age ranges.

    Example:
        >>> determine_age_band(25, ['18_24', '25_34', '35_GT'])
        '25_34'
    """
    range = None

    for age_range in age_ranges:
        age_band = age_range.split("_")
        lower, upper = 0, 999
        if len(age_band) == 1:
            lower = int(age_band[0])
            upper = lower + 1
        elif age_band[1] == "GT":
            lower = int(age_band[0])
        else:
            lower = int(age_band[0])
            upper = int(age_band[1]) + 1
        if lower <= age < upper:
            range = age_range
            break

    return range

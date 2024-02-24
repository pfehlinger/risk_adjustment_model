import pandas as pd
import logging
import os
import yaml

from pathlib import Path
from src.config import Config

log = logging.getLogger(__name__)

def age_sex_edits(gender, age, dx_code, category):
        category = _age_sex_edit_1(gender, age, dx_code)
        category = _age_sex_edit_2(gender, age, dx_code)
        category = _age_sex_edit_3(gender, age, dx_code)

        return category

def _age_sex_edit_1(gender, age, dx_code):
    if gender == 'F' and dx_code in ['D66', 'D67']:
        return '48'


def _age_sex_edit_2(gender, age, dx_code):
    if age < 18 and dx_code in ['J410', 'J411', 'J418',
                            'J42', 'J430', 'J431', 'J432',
                            'J438', 'J439', 'J440',
                            'J441', 'J449', 'J982', 'J983']:
        return '112'


def _age_sex_edit_3(gender, age, dx_code):
    if (age < 6 or age > 18) and dx_code=='F3481':
        return 'NA'
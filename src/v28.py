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
        return '112'


def _age_sex_edit_2(gender, age, dx_code):
    if age < 18 and dx_code in ['J410', 'J411', 'J418',
                            'J42', 'J430', 'J431', 'J432',
                            'J438', 'J439', 'J440',
                            'J441', 'J449', 'J982', 'J983']:
        return 'NA'


def _age_sex_edit_3(gender, age, dx_code):
    if age < 50 and dx_code in [
            'C50011', 'C50012', 'C50019', 'C50021',
            'C50022', 'C50029', 'C50111', 'C50112',
            'C50119', 'C50121', 'C50122', 'C50129',
            'C50211', 'C50212', 'C50219', 'C50221',
            'C50222', 'C50229', 'C50311', 'C50312',
            'C50319', 'C50321', 'C50322', 'C50329',
            'C50411', 'C50412', 'C50419', 'C50421',
            'C50422', 'C50429', 'C50511', 'C50512',
            'C50519', 'C50521', 'C50522', 'C50529',
            'C50611', 'C50612', 'C50619', 'C50621',
            'C50622', 'C50629', 'C50811', 'C50812',
            'C50819', 'C50821', 'C50822', 'C50829',
            'C50911', 'C50912', 'C50919', 'C50921',
            'C50922', 'C50929'
    ]:
        return '22'
    
def _age_sex_edit_4(gender, age, dx_code):
    if age >= 2 and dx_code in [
            'P040',  'P041',  'P0411', 'P0412', 
            'P0413', 'P0414', 'P0415', 'P0416', 
            'P0417', 'P0418', 'P0419', 'P041A', 
            'P042',  'P043',  'P0440', 'P0441', 
            'P0442', 'P0449', 'P045',  'P046',  
            'P048',  'P0481', 'P0489', 'P049',  
            'P270',  'P271',  'P278',  'P279',  
            'P930',  'P938',  'P961',  'P962'
    ]:
        return 'NA'

import pandas as pd
import logging
import os
import yaml
import pandas as pd

from pathlib import Path
from src.config import Config
from src.v24 import age_sex_edits_v24, get_disease_interactions_v24, CMS_VARIABLES_V24
from src.v28 import age_sex_edits_v28, get_disease_interactions_v28, CMS_VARIABLES_V28
from src.beneficiary import Beneficiary
from src.utilities import determine_age
from typing import Union, Optional

log = logging.getLogger(__name__)

class MedicareModel:
    """
    General idea is that 

    Logging file added
    Set up local paths to import files
    Write out vision for how to set up a new model (this then would help me structure codebase)
    Make a test dataset
    Work on test infrastructure
    Work on having this be a docker installed componet
    Figure out flask architecture

    How this class works:
    1. Instantiate the class with set up information: model version, year optional if same model version has multiple years and differences
    between years. If year is null, going to pull the most recent
    2. Instantiating the class loads all reference information into memory and it is ready to go.
    3. Call the score method, taking in one or more beneficiary objects, returns a dictionary of results for each beneficiary object passed in
       DO I WANT TO HAAVE THAT STORED AS AN OBJECT OF THE BENEFICIARY CLASS
    4. Since each model may have its own nuances, want to put each model in its own class that then handles certain category stuff
    """

    def __init__(self, version, year=None):
        # PF TO DO: Change the whole name thing here
        self.name = self.__class__.__name__
        self.version = version
        self.year = year
        # This should use the config directory or might not be necessary to exist
        self.directory = Path(r'C:\Users\Philissa\Documents\development\risk_adjustment_model\src')
        self.model_year = self._get_model_year()
        self.data_directory = self._get_data_directory()
        self.hierarchy_definitions = self._get_hierarchy_definitions()
        self.category_definitions = self._get_category_definitions()
        self.diag_to_category_map = self._get_diagnosis_code_to_category_mapping()
        self.category_weights = self._get_category_weights()
        self.coding_intesity_adjuster = self._get_coding_intensity_adjuster()
        self.normalization_factor = self._get_normalization_factor()
    
    def score(self, gender: str, orec: str, medicaid: bool, diagnosis_codes=[], age=None, dob=None, verbose=False) -> dict:
        """
        Determines the risk score for the inputs.

        One or both of age and dob needs to be passed in. CMS uses age as of February first for model purposes, as such if DOB is passed in
        the code will determine age as of February first. If age alone is passed in, it uses that for the age.

        Args:
            gender (str): Gender of the beneficiary being scored, valid values M or F.
            orec (str): Original Entitlement Reason Code of the beneficiary. See: https://bluebutton.cms.gov/assets/ig/ValueSet-orec.html for valid values
            medicaid (bool): Beneficiary medicaid status, True or False
            diagnosis_codes (list): List of the diagnosis codes associated with the beneficiary
            age (int): Age of the beneficiary, can be None.
            dob (str): Date of birth of the beneficiary, can be None
            verbose (bool): Indicates if trimmed output or full output is desired

        Returns:
            dict: A dictionary containing the score information. If verbose is False the output looks like
            'cn_aged': {
                'score_raw': 123,
                'score': 123,
                'category_details': {
                    'HCC1': {'weight': .5, 'diagnosis_codes': ['123', '456']},
                    'HCC2': {'weight': .5, 'diagnosis_codes': ['123', '456']},
                },
                'category_list': ['HCC1', 'HCC2'],
            },
            'cn_disabled': {
                ...
            } ,  
            'inputs': {
                'age': 65,
                'sex': 'F',
                'medicaid': False,
                'disabled': 0,
                'origds': 0
            },
            'model_version': 'v24',
            'coding_intensity_adjuster': .123,
            'normalization_factor': .123

            If verbose is True, the output looks like:
            'beneficiary_score_profile': {
                'CN_Aged': {
                    'categories': {
                        'HCC10': {
                            'weight': 0.6,
                            'type': 'disease',
                            'category_number': 10,
                            'category_description': 'Lymphoma and Other Cancers',
                            'dropped_categories': None,
                            'diagnosis_map': ['C8175', 'C8286', 'C9590']
                        },
                        'HCC55': {
                            'weight': 0.6,
                            'type': 'disease',
                            'category_number': 55,
                            'category_description': 'Substance Use Disorder, Moderate/Severe, or Substance Use with Complications',
                            'dropped_categories': None,
                            'diagnosis_map': ['F1114', 'F13988']
                        },
                        'HCC72': {
                            'weight': 0.6,
                            'type': 'disease',
                            'category_number': 72,
                            'category_description': 'Spinal Cord Disorders/Injuries',
                            'dropped_categories': None,
                            'diagnosis_map': ['S14157S']
                        },
                        'F65_69': {
                            'weight': 0.6,
                            'type': 'demographic',
                            'category_number': None,
                            'category_description': 'Female, 65 to 69 Years Old'
                        }
                    },
                'score': 10.799999999999997,
                'disease_score': 10.199999999999998,
                'demographic_score': 0.6
                },
                'CN_Disabled': {
                    ...
                },
            inputs: {
                'age': 65,
                'sex': 'F',
                'medicaid': False,
                'disabled': 0,
                'origds': 0,
                'diagnosis_codes: [123, 456]
            },
            'risk_model_age': 66,
            'model_version': 'v24',
            'year': 2024,
            'coding_intensity_adjuster': .123,
            'normalization_factor': .123,
        """

        risk_model_age = determine_age(age, dob)

        output_dict = {
            'inputs':  {
                'gender': gender,
                'orec': orec,
                'medicaid': medicaid,
                'age': age,
                'dob': dob,
                'diagnosis_codes': diagnosis_codes,
                'year': self.year,
            },
            'risk_model_age': risk_model_age,
            'model_version': self.version,
            'model_year': self.model_year,
            'coding_intensity_adjuster': self.coding_intesity_adjuster,
            'normalization_factor': self.normalization_factor
        }

        categories_dict, category_list = self.get_categories(risk_model_age, gender, orec, medicaid, diagnosis_codes)
        beneficiary_score_profile = {}
        
        for population in ['CN_Aged', 'CN_Disabled', 'CP_Aged', 'CP_Disabled', 'CF_Aged', 'CF_Disabled']:
            combine_dict = {}
            score_dict = self.get_weights(category_list, population)
            # now combine the dictionaries to make output
            for key, value in score_dict['categories'].items():
                
                if categories_dict.get(key):
                    value.update(categories_dict.get(key))
                    combine_dict[key] = value
                else:
                    combine_dict[key] = value
            score_dict['category_details'] = combine_dict
            score_dict['category_list'] = category_list
            
            beneficiary_score_profile[population] = score_dict
        
        if not verbose:
            self._trim_output(beneficiary_score_profile)
            
        output_dict['beneficiary_score_profile'] = beneficiary_score_profile

        return output_dict

    def _get_model_year(self):
        if not self.year:
            dirs = os.listdir(self.directory / 'reference_data' / 'medicare' / self.version)
            years = [int(dir) for dir in dirs]
            max_year = max(years)
        else:
            max_year = self.year
        return max_year
    
    def _get_data_directory(self) -> Path:

        data_directory = self.directory / 'reference_data' / 'medicare' / self.version / str(self.model_year)
        return data_directory
        
    def _get_hierarchy_definitions(self) -> dict:
        with open(self.data_directory / 'hierarchy_definition.yaml') as file:
            hierarchy_definitions = yaml.safe_load(file)
        return hierarchy_definitions
    
    def _get_category_definitions(self) -> dict:
      
        with open(self.data_directory / 'category_definition.yaml') as file:
            category_definitions = yaml.safe_load(file)
        return category_definitions
    
    def _get_diagnosis_code_to_category_mapping(self) -> pd.DataFrame:

        diag_to_category_map = (
            pd.read_csv(self.data_directory / 'diag_to_category_map.txt', sep='|', header=None)
            .rename({0: 'dx_code_no_decimal', 1: 'category_nbr', 2: 'unknown'}, axis=1)
        )
        
        return diag_to_category_map        
    
    def _get_category_weights(self) -> pd.DataFrame:
      
        weights = pd.read_csv(self.data_directory / 'weights.csv')
        return weights
    
    def _get_coding_intensity_adjuster(self):
        coding_intensity_adjuster = 1
        if self.version == 'v24':
            coding_intensity_adjuster = 1 - CMS_VARIABLES_V24['coding_intensity_adjuster']
        elif self.version == 'v28':
            coding_intensity_adjuster = 1 - CMS_VARIABLES_V28['coding_intensity_adjuster']
        
        return coding_intensity_adjuster
    
    def _get_normalization_factor(self):
        normalization_factor = 1
        if self.version == 'v24':
            normalization_factor = CMS_VARIABLES_V24['normalization_factor']
        elif self.version == 'v28':
            normalization_factor = CMS_VARIABLES_V28['normalization_factor']

        return normalization_factor

    def get_categories(self, age: int, gender: str, orec: str, medicaid: bool, diagnosis_codes: Union[str, list]):

        demo_categories = self.get_demographic_cats(self.version, age, gender, orec, medicaid)
        if diagnosis_codes:
            categories_dict = self.get_disease_categories(gender, age, diagnosis_codes)
        else:
            categories_dict = {}

        category_list = [key for key in categories_dict]
        category_list.extend(demo_categories)

        return categories_dict, category_list

    def get_demographic_cats(self, version, age, gender, orec, medicaid):
        """Need to do the static typing stuff above for gender, age, orec"""
        # disabled, originally disabled variables
        # Need to look into this more if it is right
        # DO I NEED TO DO SOMETHING WITH VERSION
        demo_cats = []
        disabled, orig_disabled = self._determine_disabled(age, orec)
        demo_cats.append(self._get_demographic_cats(age, gender))
        demo_int = self._get_demographic_interactions(gender, orig_disabled)
        if demo_int:
            demo_cats.append(demo_int)
        
        
        # how to handle new enrollee flag
        # demo_cats.append(

        # There are four buckets for NE for the 
        # Non-Medicaid & Non-OriginallyDisabled
        # Medicaid & Non-Originally Disabled
        # Non-Medicaid & Originally Disabled
        # Medicaid & Originally Disabled

        # print(disabled)
        # print(orec)

        # demo_cats.append(_get_demographic_cats)
        # _get_new_enrollee_demographic_cats
        # _get_demographic_interactions

        return demo_cats

    def _determine_disabled(self, age, orec):

        if age < 65 and orec != '0':
            disabled = 1
        else:
            disabled = 0

        # Should it be this: orig_disabled = (orec == '1') * (disabled == 0)
        if orec in ('1', '3') and disabled == 0:
            orig_disabled = 1
        else:
            orig_disabled = 0

        # Don't know if I want the elig part here
        # https://github.com/yubin-park/hccpy/blob/master/hccpy/_AGESEXV2.py
        
        return disabled, orig_disabled

    def _get_demographic_cats(self, age, gender):
        """need assertions of inuts to ensure valid"""
        female_demo_categories = [
            'F0_34', 'F35_44', 'F45_54', 'F55_59', 'F60_64',
            'F65_69', 'F70_74', 'F75_79', 'F80_84', 'F85_89', 
            'F90_94', 'F95_GT'
        ]
        male_demo_categories = [
            'M0_34', 'M35_44', 'M45_54', 'M55_59', 'M60_64',
            'M65_69', 'M70_74', 'M75_79', 'M80_84', 'M85_89', 
            'M90_94', 'M95_GT'
        ]
        if gender == 'F':
            if 0 <= age <= 34:
                demographic_category = female_demo_categories[0]
            elif 35 <= age <= 44:
                demographic_category = female_demo_categories[1]
            elif 45 <= age <= 54:
                demographic_category = female_demo_categories[2]
            elif 55 <= age <= 59:
                demographic_category = female_demo_categories[3]
            elif 60 <= age <= 64:
                demographic_category = female_demo_categories[4]
            elif 65 <= age <= 69:
                demographic_category = female_demo_categories[5]
            elif 70 <= age <= 74:
                demographic_category = female_demo_categories[6]
            elif 75 <= age <= 79:
                demographic_category = female_demo_categories[7]
            elif 80 <= age <= 84:
                demographic_category = female_demo_categories[8]
            elif 85 <= age <= 89:
                demographic_category = female_demo_categories[9]
            elif 90 <= age <= 94:
                demographic_category = female_demo_categories[10]
            elif 95 <= age:
                demographic_category = female_demo_categories[11]
        else:
            if 0 <= age <= 34:
                demographic_category = male_demo_categories[0]
            elif 35 <= age <= 44:
                demographic_category = male_demo_categories[1]
            elif 45 <= age <= 54:
                demographic_category = male_demo_categories[2]
            elif 55 <= age <= 59:
                demographic_category = male_demo_categories[3]
            elif 60 <= age <= 64:
                demographic_category = male_demo_categories[4]
            elif 65 <= age <= 69:
                demographic_category = male_demo_categories[5]
            elif 70 <= age <= 74:
                demographic_category = male_demo_categories[6]
            elif 75 <= age <= 79:
                demographic_category = male_demo_categories[7]
            elif 80 <= age <= 84:
                demographic_category = male_demo_categories[8]
            elif 85 <= age <= 89:
                demographic_category = male_demo_categories[9]
            elif 90 <= age <= 94:
                demographic_category = male_demo_categories[10]
            elif 95 <= age:
                demographic_category = male_demo_categories[11]

        return demographic_category

    def _get_new_enrollee_demographic_cats(self, age, gender, orec):
        """better documentation and stuff"""
        female_demo_categories = [
            'NEF0_34', 'NEF35_44', 'NEF45_54', 'NEF55_59', 'NEF60_64',
            'NEF65', 'NEF66', 'NEF67', 'NEF68', 'NEF69', 'NEF70_74', 
            'NEF75_79', 'NEF80_84', 'NEF85_89', 'NEF90_94', 'NEF95_GT'
        ]
        male_demo_categories = [
            'NEM0_34', 'NEM35_44', 'NEM45_54', 'NEM55_59', 'NEM60_64',
            'NEM65', 'NEM66', 'NEM67', 'NEM68', 'NEM69', 'NEM70_74', 
            'NEM75_79', 'NEM80_84', 'NEM85_89', 'NEM90_94', 'NEM95_GT'
        ]
        if gender == 'F':
            if 0 <= age <= 34:
                demographic_category = female_demo_categories[0]
            elif 35 <= age <= 44:
                demographic_category = female_demo_categories[1]
            elif 45 <= age <= 54:
                demographic_category = female_demo_categories[2]
            elif 55 <= age <= 59:
                demographic_category = female_demo_categories[3]
            elif 60 <= age <= 63:
                demographic_category = female_demo_categories[4]
            elif age == 64 and orec != '0':
                demographic_category = female_demo_categories[4]
            elif age == 64 and orec == '0':
                demographic_category = female_demo_categories[5]
            elif age == 65:
                demographic_category = female_demo_categories[5]
            elif age == 66:
                demographic_category = female_demo_categories[6]
            elif age == 67:
                demographic_category = female_demo_categories[7]
            elif age == 68:
                demographic_category = female_demo_categories[8]
            elif age == 69:
                demographic_category = female_demo_categories[9]
            elif 70 <= age <= 74:
                demographic_category = female_demo_categories[10]
            elif 75 <= age <= 79:
                demographic_category = female_demo_categories[11]
            elif 80 <= age <= 84:
                demographic_category = female_demo_categories[12]
            elif 85 <= age <= 89:
                demographic_category = female_demo_categories[13]
            elif 90 <= age <= 94:
                demographic_category = female_demo_categories[14]
            elif 95 <= age:
                demographic_category = female_demo_categories[15]
        else:
            if 0 <= age <= 34:
                demographic_category = male_demo_categories[0]
            elif 35 <= age <= 44:
                demographic_category = male_demo_categories[1]
            elif 45 <= age <= 54:
                demographic_category = male_demo_categories[2]
            elif 55 <= age <= 59:
                demographic_category = male_demo_categories[3]
            elif 60 <= age <= 63:
                demographic_category = male_demo_categories[4]
            elif age == 64 and orec != '0':
                demographic_category = male_demo_categories[4]
            elif age == 64 and orec == '0':
                demographic_category = male_demo_categories[5]
            elif age == 65:
                demographic_category = male_demo_categories[5]
            elif age == 66:
                demographic_category = male_demo_categories[6]
            elif age == 67:
                demographic_category = male_demo_categories[7]
            elif age == 68:
                demographic_category = male_demo_categories[8]
            elif age == 69:
                demographic_category = male_demo_categories[9]
            elif 70 <= age <= 74:
                demographic_category = male_demo_categories[10]
            elif 75 <= age <= 79:
                demographic_category = male_demo_categories[11]
            elif 80 <= age <= 84:
                demographic_category = male_demo_categories[12]
            elif 85 <= age <= 89:
                demographic_category = male_demo_categories[13]
            elif 90 <= age <= 94:
                demographic_category = male_demo_categories[14]
            elif 95 <= age:
                demographic_category = male_demo_categories[15]

        return demographic_category

    def _get_demographic_interactions(self, gender, orig_disabled):

        demo_interaction = None
        if gender == 'F' and orig_disabled == 1:
            demo_interaction = 'OriginallyDisabled_Female'
        elif gender == 'M' and orig_disabled == 1:
            demo_interaction = 'OriginallyDisabled_Male'

        return demo_interaction

    def _get_new_enrollee_demographic_interactions(self, age, orec, medicaid):
        """
        NE_ORIGDS       = (AGEF>=65)*(OREC='1');
        NMCAID_NORIGDIS = (NEMCAID <=0 and NE_ORIGDS <=0);
        MCAID_NORIGDIS  = (NEMCAID > 0 and NE_ORIGDS <=0);
        NMCAID_ORIGDIS  = (NEMCAID <=0 and NE_ORIGDS > 0);
        MCAID_ORIGDIS   = (NEMCAID > 0 and NE_ORIGDS > 0);
        """
        
        if age >= 65 and orec == '1':
            # NE_ORIGDS
            ne_originally_disabled = True
        else:
            ne_originally_disabled = False

        if not ne_originally_disabled and not medicaid:
            # Non medicaid non originally disabled
            ne_demo_int = 'NMCAID_NORIGDIS'

        if not ne_originally_disabled and medicaid:
            ne_demo_int = 'MCAID_NORIGDIS'

        if ne_originally_disabled and not medicaid:
            ne_demo_int = 'NMCAID_ORIGDIS'

        if ne_originally_disabled and medicaid:
            ne_demo_int = 'MCAID_ORIGDIS'

        return ne_demo_int


    def get_disease_categories(self, gender, age, diagnosis_codes) -> dict:
        # This needs to return a dictionary and contain diagnosis that triggered it
        # Don't want to be passing in dictionaires so instead need to maintain one and pass
        # in lists
        # Or refactor so each method returns both a dictionary and a list
        # Need age sex edits too
        final_cat_dict = {}
        category_dict = self._get_disease_categories(gender, age, diagnosis_codes)
        categories = [key for key in category_dict]
        hier_category_dict = self._apply_hierarchies(categories)
        categories = [key for key in hier_category_dict]
        category_count = self._get_payment_count_categories(categories)
        if category_count:
            categories.append(category_count)
        interactions_dict = self._get_disease_interactions(self.version, categories)
        interactions = [key for key in interactions_dict]
        if interactions:
            categories.extend(interactions)


        for category in categories:
            final_cat_dict[category] = {
                'dropped_categories': hier_category_dict.get(category, None),
                'diagnosis_map': category_dict.get(category, None),
            }
        
        # This needs to be a dict of category, dropped cateogries, diagnosis map
        return final_cat_dict
                                   

    def _get_disease_categories(self, gender, age, diagnosis_codes):

        if isinstance(diagnosis_codes, list):
            dx_categories = self.diag_to_category_map[self.diag_to_category_map['dx_code_no_decimal'].isin(diagnosis_codes)]
        else:
            dx_categories = self.diag_to_category_map[self.diag_to_category_map['dx_code_no_decimal'].isin([diagnosis_codes])]

        # dx_categories['category_nbr'] = dx_categories.apply(lambda x: age_sex_edits(gender, age, x['dx_code_no_decimal'], x['category_nbr']), axis=1)

        cat_dict = {}
        unique_cats = dx_categories['category_nbr'].unique().tolist()
        for cat in unique_cats:
            dx_codes = dx_categories[dx_categories['category_nbr']==cat]['dx_code_no_decimal'].unique().tolist()
            cat_dict['HCC'+str(cat)] = dx_codes
        
        return cat_dict

    def _apply_hierarchies(self, categories: list):
        # Don't know if I want this, copying the list
        # PF: This is wrong, see v28 HCC21, HCC22, HCC23
        category_list = categories[:]
        categories_dict = {}
        dropped_codes_total = []
        
        for category in category_list:
            dropped_codes = []
            if category in self.hierarchy_definitions['category'].keys():
                for remove_category in self.hierarchy_definitions['category'][category]['remove_code']:
                    try:
                        category_list.remove(remove_category)
                    except ValueError:
                        pass
                    else:
                        dropped_codes.append(remove_category)
                        dropped_codes_total.append(remove_category)
                if not dropped_codes:
                    categories_dict[category] = None
                else:
                    categories_dict[category] = dropped_codes
        
        # Fill in remaining categories
        for category in category_list:
            if category not in dropped_codes_total:
                categories_dict[category] = None

        return categories_dict

    def _get_payment_count_categories(self, categories: list):
        category_count = len(categories)
        category = None
        if category_count > 9:
            category = 'D10P'
        elif category_count > 0:
            category = f'D{category_count}'

        return category

    def _get_disease_interactions(self, version: str, categories: list) -> list:
        """Need to make this do something with version"""
        interaction_list = []
        if version == 'v24':
            interaction_list = get_disease_interactions_v24(categories)
        elif version == 'v28':
            interaction_list = get_disease_interactions_v28(categories)

        return interaction_list                                             

    def get_weights(self, categories: list, population: str):
        # This should be done once for each subpopulation, so a loop
        # get the score, disease score, demographic score, hcc information
        weights_new = self.category_weights.set_index('category')
        # all here
        category_dict = {}
        cat_output = {}
        # score = decimal.Decimal('0')
        # disease_score = decimal.Decimal('0')
        # counter = decimal.Decimal('0')
        # demographic_score = decimal.Decimal('0')
        score = 0
        disease_score = 0
        demographic_score = 0
        for cat in categories:
            for key, value in self.category_definitions['category'].items():
                if cat == key:
                    # weight = decimal.Decimal(weights_new['cn_aged'].loc[key])
                    weight = weights_new[population.lower()].loc[key]
                    score += weight
                        
                    if value['type'] == 'disease' or value['type'] == 'disease_interaction':
                        disease_score += weight
                    if value['type'] == 'demographic':
                        demographic_score += weight
                    # PF: Do I want category_number not to exist for demo cats? Or should it be NA?
                    # Do I want get_weights to make this dictionary? Probably not.
                    category_dict[key] = {
                        'weight': weight,
                        # have this come from category_yaml
                        'type': value['type'],
                        'category_number': value.get('number', None),
                        'category_description': value['descr'],
                    }
        cat_output['categories'] = category_dict
        cat_output['score_raw'] = score
        cat_output['disease_score_raw'] = disease_score
        cat_output['demographic_score_raw'] = demographic_score

        # Now apply coding intensity and normalization to scores
        cat_output['score'] = self._apply_norm_factor_coding_adj(score)
        cat_output['disease_score'] = self._apply_norm_factor_coding_adj(disease_score)
        cat_output['demographic_score'] = self._apply_norm_factor_coding_adj(demographic_score)
       
        return cat_output

    def _apply_norm_factor_coding_adj(self, score: float) -> float:
        return round(
            round(
                score * self.coding_intesity_adjuster, 4
            )
            / self.normalization_factor, 4
        )

    def _trim_output(self, score_dict: dict) -> dict:
        """Takes in the verbose output and trims to the smaller output"""
        for key, value in score_dict.items():
            for key_2, value_2 in value.items():
                if key_2 == 'categories':
                    for category, info in value_2.items():
                        del info['type']
                        del info['category_number']
                        del info['category_description']
                        try: 
                            del info['dropped_categories']
                        except KeyError:
                            pass
                else:
                    pass

    def validate_inputs(self):
        pass





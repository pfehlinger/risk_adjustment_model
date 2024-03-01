import logging
import os
import yaml
import importlib.resources

from pathlib import Path
from src.v24 import age_sex_edits_v24, get_disease_interactions_v24, CMS_VARIABLES_V24
from src.v28 import age_sex_edits_v28, get_disease_interactions_v28, CMS_VARIABLES_V28
from src.utilities import determine_age
from typing import Union, Optional


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

    def __init__(self, version: str, year=None):
        self.version = version
        self.year = year
        self.model_year = self._get_model_year()
        self.data_directory = self._get_data_directory()
        self.hierarchy_definitions = self._get_hierarchy_definitions()
        self.category_definitions = self._get_category_definitions()
        self.diag_to_category_map = self._get_diagnosis_code_to_category_mapping()
        self.category_weights = self._get_category_weights()
        self.coding_intesity_adjuster = self._get_coding_intensity_adjuster()
        self.normalization_factor = self._get_normalization_factor()

    # --- RA Model methods ---

    def score(self, gender: str, orec: str, medicaid: bool, diagnosis_codes=[], age=None, dob=None,
              population='CNA', verbose=False) -> dict:
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
            population (str): Population of beneficiary being scored, valid values are CNA, CND, CPA, CPD, CFA, CFD, INS, NE
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
        #PF: Add validation that one of age or DOB is provided

        risk_model_age = determine_age(age, dob)

        if population == 'NE':
            risk_model_population = self._get_new_enrollee_population(risk_model_age, orec, medicaid)
        else:
            risk_model_population = population

        output_dict = {
            'inputs':  {
                'gender': gender,
                'orec': orec,
                'medicaid': medicaid,
                'age': age,
                'dob': dob,
                'diagnosis_codes': diagnosis_codes,
                'year': self.year,
                'population': population
            },
            'risk_model_age': risk_model_age,
            'risk_model_population': risk_model_population,
            'model_version': self.version,
            'model_year': self.model_year,
            'coding_intensity_adjuster': self.coding_intesity_adjuster,
            'normalization_factor': self.normalization_factor
        }

        categories_dict, category_list = self.get_categories(risk_model_age, gender, orec, medicaid, diagnosis_codes, risk_model_population)
        combine_dict = {}
        score_dict = self.get_weights(category_list, risk_model_population)
        # now combine the dictionaries to make output
        for key, value in score_dict['categories'].items():
            if categories_dict.get(key):
                value.update(categories_dict.get(key))
                combine_dict[key] = value
            else:
                combine_dict[key] = value

        if not verbose:
            self._trim_output(combine_dict)

        score_dict['category_details'] = combine_dict
        score_dict['category_list'] = category_list
        del score_dict['categories']
        output_dict['beneficiary_score_profile'] = score_dict

        return output_dict

    def get_categories(self, age: int, gender: str, orec: str, medicaid: bool, diagnosis_codes: Union[str, list], population: str) -> tuple[dict[str, Union[dict, list]], list]:
        """
        Get categories based on demographic information and diagnosis codes.

        Args:
            age (int): The age of the individual.
            gender (str): The gender of the individual ('Male', 'Female', etc.).
            orec (str): The original reason for entitlement category.
            medicaid (bool): A boolean indicating whether the individual is on Medicaid.
            diagnosis_codes (Union[str, list]): A single diagnosis code or a list of diagnosis codes.

        Returns:
            tuple: A tuple containing two elements:
                - A dictionary mapping categories to their respective attributes.
                - A list of category keys.

            EXAMPLE RETURN

        Notes:
            This function retrieves categories based on demographic information such as age, gender, 
            original reason for entitlement category, and Medicaid status. It also considers any 
            provided diagnosis codes to fetch additional disease-specific categories.
            
            The function first retrieves demographic categories using the get_demographic_cats() method.
            Then, if diagnosis codes are provided, it retrieves disease-specific categories using 
            the get_disease_categories() method. 
            
            Finally, it combines the demographic and disease-specific categories into a list 
            of category keys and returns both the dictionary of categories and the list of keys.
        """
        demo_categories = self.get_demographic_cats(self.version, age, gender, orec, medicaid, population)
        if diagnosis_codes:
            categories_dict = self.get_disease_categories(gender, age, diagnosis_codes)
        else:
            categories_dict = {}

        category_list = [key for key in categories_dict]
        category_list.extend(demo_categories)

        return categories_dict, category_list

    def get_demographic_cats(self, version, age, gender, orec, medicaid, population):
        """Need to do the static typing stuff above for gender, age, orec"""
        # disabled, originally disabled variables
        # Need to look into this more if it is right
        # DO I NEED TO DO SOMETHING WITH VERSION
        demo_cats = []
        disabled, orig_disabled = self._determine_disabled(age, orec)
        demo_cats.append(self._get_demographic_cats(age, gender, population))
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
    
    def get_weights(self, categories: list, population: str):
        """
        Returns:
            {'categories': {'HCC1': {'weight': 0.6,
                'type': 'disease',
                'category_number': 1,
                'category_description': 'HIV/AIDS'},
                'F65_69': {'weight': 0.6,
                'type': 'demographic',
                'category_number': None,
                'category_description': 'Female, 65 to 69 Years Old'}},
                'score_raw': 1.2,
                'disease_score_raw': 0.6,
                'demographic_score_raw': 0.6,
                'score': 0.9853,
                'disease_score': 0.4927,
                'demographic_score': 0.4927}
        """
        category_dict = {}
        cat_output = {}
        score = 0
        disease_score = 0
        demographic_score = 0
        for cat in categories:
            for key, value in self.category_definitions['category'].items():
                if cat == key:
                    weight = self.category_weights[cat][population]
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

    # --- RA Model helper methods ---

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

            Reference: https://github.com/yubin-park/hccpy/blob/master/hccpy/_AGESEXV2.py
        """
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

    def _get_demographic_cats(self, age, gender, population):
        """
        Determine the demographic category based on age and gender.

        Args:
            age (int): The age of the individual.
            gender (str): The gender of the individual ('Male', 'Female', etc.).

        Returns:
            str: The demographic category of the individual.

        Notes:
            This function determines the demographic category of an individual based on their age and gender. 
            It assigns individuals to predefined demographic categories, such as age and gender bands, 
            defined as 'F0_34', 'M35_44', etc. The categories are hard-coded within the function.
            
            The function iterates through the predefined demographic categories and checks if the provided 
            age falls within the range specified for each category. Once a matching category is found, 
            it returns that category.
        """
        # PF: Might want to refactor to use yaml/json with demographic type to get the categories
        if population[:2] == 'NE':
            demo_category_ranges = [
                '0_34', '35_44', '45_54', '55_59', '60_64',
                '65', '66', '67', '68', '69', '70_74', 
                '75_79', '80_84', '85_89', '90_94', '95_GT',
            ]
        else:
            demo_category_ranges = [
                '0_34', '35_44', '45_54', '55_59', '60_64',
                '65_69', '70_74', '75_79', '80_84', '85_89', 
                '90_94', '95_GT',
            ]
        
        for age_range in demo_category_ranges:
            age_band = age_range.replace(gender, '').split('_') 
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
                demographic_category_range = age_range
                break

        if population[:2] == 'NE':
            demographic_category = f'NE{gender}{demographic_category_range}'
        else:
            demographic_category = f'{gender}{demographic_category_range}'

        return demographic_category

    def _get_demographic_interactions(self, gender, orig_disabled):

        demo_interaction = None
        if gender == 'F' and orig_disabled == 1:
            demo_interaction = 'OriginallyDisabled_Female'
        elif gender == 'M' and orig_disabled == 1:
            demo_interaction = 'OriginallyDisabled_Male'

        return demo_interaction

    def _get_new_enrollee_population(self, age, orec, medicaid):
        """
        NE_ORIGDS       = (AGEF>=65)*(OREC='1');
        NMCAID_NORIGDIS = (NEMCAID <=0 and NE_ORIGDS <=0);
        MCAID_NORIGDIS  = (NEMCAID > 0 and NE_ORIGDS <=0);
        NMCAID_ORIGDIS  = (NEMCAID <=0 and NE_ORIGDS > 0);
        MCAID_ORIGDIS   = (NEMCAID > 0 and NE_ORIGDS > 0);
        """
        if age >= 65 and orec == '1':
            ne_originally_disabled = True
        else:
            ne_originally_disabled = False
        if not ne_originally_disabled and not medicaid:
            ne_population = 'NE_NMCAID_NORIGDIS'
        if not ne_originally_disabled and medicaid:
            ne_population = 'NE_MCAID_NORIGDIS'
        if ne_originally_disabled and not medicaid:
            ne_population = 'NE_NMCAID_ORIGDIS'
        if ne_originally_disabled and medicaid:
            ne_population = 'NE_MCAID_ORIGDIS'

        return ne_population      

    def _get_disease_categories(self, gender, age, diagnosis_codes):

        if isinstance(diagnosis_codes, list):
            dx_categories = {diag:self.diag_to_category_map[diag] for diag in diagnosis_codes if diag in self.diag_to_category_map}
        else:
            dx_categories = {diagnosis_codes:self.diag_to_category_map[diagnosis_codes]}
        # dx_categories['category_nbr'] = dx_categories.apply(lambda x: age_sex_edits(gender, age, x['dx_code_no_decimal'], x['category_nbr']), axis=1)

        cat_dict = {}
        all_cats = [value for catlist in dx_categories.values() for value in catlist]
        unique_cats = set(all_cats)
        for cat in unique_cats:
            dx_codes = [key for key, value in dx_categories.items() if cat in value]
            cat_dict[cat] = dx_codes
        
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

    # --- Helper methods ---

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
            del value['type']
            del value['category_number']
            del value['category_description']
            try: 
                del value['dropped_categories']
            except KeyError:
                pass

    # --- Setup methods ---
    
    def _get_model_year(self) -> int:
        """
        The CMS Medicare Risk Adjustment model is implemented on an annual basis, and sometimes
        even if the categories do not change, weights, diagnosis code mappings, etc. can change.
        Therefore, to account for this, a year can be passed in to specify which mappings and weights
        to use. If nothing is passed in, the code will by default use the most recent valid year.
        This is the purpose of this code.

        Returns:
            int: The model year.

        Notes:
            This function retrieves the model year based on the version provided. 
            If a specific year is not provided, it fetches the latest available year 
            from the reference data directory corresponding to the version. If a year 
            is provided, it returns that year instead.

        Raises:
            FileNotFoundError: If the specified version directory or reference data 
                            directory does not exist.

        """
        if not self.year:
            with importlib.resources.path('src.reference_data', 'medicare') as data_dir:
                dirs = os.listdir(data_dir / self.version)
                years = [int(dir) for dir in dirs]
                max_year = max(years)
        else:
            max_year = self.year
        
        return max_year
    
    def _get_data_directory(self) -> Path:
        """
        Get the directory path to the reference data for the Medicare model.

        Returns:
            Path: The directory path to the reference data.

        Notes:
            This function constructs the directory path to the reference data for the Medicare model 
            based on the specified version and model year. It utilizes importlib.resources to access 
            the resources directory containing the Medicare data. It then combines the version and 
            model year to form the appropriate directory path. 

        Raises:
            FileNotFoundError: If the specified version directory or reference data directory does not exist.
        """
        with importlib.resources.path('src.reference_data', 'medicare') as data_dir:
            data_directory = data_dir / self.version / str(self.model_year)
        
        return data_directory
        
    def _get_hierarchy_definitions(self) -> dict:
        """
        Retrieve the hierarchy definitions from a YAML file.

        Returns:
            dict: A dictionary containing the hierarchy definitions.

        Notes:
            This function reads the hierarchy definitions from a YAML file located 
            in the data directory. It loads the YAML content using PyYAML's 
            safe_load() function to convert it into a Python dictionary format.
            The hierarchy definitions typically represent the structure and 
            relationships within a hierarchical dataset.

        Raises:
            FileNotFoundError: If the hierarchy definition YAML file is not found 
                            in the specified data directory.
            yaml.YAMLError: If there is an error encountered while parsing the 
                            hierarchy definition YAML file.
        """
        with open(self.data_directory / 'hierarchy_definition.yaml') as file:
            hierarchy_definitions = yaml.safe_load(file)
        
        return hierarchy_definitions
    
    def _get_category_definitions(self) -> dict:
        """
        Retrieve category definitions from a YAML file.

        Returns:
            dict: A dictionary containing the category definitions.

        Notes:
            This function reads the category definitions from a YAML file located 
            in the data directory. It utilizes PyYAML's safe_load() function to 
            parse the YAML content into a Python dictionary format.
            Category definitions typically define various categories and their 
            attributes or properties within a dataset.

        Raises:
            FileNotFoundError: If the category definition YAML file is not found 
                            in the specified data directory.
            yaml.YAMLError: If an error occurs during the parsing of the category 
                            definition YAML file.
        """
        with open(self.data_directory / 'category_definition.yaml') as file:
            category_definitions = yaml.safe_load(file)
        
        return category_definitions
    
    def _get_diagnosis_code_to_category_mapping(self) -> dict:
        """
        Retrieve diagnosis code to category mappings from a text file.

        Returns:
            dict: A dictionary mapping diagnosis codes to categories.

        Notes:
            This function reads diagnosis code to category mappings from a text file 
            located in the data directory. Each line in the file is expected to have 
            a diagnosis code and its corresponding category separated by a delimiter. 
            It constructs a dictionary where each diagnosis code is mapped to a list 
            of categories. Categories are typically represented as strings prefixed 
            with a specific identifier, such as 'HCC'.

        Raises:
            FileNotFoundError: If the diagnosis code to category mapping text file 
                            is not found in the specified data directory.
        """
        diag_to_category_map = {}
        with open(self.data_directory / 'diag_to_category_map.txt', 'r') as file:
            for line in file:
                # Split the line based on the delimiter
                parts = line.strip().split('|')  # Change ',' to your delimiter
                diag = parts[0].strip()
                category = 'HCC' + parts[1].strip()
                if diag not in diag_to_category_map:
                    diag_to_category_map[diag] = []
                diag_to_category_map[diag].append(category)
        
        return diag_to_category_map        
    
    def _get_category_weights(self) -> dict:
        """
        Retrieve category weights from a CSV file.

        Returns:
            dict: A dictionary containing category weights.

        Notes:
            This function reads category weights from a CSV file located in the data 
            directory. The CSV file is expected to have a header row specifying column 
            names, and subsequent rows representing category weights. Each row should 
            contain values separated by a delimiter, with one column representing 
            the category and others representing different weights. The function constructs 
            a nested dictionary where each category is mapped to a dictionary of weights.

        Raises:
            FileNotFoundError: If the weights CSV file is not found in the specified 
                            data directory.
            ValueError: If there is an issue with parsing weights from the CSV file.
        """
        weights = {}
        col_map = {}
        with open(self.data_directory / 'weights.csv', 'r') as file:
            for i, line in enumerate(file):
                parts = line.strip().split(',')
                if i == 0:
                    # Validate column order OR create column map
                    for x, col in enumerate(parts):
                        col_map[col] = x
                else:
                    # Assume
                    pop_weight = {}
                    category = parts[col_map['category']]
                    for key in col_map.keys():
                        if key != 'category':
                            pop_weight[key] = float(parts[col_map[key]])
                    weights[category] = pop_weight
        
        return weights
    
    def _get_coding_intensity_adjuster(self) -> float:
        """
        Get the coding intensity adjuster based on the CMS Model version.
        
        Returns:
            float: The coding intensity adjuster.
        
        Notes:
            This function retrieves the coding intensity adjuster based on the version 
            specified in the object. It looks up the adjuster value from the respective 
            CMS_VARIABLES dictionary based on the version provided ('v24' or 'v28'). 
            If the version is not recognized, the default adjuster value of 1 is returned.
        """
        coding_intensity_adjuster = 1
        if self.version == 'v24':
            coding_intensity_adjuster = 1 - CMS_VARIABLES_V24['coding_intensity_adjuster']
        elif self.version == 'v28':
            coding_intensity_adjuster = 1 - CMS_VARIABLES_V28['coding_intensity_adjuster']
        
        return coding_intensity_adjuster
    
    def _get_normalization_factor(self) -> float:
        """
        Get the normalization factor based on the CMS Model version.
        
        Returns:
            float: The normalization factor.
        
        Notes:
            This function retrieves the normalization factor based on the version 
            specified in the object. It looks up the adjuster value from the respective 
            CMS_VARIABLES dictionary based on the version provided ('v24' or 'v28'). 
            If the version is not recognized, the default normalization value of 1 is returned.
        """
        normalization_factor = 1
        if self.version == 'v24':
            normalization_factor = CMS_VARIABLES_V24['normalization_factor']
        elif self.version == 'v28':
            normalization_factor = CMS_VARIABLES_V28['normalization_factor']

        return normalization_factor



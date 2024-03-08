import os
import json
import importlib.resources
import datetime

from pathlib import Path
from src.risk_adjustment_model.utilities import determine_age_band
from src.risk_adjustment_model.output import ScoringResults
from typing import Union, Optional


class BaseMedicareModel:
    """
    This is the foundation for Medicare Models. It is not to be called directly. It loads all relevant information for that model
    and year as class attributes.


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

    # --- General Model methods that should be inherited and used as is ---

    def score(
        self,
        gender: str,
        orec: str,
        medicaid: bool,
        diagnosis_codes=[],
        age=None,
        dob=None,
        population='CNA',
        verbose=False
    ) -> dict:
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
            dict: A dictionary containing the score information.
        """
        # Add validation that one of age or DOB is provided
        risk_model_age = self._determine_age(age, dob)

        if population == 'NE': # Tim why just NE? what does NE mean?
            risk_model_population = self._get_new_enrollee_population(risk_model_age, orec, medicaid)
        else:
            # CNA, CND, CFA, CFD, CPA, CPD
            risk_model_population = population

        output_dict = ScoringResults(
            gender=gender,
            orec=orec,
            medicaid=medicaid,
            age=age,
            dob=dob,
            diagnosis_codes=diagnosis_codes,
            year=self.year,
            population=population,
            risk_model_age=risk_model_age,
            risk_model_population=risk_model_population,
            model_version=self.version,
            model_year=self.model_year,
            coding_intensity_adjuster=self.coding_intesity_adjuster,
            normalization_factor=self.normalization_factor,
            beneficiary_score_profile={}
        )

        categories_dict, category_list = self.get_categories(risk_model_age, gender, orec, medicaid, diagnosis_codes, risk_model_population)
        combine_dict = {}
        score_dict = self.get_weights(category_list, risk_model_population)
        
        # Combine the dictionaries to make output
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
        output_dict.beneficiary_score_profile = score_dict

        return output_dict

    def get_categories(
        self, 
        age: int, 
        gender: str, 
        orec: str, 
        medicaid: bool, 
        diagnosis_codes: Union[str, list], 
        population: str
    ) -> tuple[dict[str, Union[dict, list]], list]:
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
        demo_categories = self.determine_demographic_cats(self.version, age, gender, orec, medicaid, population)
        if diagnosis_codes:
            categories_dict = self.determine_disease_categories(gender, age, diagnosis_codes)
        else:
            categories_dict = {}

        category_list = [key for key in categories_dict]
        category_list.extend(demo_categories)

        return categories_dict, category_list
    
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
            for key, value in self.category_definitions.items():
                if cat == key:
                    weight = self.category_weights[cat][population]
                    score += weight
                    if value['type'] == 'disease' or value['type'] == 'disease_interaction':
                        disease_score += weight
                    if value['type'] == 'demographic':
                        demographic_score += weight
                    category_dict[key] = {
                        'weight': weight,
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
    
    def determine_disease_categories(self, gender, age, diagnosis_codes) -> dict:
        """
        This considers mapping of disease categories and applying hierarchies

        """
        final_cat_dict = {}
        category_dict, categories = self._get_disease_categories(gender, age, diagnosis_codes)
        hier_category_dict, categories = self._apply_hierarchies(categories)
        interactions = self._determine_disease_interactions(categories)
        if interactions:
            categories.extend(interactions)

        for category in categories:
            final_cat_dict[category] = {
                'dropped_categories': hier_category_dict.get(category, None),
                'diagnosis_map': category_dict.get(category, None),
            }
        
        return final_cat_dict
    
    def _get_disease_categories(self, gender, age, diagnosis_codes):
        """
        """
        if isinstance(diagnosis_codes, list):
            dx_categories = {diag:self.diag_to_category_map[diag] for diag in diagnosis_codes if diag in self.diag_to_category_map}
        else:
            dx_categories = {diagnosis_codes:self.diag_to_category_map[diagnosis_codes]}
        
        for diagnosis_code, category in dx_categories.items():
            dx_categories[diagnosis_code] = self._age_sex_edits(gender, age, diagnosis_code, category)

        cat_dict = {}
        all_cats = [value for catlist in dx_categories.values() for value in catlist]
        unique_cats = set(all_cats)
        for cat in unique_cats:
            dx_codes = [key for key, value in dx_categories.items() if cat in value]
            cat_dict[cat] = dx_codes
        
        return cat_dict, unique_cats
    
    def _apply_hierarchies(self, categories: set) -> dict:
        """
        Takes in a unique set of categories and removes categories that fall into
        hierarchies as outlined in the hierarchy_definition file.

        Returns:
            dict containing the remaining categories and any categories "dropped"
            by that category.

        """
        category_list = list(categories)
        categories_dict = {}
        dropped_codes_total = []
        
        for category in category_list:
            dropped_codes = []
            if category in self.hierarchy_definitions.keys():
                for remove_category in self.hierarchy_definitions[category]['remove_code']:
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

        return categories_dict, category_list

    def determine_demographic_cats(self, version, age, gender, orec, medicaid, population) -> list:
        """Need to do the static typing stuff above for gender, age, orec"""
        # NEED TO DO LTIMEDICAID
        demo_cats = []
        disabled, orig_disabled = self._determine_disabled(age, orec)
        demo_cats.append(self._determine_demographic_cats(age, gender, population))
        demo_int = self._get_demographic_interactions(gender, orig_disabled)
        if demo_int:
            demo_cats.append(demo_int)

        return demo_cats
    
    # --- Methods to overwrite ---

    def _determine_demographic_cats(self, age, gender, population):
        """
        This may need to be overwritten depending on the mechanices of the model.
        Ranges may change, the population may change, etc.
        """
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
        
        demographic_category_range = determine_age_band(age, demo_category_ranges)

        if population[:2] == 'NE':
            demographic_category = f'NE{gender}{demographic_category_range}'
        else:
            demographic_category = f'{gender}{demographic_category_range}'

        return demographic_category

    def _get_demographic_interactions(self, gender, orig_disabled):
        """
        Depending on model this may change
        """
        demo_interaction = None
        if gender == 'F' and orig_disabled == 1:
            demo_interaction = 'OriginallyDisabled_Female'
        elif gender == 'M' and orig_disabled == 1:
            demo_interaction = 'OriginallyDisabled_Male'

        return demo_interaction
    
    def _get_new_enrollee_population(self, age, orec, medicaid):
        """
        Depending on the model, new enrollee population may be identified
        differently. This default is the CMS Community Model

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

    def _age_sex_edits(self, gender, age, diagnosis_code, category) -> str:
        """
        Placeholder method that should be overwritten by each specific model version class.
        The expectation is the _age_sex_edits method will return a category for the
        gender, age, diagnosis code, and category passed in.
        """
        return category

    def _determine_disease_interactions(self, categories: set) -> set:
        """
        Placeholder method that should be overwritten by each specific model version class.
        The expectation is that the _determine_interactions method will take in at least a set of
        unique categories and return a set of unique categories.

        This can be used for any "category" related calculations: payment count variables
        disabled interactions, disease interactions
        """
        return categories
    
    def _get_coding_intensity_adjuster(self) -> float:
        """
        This should get overwritten based on model version and year.
        
        Returns:
            float: The coding intensity adjuster.
        """
        coding_intensity_adjuster = 1
        
        return coding_intensity_adjuster
    
    def _get_normalization_factor(self) -> float:
        """
        This should get overwritten based on model version and year.
        
        Returns:
            float: The normalization factor.
        """
        normalization_factor = 1

        return normalization_factor
    
    # --- Helper methods which should not be overwritten ---

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
        
        return disabled, orig_disabled

    def _determine_age(self, age: int, dob: str) -> int:
        """
        This code is meant to address two design considerations:
        1.  Date of birth (DOB) is PHI, thus the code allows for either age or DOB to create flexibility
            around the handling of PHI. 
        2.  The CMS Risk Adjustment Model uses age as of February 1st of the payment year. Thus if DOB
            is passed in, age needs to be computed relative to that date.

        It checks that one of DOB or age is passed in, then determines age if DOB is given. If age is given
        it returns that age and assumes that is the correct age as of February 1st of the payment year.
        
        """
        if dob == None and age == None:
                raise ValueError('Need a DOB or an Age passed in')
        elif dob:      
            reference_date = datetime.fromisoformat(f'{self.model_year}-02-01')
            age = reference_date.year - dob.year - ((reference_date.month, reference_date.day) < (dob.month, dob.day))
        elif age:
            age = age

        return age

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

        Returns:
            int: The model year.

        Raises:
            FileNotFoundError: If the specified version directory or reference data 
                            directory does not exist.

        """
        if not self.year:
            with importlib.resources.path('src.risk_adjustment_model.reference_data', 'medicare') as data_dir:
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
        """
        with importlib.resources.path('src.risk_adjustment_model.reference_data', 'medicare') as data_dir:
            data_directory = data_dir / self.version / str(self.model_year)
        
        return data_directory
        
    def _get_hierarchy_definitions(self) -> dict:
        """
        Retrieve the hierarchy definitions from a JSON file.

        Returns:
            dict: A dictionary containing the hierarchy definitions.
        """
        with open(self.data_directory / 'hierarchy_definition.json') as file:
            hierarchy_definitions = json.load(file)
        
        return hierarchy_definitions
    
    def _get_category_definitions(self) -> dict:
        """
        Retrieve category definitions from a JSON file.

        Returns:
            dict: A dictionary containing the category definitions.
        """
        with open(self.data_directory / 'category_definition.json') as file:
            category_definitions = json.load(file)
        
        return category_definitions
    
    def _get_diagnosis_code_to_category_mapping(self) -> dict:
        """
        Retrieve diagnosis code to category mappings from a text file. It expects the file
        to be a csv in the layout of diag,category_nbr.

        Returns:
            dict: A dictionary mapping diagnosis codes to categories.
        """
        diag_to_category_map = {}
        with open(self.data_directory / 'diag_to_category_map.txt', 'r') as file:
            for line in file:
                # Split the line based on the delimiter
                parts = line.strip().split('|')
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
            The CSV file is expected to have a header row specifying column 
            names, and subsequent rows representing category weights. Each row should 
            contain values separated by a delimiter, with one column representing 
            the category and others representing different weights. The function constructs 
            a nested dictionary where each category is mapped to a dictionary of weights.
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
                    pop_weight = {}
                    category = parts[col_map['category']]
                    for key in col_map.keys():
                        if key != 'category':
                            pop_weight[key] = float(parts[col_map[key]])
                    weights[category] = pop_weight
        
        return weights


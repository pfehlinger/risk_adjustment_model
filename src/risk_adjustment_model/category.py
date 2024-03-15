from src.risk_adjustment_model.config import Config
from src.risk_adjustment_model.utilities import determine_age_band, import_function
from typing import Union, Optional

class Category:
    """
    The only thing "universal" for categories across LOBs is some type of diagnosis code to category mapping.
    """

    def __init__(self, config, beneficiary):
        self.config = config
        self.beneficiary = beneficiary
        self.diagnosis_codes = beneficiary.diagnosis_codes
        self.version = config.version
        # PF: Don't know if I want this
        self.diag_to_category_map = self.config.diag_to_category_map
        # PF: Do I want these as objects on the class? Or just methods to call?
        # Do I want a way to chain these two together as one?
        # self.dx_categories = self._get_diagnosis_categories(self.diagnosis_codes)
        # self.disease_cats_dict, self.disease_categories = self._get_disease_categories(self.dx_categories)

    def _get_diagnosis_categories(self, diagnosis_codes):
        """
        """
        if isinstance(diagnosis_codes, list):
            dx_categories = {diag:self.diag_to_category_map[diag] for diag in diagnosis_codes if diag in self.diag_to_category_map}
        else:
            dx_categories = {diagnosis_codes:self.diag_to_category_map[diagnosis_codes]}

        return dx_categories
    
    def _get_disease_categories(self, dx_categories: dict):

        cat_dict = {}
        all_cats = [value for catlist in dx_categories.values() for value in catlist]
        unique_cats = set(all_cats)
        for cat in unique_cats:
            dx_codes = [key for key, value in dx_categories.items() if cat in value]
            cat_dict[cat] = dx_codes
        
        return cat_dict, unique_cats


class MedicareCategory(Category):
    """
    This handles universal components of getting medicare categories:
    - demo categories
    - disease categories
    - age sex edits
    - hierarchies
    """
    # PF: This may be unnecessary and just should rely on class inheritance
    def __init__(self, config, beneficiary):
        super().__init__(config, beneficiary)
        # Each model version may have its own demographic categories, interactions, age sex edits
        # so these are imported dynamically based on the model version
        self._determine_demographic_cats = import_function('.'+config.version, 'determine_demographic_cats')
        self._determine_demographic_interactions = import_function('.'+config.version, 'determine_demographic_interactions')
        self._age_sex_edits = import_function('.'+config.version, 'age_sex_edits')
        self._determine_disease_interactions = import_function('.'+config.version, 'determine_disease_interactions')

        self.category_details, self.category_list = self.get_categories(beneficiary)

    def get_categories(self, beneficiary) -> tuple[dict[str, Union[dict, list]], list]:
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
        demo_categories = self.determine_demographic_cats(beneficiary)
        if beneficiary.diagnosis_codes:
            categories_dict = self.determine_disease_categories(beneficiary)
        else:
            categories_dict = {}

        category_list = [key for key in categories_dict]
        category_list.extend(demo_categories)

        return categories_dict, category_list

    def determine_disease_categories(self, beneficiary) -> dict:
        """
        This considers mapping of disease categories and applying hierarchies

        """
        final_cat_dict = {}
        dx_categories = self._get_diagnosis_categories(beneficiary.diagnosis_codes)
        dx_categories = self._age_sex_edits(beneficiary.gender, beneficiary.age, dx_categories)
        category_dict, categories = self._get_disease_categories(dx_categories)
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
    
    def _get_diagnosis_categories(self, diagnosis_codes):
        """
        """
        if isinstance(diagnosis_codes, list):
            dx_categories = {diag:self.diag_to_category_map[diag] for diag in diagnosis_codes if diag in self.diag_to_category_map}
        else:
            dx_categories = {diagnosis_codes:self.diag_to_category_map[diagnosis_codes]}

        return dx_categories
    
    def _get_disease_categories(self, dx_categories):
        """
        """
        cat_dict = {}
        all_cats = [value for catlist in dx_categories.values() for value in catlist if value != 'NA']
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
            if category in self.config.hierarchy_definitions.keys():
                for remove_category in self.config.hierarchy_definitions[category]['remove_code']:
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
    
    def determine_demographic_cats(self, beneficiary) -> list:
        """Need to do the static typing stuff above for gender, age, orec"""
        # NEED TO DO LTIMEDICAID
        demo_cats = []
        demo_cats.append(self._determine_demographic_cats(beneficiary.age, beneficiary.gender, beneficiary.population))
        demo_int = self._determine_demographic_interactions(beneficiary.gender, beneficiary.orig_disabled)
        if demo_int:
            demo_cats.append(demo_int)

        return demo_cats
    

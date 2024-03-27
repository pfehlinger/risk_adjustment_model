from .utilities import _get_category_definitions, _get_category_weights


class Category:
    """
    This is an object to encapsulate a single category. It will contain
    category metadata along with the "weight" of the category
    for the appropriate model population
    """

    def __init__(
        self,
        filepath,
        risk_model_population,
        category,
        mapper_codes=None,
        dropped_categories=None,
    ):
        self.category_definitions = _get_category_definitions(filepath)
        self.category_weights = _get_category_weights(filepath)
        self.risk_model_population = risk_model_population
        self.category = category
        self.type = self._get_type(category)
        self.description = self._get_description(category)
        self.coefficient = self._get_coefficient(category, risk_model_population)
        self.number = self._get_number(category)
        self.mapper_codes = mapper_codes
        self.dropped_categories = dropped_categories

    def _get_type(self, category):
        return self.category_definitions[category]["type"]

    def _get_description(self, category):
        return self.category_definitions[category]["descr"]

    def _get_coefficient(self, category, risk_model_population):
        return self.category_weights[category][risk_model_population]

    def _get_number(self, category):
        return self.category_definitions[category].get("number", None)

    def _get_number(self, category):
        return self.category_definitions[category].get("number", None)

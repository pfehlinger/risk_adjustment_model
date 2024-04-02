from typing import Union


class GenericCodeCategory:
    """
    Encapsulates a generic code and its corresponding category mapping. This is a base
    class and should not be called directly.

    Attributes:
        category_map (dict): A dictionary containing the mapping of codes to categories.
        mapper_code (str): The code to be mapped.
        type (str): The type of code (default is None).
        category (list): A list containing the category corresponding to the code.
    """

    def __init__(self, category_map: dict, code: str, type: Union[str, None] = None):
        """
        Initializes GenericCodeCategory with the provided parameters.

        Args:
            category_map (dict): A dictionary containing the mapping of codes to categories.
            code (str): The code to be mapped.
            type (str, optional): The type of code (default is None).
        """
        self.mapper_code = code
        self.type = type
        self.category_map = category_map[type]
        self.category = self.category_map.get(code, [None])


class DxCodeCategory(GenericCodeCategory):
    """
    Represents a diagnosis code and its category mapping.

    Attributes:
        category_map (dict): A dictionary containing the mapping of codes to categories.
        code (str): The diagnosis code.
        type (str): The type of code, defaulted to "diag".
    """

    def __init__(self, category_map: dict, code: str, type: str = "diag"):
        """
        Initializes DxCodeCategory with the provided parameters.

        Args:
            category_map (dict): A dictionary containing the mapping of codes to categories.
            code (str): The diagnosis code.
            type (str, optional): The type of code (default is "diag").
        """
        super().__init__(category_map, code, type)


class NDCCodeCategory(GenericCodeCategory):
    """
    Represents a National Drug Code (NDC) and its category mapping.

    Attributes:
        category_map (dict): A dictionary containing the mapping of codes to categories.
        code (str): The NDC code.
        type (str): The type of code, defaulted to "ndc".
    """

    def __init__(self, category_map: dict, code: str, type: str = "ndc"):
        """
        Initializes NDCCodeCategory with the provided parameters.

        Args:
            category_map (dict): A dictionary containing the mapping of codes to categories.
            code (str): The NDC code.
            type (str, optional): The type of code (default is "ndc").
        """
        super().__init__(category_map, code, type)


class ProcCodeCategory(GenericCodeCategory):
    """
    Represents a procedure code (CPT, HCPCS, ICD10-CM codes, etc.) and its category mapping.

    Attributes:
        category_map (dict): A dictionary containing the mapping of codes to categories.
        code (str): The procedure code.
        type (str): The type of code, defaulted to "proc".
    """

    def __init__(self, category_map: dict, code: str, type: str = "proc"):
        """
        Initializes ProcCodeCategory with the provided parameters.

        Args:
            category_map (dict): A dictionary containing the mapping of codes to categories.
            code (str): The procedure code.
            type (str, optional): The type of code (default is "proc").
        """
        super().__init__(category_map, code, type)

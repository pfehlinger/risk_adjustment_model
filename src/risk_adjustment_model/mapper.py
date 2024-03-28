class GenericCodeCategory:
    """
    This class is to encapsulate a Generic code and what category it maps to
    """

    def __init__(self, category_map, code, type=None):
        self.mapper_code = code
        self.type = type
        self.category_map = category_map[type]
        self.category = self.category_map.get(code, [None])


class DxCodeCategory(GenericCodeCategory):
    def __init__(self, filepath, code, type="diag"):
        super().__init__(filepath, code, type)


class NDCCodeCategory(GenericCodeCategory):
    def __init__(self, filepath, code, type="ndc"):
        super().__init__(filepath, code, type)


class ProcCodeCategory(GenericCodeCategory):
    def __init__(self, filepath, code, type="proc"):
        super().__init__(filepath, code, type)

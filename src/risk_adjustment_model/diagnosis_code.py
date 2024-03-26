from dataclasses import dataclass
from .utilities import import_function


@dataclass
class DxCodeCategory:
    """
    This class is to encapsulate a diagnosis code and what category it maps to
    """

    def __init__(self, config, diagnosis_code):
        self.diagnosis_code = diagnosis_code
        self.category = config.diag_to_category_map.get(diagnosis_code, [None])


class MedicareDxCodeCategory(DxCodeCategory):
    """
    This class expands upon the DxCodeCategory class for Medicareapplying
    age sex edits appropriate for the model version.
    """

    def __init__(self, config, diagnosis_code, beneficiary):
        super().__init__(config, diagnosis_code)
        self._age_sex_edits = import_function("." + config.version, "age_sex_edits")
        self._edit_category = self._age_sex_edits(
            beneficiary.gender, beneficiary.age, self.diagnosis_code
        )
        if self._edit_category:
            self.category = self._edit_category

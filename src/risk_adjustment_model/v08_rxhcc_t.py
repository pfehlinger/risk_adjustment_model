from typing import Union
from .rxhcc_model import RxHCCModel


class MedicareModelRxHCCv08T(RxHCCModel):
    """
    RxHCC V08, "T" segment: calibrated on Specialty-filtered diagnoses (2018) and payment data
    (2019), PDP+MAPD combined. Published by CMS for PY2026. See RxHCCModel's module docstring for
    the full segment lineup and design.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v08_rxhcc_t", year)
        self.normalization_factor = self._get_normalization_factor(self.model_year)

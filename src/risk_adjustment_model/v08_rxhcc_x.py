from typing import Union
from .rxhcc_model import RxHCCModel


class MedicareModelRxHCCv08X(RxHCCModel):
    """
    RxHCC V08, "X" segment: calibrated on HCPCS-filtered diagnoses (2022) and payment data
    (2023), PDP+MAPD combined. Published by CMS for PY2026. See RxHCCModel's module docstring for
    the full segment lineup and design.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v08_rxhcc_x", year)
        self.normalization_factor = self._get_normalization_factor(self.model_year)

from typing import Union
from .rxhcc_model import RxHCCModel


class MedicareModelRxHCCv08Y2(RxHCCModel):
    """
    RxHCC V08, "Y2" segment: calibrated on HCPCS-filtered diagnoses (2023) and payment data
    (2024), PDP-only (unlike T/T2/X, which combine PDP+MAPD). Published by CMS for PY2027. See
    RxHCCModel's module docstring for the full segment lineup and design.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v08_rxhcc_y2", year)
        self.normalization_factor = self._get_normalization_factor(self.model_year)

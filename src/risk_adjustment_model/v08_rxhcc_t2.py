from typing import Union
from .rxhcc_model import RxHCCModel


class MedicareModelRxHCCv08T2(RxHCCModel):
    """
    RxHCC V08, "T2" segment: calibrated on Specialty-filtered diagnoses (2018) and payment data
    (2019), PDP+MAPD combined -- the PY2027 successor to the "T" segment (same calibration
    approach, one year later). Per CMS, it's used only for PACE organizations' legacy component
    (unlike PY2026's split, PY2027 has no non-PACE use for this segment at all -- Y1/Y2 cover
    non-PACE MA-PD/PDP directly). See RxHCCModel's module docstring for the full segment lineup
    and design.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v08_rxhcc_t2", year)
        self.normalization_factor = self._get_normalization_factor(self.model_year)

    def _get_normalization_factor(self, year: int) -> float:
        """
        Returns:
            float: The normalization factor.
        """
        norm_factor_dict = {
            2027: 1.237,
        }
        try:
            normalization_factor = norm_factor_dict[year]
        except KeyError:
            normalization_factor = 1
        return normalization_factor

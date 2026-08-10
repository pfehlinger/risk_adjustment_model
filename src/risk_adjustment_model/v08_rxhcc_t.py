from typing import Union
from .rxhcc_model import RxHCCModel


class MedicareModelRxHCCv08T(RxHCCModel):
    """
    RxHCC V08, "T" segment: calibrated on Specialty-filtered diagnoses (2018) and payment data
    (2019), PDP+MAPD combined. Published by CMS for PY2026. Per CMS, this is the legacy RxHCC
    model -- for PY2026 it's used only as the 90%-weighted legacy component of PACE
    organizations' blended risk score (the "X" segment covers the other 10%, plus all non-PACE
    Part D beneficiaries). See RxHCCModel's module docstring for the full segment lineup and
    design.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v08_rxhcc_t", year)
        self.normalization_factor = self._get_normalization_factor(self.model_year)

    def _get_normalization_factor(self, year: int) -> float:
        """
        Per CMS, this segment is used only for the legacy (90%-weighted) component of PACE
        organizations' blended risk score -- see class docstring.

        Returns:
            float: The normalization factor.
        """
        norm_factor_dict = {
            2026: 1.202,
        }
        try:
            normalization_factor = norm_factor_dict[year]
        except KeyError:
            normalization_factor = 1
        return normalization_factor

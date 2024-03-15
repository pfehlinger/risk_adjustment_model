import unittest
from src.risk_adjustment_model import MedicareModel
from math import isclose


class TestCategoryMapping(unittest.TestCase):

    def test_v24(self):
        model = MedicareModel('v24')
        results = model.score(gender='M', orec='1', medicaid=False, diagnosis_codes=['E1169'], age=67, population='CNA', verbose=False)
        self.assertTrue('HCC18' in results.category_list)
        results = model.score(gender='M', orec='1', medicaid=False, diagnosis_codes=['I209'], age=67, population='CNA', verbose=False)
        self.assertTrue('HCC88' in results.category_list)
        

class TestDemoCategoryMapping(unittest.TestCase):

    def test_v24(self):
        model = MedicareModel('v24')
        results = model.score(gender='M', orec='1', medicaid=False, diagnosis_codes=['E1169'], age=67, population='CNA', verbose=False)
        self.assertTrue('M65_69' in results.category_list)
        self.assertTrue('OriginallyDisabled_Male' in results.category_list)
        results = model.score(gender='F', orec='0', medicaid=True, diagnosis_codes=['I209'], age=86, population='CNA', verbose=False)
        self.assertTrue('F85_89' in results.category_list)


class TestAgeSexEdits(unittest.TestCase):

    def test_v24(self):
        model = MedicareModel('v24')
        results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['D66'], age=67, population='CNA', verbose=False)
        self.assertTrue('HCC48' in results.category_list)
        results = model.score(gender='M', orec='0', medicaid=True, diagnosis_codes=['J430'], age=17, population='CPD', verbose=False)
        self.assertTrue('HCC112' in results.category_list)
        results = model.score(gender='M', orec='0', medicaid=True, diagnosis_codes=['F3481'], age=25, population='CPD', verbose=False)
        # The edit should result in no disease categories just a demographic category
        self.assertTrue(len(results.category_list)==1)


class TestCategoryInteractions(unittest.TestCase):

    def test_v24(self):
        model = MedicareModel('v24')

        results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['D61811', 'C4010'], age=67, population='CNA', verbose=False)
        self.assertTrue('HCC47_gCancer' in results.category_list)

        results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['E1169', 'A3681'], age=67, population='CNA', verbose=False)
        self.assertTrue('DIABETES_CHF' in results.category_list)

        results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['A3681', 'J410'], age=67, population='CNA', verbose=False)
        self.assertTrue('CHF_gCopdCF' in results.category_list)

        results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['A3681', 'I120'], age=67, population='CNA', verbose=False)
        self.assertTrue('HCC85_gRenal_V24' in results.category_list)

        results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['J410', 'R092'], age=67, population='CNA', verbose=False)
        self.assertTrue('gCopdCF_CARD_RESP_FAIL' in results.category_list)

        results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['A3681', 'I442'], age=67, population='CNA', verbose=False)
        self.assertTrue('HCC85_HCC96' in results.category_list)

        results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=['F10120', 'F28'], age=67, population='CNA', verbose=False)
        self.assertTrue('gSubstanceUseDisorder_gPsych' in results.category_list)
        

class TestNewEnrollee(unittest.TestCase):

    def test_v24(self):
        model = MedicareModel('v24')
        # NE_NMCAID_NORIGDIS
        results = model.score(gender='F', orec='0', medicaid=False, diagnosis_codes=[], age=67, population='NE', verbose=False)
        self.assertTrue(results.risk_model_population == 'NE_NMCAID_NORIGDIS')
        self.assertTrue('NEF67' in results.category_list)
        # NE_MCAID_NORIGDIS
        results = model.score(gender='F', orec='0', medicaid=True, diagnosis_codes=[], age=67, population='NE', verbose=False)
        self.assertTrue(results.risk_model_population == 'NE_MCAID_NORIGDIS')
        self.assertTrue('NEF67' in results.category_list)
        # NE_NMCAID_ORIGDIS
        results = model.score(gender='F', orec='1', medicaid=False, diagnosis_codes=[], age=67, population='NE', verbose=False)
        self.assertTrue(results.risk_model_population == 'NE_NMCAID_ORIGDIS')
        self.assertTrue('NEF67' in results.category_list)
        # NE_MCAID_ORIGDIS
        results = model.score(gender='F', orec='1', medicaid=True, diagnosis_codes=[], age=67, population='NE', verbose=False)
        self.assertTrue(results.risk_model_population == 'NE_MCAID_ORIGDIS')
        self.assertTrue('NEF67' in results.category_list)


class TestRawScore(unittest.TestCase):

    def test_v24(self):
        model = MedicareModel('v24')
        results = model.score(gender='M', orec='0', medicaid=False, diagnosis_codes=['E1169', 'I509'], age=70, population='CNA')
        self.assertTrue(isclose(results.score_raw, 1.148))
        results = model.score(gender='M', orec='0', medicaid=False, 
                              diagnosis_codes=['E1169', 'I5030', 'I509', 'I211', 'I209', 'R05'], age=70, population='CNA')
        self.assertTrue(isclose(results.score_raw, 1.283))
        results = model.score(gender='F', orec='0', medicaid=False, 
                              diagnosis_codes=['E1169', 'I5030', 'I509', 'I211', 'I209', 'R05'], age=45, population='CND')
        self.assertTrue(isclose(results.score_raw, 1.281))



if __name__ == '__main__':

    unittest.main()
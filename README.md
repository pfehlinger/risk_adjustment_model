# risk_adjustment_model
Python implementation of Healthcare Risk Adjustment Models

This codebase implements the [Hierachical Condition Categories](https://www.cms.gov/cciio/resources/forms-reports-and-other-resources/downloads/ra-march-31-white-paper-032416.pdf) methodology used by both the Medicare Advantage program and the ACA Commercial risk adjustment program (HHS-HCC).
The Medicare SAS implementations can be found on [CMS's website](https://www.cms.gov/medicare/payment/medicare-advantage-rates-statistics/risk-adjustment) by year, and the Commercial "Do It Yourself" (DIY) SAS/Python implementations on [CMS's marketplace resources page](https://www.cms.gov/marketplace/resources/regulations-guidance) by year.

Currently, risk_adjustment_model supports the below model versions:
* Medicare (CMS-HCC)
  * V22
  * V24
  * V28
* Medicare ESRD (End-Stage Renal Disease) -- a Medicare model variant, not a separate line of
  business; imported alongside the CMS-HCC classes above
  * V21
  * V24
* Medicare RxHCC (Part D) -- also a Medicare model variant, imported alongside the classes above.
  Five independently-calibrated segments, all V08:
  * T, X (PY2026)
  * T2, Y1 (MAPD-only), Y2 (PDP-only) (PY2027)
* Commercial/ACA (HHS-HCC)
  * V07
  * V08

There a couple of key design decisions to call out:
1. ICD-9 is not supported. All diagnosis codes must be ICD-10.
1. Categories are output for a scoring run if they are "valid" for a model, even if they do not contribute to the score. For example, CMS New Enrollees only receive a score on their demographic category based on age and gender. Rather than exclude any categories associated with the ICD10 codes of the new enrollee, this code base opts to include them and assign their coefficient value to be 0.
1. Diagnosis codes are assumed to already be validated/plausible for the beneficiary submitted (e.g. from an acceptable claim source and bill type) before being passed in. This includes CMS's Medicare Code Editor-style age/sex plausibility edits (MCE conditions, e.g. rejecting a pregnancy diagnosis on a claim for a young child) — this is claims-editing data-quality logic, not risk-adjustment-model scoring logic, so it is intentionally not performed by this codebase, the same way acceptable claim source/bill-type filtering is not performed here either. A possible future enhancement would be a second, richer scoring entry point that accepts a full diagnosis/service-date/claim-type dataset and performs this filtering internally, alongside the current simpler signature.



## Prerequisites
- Python 3.12 or later
- Poetry package manager


## Installing

Eventually, this package can be installed directly from pip

```
pip install risk_adjustment_model
```

As for now, it should be installed by cloning down the repository, running poetry build on it
and then pip installing locally into an virtual environment


## File Structure

- `src/risk_adjustment_model `: The package source code is located here.
  - `reference_data/`: The necessary transformed data files, organized `<lob>/<version>/<year>/`
                       (e.g. `commercial/v08/2026/`). For Commercial/ACA these are regenerated
                       from CMS's official DIY software package's source CSVs by
                       `scripts/build_v08_reference_data.py` (see that script's docstring for
                       the source->destination mapping and how to re-run it for a new year).
  - `beneficiary.py`: class to encapsulate a "beneficiary", attributes like age, gender, dob, etc.
  - `category.py`: class to encapsulate a "category", attributes like coefficient, description, etc.
  - `mapper.py`: classes to encapsulate the relationship between mapper codes and their corresponding categories.
                 For example, diagnosis code to category relationship.
  - `model.py`: `BaseModel`, the LOB-agnostic base class all models inherit from (reference file loading, year resolution).
  - `medicare_model.py`, `commercial_model.py`: LOB-specific base classes (Medicare/CMS-HCC and Commercial/ACA HHS-HCC, respectively) shared across their model versions.
  - `reference_files_loader.py`: Contains class to encapsulate the loading of the neccessary model reference files located in
                                 the reference_data folder structure. This is necessary for performance purposes.
  - `result.py`: class to encapsulate the output of a scoring run.
  - `utilities.py`: Contains generic functions that are used throughout codebase.
  - `v22.py`, `v24.py`, `v28.py`: Medicare model version classes (`MedicareModelV22`, `MedicareModelV24`, `MedicareModelV28`).
  - `v24_esrd.py`, `v21_esrd.py`: Medicare ESRD model version classes (`MedicareModelESRDv24`, `MedicareModelESRDv21`). Unlike Community, `population` is one of DIAL/GRAFT_COMM/GRAFT_INST/NE_DIAL/NE_GRAFT/TRANSPLANT_1M/TRANSPLANT_2M/TRANSPLANT_3M -- see `MedicareModelESRDv24`'s module docstring for the full design (score composition, graft-duration bonus math, why renal categories are excluded from V24 but not V21).
  - `rxhcc_model.py`: `RxHCCModel`, the shared base class for all RxHCC segment classes (scoring logic is identical across segments; only reference data differs).
  - `v08_rxhcc_t.py`, `v08_rxhcc_x.py`, `v08_rxhcc_t2.py`, `v08_rxhcc_y1.py`, `v08_rxhcc_y2.py`: Medicare RxHCC segment classes (`MedicareModelRxHCCv08T`/`X`/`T2`/`Y1`/`Y2`). `population` is one of CE_NONLOW_AGED/CE_NONLOW_NONAGED/CE_LOW_AGED/CE_LOW_NONAGED/CE_LTI/NE_NONLOW_COMMUNITY/NE_LOW_COMMUNITY/NE_LTI -- see `RxHCCModel`'s module docstring for what distinguishes the five segments and the full population list.
  - `v07.py`, `v08.py`: Commercial/ACA model version classes (`CommercialModelV07`, `CommercialModelV08`).
- `scripts/`: Developer/maintainer tooling, not part of the published package.
  - `build_v08_reference_data.py`: Regenerates Commercial/ACA reference data for a benefit year from a CMS DIY software package.
  - `build_medicare_reference_data.py`, `build_medicare_v22_reference_data.py`, `build_medicare_v24_esrd_reference_data.py`, `build_medicare_v21_esrd_reference_data.py`, `build_medicare_rxhcc_reference_data.py`: Regenerate/cold-start Medicare (CMS-HCC, ESRD, and RxHCC) reference data from CMS DIY software packages.
  - `cross_validate_cms.py`: Cross-validates `CommercialModelV08` against CMS's own DIY software on a synthetic dataset (see script docstring for setup).
- `tests/`: Tests are stored here, one for each model version.
- `README.md`: This README file.


## Code Examples

`risk_adjustment_model` is used to score a single beneficiary. Examples below, first for the
Medicare (CMS-HCC) models, then for the Commercial/ACA (HHS-HCC) models.

## Medicare (CMS-HCC) Models

### Importing

To import any of the model classes from `risk_adjustment_model`

```python
>>> from risk_adjustment_model import MedicareModelV24, MedicareModelV28
>>> model = MedicareModelV24()
>>> print(model.score.__doc__)

        Determines the risk score for the inputs. Entry point for end users.

        Steps:
        1. Use beneficiary information to get the demographic categories
        2. Using diagnosis code inputs and beneficiary information get the diagnosis code to
           category relationship
        3. Get the unique set of categories from diagnosis codes
        4. Apply hierarchies
        5. Determine disease interactions

        Args:
            gender (str): Gender of the beneficiary being scored, valid values M or F.
            orec (str): Original Entitlement Reason Code of the beneficiary. See: https://bluebutton.cms.gov/assets/ig/ValueSet-orec.html for valid values
            medicaid (bool): Beneficiary medicaid status, True or False
            diagnosis_codes (list): List of the diagnosis codes associated with the beneficiary
            age (int): Age of the beneficiary, can be None.
            dob (str): Date of birth of the beneficiary, can be None
            population (str): Population of beneficiary being scored, valid values are CNA, CND, CPA, CPD, CFA, CFD, INS, NE
            verbose (bool): Indicates if trimmed output or full output is desired

        Returns:
            ScoringResult: An instantiated object of ScoringResult class.
>>>
```

### Scoring of a Beneficiary with Diagnosis Codes

To execute a scoring run, at minimum beneficiary attributes are needed: gender, orec, medicaid, age and/or DOB, and population.
A list of diagnosis codes (ICD-10) can be provided as appropriate.

Population values are contingent upon the model chosen, for Community models it is generally:
- CNA - Community, Non Dual, Aged (default)
- CND - Community, Non Dual, Disabled
- CPA - Community, Partial Dual, Aged
- CPD - Community, Partial Dual, Disabled
- CFA - Community, Full Dual, Aged
- CFD - Community, Full Dual, Disabled
- INS - Institutional
- NE - CMS New Enrollee


```python
>>> results = model.score(gender="M",orec="0",medicaid=False,diagnosis_codes=["E1169", "I5030", "I509", "I2111", "I209"],age=70,population="CNA",)
>>> results
ScoringResult(gender='M', orec='0', medicaid=False, age=70, dob=None, diagnosis_codes=['E1169', 'I5030', 'I509', 'I2111', 'I209'], year=None, population='CNA', risk_model_age=70, risk_model_population='CNA', model_version='v24', model_year=2024, coding_intensity_adjuster=0.941, normalization_factor=1.146, score_raw=1.343, disease_score_raw=0.9490000000000001, demographic_score_raw=0.394, score=1.1028, disease_score=0.7792, demographic_score=0.3236, category_list=['DIABETES_CHF', 'D3', 'M70_74', 'HCC86', 'HCC18', 'HCC85'], category_details={'DIABETES_CHF': {'coefficient': 0.121, 'diagnosis_map': None}, 'D3': {'coefficient': 0.0, 'diagnosis_map': None}, 'M70_74': {'coefficient': 0.394, 'diagnosis_map': None}, 'HCC86': {'coefficient': 0.195, 'diagnosis_map': ['I2111']}, 'HCC18': {'coefficient': 0.302, 'diagnosis_map': ['E1169']}, 'HCC85': {'coefficient': 0.331, 'diagnosis_map': ['I5030', 'I509']}})
>>>
```

Note: A year can be passed into the model classes when instantiating to pull category mappings and coefficient weights for a specific year, else the most recent year available will be used.

### Results

Results are output in a Python dataclass object. To see the all the attributes, use help() on the output of score.
There are a few attributes that are necessary to call out:
1. `risk_model_population` - This is the population used for scoring. Usually it matches `population`, however in some cases it is a derived population. For example, if 'NE' is passed in, the code will derive the correct new enrollee population based on `gender` and `orec`.
1. `model_year` - This is the year used for scoring. If a `year` is passed in when instantiating a model, it will that value. Else, it will be the most recent year for the model.
1. `category_details` - Dictionary where keys are individual categories and values are dictionaries containing additional details which vary based on if `verbose` parameter was set to `True` or `False`. If interested in descriptions, dropped categories, etc. the verbose output should be requested.


To see the results as a dictionary

```python
>>> from risk_adjustment_model import MedicareModelV24, MedicareModelV28
>>> model = MedicareModelV24()
>>> results = model.score(gender="M",orec="0",medicaid=False,diagnosis_codes=["E1169", "I5030", "I509", "I2111", "I209"],age=70,population="CNA",)
>>> from dataclasses import asdict
>>> print(asdict(results))
```

To see score information, use:
- `score_raw` - Unadjusted score (no coding intensity or normalization applied)
- `disease_score_raw` - Unadjusted score for disease categories or disease interactions
- `demographic_score_raw` - Unadjusted score for demographic categories or demographic interactions
- `score` - Score with coding intensity and normalization applied
- `disease_score`- Disease score with coding intensity and normalization applied
- `demographic_score` - Demographic score with coding intensity and normalization applied


```python
>>> results.score_raw
1.343
```

To see category information use: `category_list` or `category_details`

```python
>>> results.category_list
['DIABETES_CHF', 'D3', 'M70_74', 'HCC86', 'HCC18', 'HCC85']
>>> results.category_details
{'DIABETES_CHF': {'coefficient': 0.121, 'diagnosis_map': None}, 'D3': {'coefficient': 0.0, 'diagnosis_map': None}, 'M70_74': {'coefficient': 0.394, 'diagnosis_map': None}, 'HCC86': {'coefficient': 0.195, 'diagnosis_map': ['I2111']}, 'HCC18': {'coefficient': 0.302, 'diagnosis_map': ['E1169']}, 'HCC85': {'coefficient': 0.331, 'diagnosis_map': ['I5030', 'I509']}}
```


Verbose results


```python
>>> results.category_details
{'DIABETES_CHF': {'coefficient': 0.121, 'type': 'disease_interaction', 'category_number': None, 'category_description': 'Congestive Heart Failure*Diabetes', 'dropped_categories': None, 'diagnosis_map': None}, 'D3': {'coefficient': 0.0, 'type': 'disease_count', 'category_number': None, 'category_description': '3 payment HCCs', 'dropped_categories': None, 'diagnosis_map': None}, 'M70_74': {'coefficient': 0.394, 'type': 'demographic', 'category_number': None, 'category_description': 'Male, 70 to 74 Years old', 'dropped_categories': None, 'diagnosis_map': None}, 'HCC86': {'coefficient': 0.195, 'type': 'disease', 'category_number': 86, 'category_description': 'Acute Myocardial Infarction', 'dropped_categories': ['HCC88'], 'diagnosis_map': ['I2111']}, 'HCC18': {'coefficient': 0.302, 'type': 'disease', 'category_number': 18, 'category_description': 'Diabetes with Chronic Complications', 'dropped_categories': None, 'diagnosis_map': ['E1169']}, 'HCC85': {'coefficient': 0.331, 'type': 'disease', 'category_number': 85, 'category_description': 'Congestive Heart Failure', 'dropped_categories': None, 'diagnosis_map': ['I5030', 'I509']}}
```


## Medicare ESRD (End-Stage Renal Disease) Models

ESRD (`MedicareModelESRDv24`, `MedicareModelESRDv21`) is a Medicare model variant, not a separate
line of business -- import it from `risk_adjustment_model` alongside the CMS-HCC classes above.
Unlike Community, `population` is not CNA/CND/etc: CMS's own ESRD software computes a whole family
of score variants per beneficiary (dialysis, community-graft, institutional-graft, new-enrollee
dialysis/graft, flat transplant-month scores) and leaves it to the caller to know which one
applies. Consistent with how this repo already requires an explicit `population` for Community,
the caller passes one `population` value and gets back one score for it -- never every variant at
once. Valid values: `DIAL`, `GRAFT_COMM`, `GRAFT_INST`, `NE_DIAL`, `NE_GRAFT`, `TRANSPLANT_1M`,
`TRANSPLANT_2M`, `TRANSPLANT_3M`. See `MedicareModelESRDv24`'s module docstring for the full
design, including the graft-duration bonus math for GRAFT_COMM/GRAFT_INST/NE_GRAFT.

```python
>>> from risk_adjustment_model import MedicareModelESRDv24
>>> model = MedicareModelESRDv24()
>>> results = model.score(gender="M", orec="0", diagnosis_codes=["E1169"], age=67, population="DIAL")
>>> results.score_raw
0.661
>>> results = model.score(gender="F", orec="0", fbdual=True, diagnosis_codes=["D66"], age=67, population="GRAFT_COMM", graft_duration_months=6)
>>> results.risk_model_population
'GRAFT_COMM_FBD_GE65'
```

`MedicareModelESRDv21` (the legacy model) uses the same `population` vocabulary, but its own set
of beneficiary flags (`mcaid`, `ne_mcaid` -- two independent Medicaid dual-status inputs, not one;
no `pbdual`/`lti` at all). See `MedicareModelESRDv21`'s module docstring for what's simpler than
V24 (no institutional-vs-community dual/aged split, no NE actuarial adjustment, renal categories
scored normally rather than excluded).


## Medicare RxHCC (Part D) Models

RxHCC (`MedicareModelRxHCCv08T`/`X`/`T2`/`Y1`/`Y2`) is a Medicare model variant, not a separate
line of business -- import it from `risk_adjustment_model` alongside the CMS-HCC/ESRD classes
above. CMS publishes RxHCC as several independently-calibrated segments per payment year rather
than one model per year: PY2026 ships T and X (differing by which source data the regression was
calibrated on); PY2027 ships T2 (successor to T), Y1 (MAPD-only), and Y2 (PDP-only). Each segment
is its own class, since T/X/T2 differ the same way MedicareModelV22/V24/V28 differ -- an
independent calibration choice, not a fact about any individual beneficiary. See `RxHCCModel`'s
module docstring for the full rationale.

`population` is one of `CE_NONLOW_AGED`, `CE_NONLOW_NONAGED`, `CE_LOW_AGED`, `CE_LOW_NONAGED`,
`CE_LTI`, `NE_NONLOW_COMMUNITY`, `NE_LOW_COMMUNITY`, `NE_LTI` -- passed directly by the caller,
same as Community's CNA/CFA/etc, with Low/NonLow indicating Low-Income-Subsidy status. Unlike
Community, `esrd` (End-Stage Renal Disease status) replaces `medicaid`/dual-status entirely; there
is no dual-status input at all, since LIS status is already folded into `population`.

```python
>>> from risk_adjustment_model import MedicareModelRxHCCv08T, MedicareModelRxHCCv08Y1
>>> model = MedicareModelRxHCCv08T()
>>> results = model.score(gender="M", orec="0", diagnosis_codes=["E1169"], age=67, population="CE_NONLOW_AGED")
>>> results.score_raw
0.663
>>> ne_model = MedicareModelRxHCCv08Y1(year=2027)
>>> ne_results = ne_model.score(gender="M", orec="0", esrd=True, age=40, population="NE_NONLOW_COMMUNITY")
>>> ne_results.category_list
['ESRD_NORIGDIS_X_M35_44']
```


## Commercial/ACA (HHS-HCC) Models

### Importing

To import any of the Commercial model classes from `risk_adjustment_model`

```python
>>> from risk_adjustment_model import CommercialModelV07, CommercialModelV08
>>> model = CommercialModelV08()
>>> print(model.score.__doc__)

        Determines the risk score for the inputs. Entry point for end users.

        Steps:
        1. Use beneficiary information to get the demographic categories
        2. Using diagnosis code, ndc, and procedure code inputs and beneficiary information
           to get the code to category relationship
        3. Get the unique set of categories from the codes
        4. Apply hierarchies
        5. Determine disease interactions
        6. Apply groups

        Args:
            gender (str): Gender of the beneficiary being scored, valid values M or F.
            metal_level (str): Metal level of the beneficiary's insurance plan.
            csr_indicator (int): Cost-sharing reduction indicator.
            enrollment_days (int): Number of days the beneficiary has been enrolled.
            diagnosis_codes (list, optional): List of the diagnosis codes associated with the beneficiary, can be None.
            ndc_codes (list, optional): List of National Drug Codes (NDC) associated with the beneficiary, can be None.
            proc_codes (list, optional): List of procedure codes associated with the beneficiary, can be None.
            age (int, optional): Age of the beneficiary, can be None.
            dob (str, optional): Date of birth of the beneficiary, can be None.
            last_enrollment_date (str, optional): Last enrollment date of the beneficiary, can be None.
            verbose (bool): Indicates if trimmed output or full output is desired.

        Returns:
            ScoringResult: An instantiated object of ScoringResult class.
>>>
```

### Scoring of a Beneficiary with Diagnosis, NDC, and/or Procedure Codes

To execute a scoring run, at minimum beneficiary attributes are needed: gender, metal_level, csr_indicator, enrollment_days, and age and/or DOB.
Lists of diagnosis codes (ICD-10), NDC codes, and procedure/HCPCS codes can be provided as appropriate — the beneficiary's age determines whether they're scored as Infant, Child, or Adult, which in turn determines which of these are relevant (e.g. NDC/procedure codes only affect Adult and Child scoring; RXC categories are Adult-only).

`metal_level` is one of: `Platinum`, `Gold`, `Silver`, `Bronze`, `Catastrophic`.
`csr_indicator` is CMS's cost-sharing reduction indicator (an integer, generally 1-11 depending on benefit year — see the CMS DIY documentation for the current year's valid values).

```python
>>> results = model.score(gender="M", metal_level="Silver", csr_indicator=1, enrollment_days=365, diagnosis_codes=["E1169"], ndc_codes=["00002021301"], age=45, verbose=False)
>>> results
CommercialScoringResult(gender='M', age=45, dob=None, diagnosis_codes=['E1169'], year=None, risk_model_age=45, risk_model_population='Silver', model_version='v08', model_year=2026, score_raw=1.834, disease_score_raw=0, demographic_score_raw=0.171, score=1.834, disease_score=0.0, demographic_score=0.171, category_list=['RXC_06_x_HCC018_019_020_021', 'MAGE_LAST_45_49', 'RXC_06', 'G01'], category_details={'RXC_06_x_HCC018_019_020_021': {'coefficient': 0.499, 'trigger_code_map': ['RXC_06', 'HHS_HCC020']}, 'MAGE_LAST_45_49': {'coefficient': 0.171, 'trigger_code_map': None}, 'RXC_06': {'coefficient': 1.022, 'trigger_code_map': ['00002021301']}, 'G01': {'coefficient': 0.142, 'trigger_code_map': ['HHS_HCC020']}}, metal_level='Silver', csr_indicator=1, enrollment_days=365, last_enrollment_date=None, enrollment_months=12, csr_adjuster=1.0, dropped_category_list=['HHS_HCC020'], dropped_category_details={'HHS_HCC020': {'coefficient': 0.0, 'trigger_code_map': ['E1169']}})
>>>
```

Note how diagnosis code `E1169` (Type 2 diabetes with other specified complication) maps to `HHS_HCC020`, but because the beneficiary is also on insulin (NDC `00002021301`, mapping to `RXC_06`), two things happen: `HHS_HCC020` is absorbed into group `G01` (shown in `dropped_category_list`/`dropped_category_details`), and the RXC-06-times-diabetes interaction `RXC_06_x_HCC018_019_020_021` is triggered.

Note: A year can be passed into the model classes when instantiating to pull category mappings and coefficient weights for a specific year, else the most recent year available will be used.

### Results

Results are output in a Python dataclass object (`CommercialScoringResult`). To see all the attributes, use `help()` on the output of `score`.
A few attributes worth calling out beyond the ones shared with the Medicare models:
1. `risk_model_population` - For Commercial models this is the beneficiary's `metal_level`, since category weights are keyed by metal level.
1. `csr_adjuster` / `csr_indicator` - The cost-sharing reduction adjuster applied to the score, and the raw indicator it was derived from.
1. `enrollment_months` - The beneficiary's enrollment duration in months, derived from `enrollment_days`.
1. `dropped_category_list` / `dropped_category_details` - Categories that were dropped due to hierarchy or group application (e.g. an individual HCC absorbed into a group, or a lower-severity HCC removed because a higher-severity one in the same hierarchy chain is present).

To see the results as a dictionary

```python
>>> from risk_adjustment_model import CommercialModelV08
>>> model = CommercialModelV08()
>>> results = model.score(gender="M", metal_level="Silver", csr_indicator=1, enrollment_days=365, diagnosis_codes=["E1169"], ndc_codes=["00002021301"], age=45, verbose=False)
>>> from dataclasses import asdict
>>> print(asdict(results))
```

To see score information, use `score_raw`/`disease_score_raw`/`demographic_score_raw` (unadjusted) and `score`/`disease_score`/`demographic_score` (with the CSR adjuster applied), same as the Medicare models:

```python
>>> results.score_raw
1.834
>>> results.score
1.834
```

To see category information use: `category_list` or `category_details`

```python
>>> results.category_list
['RXC_06_x_HCC018_019_020_021', 'MAGE_LAST_45_49', 'RXC_06', 'G01']
>>> results.category_details
{'RXC_06_x_HCC018_019_020_021': {'coefficient': 0.499, 'trigger_code_map': ['RXC_06', 'HHS_HCC020']}, 'MAGE_LAST_45_49': {'coefficient': 0.171, 'trigger_code_map': None}, 'RXC_06': {'coefficient': 1.022, 'trigger_code_map': ['00002021301']}, 'G01': {'coefficient': 0.142, 'trigger_code_map': ['HHS_HCC020']}}
```

Verbose results

```python
>>> results.category_details
{'RXC_06_x_HCC018_019_020_021': {'coefficient': 0.499, 'type': 'rx_interaction', 'category_number': None, 'category_description': 'Additional effect for enrollees with RXC 06 and (HCC 018 or 019 or 020 or 021)', 'dropped_categories': None, 'trigger_code_map': ['RXC_06', 'HHS_HCC020']}, 'MAGE_LAST_45_49': {'coefficient': 0.171, 'type': 'demographic', 'category_number': None, 'category_description': 'Age 45-49, Male', 'dropped_categories': None, 'trigger_code_map': None}, 'RXC_06': {'coefficient': 1.022, 'type': 'rx', 'category_number': 6, 'category_description': 'Insulin', 'dropped_categories': None, 'trigger_code_map': ['00002021301']}, 'G01': {'coefficient': 0.142, 'type': 'group', 'category_number': None, 'category_description': 'G01', 'dropped_categories': ['HHS_HCC020'], 'trigger_code_map': ['HHS_HCC020']}}
```

## Cross-Validating Against CMS's Reference Software

Every model version in this repo has been checked against CMS's own Python "Do It Yourself" (DIY)
reference software at some point during development -- not just internal review. How to re-run
that check yourself differs by line of business:

### Commercial/ACA (HHS-HCC)

Automated: `scripts/cross_validate_cms.py` generates a batch of synthetic enrollees, scores them
through both this repo and CMS's real `transform.py`, and reports any mismatches.

```
poetry install --with cms_validation
export CMS_PACKAGE_DIR=/path/to/extracted/HHS_HCC_software_package_.../software/HHS_HCC
poetry run python scripts/cross_validate_cms.py --n 150 --seed 42
```

See the script's own docstring for what it deliberately excludes (MCE-editable and age/sex-edit
diagnosis codes) and why.

### Medicare (CMS-HCC, ESRD, RxHCC)

No automated equivalent exists yet for these three families (this is a real gap, not an oversight
to hide -- if you want one built, ask). Every V22/V24/V28, ESRD V24/V21, and RxHCC T/X/T2/Y1/Y2
cross-validation done so far was run manually, directly against CMS's own package, as follows:

1. Download and extract the relevant CMS Python DIY package (e.g. `CMS_HCC_v28_2026_T_package`,
   `ESRD_v24_2026_T_package`, `RxHCC_v8_2027_Y1_package`) from
   [CMS's Medicare risk adjustment page](https://www.cms.gov/medicare/payment/medicare-advantage-rates-statistics/risk-adjustment).
2. Create a virtual environment and `pip install -r requirements.txt` from inside the extracted
   package (it needs `pandas`/`numpy` directly -- this is CMS's own software, independent of this
   repo's `cms_validation` poetry group).
3. Edit `software/<Model>/data/input/user_defined/beneficiaries.csv` and `diagnoses.csv` with test
   beneficiaries. Column layout and `DOB_format` are defined in that model's `config.py` -- they
   differ by family (e.g. ESRD's beneficiaries.csv has `FBDual,PBDual,LTI`; RxHCC's has `ESRD`; V21
   ESRD's has `MCAID,NEMCAID`). **Age is computed by CMS as of February 1st of the payment year**,
   not the package's release date -- get this wrong and every score will look like a mismatch that
   isn't one.
4. From the package's base folder (the one containing `software/`, not inside it), run:
   `python ./software/<Model>/transform.py`. Output lands in
   `software/<Model>/data/output/*_scores.csv`, with one `SCORE_<population>` column per
   population CMS's software computes.
5. Call this repo's `model.score(...)` with the same beneficiary/diagnosis inputs and compare
   `results.score_raw` against the matching `SCORE_*` column. Each model class's docstring
   documents its `population` values and, for the ones with a non-obvious CMS-column mapping
   (ESRD, RxHCC), the exact naming correspondence.

The build scripts in `scripts/` (`build_medicare_reference_data.py`,
`build_medicare_v22_reference_data.py`, `build_medicare_v24_esrd_reference_data.py`,
`build_medicare_v21_esrd_reference_data.py`, `build_medicare_rxhcc_reference_data.py`) are the
tooling that *generates* `reference_data/` from these same CMS packages in the first place --
re-running the relevant one against a freshly downloaded package is itself a useful check that
the committed reference data hasn't drifted from CMS's source.


## License
MIT

## Authors/Maintainers
- Phil Fehlinger @pfehlinger

Special shout out to the below for reviewing code and providing feedback:
- Tim Frazer
- Dante Gates
- Shane Hower

## References
- https://github.com/yubin-park/hccpy (inspired risk_adjustment_model)
- https://www.nber.org/data/cms-risk-adjustment.html
- https://www.cms.gov/medicare/health-plans/medicareadvtgspecratestats/risk-adjustors.html
- https://github.com/calyxhealth/pyriskadjust
- https://github.com/AlgorexHealth/hcc-python
- https://github.com/galtay/hcc_risk_models
- https://www.cms.gov/cciio/resources/forms-reports-and-other-resources/downloads/ra-march-31-white-paper-032416.pdf
- https://www.cms.gov/cciio/resources/regulations-and-guidance/index.html

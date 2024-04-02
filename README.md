# risk_adjustment_model
Python implementation of Healthcare Risk Adjustment Models.

## Prerequisites
- Python 3.10 or later
- Poetry package manager
# risk_adjustment_model
Python implementation of Healthcare Risk Adjustment Models

This codebase implements the [Hierachical Condition Categories](https://www.cms.gov/cciio/resources/forms-reports-and-other-resources/downloads/ra-march-31-white-paper-032416.pdf) that undergrid the Medicare Advantage program.
The SAS implementations can be found on [CMS's website](https://www.cms.gov/medicare/payment/medicare-advantage-rates-statistics/risk-adjustment) by year.

Currently, risk_adjustment supports the below model versions:
* V24
* V28

There a couple of key design decisions to call out:
1. ICD-9 is not supported. All diagnosis codes must be ICD-10.
1. Categories are output for a scoring run if they are "valid" for a model, even if they do not contribute to the score. For example, CMS New Enrollees only receive a score on their demographic category based on age and gender. Rather than exclude any categories associated with the ICD10 codes of the new enrollee, this code base opts to include them and assign their coefficient value to be 0.



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
  - `reference_data/`: The necessary transformed data files (TO DO: Add how these were obtained)
  - `beneficiary.py`: class to encapsulate a "beneficiary", attributes like age, gender, dob, etc.
  - `category.py`: class to encapsulate a "category", attributes like coefficient, description, etc.
  - `mapper.py`: classes to encapsulate the relationship between mapper codes and their corresponding categories.
                 For example, diagnosis code to category relationship.
  - `model.py`: classes to encapsulate risk adjustment models generally, and for each LOB (e.g. Medicare, Commercial, Mediciad)
  - `reference_files_loader.py`: Contains class to encapsulate the loading of the neccessary model reference files located in
                                 the reference_data folder structure. This is necessary for performance purposes.
  - `result.py`: class to encapsulate the output of a scoring run.
  - `utilities.py`: Contains generic functions that are used throughout codebase.
  - `v24.py`, `v28.py`, etc.: Each file contains a class to encapsulate the specific model version.
- `tests/`: Tests are stored here, one for each model version.
- `README.md`: This README file.


## Code Examples

`risk_adjustment_model` is used to score a single beneficiary. Examples below

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

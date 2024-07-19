from typing import List, Union, Type
from .utilities import determine_age_band
from .commercial_model import CommercialModel
from .category import Category
from .beneficiary import CommercialBeneficiary


class CommercialModelV07(CommercialModel):
    """
    This class represents the V07 Model for Commercial. It inherits from the CommercialModel class.

    Methods:
        __init__: Initializes the CommercialModelV07 instance.

        Overwrites:
            _age_sex_edits: Applies age and sex edits to diagnosis codes.
            _determine_disease_interactions: Determines disease interactions based on Category objects and beneficiary information.

        Included for clarity:
            _determine_payment_count_category: Determines the payment count category based on the number of categories provided.
            _determine_age_gender_category: Determines the demographic category based on age, gender, and population.
            _determine_demographic_interactions: Determines demographic interactions based on gender, disability status, and Medicaid enrollment.

        New:
            _age_sex_edit_1 to _age_sex_edit_16: Applies 16 different age and sex edits to a diagnosis code.
    """

    def __init__(self, year: Union[int, None] = None):
        super().__init__("v07", year)

    def _age_sex_edits(
        self, gender: str, age: int, diagnosis_code: str
    ) -> Union[List[str], None]:
        """
        Wrapper method to apply all model specific age and sex edits for a diagnosis code to
        category mapping. These are found in the model software file named something like
        "V24I0ED1".

        Args:
            gender (str): Gender of the individual ('M' for male, 'F' for female).
            age (int): Age of the individual.
            diagnosis_code (str): Diagnosis code to apply edits.

        Returns:
            Union[List[str], None]: List of categories after applying edits, or None if no edits applied.
        """
        new_category = self._age_sex_edit_1(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_2(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_3(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_4(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_5(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_6(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_7(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_8(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_9(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_10(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_11(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_12(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_13(gender, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_14(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_15(age, diagnosis_code)
        if new_category:
            return new_category
        new_category = self._age_sex_edit_16(age, diagnosis_code)
        if new_category:
            return new_category

    def _age_sex_edit_1(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 1 to a diagnosis code.

        Args:
            gender (str): Gender of the individual ('M' for male, 'F' for female).
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if age < 18 and dx_code in [
            "C9100",
            "C9101",
            "C9102",
            "C9500",
            "C9501",
            "C9502",
            "C7400",
            "C7401",
            "C7402",
            "C7410",
            "C7411",
            "C7412",
            "C7490",
            "C7491",
            "C7492",
        ]:
            return ["HHS_HCC009"]

    def _age_sex_edit_2(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 2 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if age < 18 and dx_code in [
            "J410",
            "J411",
            "J418",
            "J42",
            "J440",
            "J441",
            "J4481",
            "J4489",
        ]:
            return ["HHS_HCC161_1"]

    def _age_sex_edit_3(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 3 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age < 2) and dx_code in [
            "K55011",
            "K55012",
            "K55019",
            "K55021",
            "K55022",
            "K55029",
            "K55031",
            "K55032",
            "K55039",
            "K55041",
            "K55042",
            "K55049",
            "K55051",
            "K55052",
            "K55059",
            "K55061",
            "K55062",
            "K55069",
            "K5530",
            "K5531",
            "K5532",
            "K5533",
        ]:
            return ["HHS_HCC042"]

    def _age_sex_edit_4(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 4 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age < 50) and dx_code in [
            "C50011",
            "C50012",
            "C50019",
            "C50021",
            "C50022",
            "C50029",
            "C50111",
            "C50112",
            "C50119",
            "C50121",
            "C50122",
            "C50129",
            "C50211",
            "C50212",
            "C50219",
            "C50221",
            "C50222",
            "C50229",
            "C50311",
            "C50312",
            "C50319",
            "C50321",
            "C50322",
            "C50329",
            "C50411",
            "C50412",
            "C50419",
            "C50421",
            "C50422",
            "C50429",
            "C50511",
            "C50512",
            "C50519",
            "C50521",
            "C50522",
            "C50529",
            "C50611",
            "C50612",
            "C50619",
            "C50621",
            "C50622",
            "C50629",
            "C50811",
            "C50812",
            "C50819",
            "C50821",
            "C50822",
            "C50829",
            "C50911",
            "C50912",
            "C50919",
            "C50921",
            "C50922",
            "C50929",
        ]:
            return ["HHS_HCC011"]

    def _age_sex_edit_5(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 5 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age < 2) and dx_code in [
            "J430",
            "J431",
            "J432",
            "J438",
            "J439",
            "J449",
            "J982",
            "J983",
            "F200",
            "F201",
            "F202",
            "F203",
            "F205",
            "F2081",
            "F2089",
            "F209",
            "F21",
            "F22",
            "F23",
            "F24",
            "F250",
            "F251",
            "F258",
            "F259",
            "F28",
            "F29",
            "F3010",
            "F3011",
            "F3012",
            "F3013",
            "F302",
            "F303",
            "F304",
            "F308",
            "F309",
            "F310",
            "F3110",
            "F3111",
            "F3112",
            "F3113",
            "F312",
            "F3130",
            "F3131",
            "F3132",
            "F314",
            "F315",
            "F3160",
            "F3161",
            "F3162",
            "F3163",
            "F3164",
            "F3170",
            "F3171",
            "F3172",
            "F3173",
            "F3174",
            "F3175",
            "F3176",
            "F3177",
            "F3178",
            "F3181",
            "F3189",
            "F319",
            "F322",
            "F323",
            "F332",
            "F333",
            "F440",
            "F441",
            "F4481",
            "F481",
            "F5000",
            "F5001",
            "F5002",
            "F502",
            "F600",
            "F601",
            "F602",
            "F603",
            "F604",
            "F605",
            "F606",
            "F607",
            "F6081",
            "F6089",
            "F609",
            "G47411",
            "G47419",
            "G47421",
            "G47429",
            "R4588",
            "T1491XA",
            "T360X2A",
            "T361X2A",
            "T362X2A",
            "T363X2A",
            "T364X2A",
            "T365X2A",
            "T366X2A",
            "T367X2A",
            "T368X2A",
            "T3692XA",
            "T370X2A",
            "T371X2A",
            "T372X2A",
            "T373X2A",
            "T374X2A",
            "T375X2A",
            "T378X2A",
            "T3792XA",
            "T380X2A",
            "T381X2A",
            "T382X2A",
            "T383X2A",
            "T384X2A",
            "T385X2A",
            "T386X2A",
            "T387X2A",
            "T38802A",
            "T38812A",
            "T38892A",
            "T38902A",
            "T38992A",
            "T39012A",
            "T39092A",
            "T391X2A",
            "T392X2A",
            "T39312A",
            "T39392A",
            "T394X2A",
            "T398X2A",
            "T3992XA",
            "T400X2A",
            "T401X2A",
            "T402X2A",
            "T403X2A",
            "T40412A",
            "T40422A",
            "T40492A",
            "T405X2A",
            "T40602A",
            "T40692A",
            "T40712A",
            "T40722A",
            "T408X2A",
            "T40902A",
            "T40992A",
            "T410X2A",
            "T411X2A",
            "T41202A",
            "T41292A",
            "T413X2A",
            "T4142XA",
            "T415X2A",
            "T420X2A",
            "T421X2A",
            "T422X2A",
            "T423X2A",
            "T424X2A",
            "T425X2A",
            "T426X2A",
            "T4272XA",
            "T428X2A",
            "T43012A",
            "T43022A",
            "T431X2A",
            "T43202A",
            "T43212A",
            "T43222A",
            "T43292A",
            "T433X2A",
            "T434X2A",
            "T43502A",
            "T43592A",
            "T43602A",
            "T43612A",
            "T43622A",
            "T43632A",
            "T43642A",
            "T43652A",
            "T43692A",
            "T438X2A",
            "T4392XA",
            "T440X2A",
            "T441X2A",
            "T442X2A",
            "T443X2A",
            "T444X2A",
            "T445X2A",
            "T446X2A",
            "T447X2A",
            "T448X2A",
            "T44902A",
            "T44992A",
            "T450X2A",
            "T451X2A",
            "T452X2A",
            "T453X2A",
            "T454X2A",
            "T45512A",
            "T45522A",
            "T45602A",
            "T45612A",
            "T45622A",
            "T45692A",
            "T457X2A",
            "T458X2A",
            "T4592XA",
            "T460X2A",
            "T461X2A",
            "T462X2A",
            "T463X2A",
            "T464X2A",
            "T465X2A",
            "T466X2A",
            "T467X2A",
            "T468X2A",
            "T46902A",
            "T46992A",
            "T470X2A",
            "T471X2A",
            "T472X2A",
            "T473X2A",
            "T474X2A",
            "T475X2A",
            "T476X2A",
            "T477X2A",
            "T478X2A",
            "T4792XA",
            "T480X2A",
            "T481X2A",
            "T48202A",
            "T48292A",
            "T483X2A",
            "T484X2A",
            "T485X2A",
            "T486X2A",
            "T48902A",
            "T48992A",
            "T490X2A",
            "T491X2A",
            "T492X2A",
            "T493X2A",
            "T494X2A",
            "T495X2A",
            "T496X2A",
            "T497X2A",
            "T498X2A",
            "T4992XA",
            "T500X2A",
            "T501X2A",
            "T502X2A",
            "T503X2A",
            "T504X2A",
            "T505X2A",
            "T506X2A",
            "T507X2A",
            "T508X2A",
            "T50902A",
            "T50912A",
            "T50992A",
            "T50A12A",
            "T50A22A",
            "T50A92A",
            "T50B12A",
            "T50B92A",
            "T50Z12A",
            "T50Z92A",
            "T510X2A",
            "T511X2A",
            "T512X2A",
            "T513X2A",
            "T518X2A",
            "T5192XA",
            "T520X2A",
            "T521X2A",
            "T522X2A",
            "T523X2A",
            "T524X2A",
            "T528X2A",
            "T5292XA",
            "T530X2A",
            "T531X2A",
            "T532X2A",
            "T533X2A",
            "T534X2A",
            "T535X2A",
            "T536X2A",
            "T537X2A",
            "T5392XA",
            "T540X2A",
            "T541X2A",
            "T542X2A",
            "T543X2A",
            "T5492XA",
            "T550X2A",
            "T551X2A",
            "T560X2A",
            "T561X2A",
            "T562X2A",
            "T563X2A",
            "T564X2A",
            "T565X2A",
            "T566X2A",
            "T567X2A",
            "T56812A",
            "T56822A",
            "T56892A",
            "T5692XA",
            "T570X2A",
            "T571X2A",
            "T572X2A",
            "T573X2A",
            "T578X2A",
            "T5792XA",
            "T5802XA",
            "T5812XA",
            "T582X2A",
            "T588X2A",
            "T5892XA",
            "T590X2A",
            "T591X2A",
            "T592X2A",
            "T593X2A",
            "T594X2A",
            "T595X2A",
            "T596X2A",
            "T597X2A",
            "T59812A",
            "T59892A",
            "T5992XA",
            "T600X2A",
            "T601X2A",
            "T602X2A",
            "T603X2A",
            "T604X2A",
            "T608X2A",
            "T6092XA",
            "T6102XA",
            "T6112XA",
            "T61772A",
            "T61782A",
            "T618X2A",
            "T6192XA",
            "T620X2A",
            "T621X2A",
            "T622X2A",
            "T628X2A",
            "T6292XA",
            "T63002A",
            "T63012A",
            "T63022A",
            "T63032A",
            "T63042A",
            "T63062A",
            "T63072A",
            "T63082A",
            "T63092A",
            "T63112A",
            "T63122A",
            "T63192A",
            "T632X2A",
            "T63302A",
            "T63312A",
            "T63322A",
            "T63332A",
            "T63392A",
            "T63412A",
            "T63422A",
            "T63432A",
            "T63442A",
            "T63452A",
            "T63462A",
            "T63482A",
            "T63512A",
            "T63592A",
            "T63612A",
            "T63622A",
            "T63632A",
            "T63692A",
            "T63712A",
            "T63792A",
            "T63812A",
            "T63822A",
            "T63832A",
            "T63892A",
            "T6392XA",
            "T6402XA",
            "T6482XA",
            "T650X2A",
            "T651X2A",
            "T65212A",
            "T65222A",
            "T65292A",
            "T653X2A",
            "T654X2A",
            "T655X2A",
            "T656X2A",
            "T65812A",
            "T65822A",
            "T65832A",
            "T65892A",
            "T6592XA",
            "T71112A",
            "T71122A",
            "T71132A",
            "T71152A",
            "T71162A",
            "T71192A",
            "T71222A",
            "T71232A",
            "X710XXA",
            "X711XXA",
            "X712XXA",
            "X713XXA",
            "X718XXA",
            "X719XXA",
            "X72XXXA",
            "X730XXA",
            "X731XXA",
            "X732XXA",
            "X738XXA",
            "X739XXA",
            "X7401XA",
            "X7402XA",
            "X7409XA",
            "X748XXA",
            "X749XXA",
            "X75XXXA",
            "X76XXXA",
            "X770XXA",
            "X771XXA",
            "X772XXA",
            "X773XXA",
            "X778XXA",
            "X779XXA",
            "X780XXA",
            "X781XXA",
            "X782XXA",
            "X788XXA",
            "X789XXA",
            "X79XXXA",
            "X80XXXA",
            "X810XXA",
            "X811XXA",
            "X818XXA",
            "X820XXA",
            "X821XXA",
            "X822XXA",
            "X828XXA",
            "X830XXA",
            "X831XXA",
            "X832XXA",
            "X838XXA",
        ]:
            return ["NA"]

    def _age_sex_edit_6(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 6 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age < 21) and dx_code in [
            "H353210",
            "H353211",
            "H353212",
            "H353213",
            "H353220",
            "H353221",
            "H353222",
            "H353223",
            "H353230",
            "H353231",
            "H353232",
            "H353233",
            "H353290",
            "H353291",
            "H353292",
            "H353293",
        ]:
            return ["NA"]

    def _age_sex_edit_7(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 7 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age > 0) and dx_code in [
            "P0500",
            "P0501",
            "P0502",
            "P0503",
            "P0504",
            "P0505",
            "P0506",
            "P0507",
            "P0508",
            "P0509",
            "P0510",
            "P0511",
            "P0512",
            "P0513",
            "P0514",
            "P0515",
            "P0516",
            "P0517",
            "P0518",
            "P0519",
            "P052",
            "P059",
            "P0700",
            "P0701",
            "P0702",
            "P0703",
            "P0710",
            "P0714",
            "P0715",
            "P0716",
            "P0717",
            "P0718",
            "P0720",
            "P0721",
            "P0722",
            "P0723",
            "P0724",
            "P0725",
            "P0726",
            "P0730",
            "P0731",
            "P0732",
            "P0733",
            "P0734",
            "P0735",
            "P0736",
            "P0737",
            "P0738",
            "P0739",
            "P080",
            "P081",
            "P0821",
            "P0822",
            "Z3800",
            "Z3801",
            "Z381",
            "Z382",
            "Z3830",
            "Z3831",
            "Z384",
            "Z385",
            "Z3861",
            "Z3862",
            "Z3863",
            "Z3864",
            "Z3865",
            "Z3866",
            "Z3868",
            "Z3869",
            "Z387",
            "Z388",
        ]:
            return ["NA"]

    def _age_sex_edit_8(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 8 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age >= 1) and dx_code == "Q894":
            return ["HHS_HCC097"]

    def _age_sex_edit_9(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 9 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age >= 2) and dx_code in [
            "K551",
            "K558",
            "K559",
            "P040",
            "P0411",
            "P0412",
            "P0413",
            "P0414",
            "P0415",
            "P0416",
            "P0417",
            "P0418",
            "P0419",
            "P041A",
            "P042",
            "P043",
            "P0440",
            "P0441",
            "P0442",
            "P0449",
            "P045",
            "P046",
            "P0481",
            "P0489",
            "P049",
            "P930",
            "P938",
            "P961",
            "P962",
            "Q390",
            "Q391",
            "Q392",
            "Q393",
            "Q394",
            "Q6410",
            "Q6411",
            "Q6412",
            "Q6419",
            "Q790",
            "Q791",
            "Q792",
            "Q793",
            "Q794",
            "Q7951",
        ]:
            return ["NA"]

    def _age_sex_edit_10(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 9 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age >= 2) and dx_code in ["P270", "P271", "P278", "P279"]:
            return ["HHS_HCC162"]

    def _age_sex_edit_11(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 11 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age < 6 or age > 18) and dx_code == "F3481":
            return ["NA"]

    def _age_sex_edit_12(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 11 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age >= 21) and dx_code in [
            "E700",
            "E701",
            "E7020",
            "E7021",
            "E7029",
            "E7030",
            "E70310",
            "E70311",
            "E70318",
            "E70319",
            "E70320",
            "E70321",
            "E70328",
            "E70329",
            "E70330",
            "E70331",
            "E70338",
            "E70339",
            "E7039",
            "E7040",
            "E7041",
            "E7049",
            "E705",
            "E7081",
            "E7089",
            "E709",
            "E710",
            "E71110",
            "E71111",
            "E71118",
            "E71120",
            "E71121",
            "E71128",
            "E7119",
            "E712",
            "E7130",
            "E71310",
            "E71311",
            "E71312",
            "E71313",
            "E71314",
            "E71318",
            "E7132",
            "E7139",
            "E7142",
            "E7150",
            "E71510",
            "E71511",
            "E71518",
            "E71520",
            "E71521",
            "E71522",
            "E71528",
            "E71529",
            "E7153",
            "E71540",
            "E71541",
            "E71542",
            "E71548",
            "E7200",
            "E7201",
            "E7202",
            "E7203",
            "E7204",
            "E7209",
            "E7210",
            "E7211",
            "E7212",
            "E7219",
            "E7220",
            "E7221",
            "E7222",
            "E7223",
            "E7229",
            "E723",
            "E724",
            "E7250",
            "E7251",
            "E7252",
            "E7253",
            "E7259",
            "E7281",
            "E7289",
            "E729",
            "E7420",
            "E7421",
            "E7429",
            "E744",
            "E74810",
            "E74818",
            "E74819",
            "E7489",
            "E749",
            "E771",
            "E8840",
            "E8841",
            "E8842",
            "E8843",
            "E8849",
            "H49811",
            "H49812",
            "H49813",
            "H49819",
        ]:
            return ["NA"]

    def _age_sex_edit_13(self, gender: str, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 13 to a diagnosis code.

        Args:
            gender (str): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if gender == "F" and dx_code in ["D66", "D67"]:
            return ["HHS_HCC075"]

    def _age_sex_edit_14(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 14 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age < 21) and dx_code in ["E10641", "E1011", "E1010"]:
            return ["HHS_HCC019"]

    def _age_sex_edit_15(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 15 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age < 21) and dx_code in [
            "E1022",
            "E1029",
            "E1021",
            "E1052",
            "E1059",
            "E1051",
            "E1041",
            "E1049",
            "E1044",
            "E1040",
            "E1043",
            "E1042",
            "E10610",
            "E10621",
            "E10620",
            "E10622",
            "E10618",
            "E10628",
            "E10638",
            "E10630",
            "E1069",
            "E103591",
            "E103412",
            "E103593",
            "E103559",
            "E103291",
            "E103552",
            "E103549",
            "E103393",
            "E103542",
            "E103539",
            "E10311",
            "E103219",
            "E103391",
            "E103532",
            "E103529",
            "E103531",
            "E103533",
            "E103392",
            "E103541",
            "E103543",
            "E103399",
            "E103551",
            "E10319",
            "E103553",
            "E103411",
            "E103292",
            "E103592",
            "E103413",
            "E103599",
            "E103523",
            "E103213",
            "E103319",
            "E103522",
            "E103521",
            "E103313",
            "E103519",
            "E103513",
            "E103212",
            "E103312",
            "E103512",
            "E103511",
            "E103311",
            "E103499",
            "E103211",
            "E103493",
            "E103492",
            "E1039",
            "E103299",
            "E103491",
            "E1037X9",
            "E1037X3",
            "E1037X2",
            "E1037X1",
            "E103293",
            "E103419",
            "E1036",
        ]:
            return ["HHS_HCC020"]

    def _age_sex_edit_16(self, age: int, dx_code: str) -> Union[List[str], None]:
        """
        Apply age and sex edit 16 to a diagnosis code.

        Args:
            age (int): Age of the individual.
            dx_code (str): Diagnosis code to apply the edit.

        Returns:
            Union[List[str], None]: List of categories after applying the edit, or None if the edit is not applicable.
        """
        if (age < 21) and dx_code in ["E108", "E1065", "E10649", "E109"]:
            return ["HHS_HCC021"]

    def _determine_interactions(
        self, categories: List[Type[Category]], beneficiary: Type[CommercialBeneficiary]
    ) -> List[Type[Category]]:
        """
        Determines disease interactions based on provided Category objects and beneficiary information.
        This is relevant only for the Adult and Child groups

        Args:
            categories (List[Type[Category]]): List of Category objects representing disease categories.
            beneficiary (Type[CommercialBeneficiary]): Instance of CommercialBeneficiary representing the beneficiary information.

        Returns:
            List[Type[Category]]: List of Category objects representing the disease interactions.
        """
        category_list = [
            category.category
            for category in categories
            if category.type in ["disease", "group", "rx"]
        ]

        severe_illness, transplant = self._determine_severe_illness_transplant_status(
            category_list
        )
        # RXC categories are excluded
        category_count = len(
            [
                category
                for category in category_list
                if not category.startswith("RXC") and category != "HHS_HCC022"
            ]
        )

        if beneficiary.risk_model_age_group == "Child":
            interaction_dict = self._determine_child_interactions(
                severe_illness, transplant, category_count
            )
        else:
            interaction_dict = self._determine_adult_interactions(
                category_list, severe_illness, transplant, category_count, beneficiary
            )

        interactions = [
            Category(
                reference_files=self.model_group_reference_files,
                risk_model_population=beneficiary.risk_model_population,
                category=category,
                mapper_codes=trigger_codes,
            )
            for category, trigger_codes in interaction_dict.items()
        ]
        interactions.extend(categories)

        return interactions

    def _determine_child_interactions(
        self, severe_illness: bool, transplant: bool, category_count: int
    ):
        """
        Determines the interaction categories for a child based on severe illness and transplant status.

        This function evaluates whether a child has severe illness or has undergone a transplant,
        and assigns interaction categories accordingly. It creates a dictionary of interaction
        categories based on the severity and the number of diagnosis categories.

        Args:
            severe_illness (bool): Indicates whether the child has a severe illness.
            transplant (bool): Indicates whether the child has undergone a transplant.
            category_count (int): The number of diagnosis categories associated with the child.

        Returns:
            dict: A dictionary with the interaction categories as keys and None as values.
                Possible keys include severe illness categories based on category count and
                a transplant category if applicable.

        Notes:
            - Severe illness categories are defined based on the category count:
                - "SEVERE_HCC_COUNT{count}" for counts <= 5
                - "SEVERE_HCC_COUNT6_7" for counts between 6 and 7
                - "SEVERE_HCC_COUNT8PLUS" for counts >= 8
            - A transplant category "TRANSPLANT_HCC_COUNT4PLUS" is assigned if the category count is 4 or more.
        """
        # Children only get the severe illness interactions and transplant

        interaction_dict = {}
        severe_category = None
        transplant_category = None
        if severe_illness:
            if category_count <= 5:
                severe_category = f"SEVERE_HCC_COUNT{category_count}"
            elif 6 <= category_count <= 7:
                severe_category = "SEVERE_HCC_COUNT6_7"
            elif category_count >= 8:
                severe_category = "SEVERE_HCC_COUNT8PLUS"
            # In the case of severe and count not including any trigger codes
            interaction_dict[severe_category] = None

        if transplant:
            if category_count >= 4:
                transplant_category = "TRANSPLANT_HCC_COUNT4PLUS"
                interaction_dict[transplant_category] = None

        return interaction_dict

    def _determine_infant_maturity_status(self, category_list, beneficiary):
        """
        Determines the maturity status of an infant based on their age and associated diagnosis categories.

        This function assesses the maturity status of an infant beneficiary by considering their age and
        the presence of specific diagnosis categories. It assigns a maturity status that reflects the
        infant's developmental stage.

        Args:
            category_list (List[str]): A list of diagnosis categories associated with the beneficiary.
            beneficiary (CommercialBeneficiary): An object representing the beneficiary being scored, containing demographic
                                                and other relevant information, including age.

        Returns:
            str: The maturity status of the infant. Possible values include:
                - "Age1" for infants aged 1 year or if no relevant categories are present
                - "Extremely_Immature" for specific categories indicating extreme immaturity
                - "Immature" for specific categories indicating immaturity
                - "Premature_Multiples" for categories indicating premature multiples
                - "Term" for the category indicating a term birth

        Notes:
            - The maturity status is determined based on the presence of specific diagnosis categories
            in the category_list.
            - If the infant is 1 year old, the maturity status is set to "Age1" regardless of the categories.
            - If no relevant categories are present in the category_list, the maturity status defaults to "Age1".
        """
        maturity_status = None

        # If infant is 1, then maturity status is Age1
        # else it checks the categories associated with birth to determine status
        if beneficiary.age == 1:
            maturity_status = "Age1"
        else:
            if any(
                category in category_list
                for category in ["HHS_HCC242", "HHS_HCC243", "HHS_HCC244"]
            ):
                maturity_status = "Extremely_Immature"
            elif any(
                category in category_list for category in ["HHS_HCC245", "HHS_HCC246"]
            ):
                maturity_status = "Immature"
            elif any(
                category in category_list for category in ["HHS_HCC247", "HHS_HCC248"]
            ):
                maturity_status = "Premature_Multiples"
            elif "HHS_HCC249" in category_list:
                maturity_status = "Term"
            elif all(
                category not in category_list
                for category in [
                    "HHS_HCC242",
                    "HHS_HCC243",
                    "HHS_HCC244",
                    "HHS_HCC245",
                    "HHS_HCC246",
                    "HHS_HCC247",
                    "HHS_HCC248",
                    "HHS_HCC249",
                ]
            ):
                maturity_status = "Age1"

        return maturity_status

    def _determine_infant_severity_level(self, category_list: List[str]):
        """
        Determines the severity level of an infant based on their associated diagnosis categories.

        This function evaluates the severity level of an infant beneficiary by checking the presence
        of specific diagnosis categories in the category_list. The severity level is assigned based
        on predefined severity categories.

        Args:
            category_list (List[str]): A list of diagnosis categories associated with the beneficiary.

        Returns:
            str: The severity level of the infant. Possible values include:
                - "Severity5" for the highest severity level
                - "Severity4" for high severity level
                - "Severity3" for moderate severity level
                - "Severity2" for low severity level
                - "Severity1" for the lowest severity level (default)

        Notes:
            - The function checks the presence of diagnosis categories in the following order:
            Severity5, Severity4, Severity3, Severity2, and Severity1.
            - The first matching severity level determines the severity status of the infant.
            - If no matching categories are found, the default severity status is "Severity1".
        """
        severity_5_hccs = [
            "HHS_HCC008",
            "HHS_HCC018",
            "HHS_HCC034",
            "HHS_HCC041",
            "HHS_HCC042",
            "HHS_HCC125",
            "HHS_HCC128",
            "HHS_HCC129",
            "HHS_HCC130",
            "HHS_HCC137",
            "HHS_HCC158",
            "HHS_HCC183",
            "HHS_HCC184",
            "HHS_HCC251",
        ]

        severity_4_hccs = [
            "HHS_HCC002",
            "HHS_HCC009",
            "HHS_HCC026",
            "HHS_HCC030",
            "HHS_HCC035_1",
            "HHS_HCC035_2",
            "HHS_HCC064",
            "HHS_HCC067",
            "HHS_HCC068",
            "HHS_HCC073",
            "HHS_HCC106",
            "HHS_HCC107",
            "HHS_HCC111",
            "HHS_HCC112",
            "HHS_HCC115",
            "HHS_HCC122",
            "HHS_HCC126",
            "HHS_HCC127",
            "HHS_HCC131",
            "HHS_HCC135",
            "HHS_HCC138",
            "HHS_HCC145",
            "HHS_HCC146",
            "HHS_HCC154",
            "HHS_HCC156",
            "HHS_HCC163",
            "HHS_HCC187",
            "HHS_HCC253",
        ]

        severity_3_hccs = [
            "HHS_HCC001",
            "HHS_HCC003",
            "HHS_HCC006",
            "HHS_HCC010",
            "HHS_HCC011",
            "HHS_HCC012",
            "HHS_HCC027",
            "HHS_HCC045",
            "HHS_HCC054",
            "HHS_HCC055",
            "HHS_HCC061",
            "HHS_HCC063",
            "HHS_HCC066",
            "HHS_HCC074",
            "HHS_HCC075",
            "HHS_HCC081",
            "HHS_HCC082",
            "HHS_HCC083",
            "HHS_HCC084",
            "HHS_HCC096",
            "HHS_HCC108",
            "HHS_HCC109",
            "HHS_HCC110",
            "HHS_HCC113",
            "HHS_HCC114",
            "HHS_HCC117",
            "HHS_HCC119",
            "HHS_HCC121",
            "HHS_HCC132",
            "HHS_HCC139",
            "HHS_HCC142",
            "HHS_HCC149",
            "HHS_HCC150",
            "HHS_HCC159",
            "HHS_HCC218",
            "HHS_HCC223",
            "HHS_HCC226",
            "HHS_HCC228",
        ]

        severity_2_hccs = [
            "HHS_HCC004",
            "HHS_HCC013",
            "HHS_HCC019",
            "HHS_HCC020",
            "HHS_HCC021",
            "HHS_HCC023",
            "HHS_HCC028",
            "HHS_HCC029",
            "HHS_HCC036",
            "HHS_HCC046",
            "HHS_HCC047",
            "HHS_HCC048",
            "HHS_HCC056",
            "HHS_HCC057",
            "HHS_HCC062",
            "HHS_HCC069",
            "HHS_HCC070",
            "HHS_HCC097",
            "HHS_HCC120",
            "HHS_HCC151",
            "HHS_HCC153",
            "HHS_HCC160",
            "HHS_HCC161_1",
            "HHS_HCC162",
            "HHS_HCC188",
            "HHS_HCC217",
            "HHS_HCC219",
        ]

        severity_1_hccs = [
            "HHS_HCC037_1",
            "HHS_HCC037_2",
            "HHS_HCC071",
            "HHS_HCC102",
            "HHS_HCC103",
            "HHS_HCC118",
            "HHS_HCC161_2",
            "HHS_HCC234",
            "HHS_HCC254",
        ]

        # In 2025 HHS_HCC071 is a higher severity
        if self.model_year == 2025:
            severity_1_hccs.remove("HHS_HCC071")
            severity_2_hccs.append("HHS_HCC071")

        severity_status = None

        if any(category in category_list for category in severity_5_hccs):
            severity_status = "Severity5"
        elif any(category in category_list for category in severity_4_hccs):
            severity_status = "Severity4"
        elif any(category in category_list for category in severity_3_hccs):
            severity_status = "Severity3"
        elif any(category in category_list for category in severity_2_hccs):
            severity_status = "Severity2"
        elif any(category in category_list for category in severity_1_hccs):
            severity_status = "Severity1"
        else:
            severity_status = "Severity1"

        return severity_status

    def _determine_adult_interactions(
        self,
        category_list: List[str],
        severe_illness: bool,
        transplant: bool,
        category_count: int,
        beneficiary: Type[CommercialBeneficiary],
    ) -> dict:
        """
        Determines the interaction categories for an adult beneficiary based on their diagnosis categories, severe illness, transplant status, and enrollment duration.

        This function evaluates various health conditions and their combinations to determine specific interaction categories. These interactions are based on the presence of certain diagnosis categories, severe illness, transplant status, and enrollment duration.

        Args:
            category_list (List[str]): A list of diagnosis categories associated with the beneficiary.
            severe_illness (bool): Indicates whether the beneficiary has a severe illness.
            transplant (bool): Indicates whether the beneficiary has undergone a transplant.
            category_count (int): The number of diagnosis categories associated with the beneficiary.
            beneficiary (CommercialBeneficiary): An object representing the beneficiary being scored, containing demographic and other relevant information.

        Returns:
            dict: A dictionary where keys are interaction categories and values are lists of triggering diagnosis categories.

        Notes:
            - Interaction categories are determined based on combinations of diagnosis categories related to liver, kidney, intestine, diabetes, autoimmune, and lung conditions.
            - Severe illness and transplant interaction categories are included based on the category count.
            - Enrollment duration interaction categories are also considered.
            - If certain interaction conditions are met, specific interaction categories are added to the dictionary with the relevant triggering categories.
        """
        liver = [
            category
            for category in [
                "HHS_HCC034",
                "HHS_HCC035_1",
                "HHS_HCC035_2",
                "HHS_HCC036",
                "HHS_HCC037_1",
            ]
            if category in category_list
        ]

        kidney = [
            category
            for category in ["HHS_HCC183", "HHS_HCC184", "HHS_HCC187", "HHS_HCC188"]
            if category in category_list
        ]

        intestine = [
            category
            for category in ["HHS_HCC041", "HHS_HCC048"]
            if category in category_list
        ]

        diabetes = [
            category
            for category in ["HHS_HCC018", "HHS_HCC019", "HHS_HCC020", "HHS_HCC021"]
            if category in category_list
        ]

        autoimmune = [
            category
            for category in ["HHS_HCC056", "HHS_HCC057"]
            if category in category_list
        ]

        lung = [
            category
            for category in ["HHS_HCC158", "HHS_HCC159"]
            if category in category_list
        ]

        # Keys will be interaction, values will be list of triggering categories
        interactions_dict = {}
        if all(category in category_list for category in ["RXC_01", "HHS_HCC001"]):
            interactions_dict["RXC_01_x_HCC001"] = ["RXC_01", "HHS_HCC001"]

        if all(["RXC_02" in category_list, liver]):
            interactions_dict["RXC_02_x_HCC037_1_036_035_2_035_1_034"] = [
                "RXC_02"
            ] + liver

        if all(category in category_list for category in ["RXC_03", "HHS_HCC142"]):
            interactions_dict["RXC_03_x_HCC142"] = ["RXC_03", "HHS_HCC142"]

        if all(["RXC_04" in category_list, kidney]):
            interactions_dict["RXC_04_x_HCC184_183_187_188"] = ["RXC_04"] + kidney

        if all(["RXC_05" in category_list, intestine]):
            interactions_dict["RXC_05_x_HCC048_041"] = ["RXC_05"] + intestine

        if all(["RXC_06" in category_list, diabetes]):
            interactions_dict["RXC_06_x_HCC018_019_020_021"] = ["RXC_06"] + diabetes

        if all(["RXC_07" in category_list, diabetes]):
            interactions_dict["RXC_07_x_HCC018_019_020_021"] = ["RXC_07"] + diabetes

        if all(category in category_list for category in ["RXC_08", "HHS_HCC118"]):
            interactions_dict["RXC_08_x_HCC118"] = ["RXC_08", "HHS_HCC118"]

        if all(["RXC_09" in category_list, autoimmune, intestine]):
            interactions_dict["RXC_09_x_HCC056_057_and_048_041"] = (
                ["RXC_09"] + autoimmune + intestine
            )

        if all(category in category_list for category in ["RXC_09", "HHS_HCC056"]):
            interactions_dict["RXC_09_x_HCC056"] = ["RXC_09", "HHS_HCC056"]

        if all(category in category_list for category in ["RXC_09", "HHS_HCC057"]):
            interactions_dict["RXC_09_x_HCC057"] = ["RXC_09", "HHS_HCC057"]

        if all(["RXC_09" in category_list, intestine]):
            interactions_dict["RXC_09_x_HCC048_041"] = ["RXC_09"] + intestine

        if all(["RXC_10" in category_list, lung]):
            interactions_dict["RXC_10_x_HCC159_158"] = ["RXC_10"] + lung

        if severe_illness:
            if category_count <= 9:
                severe_category = f"SEVERE_HCC_COUNT{category_count}"
                interactions_dict[severe_category] = None
            elif category_count >= 10:
                severe_category = "SEVERE_HCC_COUNT10PLUS"
                interactions_dict[severe_category] = None

        if transplant:
            if 4 <= category_count <= 7:
                transplant_category = f"TRANSPLANT_HCC_COUNT{category_count}"
                interactions_dict[transplant_category] = None
            elif category_count >= 8:
                transplant_category = "TRANSPLANT_HCC_COUNT8PLUS"
                interactions_dict[transplant_category] = None

        # Now do enrollment duration
        enrollment_duration = self._determine_enrollment_duration_category(
            category_count, beneficiary
        )
        if enrollment_duration:
            interactions_dict[enrollment_duration] = None

        return interactions_dict

    def _determine_severe_illness_transplant_status(self, category_list: List[str]):
        """
        Determines the severe illness and transplant status of a beneficiary based on their diagnosis categories.

        This function evaluates whether the beneficiary has a severe illness or has undergone a transplant by checking the presence of specific diagnosis categories in the category_list.

        Args:
            category_list (List[str]): A list of diagnosis categories associated with the beneficiary.

        Returns:
            tuple: A tuple containing two boolean values:
                - severe_illness (bool): True if the beneficiary has a severe illness, otherwise False.
                - transplant (bool): True if the beneficiary has undergone a transplant, otherwise False.

        Notes:
            - The function checks for specific diagnosis categories to determine the severe illness and transplant status.
            - Categories indicating severe illness include various HHS_HCC codes such as "HHS_HCC002", "HHS_HCC003", "HHS_HCC004", etc.
            - Categories indicating transplant include various HHS_HCC codes such as "HHS_HCC018", "HHS_HCC034", "HHS_HCC041", etc.
        """
        severe_illness = any(
            category in category_list
            for category in [
                "HHS_HCC002",
                "HHS_HCC003",
                "HHS_HCC004",
                "HHS_HCC006",
                "HHS_HCC018",
                "HHS_HCC023",
                "HHS_HCC034",
                "HHS_HCC041",
                "HHS_HCC042",
                "HHS_HCC096",
                "HHS_HCC121",
                "HHS_HCC122",
                "HHS_HCC125",
                # G13
                "HHS_HCC126",
                "HHS_HCC127",
                # G14
                "HHS_HCC128",
                "HHS_HCC129",
                ##
                "HHS_HCC135",
                "HHS_HCC145",
                "HHS_HCC156",
                "HHS_HCC158",
                "HHS_HCC163",
                "HHS_HCC183",
                "HHS_HCC218",
                "HHS_HCC223",
                "HHS_HCC251",
            ]
        )
        transplant = any(
            category in category_list
            for category in [
                "HHS_HCC018",
                "HHS_HCC034",
                "HHS_HCC041",
                # G14
                "HHS_HCC128",
                "HHS_HCC129",
                ##
                "HHS_HCC158",
                "HHS_HCC183",
                "HHS_HCC251",
            ]
        )

        return severe_illness, transplant

    def _determine_enrollment_duration_category(self, category_count: int, beneficiary):
        """
        Determines the enrollment duration category for a beneficiary based on their category count and enrollment duration.

        This function evaluates the enrollment duration category for a beneficiary if the category count is greater than 0 and the enrollment duration (in months) is 6 or less.

        Args:
            category_count (int): The number of diagnosis categories associated with the beneficiary.
            beneficiary: An object representing the beneficiary being scored, containing demographic and other relevant information, including enrollment months.

        Returns:
            Union[str, None]: The enrollment duration category if applicable, otherwise None.

        Notes:
            - The function returns an enrollment duration category in the format "HCC_ED{months}" if the beneficiary has more than 0 categories and their enrollment duration is 6 months or less.
        """
        enrollment_duration_category = None
        if category_count > 0:
            if beneficiary.enrollment_months <= 6:
                enrollment_duration_category = f"HCC_ED{beneficiary.enrollment_months}"
        return enrollment_duration_category

    def _determine_age_gender_category(self, age: int, gender: str) -> str:
        """
        Determines the demographic category based on age, gender, and population.

        Args:
            age (int): Age of the individual.
            gender (str): Gender of the individual ('M' for male, 'F' for female).
            population (str): Beneficiary model population used for scoring

        Returns:
            str: Demographic category based on age, gender, and population.
        """

        if age < 2:
            if gender == "F":
                demographic_category = None
            else:
                demographic_category = f"Age{age}_Male"
        else:
            demo_category_ranges = [
                "2_4",
                "5_9",
                "10_14",
                "15_20",
                "21_24",
                "25_29",
                "30_34",
                "35_39",
                "40_44",
                "45_49",
                "50_54",
                "55_59",
                "60_GT",
            ]

            demographic_category_range = determine_age_band(age, demo_category_ranges)
            demographic_category = f"{gender}AGE_LAST_{demographic_category_range}"

        return demographic_category

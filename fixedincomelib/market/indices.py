import os, csv
from typing import Dict, Self
import pandas as pd
# in-house
from fixedincomelib.market.basics import *
from fixedincomelib.market.interfaces import *


### IBOR Index
class IBORIndex(ql.IborIndex, Index):

    _type = "IBOR INDEX"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        ## key properties
        self.from_ql_ = True
        # mandatory
        self.currency_ = None
        self.term_ = None
        self.accrual_basis_ = None
        self.payment_business_day_conv_ = None
        self.payment_holiday_conv_ = None
        self.end_of_month_ = False
        # either
        self.fixing_functor_ = None
        # or
        self.settlement_offset_ = None
        self.settlement_holiday_ = None

        ## populate convention either from ql.index or user inputs
        assert "term" in content
        self.term_ = Period(content["term"])
        assert "convention" in content
        upper_content = dict()
        upper_content["TERM"] = Period.to_string(self.term_)
        if isinstance(content["convention"], str):
            # populate schema from existing index 
            index : ql.IborIndex = getattr(ql, content["convention"])(self.term_)
            self.currency_ : Currency = index.currency()
            upper_content["CURRENCY"] = self.currency_.code()
            self.fixing_functor_ = index.fixingDate
            upper_content["FIXING FUNCTOR"] = "FIXINGDATE_FUNCTOR"
            self.accrual_basis_ = index.dayCounter()
            upper_content["ACCRUAL BASIS"] = AccrualBasis.to_string(self.accrual_basis_)
            self.payment_business_day_conv_ = index.businessDayConvention()
            upper_content["PAYMENT BUSINESSDAY CONVENTION"] = BusinessDayConvention.to_string(self.payment_business_day_conv_)
            self.settlement_holiday_ = self.payment_holiday_conv_ = index.fixingCalendar()
            upper_content["PAYMENT HOLIDAY CONVENTION"] = HolidayConvention.to_string(self.payment_holiday_conv_)
            self.end_of_month_ =  index.endOfMonth()
            upper_content["END OF MONTH"] = self.end_of_month_
            upper_content["SETTLEMENT OFFSET"] = "NOT_USED"
            upper_content["SETTLEMENT HOLIDAY"] = upper_content["PAYMENT HOLIDAY CONVENTION"]
        else:
            self.from_ql_ = False
            v : dict = content["convention"]
            upper_content.update({k.upper(): v for k, v in v.items()})
            for k, v in upper_content.items():
                if k == "CURRENCY":
                    self.currency_ = Currency(v)
                elif k == "PAYMENT BUSINESSDAY CONVENTION":
                    self.payment_business_day_conv_ = BusinessDayConvention.new(v)
                elif k == "PAYMENT HOLIDAY CONVENTION":
                    self.payment_holiday_conv_ = HolidayConvention.new(v)
                elif k == "ACCRUAL BASIS":
                    self.accrual_basis_ = AccrualBasis.new(v)
                elif k == "SETTLEMENT OFFSET":
                    self.settlement_offset_ = Period(v)
                elif k == "SETTLEMENT HOLIDAY":
                    self.settlement_holiday_ = HolidayConvention.new(v)
                elif k == "END OF MONTH":
                    self.end_of_month_ = bool(v)
            upper_content["FIXING FUNCTOR"] = "NOT_USED" 
        Index.__init__(self, unique_name, upper_content)

    @property
    def from_ql(self) -> bool:
        return self.from_ql_

    @property
    def term(self) -> Period:
        return self.term_

    @property
    def currency(self) -> Currency:
        return self.currency_
    
    def fixingDate(self, input_dt : Date) -> Any:
        return self.fixing_functor_(input_dt)

    @property
    def term(self) -> Period:
        return self.term_

    def tenor(self) -> Period:
        return self.term_

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_ # can be none!
    
    @property
    def settlement_holiday(self) -> ql.Calendar:
        return self.settlement_holiday_
    
    @property
    def business_day_convention(self) -> int:
        return self.payment_business_day_conv_
    
    @property
    def holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_
    
    @property
    def payment_business_day_conv(self) -> int:
        return self.payment_business_day_conv_

    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_

### Overnight Index
class OvernightIndex(ql.OvernightIndex, Index):

    _type = "OVERNIGHT INDEX"

    def __init__(self, unique_name : str, content : Dict[str, str]):
    
        ### key properties
        self.from_ql_ = True
        # mandatory
        self.currency_ = None
        self.term_ = Period("1D")
        self.accrual_basis_ = None
        self.payment_business_day_conv_ = None
        self.payment_holiday_conv_ = None
        self.end_of_month_ = False
        # either
        self.fixing_functor_ = None
        # or
        self.settlement_offset_ = None
        self.settlement_holiday_ = None

        # 
        self.business_day_convention_ = None

        ### populate convention either from ql.index or user inputs
        assert "convention" in content
        upper_content = dict()
        upper_content["TERM"] = Period.to_string(self.term_)
        if isinstance(content["convention"], str):
            # from existing index
            index : ql.OvernightIndex = getattr(ql, content["convention"])()
            self.currency_ = index.currency()
            upper_content["CURRENCY"] = self.currency_.code()
            self.fixing_functor_ = index.fixingDate
            upper_content["FIXING FUNCTOR"] = "FIXINGDATE_FUNCTOR"
            self.accrual_basis_ = index.dayCounter()
            upper_content["ACCRUAL BASIS"] = AccrualBasis.to_string(self.accrual_basis_)
            self.payment_business_day_conv_ = index.businessDayConvention()
            upper_content["PAYMENT BUSINESSDAY CONVENTION"] = BusinessDayConvention.to_string(self.payment_business_day_conv_)
            self.settlement_holiday_ = self.payment_holiday_conv_ = index.fixingCalendar()
            upper_content["PAYMENT HOLIDAY CONVENTION"] = HolidayConvention.to_string(self.payment_holiday_conv_)
            self.end_of_month_ =  index.endOfMonth()
            upper_content["END OF MONTH"] = self.end_of_month_
            upper_content["SETTLEMENT OFFSET"] = "NOT USED"
            upper_content["SETTLEMENT HOLIDAY"] = upper_content["PAYMENT HOLIDAY CONVENTION"]

        else:
            self.from_ql_ = False
            v : dict = content["convention"]
            upper_content.update({k.upper(): v for k, v in v.items()})
            for k, v in upper_content.items():
                if k == "CURRENCY":
                    self.currency_ = Currency(v)
                elif k == "PAYMENT BUSINESSDAY CONVENTION":
                    self.payment_business_day_conv_ = BusinessDayConvention.new(v)
                elif k == "PAYMENT HOLIDAY CONVENTION":
                    self.payment_holiday_conv_ = HolidayConvention.new(v)
                elif k == "ACCRUAL BASIS":
                    self.accrual_basis_ = AccrualBasis.new(v)
                elif k == "SETTLEMENT OFFSET":
                    self.settlement_offset_ = Period(v)
                elif k == "SETTLEMENT HOLIDAY":
                    self.settlement_holiday_ = HolidayConvention.new(v)
                elif k == "END OF MONTH":
                    self.end_of_month_ = bool(v)
            upper_content["FIXING FUNCTOR"] = "NONE" 

        Index.__init__(self, unique_name, upper_content)

    @property
    def from_ql(self) -> bool:
        return self.from_ql_

    @property
    def term(self) -> Period:
        return self.term_

    @property
    def currency(self) -> Currency:
        return self.currency_
    
    def fixingDate(self, input_dt : Date) -> Any:
        return self.fixing_functor_(input_dt)

    @property
    def term(self) -> Period:
        return self.term_

    def tenor(self) -> Period:
        return self.term_

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday(self) -> ql.Calendar:
        return self.settlement_holiday_
    
    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_
    
    @property
    def business_day_convention(self) -> int:
        return self.payment_business_day_conv_
    
    @property
    def payment_business_day_conv(self) -> int:
        return self.payment_business_day_conv_

    @property
    def holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_
    
    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_

### Overnight Composite Index
class OvernightCompositeIndex(Index):

    _type = "OVERNIGHT COMPOSITE INDEX"

    def __init__(self, unique_name : str, content : Dict[str, str]):
    
        ### key properties
        # mandatory
        self.index_ = None
        self.compound_method_ = None

        ### populate convention either from ql.index or user inputs
        assert "convention" in content
        v : dict = content["convention"]
        upper_content = {k.upper(): v for k, v in v.items()}
        for k, v in upper_content.items():
            if k == "INDEX":
                self.index_ = v
            elif k == "COMPOUND METHOD":
                self.compound_method_ = CompoundingMethod.from_string(v)

        Index.__init__(self, unique_name, upper_content)


    @property
    def index(self) -> OvernightIndex:
        return IndexRegistry().get(self.index_)
    
    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compound_method_
    
    ### delegate to underlying index
    @property
    def from_ql(self) -> bool:
        return self.index.from_ql

    @property
    def currency(self) -> Currency:
        return self.index.currency
    
    def fixingDate(self, input_dt : Date) -> Any:
        return self.index.fixingDate(input_dt)

    @property
    def settlement_offset(self) -> Period:
        return self.index.settlement_offset
    
    @property
    def settlement_holiday(self) -> ql.Calendar:
        return self.index.settlement_holiday
    
    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.index.accrual_basis
    
    @property
    def business_day_conv(self) -> int:
        return self.index.business_day_convention
    
    @property
    def holiday_convention(self) -> int:
        return self.index.payment_business_day_conv
    
    @property
    def payment_business_day_conv(self) -> int:
        return self.index.payment_business_day_conv
    
    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.index.payment_holiday_conv

    @property
    def end_of_month(self) -> bool:
        return self.index.end_of_month

### FX Index
class FXIndex(Index):

    _type = "FX INDEX"

    def __init__(self, unique_name : str, content : Dict[str, str]):

        assert len(content["convention"]) == 9

        self.base_ccy_ = None
        self.base_business_day_conv_ = None
        self.base_holidays_ = None
        self.base_fixing_offset_ = None
        self.quoted_ccy_ = None
        self.quoted_business_day_conv_ = None
        self.quoted_holidays_ = None
        self.quoted_fixing_offset_ = None
        self.premium_ccy_ = None
        
        upper_content = {k.upper(): v for k,v in content["convention"].items()}
        for k, v in upper_content.items():
            if k == "BASE CURRENCY":
                self.base_ccy_ = v
            elif k == "BASE BUSINESSDAY CONVENTION":
                self.base_business_day_conv_ = v
            elif k == "BASE HOLIDAYS":
                self.base_holidays_ = v
            elif k == "BASE FIXING OFFSET":
                self.base_fixing_offset_ = v
            elif k == "QUOTED CURRENCY":
                self.quoted_ccy_ = v
            elif k == "QUOTED BUSINESSDAY CONVENTION":
                self.quoted_business_day_conv_ = v
            elif k == "QUOTED HOLIDAYS":
                self.quoted_holidays_ = v
            elif k == "QUOTED FIXING OFFSET":
                self.quoted_fixing_offset_ = v
            elif k == "PREMIUM CURRENCY":
                self.premium_ccy_ = v

        super().__init__(unique_name, self.__dict__.copy())

    @property
    def base_ccy(self) -> Currency:
        return Currency(self.base_ccy_)
    
    @property
    def base_business_day_conv(self) -> int:
        return BusinessDayConvention.new(self.base_business_day_conv_)
    
    @property
    def base_holidays(self) -> ql.Calendar:
        return HolidayConvention.new(self.base_holidays_)

    @property
    def base_fixing_offset(self) -> Period:
        return Period(self.base_fixing_offset_)
    
    @property
    def quoted_ccy(self) -> Currency:
        return Currency(self.quoted_ccy_)
    
    @property
    def quoted_business_day_conv(self) -> int:
        return BusinessDayConvention.new(self.quoted_business_day_conv_)
    
    @property
    def quoted_holidays(self) -> ql.Calendar:
        return HolidayConvention.new(self.quoted_holidays_)

    @property
    def quoted_fixing_offset(self) -> Period:
        return Period(self.quoted_fixing_offset_)
    
    @property
    def premium_ccy(self) -> Currency:
        return Currency(self.premium_ccy_)

    def currency(self) -> Currency:
        return self.base_ccy

### Registry
class IndexRegistry(Registry):

    def __new__(cls) -> Self:
        return super().__new__(cls, "indices", "Index", "yaml")

    def register(self, key: str, value: Any) -> None:
        super().register(key, value)
        func = IndexRegFunction().get(value["type"])
        self._map[key.upper()] = func(key, value)

    def get(self, key: str, **args) -> Index:
        if key.upper() not in self._map:
            raise Exception(f"Cannot find {key} in index registry.")
        return self._map[key.upper()]

    def display_all_indices(self) -> pd.DataFrame:
        to_print = []
        for k, _ in self._map.items():
            index: Index = self.get(k)
            index_name = index.index_name()
            index_type = index.type()
            to_print.append([index_type, index_name])
        return pd.DataFrame(to_print, columns=["Type", "Indices"])

class IndexFixingsManager(Registry):

    _fixing_path = ""

    def __new__(cls) -> Self:
        
        if cls._instance is None:
            # init
            obj = super().__new__(cls, "", "", "yaml")
            obj._map = dict()
            # read files
            this_config = get_config()
            cls._fixing_path = this_config["fixing source"]
            for file_name in os.listdir(cls._fixing_path):
                file = os.path.join(cls._fixing_path, file_name)
                if os.path.exists(file):
                    obj.register(file_name, "")
            # finalize
            cls._instance = obj
            cls._registry_type = "IndexFixings"
        return cls._instance

    def register(self, key: str, value: Any) -> None:
        super().register(key, value)
        this_path = os.path.join(self._fixing_path, key)
        index_name = key.replace('.csv', '')
        with open(this_path, newline="") as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for this_line in csv_reader:
                fixing_date = Date(dt.datetime.strptime(this_line["date"], "%Y-%m-%d").date())
                self._map.setdefault(index_name.upper(), {})[fixing_date] = float(this_line["fixing"])

    def insert_fixing(self, index: str, date: Date, fixing: float):
        this_map = self.get(index.lower())
        if date in this_map:
            return
        else:
            this_map[date] = fixing

    def exist_fixing(self, index: str, date: Date):
        this_map = self.get(index.lower())
        return date in this_map

    def get_fixing(self, index: str, date: Date):
        this_map = self.get(index.lower())
        if date in this_map:
            return this_map[date]
        else:
            raise Exception(f"Cannot find {index} for date {date.ISO()}")

    def remove_fixing(self, index: str, date: Optional[Date] = None):
        if date is None:
            self.erase(index)
        else:
            this_map: dict = self.get(index)
            this_map.pop(Date(date))

### registry
IndexRegFunction().register(IBORIndex._type, IBORIndex)
IndexRegFunction().register(OvernightIndex._type, OvernightIndex)
IndexRegFunction().register(OvernightCompositeIndex._type, OvernightCompositeIndex)
IndexRegFunction().register(FXIndex._type, FXIndex)
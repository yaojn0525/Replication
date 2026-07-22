from enum import Enum
from typing import Optional, Any
import QuantLib as ql
from fixedincomelib.utilities import noramlize_surrogated_str

### wrapper
class Currency(ql.Currency):

    def __init__(self, ccy_str : Optional[str]="INVALID"):
        if ccy_str.upper() == "INVALID":
            super().__init__()
        else:
            this_ccy : ql.Currency = getattr(ql, f"{ccy_str}Currency")()
            m_args = (
                this_ccy.name(), 
                this_ccy.code(), 
                this_ccy.numericCode(), 
                noramlize_surrogated_str(this_ccy.symbol()), 
                noramlize_surrogated_str(this_ccy.fractionSymbol()),
                this_ccy.fractionsPerUnit(), 
                this_ccy.rounding(),
                this_ccy.triangulationCurrency())
            super().__init__(*m_args)
    
    def is_valid(self):
        return not self.empty()

    @classmethod
    def to_string(cls, ccy : ql.Currency) -> str:
        return ccy.code()

### factory
class BusinessDayConvention:

    BDC_MAP = {
        "F" : ql.Following,
        "MF" : ql.ModifiedFollowing,
        "P" : ql.Preceding,
        "NONE" : ql.Preceding
    }

    @classmethod
    def new(cls, input : Optional[str]="NONE"):
        if input.upper() in BusinessDayConvention.BDC_MAP:
            return BusinessDayConvention.BDC_MAP[input.upper()]
        else:
            raise Exception(f"{input} is not current supported business day convention.")
    
    @classmethod
    def to_string(cls, bdc : Any):
        for k, v in BusinessDayConvention.BDC_MAP.items():
            if bdc == v:
                return k.upper()
        return "NONE"
    
    @classmethod
    def is_valid(cls, bdc : Any):
        return bdc != ql.Unadjusted

### factory
class HolidayConvention:
    
    HDC_MAP = {
        'NONE': ql.NullCalendar(),
        'NYC':  ql.UnitedStates(ql.UnitedStates.LiborImpact),
        'TOR':  ql.Canada(),
        'USGS': ql.UnitedStates(ql.UnitedStates.FederalReserve),
        'LON':  ql.UnitedKingdom(ql.UnitedKingdom.Exchange),
        'TOK':  ql.Japan(),
        'TARGET': ql.JointCalendar(ql.TARGET(), ql.France(), ql.Germany(), ql.Italy()),
        'SYD':  ql.Australia(),
    }

    @classmethod
    def new(cls, input : Optional[str]="NONE") -> ql.Calendar:
        calendars = []
        for hol in input.split(','):
            this_hol = hol.strip().upper()
            if this_hol not in cls.HDC_MAP:
                raise Exception(f"{this_hol} is not a supported Holiday Center.")
            calendars.append(cls.HDC_MAP[this_hol])
        if len(calendars) == 1:
            return calendars[0]
        else:
             return ql.JointCalendar(calendars)           
    
    @classmethod
    def to_string(cls, hdc : ql.Calendar):
        for k, v in HolidayConvention.HDC_MAP.items():
            if hdc == v:
                return k.upper()
        return "NONE"
    
    @classmethod
    def is_valid(cls, hdc : ql.Calendar):
        return hdc != ql.NullCalendar()
 
### factory
class AccrualBasis:

    DAY_COUNTER_MAP = {
        "NONE" : ql.SimpleDayCounter(),
        "SIMPLE" : ql.SimpleDayCounter(),
        "ACTUAL/360" : ql.Actual360(),
        "30/360 (US)" : ql.Thirty360(ql.Thirty360.USA),
        "30/360 (BOND BASIS)" : ql.Thirty360(ql.Thirty360.BondBasis),
        "30E/360 (EURBOND BASIS)" : ql.Thirty360(ql.Thirty360.European),
        "30/360 (ITALIAN)" : ql.Thirty360(ql.Thirty360.Italian),
        "30E/360 (ISDA)" : ql.Thirty360(ql.Thirty360.ISDA),        
        "30/360 (NASD)" : ql.Thirty360(ql.Thirty360.NASD),        
        "ACTUAL/ACTUAL (ISMA)" : ql.ActualActual(ql.ActualActual.Bond),
        "ACTUAL/ACTUAL (ISDA)" : ql.ActualActual(ql.ActualActual.ISDA),
        "ACTUAL/ACTUAL (AFB)" : ql.ActualActual(ql.ActualActual.AFB), # euro
        "ACTUAL/365 (FIXED)" : ql.Actual365Fixed(ql.Actual365Fixed.Standard),
        "ACTUAL/365 (FIXED) CANADIAN BOND" : ql.Actual365Fixed(ql.Actual365Fixed.Canadian),
        "ACTUAL/365 (NO LEAP)" : ql.Actual365Fixed(ql.Actual365Fixed.NoLeap),
        "BUSINESS/252(BRAZIL)" : ql.Business252()
    }
    
    @classmethod
    def new(self, input_str : Optional[str]="NONE") -> ql.DayCounter:
        if input_str.upper() in AccrualBasis.DAY_COUNTER_MAP:
            return AccrualBasis.DAY_COUNTER_MAP[input_str.upper()]
        else:
            raise Exception(f"Does not support day counter with accrual basis {input_str}.")

    @classmethod
    def to_string(cls, day_counter : ql.DayCounter):
        return day_counter.__str__().replace(" day counter", "") 

### customized enum
class CompoundingMethod(Enum):

    SIMPLE = "simple"
    CONTINUOUS = "continuous"
    ARITHMETIC = "arithmetic"
    COMPOUND = "compound"
    FLAT_COMPOUND = "flat_compound"
    SPREAD_EXCLUSIVE_COMPOUND = "spread_exclusive_compound"

    @classmethod
    def from_string(cls, value: str) -> "CompoundingMethod":
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid token: {value}")

    def to_string(self) -> str:
        return self.value
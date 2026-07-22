from enum import Enum
import QuantLib as ql
# in-house
from fixedincomelib.date import *
from fixedincomelib.market import *

class LongOrShort(Enum):
    
    LONG = 'long'
    SHORT = 'short'

    @classmethod
    def from_string(cls, value: str) -> 'LongOrShort':
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid token: {value}")

    def to_string(self) -> str:
        return self.value

class PayOrReceive(Enum):
    
    PAY = 'pay'
    RECEIVE = 'receive'

    @classmethod
    def reverse(cls, pay_or_rec : "PayOrReceive"):
        return PayOrReceive.RECEIVE if pay_or_rec == PayOrReceive.PAY else PayOrReceive.PAY

    @classmethod
    def from_string(cls, value: str) -> 'PayOrReceive':
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid token: {value}")

    def to_string(self) -> str:
        return self.value

def resolve_schedule_generation(generation_code : int|str) -> int:
    if isinstance(generation_code, int):
        return ql.DateGeneration.Backward if generation_code == 0 else ql.DateGeneration.Forward
    elif isinstance(generation_code, str):
        return ql.DateGeneration.Backward if generation_code.upper() == "BACKWARD" else ql.DateGeneration.Forward
    else:
        raise Exception("Cannot resolve schedule generation rule.")
    
def add_period_by_index(
        start_date : Date, 
        term : Period, 
        index : OvernightIndex | OvernightCompositeIndex | IBORIndex) -> Date:
    
    return add_period(
        start_date, 
        term, 
        index.payment_business_day_conv, 
        index.settlement_holiday, 
        index.end_of_month)
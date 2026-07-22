from typing import Any, Optional, Dict

from sympy import N
# in house
from fixedincomelib.market.basics import *
from fixedincomelib.market.interfaces import *
from fixedincomelib.market.indices import *
from fixedincomelib.market.funding_identifiers import *

#########################################################

# basics
class DataConventionInstantaneousForwardRate(DataConvention):

    _type = "INSTANTANEOUS FORWARD RATE"

    def __init__(self, unique_name : str, content : Dict[str, str]):

        valid_count = 1
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.index_ : Index = None
        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k.upper() == "INDEX":
                if IndexRegistry().exists(v):
                    self.index_ = IndexRegistry().get(v)
                elif FundingIdentifierRegistry().exists(v):
                    self.index_ = FundingIdentifierRegistry().get(v)
                else:
                    raise Exception(f"Invalid index {v}.")

        super().__init__(unique_name, upper_content)

    @property
    def index(self) -> Index:
        return self.index_

# tick
class DataConventionFRAOrFixing(DataConvention):

    _type = "FRA OR FIXING"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 10
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.index_ : IBORIndex|OvernightIndex = None
        self.accrual_basis_ : ql.DayCounter = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        self.fra_style_ : str = None
        self.end_of_month_ : bool = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "INDEX":
                self.index_ = IndexRegistry().get(v)
            elif k == "ACCRUAL BASIS":
                self.accrual_basis_ = AccrualBasis.new(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)
            elif k == "FRA STYLE":
                self.fra_style_ = v
                assert v.upper() in ["ISDA", "AFMA"]
            elif k == "END OF MONTH":
                self.end_of_month_ = bool(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> int:
        return self.settlement_holiday_convention_
    
    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def index(self) -> IBORIndex|OvernightIndex:
        return self.index_

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
    def fra_style(self) -> str:
        return self.fra_style_
    
    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_

# tick
class DataConventionOvernightIndexFuture(DataConvention):

    _type = "OVERNIGHT INDEX FUTURE"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 8
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.currency_ : Currency = None
        self.contractual_notional_ : float = None
        self.index_ : OvernightCompositeIndex = None
        self.rate_cutoff_ : Period = None
        self.payment_offset_ : Period = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        self.basis_point_ : float = None

        self.notional_ = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "CONTRACTUAL NOTIONAL":
                self.notional_ = self.contractual_notional_ = float(v)
            elif k == "INDEX":
                self.index_ = IndexRegistry().get(v)
            elif k == "RATE CUTOFF":
                self.rate_cutoff_ = Period(v)
            elif k == "PAYMENT OFFSET":
                self.payment_offset_ = Period(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)
            elif k == "BASIS POINT":
                self.basis_point_ = float(v)

        super().__init__(unique_name, upper_content)

    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def contractual_notional(self) -> float:
        return self.contractual_notional_

    @property
    def index(self) -> OvernightCompositeIndex:
        return self.index_

    @property
    def rate_cutoff(self) -> Period:
        return self.rate_cutoff_

    @property
    def payment_offset(self) -> Period:
        return self.payment_offset_

    @property
    def payment_business_day_convention(self) -> int:
        return self.payment_business_day_conv_

    @property
    def payment_holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def basis_point(self) -> float:
        return self.basis_point_

# tick
class DataConventionOvernightIndexSwap(DataConvention):

    _type = "OVERNIGHT INDEX SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 11
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.accrual_period_ : Period = None
        self.accrual_basis_ : ql.DayCounter = None
        self.index_ : OvernightCompositeIndex = None
        self.rate_cutoff_ : Period = None
        self.payment_offset_ : Period = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "ACCRUAL PERIOD":
                self.accrual_period_ = Period(v)
            elif k == "ACCRUAL BASIS":
                self.accrual_basis_ = AccrualBasis.new(v)
            elif k == "INDEX":
                self.index_ = IndexRegistry().get(v)
            elif k == "RATE CUTOFF":
                self.rate_cutoff_ = Period(v)
            elif k == "PAYMENT OFFSET":
                self.payment_offset_ = Period(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> int:
        return self.settlement_holiday_convention_
    
    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def accrual_period(self) -> Period:
        return self.accrual_period_

    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_

    @property
    def index(self) -> OvernightCompositeIndex:
        return self.index_
    
    @property
    def rate_cutoff(self) -> Period:
        return self.rate_cutoff_
    
    @property
    def payment_offset(self) -> Period:
        return self.payment_offset_

    @property
    def payment_business_day_conv(self) -> int:
        return self.payment_business_day_conv_
    
    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.payment_holiday_conv_

# tick
# overnight composite over ibor
class DataConventionOvernightIndexBasisSwap(DataConvention):

    _type = "OVERNIGHT INDEX BASIS SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):

        valid_count = 11
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.on_index_ : OvernightCompositeIndex = None
        self.rate_cutoff_ : Period = None
        self.ibor_index_ : IBORIndex = None
        self.payment_offset_ : Period = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        self.accrual_period_ : Period = None

        upper_content : Dict[str, str] = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "OVERNIGHT COMPOSITE INDEX":
                self.on_index_ = IndexRegistry().get(v)
            elif k == "RATE CUTOFF":
                self.rate_cutoff_ = Period(v)
            elif k == "IBOR INDEX":
                self.ibor_index_ = IndexRegistry().get(v)
            elif k == "PAYMENT OFFSET":
                self.payment_offset_ = Period(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)
            elif k == "ACCRUAL PERIOD":
                self.accrual_period_ = Period(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_
    
    @property
    def currency(self) -> Currency:
        return self.currency_
    
    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def on_index(self) -> OvernightCompositeIndex:
        return self.on_index_
    
    @property
    def rate_cutoff(self) -> Period:
        return self.rate_cutoff_
    
    @property
    def ibor_index(self) -> IBORIndex:
        return self.ibor_index_
    
    @property
    def payment_offset(self) -> Period:
        return self.payment_offset_
    
    @property
    def payment_business_day_convention(self) -> int:
        return self.payment_business_day_conv_

    @property
    def payment_holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def accrual_period(self) -> Period:
        return self.accrual_period_

# tick
# overnight composite over overnight composite
class DataConventionOISBasisSwap(DataConvention):

    _type = "OIS BASIS SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):

        valid_count = 12
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.basis_on_index_ : OvernightCompositeIndex = None
        self.rate_cutoff_ : Period = None
        self.reference_on_index_ : OvernightCompositeIndex = None
        self.payment_offset_ : Period = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        self.basis_accrual_period_ : Period = None
        self.reference_accrual_period_ : Period = None

        upper_content : Dict[str, str] = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "BASIS OVERNIGHT COMPOSITE INDEX":
                self.basis_on_index_ = IndexRegistry().get(v)
            elif k == "RATE CUTOFF":
                self.rate_cutoff_ = Period(v)
            elif k == "REFERENCE OVERNIGHT COMPOSITE INDEX":
                self.reference_on_index_ = IndexRegistry().get(v)
            elif k == "PAYMENT OFFSET":
                self.payment_offset_ = Period(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)
            elif k == "BASIS ACCRUAL PERIOD":
                self.basis_accrual_period_ = Period(v)
            elif k == "REFERENCE ACCRUAL PERIOD":
                self.reference_accrual_period_ = Period(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_
    
    @property
    def currency(self) -> Currency:
        return self.currency_
    
    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def basis_on_index(self) -> OvernightCompositeIndex:
        return self.basis_on_index_
    
    @property
    def rate_cutoff(self) -> Period:
        return self.rate_cutoff_
    
    @property
    def reference_on_index(self) -> OvernightCompositeIndex:
        return self.reference_on_index_
    
    @property
    def payment_offset(self) -> Period:
        return self.payment_offset_
    
    @property
    def payment_business_day_convention(self) -> int:
        return self.payment_business_day_conv_

    @property
    def payment_holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def basis_accrual_period(self) -> Period:
        return self.basis_accrual_period_
    
    @property
    def reference_accrual_period(self) -> Period:
        return self.reference_accrual_period_

# tick
# overnight composite over overnight composite
class DataConventionOvernightIndexCurrencyBasisSwap(DataConvention):

    _type = "OVERNIGHT INDEX CURRENCY BASIS SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 14
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.mark_notional_to_market_ : str = "None"
        self.fx_rate_fixing_holiday_ : ql.Calendar = None
        self.fx_rate_fixing_offset_ : Period = None
        self.basis_currency_ : Currency = None
        self.basis_notional_ : float = None
        self.basis_on_index_ : OvernightCompositeIndex = None
        self.basis_accrual_period_ : Period = None
        self.basis_payment_offset_ : Period = None
        self.reference_currency_ : Currency = None
        self.reference_on_index_ : OvernightCompositeIndex = None
        self.reference_accrual_period_ : Period = None
        self.reference_payment_offset_ : Period = None

        self.notional_ = None
        self.currency_ = None

        upper_content : Dict[str, str] = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "MARK NOTIONAL TO MARKET":
                self.mark_notional_to_market_ = v
            elif k == "FX RATE FIXING HOLIDAY CONVENTION":
                self.fx_rate_fixing_holiday_ = HolidayConvention.new(v)
            elif k == "FX RATE FIXING OFFSET":
                self.fx_rate_fixing_offset_ = Period(v)
            elif k == "BASIS CURRENCY":
                self.currency_ = self.basis_currency_ = Currency(v)
            elif k == "BASIS NOTIONAL":
                self.notional_ = self.basis_notional_ = float(v)
            elif k == "BASIS OVERNIGHT COMPOSITE INDEX":
                self.basis_on_index_ = IndexRegistry().get(v)
            elif k == "BASIS ACCRUAL PERIOD":
                self.basis_accrual_period_ = Period(v)
            elif k == "BASIS PAYMENT OFFSET":
                self.basis_payment_offset_ = Period(v)
            elif k == "REFERENCE CURRENCY":
                self.reference_currency_ = Currency(v)
            elif k == "REFERENCE OVERNIGHT COMPOSITE INDEX":
                self.reference_on_index_ = IndexRegistry().get(v)
            elif k == "REFERENCE ACCRUAL PERIOD":
                self.reference_accrual_period_ = Period(v)
            elif k == "REFERENCE PAYMENT OFFSET":
                self.reference_payment_offset_ = Period(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_
    
    @property
    def mark_notional_to_market(self) -> str:
        return self.mark_notional_to_market_
    
    @property
    def fx_rate_fixing_holiday_convention(self) -> ql.Calendar:
        return self.fx_rate_fixing_holiday_

    @property
    def fx_rate_fixing_offset(self) -> Period:
        return self.fx_rate_fixing_offset_

    @property
    def basis_currency(self) -> Currency:
        return self.basis_currency_
    
    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def basis_notional(self) -> float:
        return self.basis_notional_
    
    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def basis_on_index(self) -> OvernightCompositeIndex:
        return self.basis_on_index_
    
    @property
    def basis_accrual_period(self) -> Period:
        return self.basis_accrual_period_
    
    @property
    def basis_payment_offset(self) -> Period:
        return self.basis_payment_offset_

    @property
    def reference_currency(self) -> Currency:
        return self.reference_currency_

    @property
    def reference_on_index(self) -> OvernightCompositeIndex:
        return self.reference_on_index_
    
    @property
    def reference_accrual_period(self) -> Period:
        return self.reference_accrual_period_
    
    @property
    def reference_payment_offset(self) -> Period:
        return self.reference_payment_offset_
    
# tick
# ibor vs overnight composite
class DataConventionOISIBORCurrencyBasisSwap(DataConvention):

    _type = "OIS IBOR CURRENCY BASIS SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 15
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.mark_notional_to_market_ : str = "None"
        self.fx_rate_fixing_holiday_ : ql.Calendar = None
        self.fx_rate_fixing_offset_ : Period = None
        self.ibor_currency_ : Currency = None
        self.ibor_notional_ : float = None
        self.ibor_index_ : IBORIndex = None
        self.ibor_accrual_period_ : Period = None
        self.ibor_payment_offset_ : Period = None
        self.on_currency_ : Currency = None
        self.on_index_ : OvernightCompositeIndex = None
        self.on_accrual_period_ : Period = None
        self.on_payment_offset_ : Period = None
        self.is_basis_leg_ibor_ : bool = True

        upper_content : Dict[str, str] = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "MARK NOTIONAL TO MARKET":
                self.mark_notional_to_market_ = v
            elif k == "FX RATE FIXING HOLIDAY CONVENTION":
                self.fx_rate_fixing_holiday_ = HolidayConvention.new(v)
            elif k == "FX RATE FIXING OFFSET":
                self.fx_rate_fixing_offset_ = Period(v)
            elif k == "IBOR CURRENCY":
                self.ibor_currency_ = Currency(v)
            elif k == "IBOR NOTIONAL":
                self.ibor_notional_ = float(v)
            elif k == "IBOR OVERNIGHT COMPOSITE INDEX":
                self.ibor_index_ = IndexRegistry().get(v)
            elif k == "IBOR ACCRUAL PERIOD":
                self.ibor_accrual_period_ = Period(v)
            elif k == "IBOR PAYMENT OFFSET":
                self.ibor_payment_offset_ = Period(v)
            elif k == "OVERNIGHT COMPOSITE CURRENCY":
                self.on_currency_ = Currency(v)
            elif k == "OVERNIGHT COMPOSITE INDEX":
                self.on_index_ = IndexRegistry().get(v)
            elif k == "OVERNIGHT COMPOSITE ACCRUAL PERIOD":
                self.on_accrual_period_ = Period(v)
            elif k == "OVERNIGHT COMPOSITE PAYMENT OFFSET":
                self.on_payment_offset_ = Period(v)
            elif k == "BASIS LEG":
                self.is_basis_leg_ibor_ = v.upper() == "IBOR"
        
        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_
    
    @property
    def mark_notional_to_market(self) -> str:
        return self.mark_notional_to_market_
    
    @property
    def fx_rate_fixing_holiday_convention(self) -> ql.Calendar:
        return self.fx_rate_fixing_holiday_

    @property
    def fx_rate_fixing_offset(self) -> Period:
        return self.fx_rate_fixing_offset_

    @property
    def ibor_currency(self) -> Currency:
        return self.ibor_currency_
    
    @property
    def ibor_notional(self) -> float:
        return self.ibor_notional_
    
    @property
    def ibor_on_index(self) -> IBORIndex:
        return self.ibor_index_
    
    @property
    def ibor_accrual_period(self) -> Period:
        return self.ibor_accrual_period_
    
    @property
    def ibor_payment_offset(self) -> Period:
        return self.ibor_payment_offset_

    @property
    def on_currency(self) -> Currency:
        return self.on_currency_
    
    @property
    def on_on_index(self) -> OvernightCompositeIndex:
        return self.on_index_
    
    @property
    def on_accrual_period(self) -> Period:
        return self.on_accrual_period_
    
    @property
    def on_payment_offset(self) -> Period:
        return self.on_payment_offset_

    @property
    def is_basis_leg_ibor(self) -> str:
        return self.is_basis_leg_ibor_

# tick
class DataConventionGenericForward(DataConvention):

    _type = "GENERIC FORWARD"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 10
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.index_ : Index = None
        self.accrual_basis_ : ql.DayCounter = None
        self.payment_business_day_conv_ = None
        self.payment_holiday_conv_ = None
        self.end_of_month_ : bool = None
        self.compounding_method_ : CompoundingMethod = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            if k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "INDEX":
                if IndexRegistry().exists(v):
                    self.index_ = IndexRegistry().get(v)
                elif FundingIdentifierRegistry().exists(v):
                    self.index_ = FundingIdentifierRegistry().get(v)
                else:
                    raise Exception(f"Invalid index {v}.")
            elif k == "ACCRUAL BASIS":
                self.accrual_basis_ = AccrualBasis.new(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)
            elif k == "END OF MONTH":
                self.end_of_month_ = bool(v)
            elif k == "COMPOUNDING METHOD":
                self.compounding_method_ = CompoundingMethod.from_string(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_

    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_

    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def index(self) -> Index:
        return self.index_

    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_

    @property
    def business_day_convention(self) -> int:
        return self.payment_business_day_conv_

    @property
    def holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_

    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_

# tick
class DataConventionGenericForwardSpread(DataConvention):

    _type = "GENERIC FORWARD SPREAD"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 13
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.basis_currency_ : Currency = None
        self.basis_notional_ : float = None
        self.basis_index_ : Index = None
        self.basis_accrual_basis_ : ql.DayCounter = None
        self.reference_currency_ : Currency = None
        self.reference_index_ : Index = None
        self.reference_accrual_basis_ : ql.DayCounter = None
        self.payment_business_day_conv_ = None
        self.payment_holiday_conv_ = None
        self.end_of_month_ : bool = None
        self.compounding_method_ : CompoundingMethod = None

        self.notional_ = None
        self.currency_ = None
        self.settlement_business_day_convention_ : int = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "BASIS CURRENCY":
                self.currency_ = self.basis_currency_ = Currency(v)
            elif k == "BASIS NOTIONAL":
                self.notional_ = self.basis_notional_ = float(v)
            elif k == "BASIS INDEX":
                if IndexRegistry().exists(v):
                    self.basis_index_ = IndexRegistry().get(v)
                elif FundingIdentifierRegistry().exists(v):
                    self.basis_index_ = FundingIdentifierRegistry().get(v)
                else:
                    raise Exception(f"Invalid basis index {v}.")
            elif k == "BASIS ACCRUAL BASIS":
                self.basis_accrual_basis_ = AccrualBasis.new(v)
            elif k == "REFERENCE CURRENCY":
                self.reference_currency_ = Currency(v)
            elif k == "REFERENCE INDEX":
                if IndexRegistry().exists(v):
                    self.reference_index_ = IndexRegistry().get(v)
                elif FundingIdentifierRegistry().exists(v):
                    self.reference_index_ = FundingIdentifierRegistry().get(v)
                else:
                    raise Exception(f"Invalid reference index {v}.")
            elif k == "REFERENCE ACCRUAL BASIS":
                self.accrual_basis_ = AccrualBasis.new(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.settlement_business_day_convention_ = \
                    self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)
            elif k == "END OF MONTH":
                self.end_of_month_ = bool(v)
            elif k == "COMPOUNDING METHOD":
                self.compounding_method_ = CompoundingMethod.from_string(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_

    @property
    def settlement_business_day_convention(self) -> int:
        return self.settlement_business_day_convention_

    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_

    @property
    def basis_currency(self) -> Currency:
        return self.basis_currency_
    
    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def basis_notional(self) -> float:
        return self.basis_notional_
    
    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def basis_index(self) -> Index:
        return self.basis_index_

    @property
    def reference_index(self) -> Index:
        return self.reference_index_

    @property
    def basis_accrual_basis(self) -> ql.DayCounter:
        return self.basis_accrual_basis_
    
    @property
    def reference_accrual_basis(self) -> ql.DayCounter:
        return self.reference_accrual_basis_

    @property
    def payment_business_day_convention(self) -> int:
        return self.payment_business_day_conv_

    @property
    def payment_holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_

    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_

# tick
class DataConventionIborSpreadZeroRate(DataConvention):

    _type = "IBOR SPREAD ZERO RATE"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 2
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.basis_ibor_index_ : IBORIndex = None
        self.reference_index_ : Index = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "BASIS IBOR INDEX":
                self.basis_ibor_index_ = IndexRegistry().get(v)
            elif k == "REFERENCE INDEX":
                if IndexRegistry().exists(v):
                    self.reference_index_ = IndexRegistry().get(v)
                elif FundingIdentifierRegistry().exists(v):
                    self.reference_index_ = FundingIdentifierRegistry().get(v)
                else:
                    raise Exception(f"Invalid reference index {v}.")

        super().__init__(unique_name, upper_content)

    @property
    def basis_ibor_index(self) -> IBORIndex:
        return self.basis_ibor_index_

    @property
    def reference_index(self) -> Index:
        return self.reference_index_

# tick (no meaningful example in yaml, will add later)
class DataConventionGenericSpread(DataConvention):

    _type = "GENERIC SPREAD"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 2
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.target_data_convention_ : DataConvention = None
        self.reference_data_convention_ : DataConvention = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "TARGET DATA CONVENTION":
                self.target_data_convention_ = v
            elif k == "REFERENCE DATA CONVENTION":
                self.reference_data_convention_ = v

        super().__init__(unique_name, upper_content)

    @property
    def target_data_convention(self) -> DataConvention:
        return DataConventionRegistry().get(self.target_data_convention_)

    @property
    def reference_data_convention(self) -> DataConvention:
        return DataConventionRegistry().get(self.reference_data_convention_)

    @property
    def currency(self) -> Currency:
        return self.target_data_convention.currency
    
    @property
    def notional(self) -> float:
        return self.target_data_convention.notional

# tick
class DataConventionFRN(DataConvention):

    _type = "FLOATING RATE NOTE"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 7
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.index_ : IBORIndex|OvernightIndex = None
        self.payment_business_day_conv_ = None
        self.payment_holiday_conv_ = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "INDEX":
                self.basis_index_ = IndexRegistry().get(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_

    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_

    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def index(self) -> Index:
        return self.index_

    @property
    def payment_business_day_convention(self) -> int:
        return self.payment_business_day_conv_

    @property
    def payment_holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_

# tick
class DataConventionSwapSpreadBasisSwap(DataConvention):

    _type = "SWAP SPREAD BASIS SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 6
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.basis_swap_ : str = None
        self.reference_swap_ : str = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "BASIS SWAP":
                self.basis_swap_ = v
            elif k == "REFERENCE SWAP":
                self.reference_swap_ = v

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_

    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_

    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def basis_swap(self) -> DataConvention:
        return DataConventionRegistry().get(self.basis_swap_)

    @property
    def reference_swap(self) -> DataConvention:
        return DataConventionRegistry().get(self.reference_swap_)

# tick
class DataConventionFXRateIndex(DataConvention):

    _type = "FX RATE INDEX"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 1
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.fx_index_ : FXIndex = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "FX INDEX":
                self.fx_index_ = IndexRegistry().get(v)

        super().__init__(unique_name, upper_content)

    @property
    def fx_index(self) -> FXIndex:
        return self.fx_index_

##########

# tick
# rare
class DataConventionCashDeposit(DataConvention):

    _type = "CASH DEPOSIT"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 8
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.accrual_basis_ : ql.DayCounter = None
        self.payment_business_day_conv_ = None
        self.payment_holiday_conv_ = None
        self.end_of_month_ : bool = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            if k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "ACCRUAL BASIS":
                self.accrual_basis_ = AccrualBasis.new(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)
            elif k == "END OF MONTH":
                self.end_of_month_ = bool(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_

    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_

    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_

    @property
    def business_day_convention(self) -> int:
        return self.payment_business_day_conv_

    @property
    def holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_

# tick
# old days
class DataConventionIBORFuture(DataConvention):

    _type = "IBOR FUTURE"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 10
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.contractual_notional_ : float = None
        self.ibor_index_ : IBORIndex = None
        self.accrual_basis_ : ql.DayCounter = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        self.basis_point_value_type_ : str = None
        self.basis_point_value_ : float = None

        self.notional_ = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            if k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "CONTRACTUAL NOTIONAL":
                self.notional_ = self.contractual_notional_ = float(v)
            elif k == "IBOR INDEX":
                self.ibor_index_ = IndexRegistry().get(v)
            elif k == "ACCRUAL BASIS":
                self.accrual_basis_ = AccrualBasis.new(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)
            elif k == "BASIS POINT VALUE TYPE":
                self.basis_point_value_type_ = v
            elif k == "BASIS POINT VALUE":
                self.basis_point_value_ = float(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_

    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.settlement_holiday_convention_

    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def contractual_notional(self) -> float:
        return self.contractual_notional_
    
    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def ibor_index(self) -> IBORIndex:
        return self.ibor_index_
    
    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_

    @property
    def business_day_convention(self) -> int:
        return self.payment_business_day_conv_

    @property
    def holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_conv_

    @property
    def basis_point_value_type(self) -> str:
        return self.basis_point_value_type_

    @property
    def basis_point_value(self) -> float:
        return self.basis_point_value_

# tick
# old days
class DataConventionSwap(DataConvention):

    _type = "SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 10
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.ibor_index_ : IBORIndex = None
        self.accrual_period_ : Period = None
        self.accrual_basis_ : ql.DayCounter = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        self.value_date_as_first_fixing_date_ : bool = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "IBOR INDEX":
                self.ibor_index_ = IndexRegistry().get(v)
            elif k == "ACCRUAL PERIOD":
                self.accrual_period_ = Period(v)
            elif k == "ACCRUAL BASIS":
                self.accrual_basis_ = AccrualBasis.new(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)
            elif k == "VALUE DATE AS FIRST FIXING DATE":
                self.value_date_as_first_fixing_date_ = bool(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> int:
        return self.settlement_holiday_convention_
    
    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def index(self) -> IBORIndex:
        return self.ibor_index_

    @property
    def accrual_period(self) -> Period:
        return self.accrual_period_

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
    def value_date_as_first_fixing_date(self) -> bool:
        return self.value_date_as_first_fixing_date_

# tick
# old days
class DataConventionBasisSwap(DataConvention):

    _type = "BASIS SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 8
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.basis_ibor_index_ : IBORIndex = None
        self.reference_ibor_index_ : IBORIndex = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "BASIS IBOR INDEX":
                self.basis_ibor_index_ = IndexRegistry().get(v)
            elif k == "REFERENCE IBOR INDEX":
                self.reference_ibor_index_ = IndexRegistry().get(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> int:
        return self.settlement_holiday_convention_
    
    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def basis_index(self) -> IBORIndex:
        return self.basis_ibor_index_

    @property
    def reference_index(self) -> IBORIndex:
        return self.reference_ibor_index_

    @property
    def payment_business_day_conv(self) -> int:
        return self.payment_business_day_conv_
    
    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.payment_holiday_conv_

# tick
# old days
class DataConventionCurrencyBasisSwap(DataConvention):

    _type = "CURRENCY BASIS SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 11
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.mark_notional_to_market_ : str = "None"
        self.fx_rate_holiday_ : ql.Calendar = None
        self.fx_rate_fixing_offset_ : ql.Calendar = None
        self.basis_currency_ : Currency = None
        self.basis_notional_ : float = None
        self.basis_ibor_index_ : IBORIndex = None
        self.reference_currency_ : Currency = None
        self.reference_ibor_index_ : IBORIndex = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None

        self.currency_ = None
        self.notional_ = None

        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "MARK NOTIONAL TO MARKET":
                self.mark_notional_to_market_ = str(v)
            elif k == "FX RATE HOLIDAY CONVENTION":
                self.fx_rate_holiday_ = HolidayConvention.new(v)
            elif k == "FX RATE FIXING OFFSET":
                self.fx_rate_fixing_offset_ = Period(v)
            elif k == "BASIS CURRENCY":
                self.currency_ = self.basis_currency_ = Currency(v)
            elif k == "BASIS NOTIONAL":
                self.notional_ = self.basis_notional_ = float(v)
            elif k == "BASIS IBOR INDEX":
                self.basis_ibor_index_ = IndexRegistry().get(v)
            elif k == "REFERENCE CURRENCY":
                self.reference_currency_ = Currency(v)
            elif k == "REFERENCE IBOR INDEX":
                self.reference_ibor_index_ = IndexRegistry().get(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def fx_rate_holiday_convention(self) -> ql.Calendar:
        return self.fx_rate_holiday_

    @property
    def fx_rate_fixing_offset(self) -> Period:
        return self.fx_rate_fixing_offset_
    
    @property
    def basis_currency(self) -> Currency:
        return self.basis_currency_
    
    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def basis_notional(self) -> float:
        return self.basis_notional_
    
    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def basis_index(self) -> IBORIndex:
        return self.basis_ibor_index_

    @property
    def reference_currency(self) -> Currency:
        return self.reference_currency_

    @property
    def reference_index(self) -> IBORIndex:
        return self.reference_ibor_index_

    @property
    def payment_business_day_conv(self) -> int:
        return self.payment_business_day_conv_
    
    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.payment_holiday_conv_

# tick
# rare !
class DataConventionOvernightIndexFRASpread(DataConvention):

    _type = "OVERNIGHT INDEX FRA SPREAD"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 2
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.fra_data_convention_ : str = None
        self.ois_data_convention_ : str = None
        
        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "FRA DATA CONVENTION":
                self.fra_data_convention_ = v
            elif k == "OIS DATA CONVENTION":
                self.ois_data_convention_ = v

        super().__init__(unique_name, upper_content)

    @property
    def fra_data_convention(self) -> DataConvention:
        return DataConventionRegistry().get(self.fra_data_convention_)

    @property
    def ois_data_convention(self) -> DataConvention:
        return DataConventionRegistry().get(self.ois_data_convention_)

# tick
# rare !
class DataConventionCompoundSwap(DataConvention):

    _type = "COMPOUND SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 10
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.ibor_index_ : IBORIndex = None # compound leg
        self.ibor_payment_period_ : Period = None # compound leg
        self.accrual_period_ : Period = None  # fixed leg
        self.accrual_basis_ : ql.DayCounter = None # fixed leg
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        
        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "INDEX":
                self.ibor_index_ = IndexRegistry().get(v)
            elif k == "PAYMENT PERIOD":
                self.ibor_payment_period_ = Period(v)
            elif k == "ACCRUAL PERIOD":
                self.accrual_period_ = Period(v)
            elif k == "ACCRUAL BASIS":
                self.accrual_basis_ = AccrualBasis.new(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> int:
        return self.settlement_holiday_convention_
    
    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def ibor_index(self) -> IBORIndex:
        return self.ibor_index_

    @property
    def ibor_payment_period(self) -> Period:
        return self.ibor_payment_period_

    @property
    def accrual_period(self) -> Period:
        return self.accrual_period_

    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_

    @property
    def payment_business_day_conv(self) -> int:
        return self.payment_business_day_conv_
    
    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.payment_holiday_conv_

# tick
# rare !
class DataConventionCompoundBasisSwap(DataConvention):

    _type = "COMPOUND BASIS SWAP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 10
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.settlement_offset_ : Period = None
        self.settlement_holiday_convention_ : ql.Calendar = None
        self.currency_ : Currency = None
        self.notional_ : float = None
        self.basis_ibor_index_ : IBORIndex = None # basis leg
        self.basis_ibor_payment_period_ : Period = None # basis leg
        self.compound_method_ : CompoundingMethod = None # basis leg
        self.reference_ibor_index_ : IBORIndex = None # reference leg
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        
        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "SETTLEMENT OFFSET":
                self.settlement_offset_ = Period(v)
            elif k == "SETTLEMENT HOLIDAY CONVENTION":
                self.settlement_holiday_convention_ = HolidayConvention.new(v)
            elif k == "CURRENCY":
                self.currency_ = Currency(v)
            elif k == "NOTIONAL":
                self.notional_ = float(v)
            elif k == "BASIS INDEX":
                self.basis_ibor_index_ = IndexRegistry().get(v)
            elif k == "BASIS PAYMENT PERIOD":
                self.basis_ibor_payment_period_ = Period(v)
            elif k == "COMPOUND METHOD":
                self.compound_method_ = CompoundingMethod.from_string(v)
            elif k == "REFERENCE INDEX":
                self.reference_ibor_index_ = IndexRegistry().get(v)
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)

        super().__init__(unique_name, upper_content)

    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_holiday_convention(self) -> int:
        return self.settlement_holiday_convention_
    
    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def basis_ibor_index(self) -> IBORIndex:
        return self.basis_ibor_index_

    @property
    def basis_ibor_payment_period(self) -> Period:
        return self.basis_ibor_payment_period_

    @property
    def compound_method(self) -> CompoundingMethod:
        return self.compound_method_

    @property
    def reference_ibor_index(self) -> IBORIndex:
        return self.reference_ibor_index_

    @property
    def payment_business_day_conv(self) -> int:
        return self.payment_business_day_conv_
    
    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.payment_holiday_conv_

# subject to change
class DataConventionJump(DataConvention):

    _type = "JUMP"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 2
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.index_ : Index = None
        self.jump_size_ : int = None
        
        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "INDEX":
                self.index_ = cast_to_index(v)
                assert self.index_
            elif k == "JUMP SIZE":
                self.jump_size_ = float(v)

        super().__init__(unique_name, upper_content)

    @property
    def index(self) -> Index:
        return self.index_
    
    @property
    def jump_size(self) -> float:
        return self.jump_size_


# subject to change
class DataConventionSwaption(DataConvention):

    _type = "SWAPTION"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 3
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.index_ : Index = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        
        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "INDEX":
                self.index_ = cast_to_index(v)
                assert self.index_
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)

        super().__init__(unique_name, upper_content)

    @property
    def index(self) -> Index:
        return self.index_

    @property
    def payment_business_day_conv(self) -> int:
        return self.payment_business_day_conv_
    
    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.payment_holiday_conv_

# subject to change
class DataConventionCapFloor(DataConvention):

    _type = "CAPFLOOR"

    def __init__(self, unique_name : str, content : Dict[str, str]):
        
        valid_count = 3
        if len(content) != valid_count:
            raise ValueError(f"{unique_name}: content should have {valid_count} fields, got {len(content)}")

        self.index_ : Index = None
        self.payment_business_day_conv_ : int = None
        self.payment_holiday_conv_ : ql.Calendar = None
        
        upper_content = {k.upper(): v for k, v in content.items()}
        for k, v in upper_content.items():
            if k == "INDEX":
                self.index_ = cast_to_index(v)
                assert self.index_
            elif k == "PAYMENT BUSINESS DAY CONVENTION":
                self.payment_business_day_conv_ = BusinessDayConvention.new(v)
            elif k == "PAYMENT HOLIDAY CONVENTION":
                self.payment_holiday_conv_ = HolidayConvention.new(v)

        super().__init__(unique_name, upper_content)

    @property
    def index(self) -> Index:
        return self.index_

    @property
    def payment_business_day_conv(self) -> int:
        return self.payment_business_day_conv_
    
    @property
    def payment_holiday_conv(self) -> ql.Calendar:
        return self.payment_holiday_conv_

#########################################################

### not fo curve calibration but we need it
# class DataConventionBondFuture(DataConvention):
###
    
### deferred list
# class DataConventionRepo(DataConvention):
# class DataConventionBond(DataConvention):
# class DataConventionSwapSpread(DataConvention): # for bond vs swap
###
    
### skip list
# class DataConventionCurrencySwap(DataConvention):
# class DataConventionFixedCurrencySwap(DataConvention):
# class DataConventionZeroCouponSwapRate(DataConvention):
# class DataConventionZeroCouponSwapRateSpread(DataConvention):=
###

class DataConventionRegistry(Registry):

    def __new__(cls) -> Self:
        return super().__new__(cls, "data_conventions", "DataConevention", "yaml")

    def register(self, key: str, value: Any) -> None:
        super().register(key, value)
        func = DataConventionRegFunction().get(value["type"])
        self._map[key.upper()] = func(key, value["convention"])

    def display_all_data_conventions(self) -> pd.DataFrame:
        to_print = [[k, v.type()] for k, v in self._map.items()]
        return pd.DataFrame(to_print, columns=["Name", "Type"])

### registry
DataConventionRegFunction().register(DataConventionInstantaneousForwardRate._type, DataConventionInstantaneousForwardRate)
DataConventionRegFunction().register(DataConventionFRAOrFixing._type, DataConventionFRAOrFixing)
DataConventionRegFunction().register(DataConventionOvernightIndexFuture._type, DataConventionOvernightIndexFuture)
DataConventionRegFunction().register(DataConventionOvernightIndexSwap._type, DataConventionOvernightIndexSwap)
DataConventionRegFunction().register(DataConventionOvernightIndexBasisSwap._type, DataConventionOvernightIndexBasisSwap)
DataConventionRegFunction().register(DataConventionOISBasisSwap._type, DataConventionOISBasisSwap)
DataConventionRegFunction().register(DataConventionOvernightIndexCurrencyBasisSwap._type, DataConventionOvernightIndexCurrencyBasisSwap)
DataConventionRegFunction().register(DataConventionOISIBORCurrencyBasisSwap._type, DataConventionOISIBORCurrencyBasisSwap)
DataConventionRegFunction().register(DataConventionGenericForward._type, DataConventionGenericForward)
DataConventionRegFunction().register(DataConventionGenericForwardSpread._type, DataConventionGenericForwardSpread)
DataConventionRegFunction().register(DataConventionIborSpreadZeroRate._type, DataConventionIborSpreadZeroRate)
DataConventionRegFunction().register(DataConventionGenericSpread._type, DataConventionGenericSpread)
DataConventionRegFunction().register(DataConventionFRN._type, DataConventionFRN)
DataConventionRegFunction().register(DataConventionSwapSpreadBasisSwap._type, DataConventionSwapSpreadBasisSwap)
DataConventionRegFunction().register(DataConventionFXRateIndex._type, DataConventionFXRateIndex)
DataConventionRegFunction().register(DataConventionCashDeposit._type, DataConventionCashDeposit)
DataConventionRegFunction().register(DataConventionIBORFuture._type, DataConventionIBORFuture)
DataConventionRegFunction().register(DataConventionSwap._type, DataConventionSwap)
DataConventionRegFunction().register(DataConventionBasisSwap._type, DataConventionBasisSwap)
DataConventionRegFunction().register(DataConventionCurrencyBasisSwap._type, DataConventionCurrencyBasisSwap)
DataConventionRegFunction().register(DataConventionOvernightIndexFRASpread._type, DataConventionOvernightIndexFRASpread)
DataConventionRegFunction().register(DataConventionCompoundSwap._type, DataConventionCompoundSwap)
DataConventionRegFunction().register(DataConventionCompoundBasisSwap._type, DataConventionCompoundBasisSwap)
DataConventionRegFunction().register(DataConventionSwaption._type, DataConventionSwaption)
DataConventionRegFunction().register(DataConventionCapFloor._type, DataConventionCapFloor)
DataConventionRegFunction().register(DataConventionJump._type, DataConventionJump)
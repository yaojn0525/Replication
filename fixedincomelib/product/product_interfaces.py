from abc import ABCMeta, abstractmethod
from typing import Self, Any, List, Dict
# in-house
from fixedincomelib.date import *
from fixedincomelib.market import *
from fixedincomelib.utilities import *
from fixedincomelib.product.utilities import *

    
class ProductBuilderRegistry(Registry):
    
    def __new__(cls) -> Self:
        return super().__new__(cls, '', cls.__name__)

    def register(self, key : Any, value : Any) -> None:
        super().register(key, value)
        self._map[key] = value

class ProductVisitor(metaclass=ABCMeta):
    pass

class Product(metaclass=ABCMeta):
    
    _version = -1
    _product_type = ''

    def __init__(self) -> None:
        self.first_date_ = None
        self.last_date_ = None
        self.notional_ = None
        self.long_or_short_ = LongOrShort.LONG
        self.currency_ = None

    @abstractmethod
    def serialize(self) -> dict:
        pass

    @abstractmethod
    def deserialize(cls, input_dict) -> 'Product':
        pass

    @abstractmethod
    def accept(self, visitor: ProductVisitor):
        pass
    
    @property
    def product_type(self) -> str:
        return self._product_type

    @property
    def first_date(self) -> Date:
        return self.first_date_
    
    @property
    def last_date(self) -> Date:
        return self.last_date_

    @property
    def notional(self) -> float | Dict[Currency, float]:
        return self.notional_
    
    @property
    def long_or_short(self) -> LongOrShort | List[LongOrShort]:
        return self.long_or_short_
    
    @property
    def currency(self) -> Currency | List[Currency]:
        return self.currency_

class ProductCashflow(Product):

    def __init__(
        self,
        term_or_termination_date : TermOrDate,
        notional : float,
        currency : Currency,
        long_or_short : Optional[LongOrShort]=LongOrShort.LONG,
        effective_date : Optional[Date]=Date(),
        index : Optional[Index]=None,
        fixed_rate_or_spread : Optional[float]=None,
        accrual_basis : Optional[ql.DayCounter]=None,
        pay_date_or_payment_offset: Optional[TermOrDate]=TermOrDate("0D"),
        business_day_convention : Optional[int]=ql.Unadjusted,
        holiday_convention : Optional[ql.Calendar]=ql.NullCalendar(),
        payment_business_day_convention : Optional[int]=ql.Unadjusted,
        payment_holiday_convention : Optional[ql.Calendar]=ql.NullCalendar(),
        pay_in_advance : Optional[bool]=False,
        fixing_offset : Optional[Period]=ql.NoFrequency) -> None:

        super().__init__()
        
        ### sort basics
        self.notional_ = notional
        self.currency_ = currency
        self.long_or_short_ = long_or_short

        ### sort out index
        self.index_ = index
        self.is_on_ = False
        self.is_on_composite_ = False
        if self.index_:
            self.is_on_ = isinstance(self.index_, OvernightIndex)
            self.is_on_composite_ = isinstance(self.index_, OvernightCompositeIndex)

        ### sort out convention stuffs
        self.business_day_convention_ = self.payment_business_day_convention_ = business_day_convention
        self.holiday_convention_ = self.payment_holiday_convention_ = holiday_convention
        if BusinessDayConvention.is_valid(payment_business_day_convention):
            self.payment_business_day_convention_ = payment_business_day_convention
        if HolidayConvention.is_valid(payment_holiday_convention):
            self.payment_holiday_convention_ = payment_holiday_convention
        self.pay_in_advance_ = pay_in_advance
        if not effective_date.is_valid():
            self.pay_in_advance_ = False

        ### sort out date
        self.termination_date_ = None
        self.effective_date_ = effective_date
        self.term_or_termination_date_ = term_or_termination_date
        if not self.index_:
            if not self.effective_date_:
                # either it's a bullet cashflow
                assert not term_or_termination_date.is_term()
                self.effective_date_ = self.termination_date_ = term_or_termination_date.get_date()
            else:
                # or it's a fixed accrued 
                if term_or_termination_date.is_term():
                    self.termination_date_ = add_period(
                        self.effective_date_,
                        self.term_or_termination_date_.get_term(),
                        self.business_day_convention_,
                        self.holiday_convention_)
                else:
                    self.termination_date_ = self.term_or_termination_date_.get_date()
        else:
            # either
            if self.term_or_termination_date_.is_term():
                self.termination_date_ = add_period_by_index(
                    self.effective_date_,
                    self.term_or_termination_date_.get_term(),
                    self.index_)
            else:
                self.termination_date_ = self.term_or_termination_date_.get_date()
        self.first_date_ = self.effective_date_
        
        ### pay date
        self.payment_date_ = self.effective_date_ if self.pay_in_advance_ else self.termination_date_
        self.pay_date_or_payment_offset_ = pay_date_or_payment_offset
        self.payment_offset_ = None
        if not self.pay_date_or_payment_offset_.is_term():
            self.payment_date_ = self.pay_date_or_payment_offset_.get_date()
        else:
            self.payment_offset_ = self.pay_date_or_payment_offset_.get_term()
            self.payment_date_ = add_period(
                self.payment_date_,
                self.payment_offset_,
                self.payment_business_day_convention_,
                self.payment_holiday_convention_)
        self.last_date_ = max(self.payment_date_, self.termination_date_)
        
        ### fixing date
        self.fixing_offset_ = fixing_offset
        self.fixing_date_ = None
        if self.index_:
            # find anchored date
            pivot_date = self.termination_date_
            if isinstance(self.index_, IBORIndex):
                pivot_date = self.effective_date_
            # two cases
            casted_index : OvernightIndex | OvernightCompositeIndex | IBORIndex = self.index_
            if casted_index.from_ql:
                # if fixingDate functor exist (that means we wrapped ql.Index)
                self.fixing_date_ = casted_index.fixingDate(pivot_date)
            else:
                # if fixingDate functor does not exist (our own index)
                self.fixing_date_ = add_period(
                    pivot_date,
                    Period.negate_period(casted_index.settlement_offset),
                    casted_index.payment_business_day_conv,
                    casted_index.settlement_holiday)

        ### others
        self.fixed_rate_ = self.spread_ = None
        if self.index_:
            self.fixed_rate_ = None
            self.spread_ = fixed_rate_or_spread if fixed_rate_or_spread is not None else 0.
        else:
            # bullet or fixed accrued
            if effective_date:
                # fixed accrued
                self.fixed_rate_ = fixed_rate_or_spread
                self.spread_ = None
            else:
                # bullet
                self.fixed_rate_ = self.spread_ = None
        self.accrued_ = None
        self.accrual_basis_ = accrual_basis
        if effective_date:
            if self.index_:
                if accrual_basis:
                    # if we have accrual basis override
                    self.accrued_ = accrued(
                        self.effective_date_,
                        self.termination_date_,
                        self.accrual_basis_,
                        self.business_day_convention_,
                        self.holiday_convention_)
                else:
                    casted_index : IBORIndex | OvernightIndex | OvernightCompositeIndex = self.index_
                    self.accrual_basis_ = casted_index.accrual_basis
                    self.accrued_ = accrued(
                        self.effective_date, 
                        self.termination_date,
                        self.accrual_basis_,
                        casted_index.payment_business_day_conv,
                        casted_index.settlement_holiday)
            else:
                self.accrued_ = accrued(
                    self.effective_date_,
                    self.termination_date_,
                    self.accrual_basis_,
                    self.business_day_convention_,
                    self.holiday_convention_)
                
    @property
    def index(self) -> Index:
        return self.index_
    
    @property
    def is_on(self) -> bool:
        return self.is_on_
    
    @property
    def effective_date(self) -> Date:
        return self.effective_date_
    
    @property
    def term_or_termination_date(self) -> TermOrDate:
        return self.term_or_termination_date_
    
    @property
    def termination_date(self) -> Date:
        return self.termination_date_
    
    @property
    def payment_date(self) -> Date:
        return self.payment_date_
    
    @property
    def payment_offset(self) -> Period:
        return self.payment_offset_
    
    @property
    def pay_date_or_payment_offset(self) -> TermOrDate:
        return self.pay_date_or_payment_offset_

    @property
    def fixing_offset(self) -> Period:
        return self.fixing_offset_
    
    @property
    def fixing_date(self) -> Date:
        return self.fixing_date_
    
    @property
    def business_day_convention(self) -> int:
        return self.business_day_convention_
    
    @property
    def payment_business_day_convention(self) -> int:
        return self.payment_business_day_convention_
    
    @property
    def holiday_convention(self) -> ql.Calendar:
        return self.holiday_convention_
    
    @property
    def payment_holiday_convention(self) -> ql.Calendar:
        return self.payment_holiday_convention_
    
    @property
    def accrual_basis(self) -> str:
        return AccrualBasis.to_string(self.accrual_basis_)
    
    @property
    def accrued(self) -> float:
        return self.accrued_

    @property
    def pay_in_advance(self) -> bool:
        return self.pay_in_advance_
    
    @property
    def spread(self) -> float:
        return self.spread_
    
    @property
    def fixed_rate(self) -> float:
        return self.fixed_rate_
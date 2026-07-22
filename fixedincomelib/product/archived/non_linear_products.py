from enum import Enum
import pandas as pd
from typing import List, Optional, Union
from dataclasses import dataclass
import QuantLib as ql
import numpy as np
from fixedincomelib.date.utilities import add_period, frequency_from_period
from fixedincomelib.market.basics import *
from Untitled.fixedincomelib.market.interfaces import IndexRegistry, DataConventionRegistry
from fixedincomelib.market.data_conventions import (
    CompoundingMethod,
    DataConventionRFRCapFloor,
    DataConventionRFRCapletFloorlet,
)
from fixedincomelib.market.indices import FXIndex
from fixedincomelib.market import (
    Currency,
    AccrualBasis,
    BusinessDayConvention,
    HolidayConvention,
    DataConventionRegistry,
    IndexRegistry
)
from fixedincomelib.product.utilities import LongOrShort, PayOrReceive
from fixedincomelib.product.product_interfaces import (
    Product,
    ProductVisitor,
    ProductBuilderRegistry,
)
from fixedincomelib.date import Date, Period, TermOrDate, make_schedule, accrued
from fixedincomelib.product.product_portfolio import ProductPortfolio
from fixedincomelib.product.linear_products import ProductOvernightIndexSwap


class CapOrFloor(Enum):
    CAP = "CAP"
    FLOOR = "FLOOR"

    @classmethod
    def from_string(cls, value: str) -> "CapOrFloor":
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.upper())
        except ValueError:
            raise ValueError(f"Invalid token: {value}")

    def to_string(self) -> str:
        return self.value

class ProductRFRCapletFloorlet(Product):

    _version = 1
    _product_type = "PRODUCT_RFR_CAPLET_FLOORLET"

    def __init__(
        self,
        effective_date: Date,
        # expiry_date: Date,
        expiry_offset: Union[str,Period],
        term_or_termination_date: TermOrDate,
        payment_date: Date,
        on_index: str,
        strike: float,
        notional: float,
        cap_or_floor: CapOrFloor,
        accrual_basis: AccrualBasis,
        long_or_short: LongOrShort = LongOrShort.LONG
    ) -> None:

        super().__init__()

        self.on_index_str_ = on_index
        self.on_index_ = IndexRegistry().get(on_index)

        self.first_date_ = self.effective_date_ = effective_date
        self.payment_date_ = payment_date
        self.last_date_ = self.payment_date_
        self.expiry_offset_ = Period(expiry_offset) if isinstance(expiry_offset, str) else expiry_offset

        calendar = self.on_index_.fixingCalendar()
        self.expiry_date_ = Date(
            calendar.advance(
                self.effective_date_,
                self.expiry_offset_,
                self.on_index_.businessDayConvention(),
            )
        )
        if term_or_termination_date.is_term():
            calendar = self.on_index_.fixingCalendar()
            self.termination_date_ = Date(
                calendar.advance(
                    self.effective_date_,
                    term_or_termination_date.get_term(),
                    self.on_index_.businessDayConvention(),
                )
            )
        else:
            self.termination_date_ = term_or_termination_date.get_date()
        
        self.strike_ = strike
        self.notional_ = notional
        self.long_or_short_ = long_or_short
        self.accrual_basis_ = accrual_basis
        self.cap_or_floor_ = cap_or_floor
        self.currency_ = Currency(self.on_index_.currency().code())
        self.accrual_ = accrued(self.effective_date_, self.termination_date_, self.accrual_basis_)

    @property
    def effective_date(self) -> Date:
        return self.effective_date_
    
    @property
    def expiry_date(self) -> Date:
        return self.expiry_date_
    
    @property
    def expiry_offset(self) -> Period:
        return self.expiry_offset_
    
    @property
    def termination_date(self) -> Date:
        return self.termination_date_
    
    @property
    def payment_date(self) -> Date:
        return self.payment_date_
    
    @property
    def on_index_str(self) -> str:
        return self.on_index_str_
    
    @property
    def on_index(self) -> ql.QuantLib.OvernightIndex:
        return self.on_index_

    @property
    def strike(self) -> float:
        return self.strike_
    
    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def cap_or_floor(self) -> CapOrFloor:
        return self.cap_or_floor_
    
    @property
    def accrual_basis(self) -> AccrualBasis:
        return self.accrual_basis_
    
    @property
    def accrual(self) -> float:
        return self.accrual_

    @property
    def currency(self):
        return self.currency_

    @property
    def long_or_short(self):
        return self.long_or_short_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["EXPIRY_OFFSET"] = str(self.expiry_offset_)
        content["EXPIRY_DATE"] = self.expiry_date_.ISO()
        content["TERMINATION_DATE"] = self.termination_date.ISO()
        content["PAYMENT_DATE"] = self.payment_date.ISO()
        content["ON_INDEX"] = self.on_index_str
        content["NOTIONAL"] = self.notional
        content["STRIKE"] = self.strike
        content["LONG_OR_SHORT"] = self.long_or_short.to_string().upper()
        content["CAP_OR_FLOOR"] = self.cap_or_floor.to_string().upper()
        content["ACCRUAL_BASIS"] = self.accrual_basis.value_str
        
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductRFRCapletFloorlet":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        expiry_offset = input_dict["EXPIRY_OFFSET"]
        termination_date = TermOrDate(input_dict["TERMINATION_DATE"])
        payment_date = Date(input_dict["PAYMENT_DATE"])
        on_index = input_dict["ON_INDEX"]
        notional = float(input_dict["NOTIONAL"])
        strike = float(input_dict["STRIKE"])
        long_or_short = LongOrShort.from_string(input_dict["LONG_OR_SHORT"])
        cap_or_floor = CapOrFloor.from_string(input_dict["CAP_OR_FLOOR"])
        accrual_basis = AccrualBasis(input_dict["ACCRUAL_BASIS"])

        return cls(effective_date, 
                   expiry_offset,
                   termination_date, 
                   payment_date, 
                   on_index,
                   strike,
                   notional,
                   cap_or_floor,
                   accrual_basis,
                   long_or_short,
                   )

class ProductRFRCapFloor(Product):

    _version = 1
    _product_type = "PRODUCT_RFR_CAP_FLOOR"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        on_index: str,
        strike: float,
        notional: float,
        cap_or_floor: CapOrFloor,
        accrual_period: Period,
        accrual_basis: AccrualBasis,
        payment_offset: Period,
        payment_business_day_convention: BusinessDayConvention,
        payment_holiday_convention: HolidayConvention,
        long_or_short: LongOrShort = LongOrShort.LONG,
        business_day_convention: Optional[BusinessDayConvention] = BusinessDayConvention("F"),
        holiday_convention: Optional[HolidayConvention] = HolidayConvention("USGS")
    ) -> None:
        super().__init__()

        self.on_index_str_ = on_index
        self.on_index_ = IndexRegistry().get(on_index)

        self.first_date_ = self.effective_date_ = effective_date
        if term_or_termination_date.is_term():
            calendar = self.on_index_.fixingCalendar()
            self.termination_date_ = Date(
                calendar.advance(
                    self.effective_date_,
                    term_or_termination_date.get_term(),
                    self.on_index_.businessDayConvention(),
                )
            )
        else:
            self.termination_date_ = term_or_termination_date.get_date()
        
        self.strike_ = strike
        self.notional_ = notional
        self.cap_or_floor_ = cap_or_floor
        self.accrual_period_ = accrual_period
        self.accrual_basis_ = accrual_basis
        self.payment_offset_ = payment_offset
        self.payment_business_day_convention_ = payment_business_day_convention
        self.payment_holiday_convention_ = payment_holiday_convention
        self.long_or_short_ = long_or_short
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention
        self.currency_ = Currency(self.on_index_.currency().code())
        
        schedule = make_schedule(
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrual_period=self.accrual_period_,
            holiday_convention=self.holiday_convention_,
            business_day_convention=self.business_day_convention_,
            accrual_basis=self.accrual_basis_,
            payment_offset=self.payment_offset_,
            payment_business_day_convention=self.payment_business_day_convention_,
            payment_holiday_convention=self.payment_holiday_convention_,
        )
        self.caplets_ = []
        for _, row in schedule.iterrows():
            this_caplet = ProductRFRCapletFloorlet(
                effective_date=Date(row["StartDate"]),
                expiry_offset="0D",
                term_or_termination_date=TermOrDate(row["EndDate"]),
                payment_date=Date(row["PaymentDate"]),
                on_index=self.on_index_str_,
                strike=self.strike_,
                notional=self.notional_,
                cap_or_floor=self.cap_or_floor_,
                accrual_basis=self.accrual_basis_,
                long_or_short=self.long_or_short_
            )
            self.caplets_.append(this_caplet)
        if len(self.caplets_) > 0:
            self.last_date_ = self.caplets_[-1].payment_date
        else:
            self.last_date_ = self.termination_date_
    
    @property
    def effective_date(self) -> Date:
        return self.effective_date_
    
    @property
    def termination_date(self) -> Date:
        return self.termination_date_
    
    @property
    def on_index_str(self) -> str:
        return self.on_index_str_
    
    @property
    def on_index(self) -> ql.QuantLib.OvernightIndex:
        return self.on_index_
    
    @property
    def strike(self) -> float:
        return self.strike_
    
    @property
    def notional(self) -> float:
        return self.notional_
    
    @property
    def cap_or_floor(self) -> CapOrFloor:
        return self.cap_or_floor_
    
    @property
    def accrual_period(self) -> Period:
        return self.accrual_period_
    
    @property
    def accrual_basis(self) -> AccrualBasis:
        return self.accrual_basis_
    
    @property
    def payment_offset(self) -> Period:
        return self.payment_offset_
    
    @property
    def payment_business_day_convention(self) -> BusinessDayConvention:
        return self.payment_business_day_convention_
    
    @property
    def payment_holiday_convention(self) -> HolidayConvention:
        return self.payment_holiday_convention_
    
    @property
    def long_or_short(self) -> LongOrShort:
        return self.long_or_short_
    
    @property
    def currency(self) -> Currency:
        return self.currency_
    
    def num_caplets(self) -> int:
        return len(self.caplets_)
    
    def caplets(self, i: int) -> ProductRFRCapletFloorlet:
        return self.caplets_[i]
    
    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)
    
    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        # content["EXPIRY_DATE"] = self.expiry_date_.ISO()
        content["TERMINATION_DATE"] = self.termination_date.ISO()
        content["ON_INDEX"] = self.on_index_str
        content["STRIKE"] = self.strike
        content["NOTIONAL"] = self.notional
        content["CAP_OR_FLOOR"] = self.cap_or_floor.to_string().upper()
        content["ACCRUAL_PERIOD"] = str(self.accrual_period)
        content["ACCRUAL_BASIS"] = self.accrual_basis.value_str
        content["PAYMENT_OFFSET"] = str(self.payment_offset)
        content["PAYMENT_BUSINESS_DAY_CONVENTION"] = self.payment_business_day_convention.value_str
        content["PAYMENT_HOLIDAY_CONVENTION"] = self.payment_holiday_convention.value_str
        content["LONG_OR_SHORT"] = self.long_or_short.to_string().upper()
        content["BUSINESS_DAY_CONVENTION"] = self.business_day_convention_.value_str
        content["HOLIDAY_CONVENTION"] = self.holiday_convention_.value_str
        return content
    
    @classmethod
    def deserialize(cls, input_dict) -> "ProductRFRCapFloor":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        # expiry_date = Date(input_dict["EXPIRY_DATE"])
        termination_date = TermOrDate(input_dict["TERMINATION_DATE"])
        on_index = input_dict["ON_INDEX"]
        strike = float(input_dict["STRIKE"])
        notional = float(input_dict["NOTIONAL"])
        cap_or_floor = CapOrFloor.from_string(input_dict["CAP_OR_FLOOR"])
        accrual_period = Period(input_dict["ACCRUAL_PERIOD"])
        accrual_basis = AccrualBasis(input_dict["ACCRUAL_BASIS"])
        payment_offset = Period(input_dict["PAYMENT_OFFSET"])
        payment_business_day_convention = BusinessDayConvention(input_dict["PAYMENT_BUSINESS_DAY_CONVENTION"])
        payment_holiday_convention = HolidayConvention(input_dict["PAYMENT_HOLIDAY_CONVENTION"])
        long_or_short = LongOrShort.from_string(input_dict["LONG_OR_SHORT"])
        business_day_convention = BusinessDayConvention(input_dict["BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention(input_dict["HOLIDAY_CONVENTION"])

        return cls(effective_date, 
                #    expiry_date,
                   termination_date, 
                   on_index,
                   strike,
                   notional,
                   cap_or_floor,
                   accrual_period,
                   accrual_basis,
                   payment_offset,
                   payment_business_day_convention,
                   payment_holiday_convention,
                   long_or_short,
                   business_day_convention,
                   holiday_convention
                   )

class ProductRFRSwaption(Product):

    _version = 1
    _product_type = "PRODUCT_RFR_SWAPTION"

    def __init__(
        self,
        expiry_date: Date,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        payment_off_set: Period,
        on_index: str,
        strike: float,
        pay_or_rec: PayOrReceive,
        notional: float,
        accrual_period: Period,
        accrual_basis: AccrualBasis,
        floating_leg_accrual_period: Optional[Period] = None,
        pay_business_day_convention: Optional[BusinessDayConvention] = BusinessDayConvention("F"),
        pay_holiday_convention: Optional[HolidayConvention] = HolidayConvention("USGS"),
        spread: Optional[float] = 0.0,
        compounding_method: Optional[CompoundingMethod] = CompoundingMethod.COMPOUND,
        long_or_short: LongOrShort = LongOrShort.LONG
    ) -> None:

        super().__init__()

        self.on_index_str_ = on_index
        self.on_index_ = IndexRegistry().get(on_index)
        self.expiry_date_ = expiry_date
        self.first_date_ = self.expiry_date_
        self.effective_date_ = effective_date
        self.term_or_termination_date_ = term_or_termination_date
        self.payment_offset_ = payment_off_set

        if term_or_termination_date.is_term():
            calendar = self.on_index_.fixingCalendar()
            self.termination_date_ = Date(
                calendar.advance(
                    self.effective_date_,
                    term_or_termination_date.get_term(),
                    self.on_index_.businessDayConvention(),
                )
            )
        else:
            self.termination_date_ = term_or_termination_date.get_date()
     
        self.strike_ = strike
        self.pay_or_rec_ = pay_or_rec
        self.notional_ = notional
        self.accrual_basis_ = accrual_basis
        self.accrual_period_ = accrual_period
        self.floating_leg_accrual_period_ = (
            self.accrual_period_
            if floating_leg_accrual_period is None
            else floating_leg_accrual_period
        )
        self.pay_business_day_convention_ = pay_business_day_convention
        self.pay_holiday_convention_ = pay_holiday_convention
        self.spread_ = spread
        self.compounding_method_ = compounding_method
        self.long_or_short_ = long_or_short

        self.swap_tenor_ = accrued(
            self.effective_date_,
            self.termination_date_,
            self.accrual_basis_
        )
        
        self.currency_ = Currency(self.on_index_.currency().code())
      
        # underlying swap
        self.underlying_swap_ = ProductRFRSwap(
            effective_date=self.effective_date_,
            term_or_termination_date= self.term_or_termination_date_,
            payment_off_set= self.payment_offset_,
            on_index=self.on_index_str_,
            fixed_rate=self.strike_, # strike is the fixed rate of underlying swap
            pay_or_rec=self.pay_or_rec_,
            notional=self.notional_,
            accrual_period=self.accrual_period_,
            accrual_basis=self.accrual_basis_,
            floating_leg_accrual_period=self.floating_leg_accrual_period_,
            pay_business_day_convention=self.pay_business_day_convention_,
            pay_holiday_convention=self.pay_holiday_convention_,
            spread=self.spread_,
            compounding_method=self.compounding_method_,
        )

    @property
    def expiry_date(self) -> Date:
        return self.expiry_date_

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
    def payment_offset(self) -> Period:
        return self.payment_offset_

    @property
    def on_index_str(self) -> str:
        return self.on_index_str_

    @property
    def on_index(self) -> ql.QuantLib.OvernightIndex:
        return self.on_index_

    @property
    def strike(self) -> float:
        return self.strike_

    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def accrual_period(self) -> Period:
        return self.accrual_period_

    @property
    def floating_leg_accrual_period(self) -> Period:
        return self.floating_leg_accrual_period_

    @property
    def accrual_basis(self) -> AccrualBasis:
        return self.accrual_basis_

    @property
    def pay_business_day_convention(self) -> BusinessDayConvention:
        return self.pay_business_day_convention_

    @property
    def pay_holiday_convention(self) -> HolidayConvention:
        return self.pay_holiday_convention_

    @property
    def spread(self) -> float:
        return self.spread_

    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_

    @property
    def long_or_short(self) -> LongOrShort:
        return self.long_or_short_

    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def underlying_swap(self) -> ProductRFRSwap:
        return self.underlying_swap_

    @property
    def swap_tenor(self) -> float:
        return self.swap_tenor_

    def is_payer(self) -> bool:
        return self.pay_or_rec_ == PayOrReceive.PAY

    def is_receiver(self) -> bool:
        return self.pay_or_rec_ == PayOrReceive.RECEIVE

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EXPIRY_DATE"] = self.expiry_date.ISO()
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        if self.term_or_termination_date.is_term():
            content["TERM_OR_TERMINATION_DATE"] = self.term_or_termination_date.get_term().__str__()
        else:
            content["TERM_OR_TERMINATION_DATE"] = self.term_or_termination_date.get_date().ISO()
        content["PAYMENT_OFFSET"] = str(self.payment_offset_)
        content["ON_INDEX"] = self.on_index_str_
        content["STRIKE"] = self.strike
        content["PAY_OR_REC"] = self.pay_or_rec.to_string().upper()
        content["NOTIONAL"] = self.notional
        content["ACCRUAL_PERIOD"] = self.accrual_period.__str__()
        content["FLOATING_LEG_ACCRUAL_PERIOD"] = self.floating_leg_accrual_period.__str__()
        content["ACCRUAL_BASIS"] = self.accrual_basis.value_str
        content["PAY_BUSINESS_DAY_CONVENTION"] = self.pay_business_day_convention.value_str
        content["PAY_HOLIDAY_CONVENTION"] = self.pay_holiday_convention.value_str
        content["SPREAD"] = self.spread
        content["COMPOUNDING_METHOD"] = self.compounding_method.to_string().upper()
        content["LONG_OR_SHORT"] = self.long_or_short.to_string().upper()
        
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductRFRSwaption":
        expiry_date = Date(input_dict["EXPIRY_DATE"])
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        payment_offset = Period(input_dict["PAYMENT_OFFSET"])
        on_index = input_dict["ON_INDEX"]
        strike = float(input_dict["STRIKE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        notional = float(input_dict["NOTIONAL"])
        accrual_period = Period(input_dict["ACCRUAL_PERIOD"])
        floating_leg_accrual_period = Period(input_dict["FLOATING_LEG_ACCRUAL_PERIOD"])
        accrual_basis = AccrualBasis(input_dict["ACCRUAL_BASIS"])
        pay_business_day_convention = BusinessDayConvention(
            input_dict["PAY_BUSINESS_DAY_CONVENTION"]
        )
        pay_holiday_convention = HolidayConvention(input_dict["PAY_HOLIDAY_CONVENTION"])
        spread = float(input_dict["SPREAD"])
        compounding_method = CompoundingMethod.from_string(input_dict["COMPOUNDING_METHOD"])
        long_or_short = LongOrShort.from_string(input_dict["LONG_OR_SHORT"])

        return cls(
            expiry_date=expiry_date,
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            payment_off_set=payment_offset,
            on_index=on_index,
            strike=strike,
            pay_or_rec=pay_or_rec,
            notional=notional,
            accrual_period=accrual_period,
            accrual_basis=accrual_basis,
            floating_leg_accrual_period=floating_leg_accrual_period,
            pay_business_day_convention=pay_business_day_convention,
            pay_holiday_convention=pay_holiday_convention,
            spread=spread,
            compounding_method=compounding_method,
            long_or_short=long_or_short,
        )


# register
ProductBuilderRegistry().register(ProductRFRCapletFloorlet._product_type, ProductRFRCapletFloorlet)
ProductBuilderRegistry().register(ProductRFRCapFloor._product_type, ProductRFRCapFloor)
ProductBuilderRegistry().register(ProductRFRSwaption._product_type, ProductRFRSwaption)

# support de-serilization
ProductBuilderRegistry().register(f"{ProductRFRCapletFloorlet._product_type}_DES", ProductRFRCapletFloorlet.deserialize)
ProductBuilderRegistry().register(f"{ProductRFRCapFloor._product_type}_DES", ProductRFRCapFloor.deserialize)
ProductBuilderRegistry().register(f"{ProductRFRSwaption._product_type}_DES", ProductRFRSwaption.deserialize)
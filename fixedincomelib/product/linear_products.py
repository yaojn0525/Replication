from typing import List, Optional

# in-house
from fixedincomelib.date import *
from fixedincomelib.market import *
from fixedincomelib.product.utilities import *
from fixedincomelib.product.product_interfaces import *
from fixedincomelib.product.product_portfolio import ProductPortfolio

### ATOMIC PRODUCTS (NO NEED TO SUPPORT FACTORY CREATION)

class ProductBulletCashflow(ProductCashflow):

    _version = 1
    _product_type = "PRODUCT_BULLET_CASHFLOW"

    def __init__(
        self,
        termination_date: Date,
        currency: Currency,
        notional: float,
        long_or_short: LongOrShort,
        pay_date_or_payment_offset: Optional[TermOrDate]=TermOrDate("0D")) -> None:

        super().__init__(
            term_or_termination_date=TermOrDate(termination_date),
            notional=notional,
            long_or_short=long_or_short,
            currency=currency,
            pay_date_or_payment_offset=pay_date_or_payment_offset)

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["TERMINATION_DATE"] = self.termination_date.ISO()
        content["LONG_OR_SHORT"] = self.long_or_short.to_string().upper()
        content["NOTIONAL"] = self.notional
        content["CURRENCY"] = self.currency.code()
        content["PAYMENT_DATE_OR_OFFSET"] = TermOrDate.to_string(self.pay_date_or_payment_offset)
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductBulletCashflow":
        termination_date = Date(input_dict["TERMINATION_DATE"])
        long_or_short = LongOrShort.from_string(input_dict["LONG_OR_SHORT"])
        notional = float(input_dict["NOTIONAL"])
        currency = Currency(input_dict["CURRENCY"])
        payment_date_or_offset = TermOrDate(input_dict["PAYMENT_DATE_OR_OFFSET"])
        return cls(termination_date, currency, notional, long_or_short, payment_date_or_offset)

class ProductFixedAccrued(ProductCashflow):

    _version = 1
    _product_type = "PRODUCT_FIXED_ACCRUED"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec : PayOrReceive,
        currency: Currency,
        notional: float,
        coupon : float,
        accrual_basis: ql.DayCounter,
        business_day_convention: Optional[int]=ql.Unadjusted,
        holiday_convention: Optional[ql.Calendar]=ql.NullCalendar(),
        pay_date_or_payment_offset: Optional[TermOrDate]=TermOrDate("0D"),
        pay_business_day_convention: Optional[BusinessDayConvention] = ql.Unadjusted,
        pay_holiday_convention: Optional[ql.Calendar] = ql.NullCalendar()
    ) -> None:

        super().__init__(
            term_or_termination_date=term_or_termination_date,
            notional=notional,
            currency=currency,
            long_or_short=LongOrShort.LONG if notional >= 0 else LongOrShort.SHORT,
            effective_date=effective_date,
            fixed_rate_or_spread=coupon,
            accrual_basis=accrual_basis,
            pay_date_or_payment_offset=pay_date_or_payment_offset,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            payment_business_day_convention=pay_business_day_convention,
            payment_holiday_convention=pay_holiday_convention)
        self.pay_or_rec_ = pay_or_rec

    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.term_or_termination_date)
        content["PAY_OR_REC"] = self.pay_or_rec.value
        content["CURRENCY"] = self.currency.code()
        content["NOTIONAL"] = self.notional
        content["COUPON"] = self.fixed_rate
        content["ACCRUAL_BASIS"] = AccrualBasis.to_string(self.accrual_basis)
        content["BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.business_day_convention)
        content["HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.holiday_convention)
        content["PAYMENT_DATE_OR_OFFSET"] = TermOrDate.to_string(self.pay_date_or_payment_offset)
        content["PAY_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.business_day_convention)
        content["PAY_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.holiday_convention)
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductFixedAccrued":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive(input_dict["PAY_OR_REC"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        coupon = float(input_dict["COUPON"])
        accrual_basis = AccrualBasis.new(input_dict["ACCRUAL_BASIS"])
        business_day_convention = BusinessDayConvention.new(input_dict["BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["HOLIDAY_CONVENTION"])
        pay_date_or_offset = TermOrDate(input_dict["PAYMENT_DATE_OR_OFFSET"])
        pay_business_day_convention = BusinessDayConvention.new(input_dict["PAY_BUSINESS_DAY_CONVENTION"])
        pay_holiday_convention = HolidayConvention.new(input_dict["PAY_HOLIDAY_CONVENTION"])
        return ProductFixedAccrued(
            effective_date,
            term_or_termination_date,
            pay_or_rec,
            currency,
            notional,
            coupon,
            accrual_basis, 
            business_day_convention,
            holiday_convention,
            pay_date_or_offset,
            pay_business_day_convention,
            pay_holiday_convention)

class ProductOvernightIndexCompositeCashflow(ProductCashflow):

    _version = 1
    _product_type = "PRODUCT_OVERNIGHT_COMPOSITE_INDEX_CASHFLOW"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec : PayOrReceive,
        on_composite_index: OvernightCompositeIndex,
        spread: float,
        currency: Currency,
        notional: float,
        leverage: Optional[float]=1.,
        accrual_basis: Optional[ql.DayCounter]=None,
        pay_date_or_payment_offset: Optional[TermOrDate]=TermOrDate("0D"),
        payment_business_day_convention : Optional[int]=ql.Unadjusted,
        payment_holiday_convention : Optional[ql.Calendar]=ql.NullCalendar(),
        look_back_window : Optional[Period]=Period(ql.NoFrequency),
        rate_cutoff : Optional[Period]=Period(ql.NoFrequency)
    ) -> None:

        super().__init__(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            currency=currency,
            notional=notional,
            index=on_composite_index,
            fixed_rate_or_spread=spread,
            accrual_basis=accrual_basis,
            pay_date_or_payment_offset=pay_date_or_payment_offset,
            payment_business_day_convention=payment_business_day_convention,
            payment_holiday_convention=payment_holiday_convention)

        self.pay_or_rec_ = pay_or_rec
        self.leverage_ = leverage
        self.rates_cut_off_ = rate_cutoff
        self.look_back_window_ = look_back_window

    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def leverage(self) -> float:
        return self.leverage_

    @property
    def rate_cutoff(self) -> Period:
        return self.rates_cut_off_

    @property
    def look_back_window(self) -> Period:
        return self.look_back_window_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.term_or_termination_date)
        content["PAY_OR_REC"] = PayOrReceive.to_string(self.pay_or_rec)
        content["ON_COMPOSITE_INDEX"] = self.index.index_name()
        content["SPREAD"] = self.spread
        content["CURRENCY"] = self.currency.code()
        content["NOTIONAL"] = self.notional
        content["LEVERAGE"] = self.leverage
        content["ACCRUAL_BASIS"] = AccrualBasis.to_string(self.accrual_basis) if self.accrual_basis else "NONE"
        content["PAYMENT_DATE_OR_OFFSET"] = TermOrDate.to_string(self.pay_date_or_payment_offset)
        content["PAYMENT_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.payment_business_day_convention)
        content["PAYMENT_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.payment_holiday_convention)
        content["RATES_CUT_OFF"] = Period.to_string(self.rate_cutoff)
        content["LOOKBACK_WINDOW"] = Period.to_string(self.look_back_window)
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductOvernightIndexCompositeCashflow":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        on_composite_index = IndexRegistry().get(input_dict["ON_COMPOSITE_INDEX"])
        spread = float(input_dict["SPREAD"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        leverage = float(input_dict.get("LEVERAGE", 1.))
        accrual_basis = None
        if input_dict["ACCRUAL_BASIS"].upper() != "NONE":
            accrual_basis = AccrualBasis.new(input_dict["ACCRUAL_BASIS"])
        pay_date_or_offset = TermOrDate(input_dict["PAYMENT_DATE_OR_OFFSET"])
        payment_business_day_convention = BusinessDayConvention.new(input_dict["PAYMENT_BUSINESS_DAY_CONVENTION"])
        payment_holiday_convention = HolidayConvention.new(input_dict["PAYMENT_HOLIDAY_CONVENTION"])
        rate_cutoff = Period(input_dict["RATES_CUT_OFF"])
        lookback_window = Period(input_dict["LOOKBACK_WINDOW"])
        return ProductOvernightIndexCompositeCashflow(
            effective_date,
            term_or_termination_date,
            pay_or_rec,
            on_composite_index,
            spread,
            currency,
            notional,
            leverage,
            accrual_basis,
            pay_date_or_offset,
            payment_business_day_convention,
            payment_holiday_convention,
            rate_cutoff,
            lookback_window)

class ProductIBORIndexCashflow(ProductCashflow):

    _version = 1
    _product_type = "PRODUCT_IBOR_INDEX_CASHFLOW"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec : PayOrReceive,
        ibor_index: Index,
        spread: float,
        currency: Currency,
        notional: float,
        leverage: Optional[float]=1.,
        accrual_basis: Optional[AccrualBasis]=None,
        pay_date_or_payment_offset: Optional[TermOrDate]=TermOrDate("0D"),
        payment_business_day_convention : Optional[int]=ql.Unadjusted,
        payment_holiday_convention : Optional[ql.Calendar]=ql.NullCalendar(),
        pay_in_advance : Optional[bool]=False
    ) -> None:

        super().__init__(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            currency=currency,
            notional=notional,
            index=ibor_index,
            fixed_rate_or_spread=spread,
            accrual_basis=accrual_basis,
            pay_in_advance=pay_in_advance,
            pay_date_or_payment_offset=pay_date_or_payment_offset,
            payment_business_day_convention=payment_business_day_convention,
            payment_holiday_convention=payment_holiday_convention)
        self.pay_or_rec_ = pay_or_rec
        self.leverage_ = leverage

    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def leverage(self) -> float:
        return self.leverage_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.term_or_termination_date)
        content["PAY_OR_REC"] = PayOrReceive.to_string(self.pay_or_rec)
        content["IBOR_INDEX"] = self.index.index_name()
        content["SPREAD"] = self.spread
        content["CURRENCY"] = self.currency.code()
        content["NOTIONAL"] = self.notional
        content["LEVERAGE"] = self.leverage
        content["ACCRUAL_BASIS"] = AccrualBasis.to_string(self.accrual_basis) if self.accrual_basis else "NONE"
        content["PAYMENT_DATE_OR_OFFSET"] = self.payment_date.ISO()
        content["PAYMENT_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.payment_business_day_convention)
        content["PAYMENT_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.payment_holiday_convention)
        content["PAY_IN_ADVANCE"] = self.pay_in_advance
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductIBORIndexCashflow":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        ibor_index = IndexRegistry().get(input_dict["IBOR_INDEX"])
        spread = float(input_dict["SPREAD"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        leverage = float(input_dict.get("LEVERAGE", 1.))
        accrual_basis = None
        if input_dict["ACCRUAL_BASIS"] != "NONE":
            accrual_basis = AccrualBasis.new(input_dict["ACCRUAL_BASIS"])
        pay_date_or_offset = TermOrDate(input_dict["PAYMENT_DATE_OR_OFFSET"])
        payment_business_day_convention = BusinessDayConvention.new(input_dict["PAYMENT_BUSINESS_DAY_CONVENTION"])
        payment_holiday_convention = HolidayConvention.new(input_dict["PAYMENT_HOLIDAY_CONVENTION"])
        pay_in_advance = bool(input_dict["PAY_IN_ADVANCE"])
        return ProductIBORIndexCashflow(
            effective_date,
            term_or_termination_date,
            pay_or_rec,
            ibor_index,
            spread,
            currency,
            notional,
            leverage,
            accrual_basis,
            pay_date_or_offset,
            payment_business_day_convention,
            payment_holiday_convention,
            pay_in_advance)

class ProductIBORCompoundingCashflow(ProductIBORIndexCashflow):

    _version = 1
    _product_type = "PRODUCT_IBOR_COMPOUNDING_CASHFLOW"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec : PayOrReceive,
        ibor_index: Index,
        spread: float,
        currency: Currency,
        notional: float,
        calculation_period: Period,
        leverage: Optional[float]=1.,
        pay_date_or_payment_offset: Optional[Period|Date]=Period(ql.NoFrequency),
        payment_business_day_convention: Optional[int]=ql.Unadjusted,
        payment_holiday_convention: Optional[ql.Calendar]=ql.NullCalendar(),
        compounding_method: Optional[CompoundingMethod]=CompoundingMethod.SPREAD_EXCLUSIVE_COMPOUND
    ) -> None:

        super().__init__(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=pay_or_rec,
            ibor_index=ibor_index,
            spread=spread,
            currency=currency,
            notional=notional,
            accrual_basis=None,
            pay_date_or_payment_offset=pay_date_or_payment_offset,
            payment_business_day_convention=payment_business_day_convention,
            payment_holiday_convention=payment_holiday_convention,
            pay_in_advance=False)
        self.pay_or_rec_ = pay_or_rec

        ### extra info
        assert (compounding_method == CompoundingMethod.FLAT_COMPOUND) or \
            (compounding_method == CompoundingMethod.SPREAD_EXCLUSIVE_COMPOUND)
        
        self.compounding_method_ = compounding_method
        self.leverage_ = leverage
        self.calculation_period_ = calculation_period

        ### sort out compounding 
        casted_ibor : IBORIndex = self.index
        # listfy member variables
        self.fixing_dates_ = []
        self.accrual_start_dates_ = []
        self.accrual_end_dates_ = []
        self.accrues_ = [] 
        # period by period
        this_start_date = self.effective_date_
        while this_start_date < self.termination_date_:
            this_fixing_date = casted_ibor.fixingDate(this_start_date)
            this_end_date = add_period_by_index(
                this_start_date, 
                self.calculation_period_, 
                self.index_)
            this_accrue = accrued(
                this_start_date, 
                this_end_date, 
                self.accrual_basis_, 
                casted_ibor.payment_business_day_conv, 
                casted_ibor.settlement_holiday)
            self.fixing_dates_.append(this_fixing_date)
            self.accrual_start_dates_.append(this_start_date)
            self.accrual_end_dates_.append(this_end_date)
            self.accrues_.append(this_accrue)
            # update start date
            this_start_date = this_end_date              
        # we may have a short stub in the end
        if this_start_date != self.termination_date_:
            end_dt = self.accrual_end_dates_[-1]
            self.accrual_end_dates_[-1] = self.termination_date_
            self.accrues_[-1] = accrued(
                self.accrual_start_dates_[-1], 
                end_dt, 
                self.accrual_basis_,
                casted_ibor.payment_business_day_conv,
                casted_ibor.settlement_holiday)
    
    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def leverage(self) -> float:
        return self.leverage_
    
    @property
    def calculation_period(self) -> Period:
        return self.calculation_period_

    @property
    def ibor_fixing_dates(self) -> List[Date]:
        return self.fixing_dates_
    
    @property
    def accrual_start_dates(self) -> List[Date]:
        return self.accrual_start_dates_
    
    @property
    def accrual_end_dates(self) -> List[Date]:
        return self.accrual_end_dates_
    
    @property
    def accrued(self) -> List[float]:
        return self.accrued_
    
    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.term_or_termination_date)
        content["PAY_OR_REC"] = PayOrReceive.to_string(self.pay_or_rec)
        content["IBOR_INDEX"] = self.index.index_name()
        content["SPREAD"] = self.spread
        content["CURRENCY"] = self.currency.code()
        content["NOTIONAL"] = self.notional
        content["CALCULATION_PERIOD"] = Period.to_string(self.calculation_period)
        content["LEVERAGE"] = self.leverage
        content["PAYMENT_DATE_OR_OFFSET"] = TermOrDate.to_string(self.pay_date_or_payment_offset)
        content["PAYMENT_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.payment_business_day_convention)
        content["PAYMENT_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.payment_holiday_convention)
        content["COMPOUNDING_METHOD"] = self.compounding_method.to_string().upper()
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductIBORCompoundingCashflow":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        ibor_index = IndexRegistry().get(input_dict["IBOR_INDEX"])
        spread = float(input_dict["SPREAD"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        calculation_period = Period(input_dict["CALCULATION_PERIOD"])
        leverage = float(input_dict["LEVERAGE"])            
        payment_date = TermOrDate(input_dict["PAYMENT_DATE_OR_OFFSET"])
        payment_business_day_convention = BusinessDayConvention.new(input_dict["PAYMENT_BUSINESS_DAY_CONVENTION"])
        payment_holiday_convention = HolidayConvention.new(input_dict["PAYMENT_HOLIDAY_CONVENTION"])
        compounding_method = CompoundingMethod.from_string(input_dict["COMPOUNDING_METHOD"])
        return ProductIBORCompoundingCashflow(
            effective_date,
            term_or_termination_date,
            pay_or_rec,
            ibor_index,
            spread,
            currency,
            notional,
            calculation_period,
            leverage,
            payment_date,
            payment_business_day_convention,
            payment_holiday_convention,
            compounding_method)

class ProductInterestRateStream(ProductPortfolio):

    _version = 1
    _product_type = "PRODUCT_INTEREST_RATE_STREAM"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec : PayOrReceive,
        fixed_rate_or_spread : float,
        currency: Currency,
        notional : float,
        business_day_convention : int,
        holiday_convention : ql.Calendar,
        index: Optional[Index]=None,
        leverage : Optional[float]=1.,
        accrual_basis: Optional[ql.DayCounter]=None,
        accrual_period : Optional[Period]=Period(ql.NoFrequency),
        calculation_period : Optional[Period]=Period(ql.NoFrequency),
        pay_in_advance : Optional[bool]=False,
        payment_date_or_offset: Optional[TermOrDate]=TermOrDate("0D"),
        payment_business_day_convention : Optional[int]=ql.Unadjusted,
        payment_holiday_convention : Optional[ql.Calendar]=ql.NullCalendar(),
        compounding_method: Optional[CompoundingMethod]=CompoundingMethod.FLAT_COMPOUND,
        look_back_window : Optional[Period]=Period(ql.NoFrequency),
        rate_cutoff : Optional[Period]=Period(ql.NoFrequency),
        schedule_generation_rule : Optional[int] = ql.DateGeneration.Backward,
        end_of_month: Optional[bool] = False,
        first_regular_date : Optional[Date]=Date(),
        next_to_last_date : Optional[Date]=Date()):

        self.effective_date_ = effective_date
        self.term_or_termination_date_ = term_or_termination_date
        self.pay_or_rec_ = pay_or_rec
        self.notional_ = notional
        self.currency_ = currency
        self.index_ = index
        self.fixed_rate_ = None
        self.spread_ = None
        assert payment_date_or_offset.is_term()
        self.payment_offset_ = payment_date_or_offset.get_term()
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention
        self.payment_business_day_convention_ = payment_business_day_convention \
            if BusinessDayConvention.is_valid(payment_business_day_convention) else self.business_day_convention_
        self.payment_holiday_convention_ = payment_holiday_convention \
            if HolidayConvention.is_valid(payment_holiday_convention)  else self.holiday_convention_
        self.leverage_ = leverage
        self.accrual_basis_ = accrual_basis
        self.accrual_period_ = accrual_period
        self.calculation_period_ = calculation_period
        self.compounding_method_ = compounding_method
        self.pay_in_advance_ = pay_in_advance
        self.look_back_window_ = look_back_window
        self.rate_cutoff_ = rate_cutoff
        self.schedule_generation_rule_ = schedule_generation_rule
        self.end_of_month_ = end_of_month
        self.first_regular_date_ = first_regular_date
        self.next_to_last_date_ = next_to_last_date

        ### resolve index
        self.is_on_composite_ = False
        if self.index_:
            if isinstance(self.index_, OvernightCompositeIndex):
                self.is_on_composite_ = True
                casted_on_composite_index : OvernightCompositeIndex = self.index_
                self.accrual_basis_ = accrual_basis if accrual_basis else \
                    casted_on_composite_index.index.accrual_basis
            elif isinstance(self.index_, IBORIndex):
                casted_ibor_index : IBORIndex = self.index_
                self.accrual_basis_ = accrual_basis if accrual_basis else \
                    casted_ibor_index.accrual_basis
                if not self.calculation_period_:
                    self.accrual_period_ = casted_ibor_index.term

        ### get termination date
        self.termination_date_ =  None
        if self.term_or_termination_date_.is_term():
            self.termination_date_ = add_period(
                self.effective_date_,
                self.term_or_termination_date_.get_term(),
                business_day_convention,
                holiday_convention,
                self.end_of_month_)
        else:
            self.termination_date_ = self.term_or_termination_date_.get_date()

        ### generate schedule
        schedule = make_schedule(
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrual_period=accrual_period,
            holiday_convention=self.holiday_convention_,
            business_day_convention=self.business_day_convention_,
            accrual_basis=AccrualBasis.new("ACTUAL/ACTUAL (ISDA)"), # not
            rule=self.schedule_generation_rule_,
            end_of_month=self.end_of_month_,
            fix_in_arrear=self.is_on_composite_,
            payment_offset=self.payment_offset_,
            payment_business_day_convention=self.payment_business_day_convention_,
            payment_holiday_convention=self.payment_holiday_convention_,
            first_regular_date=self.first_regular_date_,
            next_to_last_date=self.next_to_last_date_)

        ### create cashflow product
        products, weights = [], []
        for _, row in schedule.iterrows():
            this_cashflow = None
            start = row.StartDate
            end = TermOrDate(row.EndDate)
            if not self.index_:
                assert accrual_period.is_valid()
                # tied to fixed rate
                self.fixed_rate_ = fixed_rate_or_spread
                this_cashflow = ProductFixedAccrued(
                    Date(start),
                    end,
                    self.pay_or_rec_,
                    self.currency_,
                    self.notional_,
                    self.fixed_rate_,
                    self.accrual_basis_,
                    self.business_day_convention_,
                    self.holiday_convention_,
                    TermOrDate(self.payment_offset_),
                    self.payment_business_day_convention_,
                    self.payment_holiday_convention_)
            else:
                # tied to index
                self.spread_ = fixed_rate_or_spread
                if self.is_on_composite_:
                    # tied to overnight composite index
                    this_cashflow = ProductOvernightIndexCompositeCashflow(
                        Date(start),
                        end,
                        self.pay_or_rec_,
                        self.index_,
                        self.spread_,
                        self.currency_,
                        self.notional_,
                        leverage,
                        self.accrual_basis_,
                        TermOrDate(self.payment_offset_),
                        self.payment_business_day_convention_,
                        self.payment_holiday_convention_,
                        self.look_back_window_,
                        self.rate_cutoff_)
                else:
                    if self.calculation_period_.is_valid():
                        # tied to compounding index
                        assert self.compounding_method_ in [CompoundingMethod.FLAT_COMPOUND, CompoundingMethod.SPREAD_EXCLUSIVE_COMPOUND]
                        this_cashflow = ProductIBORCompoundingCashflow(
                            Date(start),
                            end,
                            self.pay_or_rec_,
                            self.index_,
                            self.spread_,
                            self.currency_,
                            self.notional_,
                            self.calculation_period_,
                            leverage,
                            TermOrDate(self.payment_offset_),
                            self.payment_business_day_convention_,
                            self.payment_holiday_convention_,
                            self.compounding_method_)
                    else:
                        # tied to simple ibor
                        this_cashflow = ProductIBORIndexCashflow(
                            Date(start),
                            end,
                            self.pay_or_rec_,
                            self.index_,
                            self.spread_,
                            self.currency_,
                            self.notional_,
                            leverage,
                            self.accrual_basis_,
                            TermOrDate(self.payment_offset_),
                            self.payment_business_day_convention_,
                            self.payment_holiday_convention_,
                            self.pay_in_advance_)
                    
            # populate interest rate stream
            products.append(this_cashflow)
            weights.append(1.0)

        super().__init__(products, weights)

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
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_
    
    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def currency(self) -> Currency:
        return self.currency_

    @property
    def index(self) -> Index:
        return self.index_

    @property
    def spread(self) -> float:
        return self.spread_
    
    @property
    def fixed_rate(self) -> float:
        return self.fixed_rate_

    @property
    def leverage(self):
        return self.leverage_
    
    @property
    def payment_offset(self) -> Period:
        return self.payment_offset_

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
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_

    @property
    def accrual_period(self) -> Period:
        return self.accrual_period_
    
    @property
    def calculation_period(self) -> Period:
        return self.calculation_period_

    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_

    @property
    def pay_in_advance(self) -> bool:
        return self.pay_in_advance_

    @property
    def pay_in_advance(self) -> bool:
        return self.pay_in_advance_
    
    @property
    def look_back_window(self) -> Period:
        return self.look_back_window_
    
    @property
    def rate_cutoff(self) -> Period:
        return self.rate_cutoff_

    @property
    def schedule_generation_rule(self) -> int:
        return self.schedule_generation_rule_
    
    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_
    
    @property
    def first_regular_date(self):
        return self.first_regular_date_
    
    @property
    def next_to_last_date(self):
        return self.next_to_last_date_
        
    def cashflow(self, i: int) -> ProductCashflow:
        return self.element(i)

    def num_cashflows(self) -> int:
        return self.num_elements_

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.term_or_termination_date)
        content["PAY_OR_REC"] = PayOrReceive.to_string(self.pay_or_rec)
        content["FIXED_RATE_OR_SPREAD"] = self.fixed_rate if self.fixed_rate else self.spread
        content["CURRENCY"] = self.currency[0].code()
        content["NOTIONAL"] = list(self.notional.values())[0]
        content["BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.business_day_convention)
        content["HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.holiday_convention)
        content["INDEX"] = self.index.index_name() if self.index else "INVALID"
        content["LEVERAGE"] = self.leverage
        content["ACCRUAL_BASIS"] = AccrualBasis.to_string(self.accrual_basis) \
            if self.accrual_basis else "NONE"
        content["ACCRUAL_PERIOD"] = Period.to_string(self.accrual_period)
        content["CALCULATION_PERIOD"] = Period.to_string(self.accrual_period)
        content["PAY_IN_ADVANCE"] = self.pay_in_advance
        content["PAYMENT_DATE_OR_OFFSET"] = Period.to_string(self.payment_offset)
        content["PAYMENT_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.payment_business_day_convention)
        content["PAYMENT_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.payment_holiday_convention)
        content["COMPOUNDING_METHOD"] = self.compounding_method.to_string().upper()
        content["LOOK_BACK_WINDOW"] = Period.to_string(self.look_back_window)
        content["RATE_CUTOFF"] = Period.to_string(self.rate_cutoff)
        content["SCHEDULE_GENERATION_CODE"] = self.schedule_generation_rule
        content["END_OF_MONTH"] = self.end_of_month
        content["FIRST_REGULAR_DATE"] = self.first_regular_date.ISO()
        content["NEXT_TO_LAST_DATE"] = self.next_to_last_date.ISO()
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductInterestRateStream":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        fixed_rate_or_spread = float(input_dict["FIXED_RATE_OR_SPREAD"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        business_day_convention = BusinessDayConvention.new(input_dict["BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["HOLIDAY_CONVENTION"])
        index = IndexRegistry().get(input_dict["INDEX"]) if input_dict["INDEX"] != "INVALID" else None
        leverage = float(input_dict["LEVERAGE"])
        accrual_basis = AccrualBasis.new(input_dict["ACCRUAL_BASIS"])
        accrual_period = Period(input_dict["ACCRUAL_PERIOD"])
        calculation_period = Period(input_dict["CALCULATION_PERIOD"])
        pay_in_advance = bool(input_dict["PAY_IN_ADVANCE"])
        pay_date_or_offset = TermOrDate(input_dict["PAYMENT_DATE_OR_OFFSET"])
        payment_business_day_convention = BusinessDayConvention.new(input_dict["PAYMENT_BUSINESS_DAY_CONVENTION"])
        payment_holiday_convention = HolidayConvention.new(input_dict["PAYMENT_HOLIDAY_CONVENTION"])
        compounding_method = CompoundingMethod.from_string(input_dict["COMPOUNDING_METHOD"])
        lookback_window = Period(input_dict["LOOK_BACK_WINDOW"])
        rate_cutoff = Period(input_dict["RATE_CUTOFF"])
        schedule_generation_rule = resolve_schedule_generation(input_dict["SCHEDULE_GENERATION_CODE"])
        end_of_month = bool(input_dict["END_OF_MONTH"])
        first_regular_date = Date(input_dict["FIRST_REGULAR_DATE"])
        next_to_last_date = Date(input_dict["NEXT_TO_LAST_DATE"])
        return ProductInterestRateStream(
            effective_date,
            term_or_termination_date,
            pay_or_rec,
            fixed_rate_or_spread,
            currency,
            notional,
            business_day_convention,
            holiday_convention,
            index,
            leverage,
            accrual_basis,
            accrual_period,
            calculation_period,
            pay_in_advance,
            pay_date_or_offset,
            payment_business_day_convention,
            payment_holiday_convention,
            compounding_method,
            lookback_window,
            rate_cutoff,
            schedule_generation_rule,
            end_of_month,
            first_regular_date,
            next_to_last_date)


### CALIBRATION INSTRUMENTS
class ProductCashDeposit(ProductFixedAccrued):

    _version = 1
    _product_type = "PRODUCT_CASH_DEPOSIT"

    def __init__(
        self,
        effective_date : Date,
        term_or_termination_date : TermOrDate,
        pay_or_rec : PayOrReceive,
        currency: Currency,
        notional: float,
        coupon : float,
        accrual_basis : ql.DayCounter,
        pay_date_or_offset : Optional[TermOrDate]=TermOrDate("0D"),
        pay_business_day_convention : Optional[int]=ql.Unadjusted,
        pay_holiday_convention : Optional[ql.Calendar]=ql.NullCalendar()
    ) -> None:
        
        super().__init__(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=pay_or_rec,
            currency=currency,
            notional=notional,
            coupon=coupon,
            accrual_basis=accrual_basis,
            business_day_convention=pay_business_day_convention,
            holiday_convention=pay_holiday_convention,
            pay_date_or_payment_offset=pay_date_or_offset,
            pay_business_day_convention=pay_business_day_convention,
            pay_holiday_convention=pay_holiday_convention)

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = super().serialize()
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductCashDeposit":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive(input_dict["PAY_OR_REC"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        coupon = float(input_dict["COUPON"])
        accrual_basis = AccrualBasis.new(input_dict["ACCRUAL_BASIS"])
        pay_date_or_offset = TermOrDate(input_dict["PAYMENT_DATE_OR_OFFSET"])
        business_day_convention = BusinessDayConvention.new(input_dict["PAY_BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["PAY_HOLIDAY_CONVENTION"])
        return ProductCashDeposit(
            effective_date,
            term_or_termination_date,
            pay_or_rec,
            currency,
            notional,
            coupon,
            accrual_basis, 
            pay_date_or_offset,
            business_day_convention,
            holiday_convention)

class ProductFRAOrFixing(ProductIBORIndexCashflow):

    _version = 1
    _product_type = "PRODUCT_FRA_OR_FIXING"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec: PayOrReceive,
        currency : Currency,
        notional : float,
        coupon : float,
        index : IBORIndex,
        pay_date_or_offset : Optional[TermOrDate]=TermOrDate("0D"),
        fra_discounting_style : Optional[str]="ISDA"
    ) -> None:

        assert fra_discounting_style.upper() in ["ISDA", "AFMA"]
        super().__init__(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=pay_or_rec,
            ibor_index=index,
            spread=0.,
            currency=currency,
            notional=notional,
            pay_date_or_payment_offset=pay_date_or_offset,
            payment_business_day_convention=index.payment_business_day_conv,
            payment_holiday_convention=index.payment_holiday_conv)
        
        self.coupon_ = coupon
        self.pay_or_rec_ = pay_or_rec
        self.fra_discounting_style_ = fra_discounting_style
        
    @property
    def coupon(self) -> float:
        return self.coupon_

    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_
    
    @property
    def fra_discounting_style(self) -> str:
        return self.fra_discounting_style_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = super().serialize()
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["COUPON"] = self.coupon
        content["PAY_OR_REC"] = self.pay_or_rec.to_string().upper()
        content["FRA_DISCOUNTING_STYLE"] = self.fra_discounting_style
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductFRAOrFixing":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        coupon = float(input_dict["COUPON"])
        ibor_index = IndexRegistry().get(input_dict["IBOR_INDEX"])
        pay_date_or_offset = TermOrDate(input_dict["PAYMENT_DATE_OR_OFFSET"])
        fra_discounting_style = input_dict["FRA_DISCOUNTING_STYLE"]
        return cls(
            effective_date,
            term_or_termination_date,
            pay_or_rec,
            currency,
            notional,
            coupon,
            ibor_index,
            pay_date_or_offset,
            fra_discounting_style)

class ProductOvernightIndexFuture(ProductOvernightIndexCompositeCashflow):

    _version = 1
    _product_type = "PRODUCT_OVERNIGHT_INDEX_FUTURE"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        long_or_short: LongOrShort,
        amount: float,
        on_composite_index: OvernightCompositeIndex,        
        strike : Optional[float]=0.,
        pay_date_or_offset : Optional[TermOrDate]=TermOrDate("0D"),
        payment_business_day_conv: Optional[int] = ql.Unadjusted,
        payment_holiday_conv: Optional[ql.Calendar] = ql.NullCalendar(),
        contractual_notional: Optional[float] = 1000000.0,
        basis_point: Optional[float] = 25,
        look_back_window : Optional[Period] = Period(ql.NoFrequency),
        rates_cutoff : Optional[Period] = Period(ql.NoFrequency)
    ) -> None:

        assert amount >= 0 
        self.amount_ = amount # number of contracts
        self.sign_ = 1.0 if long_or_short == LongOrShort.LONG else -1.0
        self.contractual_notional_ = contractual_notional # notional per contract
        self.basis_point_ = basis_point # represents scaled accrued
        notional = self.sign_ * self.amount_ * self.contractual_notional_ * (self.basis_point_ / 1e4)
        self.strike_ = strike # strike / 100. 
        
        super().__init__(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=PayOrReceive.RECEIVE,
            on_composite_index=on_composite_index,
            spread=0.,
            currency=on_composite_index.index.currency,
            notional=notional,
            accrual_basis=on_composite_index.index.accrual_basis,
            pay_date_or_payment_offset=pay_date_or_offset,
            payment_business_day_convention=payment_business_day_conv,
            payment_holiday_convention=payment_holiday_conv,
            look_back_window=look_back_window,
            rate_cutoff=rates_cutoff)

    @property
    def amount(self) -> float:
        return self.amount_
    
    @property
    def basis_point(self) -> float:
        return self.basis_point_

    @property
    def contractual_notional(self) -> float:
        return self.contractual_notional_
    
    @property
    def sign(self) -> float:
        return self.sign_

    @property
    def strike(self) -> float:
        return self.strike_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = super().serialize()
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["LONG_OR_SHORT"] = self.long_or_short.to_string()
        content["AMOUNT"] = self.amount
        content["STRIKE"] = self.strike
        content["CONTRACTUAL_NOTIONAL"] = self.contractual_notional
        content["BASIS_POINT"] = self.basis_point
        content["LOOK_BACK_WINDOW"] = Period.to_string(self.look_back_window)
        content["RATE_CUT_OFFSET"] = Period.to_string(self.rate_cutoff)
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductOvernightIndexFuture":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        long_or_short = LongOrShort(input_dict["LONG_OR_SHORT"])
        amount = float(input_dict["AMOUNT"])
        on_composite_index = IndexRegistry().get(input_dict["ON_COMPOSITE_INDEX"])
        strike = input_dict["STRIKE"]
        payoffset = TermOrDate(input_dict["PAYMENT_DATE_OR_OFFSET"])
        business_day_conv = BusinessDayConvention.new(input_dict["PAYMENT_BUSINESS_DAY_CONVENTION"])
        holiday_conv = HolidayConvention.new(input_dict["PAYMENT_HOLIDAY_CONVENTION"])
        contractual_notional = float(input_dict["CONTRACTUAL_NOTIONAL"])
        basis_point = float(input_dict["BASIS_POINT"])
        look_back_window = Period(input_dict["LOOK_BACK_WINDOW"])
        rate_cutoff = Period(input_dict["RATE_CUT_OFFSET"])
        return ProductOvernightIndexFuture(
            effective_date,
            term_or_termination_date,
            long_or_short,
            amount,
            on_composite_index,
            strike,
            payoffset,
            business_day_conv,
            holiday_conv,
            contractual_notional,
            basis_point,
            look_back_window,
            rate_cutoff)

class ProductOvernightIndexSwap(Product):

    _version = 1
    _product_type = "PRODUCT_OVERNIGHT_INDEX_SWAP"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        on_composite_index: OvernightCompositeIndex,
        fixed_rate: float,
        pay_or_rec: PayOrReceive,
        notional: float,
        accrual_period: Period,
        accrual_basis: ql.DayCounter,
        business_day_convention : int,
        holiday_convention : ql.Calendar,
        schedule_generation_rule : Optional[int]=ql.DateGeneration.Backward,
        floating_leg_accrual_period: Optional[Period] = None,
        payment_off_set: Optional[Period]=Period(ql.NoFrequency),
        pay_business_day_convention: Optional[int] = ql.Unadjusted,
        pay_holiday_convention: Optional[ql.Calendar] = ql.NullCalendar(),
        look_back_window : Optional[Period]=Period(ql.NoFrequency),
        rate_cutoff: Optional[Period] = Period(ql.NoFrequency),
        first_regular_date : Optional[Date]=Date(),
        next_to_last_date : Optional[Date]=Date()
    ) -> None:

        super().__init__()
        self.pay_or_rec_ = pay_or_rec
        self.long_or_short_ = LongOrShort.SHORT if notional < 0 else LongOrShort.LONG
        self.notional_ = notional
        self.currency_ = on_composite_index.index.currency

        ### fixed leg
        self.fixed_leg_ = ProductInterestRateStream(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=self.pay_or_rec_,
            fixed_rate_or_spread=fixed_rate,
            currency=on_composite_index.index.currency,
            notional=notional,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            accrual_basis=accrual_basis,
            accrual_period=accrual_period,
            calculation_period=None,
            pay_in_advance=False,
            payment_date_or_offset=TermOrDate(payment_off_set),
            payment_business_day_convention=pay_business_day_convention,
            payment_holiday_convention=pay_holiday_convention,
            schedule_generation_rule=schedule_generation_rule,
            end_of_month=on_composite_index.index.end_of_month,
            first_regular_date=first_regular_date,
            next_to_last_date=next_to_last_date)
        
        ### floating leg
        self.floating_leg_accrual_period_ = floating_leg_accrual_period \
            if floating_leg_accrual_period else accrual_period
        self.floating_leg_ = ProductInterestRateStream(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=PayOrReceive.reverse(self.pay_or_rec_),
            fixed_rate_or_spread=0.,
            currency=on_composite_index.index.currency,
            notional=notional,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            index=on_composite_index,
            accrual_basis=accrual_basis,
            accrual_period=self.floating_leg_accrual_period_,
            payment_date_or_offset=TermOrDate(payment_off_set),
            payment_business_day_convention=pay_business_day_convention,
            payment_holiday_convention=pay_holiday_convention,
            look_back_window=look_back_window,
            rate_cutoff=rate_cutoff,
            schedule_generation_rule=schedule_generation_rule,
            end_of_month=on_composite_index.index.end_of_month,
            first_regular_date=first_regular_date,
            next_to_last_date=next_to_last_date)
        
        ### populate the basics
        self.first_date_ = min(self.fixed_leg.first_date, self.floating_leg.first_date)
        self.last_date_ = min(self.fixed_leg.last_date, self.floating_leg.last_date)
    
    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_
    
    @property
    def floating_leg_accrual_period(self) -> Period:
        return self.floating_leg_accrual_period_

    @property
    def floating_leg(self) -> ProductInterestRateStream:
        return self.floating_leg_

    @property
    def fixed_leg(self) -> ProductInterestRateStream:
        return self.fixed_leg_    

    def floating_leg_cash_flow(self, i: int) -> ProductOvernightIndexCompositeCashflow:
        assert 0 <= i < self.floating_leg_.num_cashflows()
        return self.floating_leg_.element(i)

    def fixed_leg_cash_flow(self, i: int) -> ProductFixedAccrued:
        assert 0 <= i < self.fixed_leg_.num_cashflows()
        return self.fixed_leg_.element(i)

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.floating_leg.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.floating_leg.term_or_termination_date)
        content["ON_INDEX"] = self.floating_leg.index.index_name()
        content["FIXED_RATE"] = self.fixed_leg.fixed_rate
        content["PAY_OR_REC"] = self.pay_or_rec.to_string().upper()
        content["NOTIONAL"] = self.notional
        content["ACCRUAL_PERIOD"] = Period.to_string(self.fixed_leg.accrual_period)
        content["ACCRUAL_BASIS"] = AccrualBasis.to_string(self.fixed_leg.accrual_basis)
        content["PAYMENT_OFFSET"] = Period.to_string(self.fixed_leg.payment_offset)
        content["BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.floating_leg.business_day_convention)
        content["HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.floating_leg.holiday_convention)
        content["SCHEDULE GENERATION RULE"] = self.fixed_leg.schedule_generation_rule
        content["FLOATING_LEG_ACCRUAL_PERIOD"] = Period.to_string(self.floating_leg.accrual_period)
        content["PAY_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.floating_leg.payment_business_day_convention)
        content["PAY_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.floating_leg.payment_holiday_convention)
        content["LOOK_BACK_WINDOW"] = Period.to_string(self.floating_leg.look_back_window)
        content["RATE_CUT_OFF"] = Period.to_string(self.floating_leg.rate_cutoff)
        content["FIRST_REGULAR_DATE"] = self.fixed_leg.first_regular_date.ISO()
        content["NEXT_TO_LAST_DATE"] = self.fixed_leg.next_to_last_date.ISO()
        return content
    
    @classmethod
    def deserialize(cls, input_dict) -> "ProductOvernightIndexSwap":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        on_composite_index = IndexRegistry().get(input_dict["ON_INDEX"])
        fixed_rate = float(input_dict["FIXED_RATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        notional = float(input_dict["NOTIONAL"])
        accrual_period = Period(input_dict["ACCRUAL_PERIOD"])
        accrual_basis = AccrualBasis.new(input_dict["ACCRUAL_BASIS"])
        business_day_convention = BusinessDayConvention.new(input_dict["BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["HOLIDAY_CONVENTION"])
        schedule_generation_rule = ql.DateGeneration.Backward \
            if int(input_dict["SCHEDULE GENERATION RULE"]) == 0 else ql.DateGeneration.Forward
        floating_leg_accrual_period = Period(input_dict["FLOATING_LEG_ACCRUAL_PERIOD"])
        pay_offset = Period(input_dict["PAYMENT_OFFSET"])
        pay_business_day_convention = BusinessDayConvention.new(input_dict["PAY_BUSINESS_DAY_CONVENTION"])
        pay_holiday_convention = HolidayConvention.new(input_dict["PAY_HOLIDAY_CONVENTION"])
        look_back_window = Period(input_dict["LOOK_BACK_WINDOW"])
        rate_cutoff = Period(input_dict["RATE_CUT_OFF"])
        first_regular_date = Date(input_dict["FIRST_REGULAR_DATE"])
        next_to_last_date = Date(input_dict["NEXT_TO_LAST_DATE"])
        return ProductOvernightIndexSwap(
            effective_date,
            term_or_termination_date,
            on_composite_index,
            fixed_rate,
            pay_or_rec,
            notional,
            accrual_period,
            accrual_basis,
            business_day_convention,
            holiday_convention,
            schedule_generation_rule,
            floating_leg_accrual_period,
            pay_offset,
            pay_business_day_convention,
            pay_holiday_convention,
            look_back_window,
            rate_cutoff,
            first_regular_date,
            next_to_last_date)

class ProductOvernightIndexBasisSwap(Product):

    _version = 1
    _product_type = "PRODUCT_OVERNIGHT_INDEX_BASIS_SWAP"

    # leg 1: Overnight Composite Index
    # leg 2: Ibor

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        on_composite_index : OvernightCompositeIndex,
        ibor_index : IBORIndex,
        spread: float, # over on composite index
        pay_or_rec_on_composite_index_leg : PayOrReceive,
        notional: float,
        accrual_period : Period,
        business_day_convention : int,
        holiday_convention : ql.Calendar,
        schedule_generation_rule : Optional[int]=ql.DateGeneration.Backward,
        on_accrual_basis : Optional[ql.DayCounter]=None,
        ibor_accrual_basis : Optional[ql.DayCounter]=None,
        payment_off_set: Optional[Period]=Period(ql.NoFrequency),
        pay_business_day_convention: Optional[int] = ql.Unadjusted,
        pay_holiday_convention: Optional[ql.Calendar] = ql.NullCalendar(),
        look_back_window : Optional[Period]=Period(ql.NoFrequency),
        rate_cutoff: Optional[Period] = Period(ql.NoFrequency),
        first_regular_date : Optional[Date]=Date(),
        next_to_last_date : Optional[Date]=Date()
    ) -> None:
        
        super().__init__()
        self.notional_ = notional
        self.long_or_short_ = LongOrShort.SHORT if self.notional_ < 0 else LongOrShort.LONG
        self.currency_ = on_composite_index.index.currency
        self.on_accrual_basis_ = on_accrual_basis
        self.ibor_accrual_basis_ = ibor_accrual_basis
        self.pay_or_rec_on_composite_index_leg_ = pay_or_rec_on_composite_index_leg
        ### on composite index leg
        self.on_composite_index_leg_ = ProductInterestRateStream(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=self.pay_or_rec_on_composite_index_leg_,
            fixed_rate_or_spread=spread,
            currency=on_composite_index.index.currency,
            notional=notional,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            index=on_composite_index,
            accrual_basis=self.on_accrual_basis_,
            accrual_period=accrual_period,
            payment_date_or_offset=TermOrDate(payment_off_set),
            payment_business_day_convention=pay_business_day_convention,
            payment_holiday_convention=pay_holiday_convention,
            look_back_window=look_back_window,
            rate_cutoff=rate_cutoff,
            schedule_generation_rule=schedule_generation_rule,
            end_of_month=on_composite_index.index.end_of_month,
            first_regular_date=first_regular_date,
            next_to_last_date=next_to_last_date)
        ### ibor leg
        self.ibor_index_leg_ = ProductInterestRateStream(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=PayOrReceive.reverse(self.pay_or_rec_on_composite_index_leg_),
            fixed_rate_or_spread=0.,
            currency=ibor_index.currency,
            notional=notional,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            index=ibor_index,
            leverage=1.,
            accrual_basis=self.ibor_accrual_basis_,
            accrual_period=accrual_period,
            pay_in_advance=False,
            payment_date_or_offset=TermOrDate(payment_off_set),
            payment_business_day_convention=pay_business_day_convention,
            payment_holiday_convention=pay_holiday_convention,
            schedule_generation_rule=schedule_generation_rule,
            end_of_month=on_composite_index.index.end_of_month)
        
        ### populate the basics
        self.first_date_ = min(self.on_composite_index_leg.first_date, self.ibor_index_leg.first_date)
        self.last_date_ = min(self.on_composite_index_leg.last_date, self.ibor_index_leg.last_date) 
    
    @property
    def pay_or_rec_on_composite_index_leg(self) -> PayOrReceive:
        return self.pay_or_rec_on_composite_index_leg_

    @property
    def on_composite_index_leg(self) -> ProductInterestRateStream:
        return self.on_composite_index_leg_

    @property
    def ibor_index_leg(self) -> ProductInterestRateStream:
        return self.ibor_index_leg_    

    @property
    def on_accrual_basis(self) -> ql.DayCounter:
        return self.on_accrual_basis_
    
    @property
    def ibor_accrual_basis(self) -> ql.DayCounter:
        return self.ibor_accrual_basis_

    def on_composite_index_leg_cash_flow(self, i: int) -> ProductOvernightIndexCompositeCashflow:
        assert 0 <= i < self.on_composite_index_leg.num_cashflows()
        return self.on_composite_index_leg.element(i)

    def ibor_index_leg_cash_flow(self, i: int) -> ProductFixedAccrued:
        assert 0 <= i < self.ibor_index_leg.num_cashflows()
        return self.ibor_index_leg.element(i)

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.on_composite_index_leg.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.on_composite_index_leg.term_or_termination_date)
        content["ON_COMPOSITE_INDEX"] = self.on_composite_index_leg.index.index_name()
        content["IBOR_INDEX"] = self.ibor_index_leg.index.index_name()
        content["SPREAD_OVER_ON_COMPOSITE_INDEX"] = self.on_composite_index_leg.spread
        content["PAY_OR_REC_ON_COMPOSITE_INDEX"] = self.pay_or_rec_on_composite_index_leg.to_string().upper()
        content["NOTIONAL"] = self.notional
        content["ACCRUAL_PERIOD"] = Period.to_string(self.on_composite_index_leg.accrual_period)
        content["BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.on_composite_index_leg.business_day_convention)
        content["HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.on_composite_index_leg.holiday_convention)
        content["SCHEDULE GENERATION RULE"] = self.on_composite_index_leg.schedule_generation_rule
        content["ON_LEG_ACCRUAL_BASIS"] = AccrualBasis.to_string(self.on_accrual_basis)
        content["IBOR_LEG_ACCRUAL_BASIS"] = AccrualBasis.to_string(self.ibor_accrual_basis)
        content["PAYMENT_OFFSET"] = Period.to_string(self.on_composite_index_leg.payment_offset)
        content["PAY_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.on_composite_index_leg.payment_business_day_convention)
        content["PAY_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.on_composite_index_leg.payment_holiday_convention)
        content["LOOK_BACK_WINDOW"] = Period.to_string(self.on_composite_index_leg.look_back_window)
        content["RATE_CUT_OFF"] = Period.to_string(self.on_composite_index_leg.rate_cutoff)
        content["FIRST_REGULAR_DATE"] = self.on_composite_index_leg.first_regular_date.ISO()
        content["NEXT_TO_LAST_DATE"] = self.on_composite_index_leg.next_to_last_date.ISO()
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductOvernightIndexBasisSwap":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        on_composite_index = IndexRegistry().get(input_dict["ON_COMPOSITE_INDEX"])
        ibor_index = IndexRegistry().get(input_dict["IBOR_INDEX"])
        spread = input_dict["SPREAD_OVER_ON_COMPOSITE_INDEX"]
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC_ON_COMPOSITE_INDEX"])
        notional = float(input_dict["NOTIONAL"])
        accrual_period = Period(input_dict["ACCRUAL_PERIOD"])
        business_day_convention = BusinessDayConvention.new(input_dict["BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["HOLIDAY_CONVENTION"])
        schedule_generation_rule = ql.DateGeneration.Backward \
            if int(input_dict["SCHEDULE GENERATION RULE"]) == 0 else ql.DateGeneration.Forward
        on_leg_accrual_basis = AccrualBasis.new(input_dict["ON_LEG_ACCRUAL_BASIS"])
        ibor_leg_accrual_basis = AccrualBasis.new(input_dict["IBOR_LEG_ACCRUAL_BASIS"])
        pay_offset = Period(input_dict["PAYMENT_OFFSET"])
        pay_business_day_convention = BusinessDayConvention.new(input_dict["PAY_BUSINESS_DAY_CONVENTION"])
        pay_holiday_convention = HolidayConvention.new(input_dict["PAY_HOLIDAY_CONVENTION"])
        look_back_window = Period(input_dict["LOOK_BACK_WINDOW"])
        rate_cutoff = Period(input_dict["RATE_CUT_OFF"])
        first_regular_date = Date(input_dict["FIRST_REGULAR_DATE"])
        next_to_last_date = Date(input_dict["NEXT_TO_LAST_DATE"])
        return ProductOvernightIndexBasisSwap(
            effective_date,
            term_or_termination_date,
            on_composite_index,
            ibor_index,
            spread,
            pay_or_rec,
            notional,
            accrual_period,
            business_day_convention,
            holiday_convention,
            schedule_generation_rule,
            on_leg_accrual_basis,
            ibor_leg_accrual_basis,
            pay_offset,
            pay_business_day_convention,
            pay_holiday_convention,
            look_back_window,
            rate_cutoff,
            first_regular_date,
            next_to_last_date)

class ProductOISBasisSwap(Product):

    _version = 1
    _product_type = "PRODUCT_OIS_BASIS_SWAP"

    # leg 1: Overnight Composite Index
    # leg 2: Overnight Composite Index

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        basis_on_composite_index : OvernightCompositeIndex,
        reference_on_composite_index : OvernightCompositeIndex,
        spread: float, # over basis leg
        pay_or_rec : PayOrReceive, # basis leg
        notional: float,
        accrual_period : Period,
        business_day_convention : int,
        holiday_convention : ql.Calendar,
        schedule_generation_rule : Optional[int]=ql.DateGeneration.Backward,
        basis_on_accrual_basis : Optional[ql.DayCounter]=None,
        reference_on_accrual_basis : Optional[ql.DayCounter]=None,
        payment_off_set: Optional[Period]=Period(ql.NoFrequency),
        pay_business_day_convention: Optional[int] = ql.Unadjusted,
        pay_holiday_convention: Optional[ql.Calendar] = ql.NullCalendar(),
        look_back_window : Optional[Period]=Period(ql.NoFrequency),
        rate_cutoff: Optional[Period] = Period(ql.NoFrequency),
        first_regular_date : Optional[Date]=Date(),
        next_to_last_date : Optional[Date]=Date()
    ) -> None:
        
        super().__init__()
        self.basis_on_accrual_basis_ = basis_on_accrual_basis
        self.reference_on_accrual_basis_ = reference_on_accrual_basis
        self.pay_or_rec_ = pay_or_rec
        ### basis on composite index
        self.basis_leg_ = ProductInterestRateStream(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=self.pay_or_rec_,
            fixed_rate_or_spread=spread,
            currency=basis_on_composite_index.index.currency,
            notional=notional,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            index=basis_on_composite_index,
            accrual_basis=self.basis_on_accrual_basis_,
            accrual_period=accrual_period,
            payment_date_or_offset=TermOrDate(payment_off_set),
            payment_business_day_convention=pay_business_day_convention,
            payment_holiday_convention=pay_holiday_convention,
            look_back_window=look_back_window,
            rate_cutoff=rate_cutoff,
            schedule_generation_rule=schedule_generation_rule,
            end_of_month=basis_on_composite_index.index.end_of_month,
            first_regular_date=first_regular_date,
            next_to_last_date=next_to_last_date)
        ### ois leg base
        self.reference_leg_ = ProductInterestRateStream(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=PayOrReceive.reverse(self.pay_or_rec_),
            fixed_rate_or_spread=0.,
            currency=reference_on_composite_index.index.currency,
            notional=notional,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            index=reference_on_composite_index,
            accrual_basis=self.reference_on_accrual_basis_,
            accrual_period=accrual_period,
            payment_date_or_offset=TermOrDate(payment_off_set),
            payment_business_day_convention=pay_business_day_convention,
            payment_holiday_convention=pay_holiday_convention,
            look_back_window=look_back_window,
            rate_cutoff=rate_cutoff,
            schedule_generation_rule=schedule_generation_rule,
            end_of_month=reference_on_composite_index.index.end_of_month,
            first_regular_date=first_regular_date,
            next_to_last_date=next_to_last_date)
        
        ### populate the basics
        self.first_date_ = min(self.basis_leg.first_date, self.reference_leg.first_date)
        self.last_date_ = min(self.basis_leg.last_date, self.reference_leg.last_date)
        self.notional_ = notional
        self.currency_ = self.basis_leg_.currency
    
    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def basis_leg(self) -> ProductInterestRateStream:
        return self.basis_leg_

    @property
    def reference_leg(self) -> ProductInterestRateStream:
        return self.reference_leg_
    
    @property
    def basis_on_accrual_basis(self) -> ql.DayCounter:
        return self.basis_on_accrual_basis_

    @property
    def reference_on_accrual_basis(self) -> ql.DayCounter:
        return self.reference_on_accrual_basis_    

    def basis_leg_cash_flow(self, i: int) -> ProductOvernightIndexCompositeCashflow:
        assert 0 <= i < self.basis_leg.num_cashflows()
        return self.basis_leg.element(i)

    def reference_leg_cash_flow(self, i: int) -> ProductFixedAccrued:
        assert 0 <= i < self.reference_leg.num_cashflows()
        return self.reference_leg.element(i)

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.basis_leg.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.basis_leg.term_or_termination_date)
        content["BASIS_ON_COMPOSITE_INDEX"] = self.basis_leg.index.index_name()
        content["REFERENCE_ON_COMPOSITE_INDEX"] = self.reference_leg.index.index_name()
        content["SPREAD"] = self.basis_leg.spread
        content["PAY_OR_REC"] = self.basis_leg.pay_or_rec.to_string().upper()
        content["NOTIONAL"] = self.notional
        content["ACCRUAL_PERIOD"] = Period.to_string(self.basis_leg.accrual_period)
        content["BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.basis_leg.business_day_convention)
        content["HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.basis_leg.holiday_convention)
        content["SCHEDULE GENERATION RULE"] = self.basis_leg.schedule_generation_rule
        content["BASIS_LEG_ACCRUAL_BASIS"] = AccrualBasis.to_string(self.basis_leg.accrual_basis)
        content["REFERENCE_LEG_ACCRUAL_BASIS"] = AccrualBasis.to_string(self.reference_leg.accrual_basis)
        content["PAYMENT_OFFSET"] = Period.to_string(self.basis_leg.payment_offset)
        content["PAY_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.basis_leg.payment_business_day_convention)
        content["PAY_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.basis_leg.payment_holiday_convention)
        content["LOOK_BACK_WINDOW"] = Period.to_string(self.basis_leg.look_back_window)
        content["RATE_CUT_OFF"] = Period.to_string(self.basis_leg.rate_cutoff)
        content["FIRST_REGULAR_DATE"] = self.basis_leg.first_regular_date.ISO()
        content["NEXT_TO_LAST_DATE"] = self.basis_leg.next_to_last_date.ISO()
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductOISBasisSwap":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        basis_on_composite_index = IndexRegistry().get(input_dict["BASIS_ON_COMPOSITE_INDEX"])
        reference_on_composite_index = IndexRegistry().get(input_dict["REFERENCE_ON_COMPOSITE_INDEX"])
        spread = float(input_dict["SPREAD"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        notional = float(input_dict["NOTIONAL"])
        accrual_period = Period(input_dict["ACCRUAL_PERIOD"])
        business_day_convention = BusinessDayConvention.new(input_dict["BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["HOLIDAY_CONVENTION"])
        schedule_generation_rule = ql.DateGeneration.Backward \
            if int(input_dict["SCHEDULE GENERATION RULE"]) == 0 else ql.DateGeneration.Forward
        basis_on_leg_accrual_basis = AccrualBasis.new(input_dict["BASIS_LEG_ACCRUAL_BASIS"])
        reference_on_leg_accrual_basis = AccrualBasis.new(input_dict["REFERENCE_LEG_ACCRUAL_BASIS"])
        pay_offset = Period(input_dict["PAYMENT_OFFSET"])
        pay_business_day_convention = BusinessDayConvention.new(input_dict["PAY_BUSINESS_DAY_CONVENTION"])
        pay_holiday_convention = HolidayConvention.new(input_dict["PAY_HOLIDAY_CONVENTION"])
        look_back_window = Period(input_dict["LOOK_BACK_WINDOW"])
        rate_cutoff = Period(input_dict["RATE_CUT_OFF"])
        first_regular_date = Date(input_dict["FIRST_REGULAR_DATE"])
        next_to_last_date = Date(input_dict["NEXT_TO_LAST_DATE"])
        return ProductOISBasisSwap(
            effective_date,
            term_or_termination_date,
            basis_on_composite_index,
            reference_on_composite_index,
            spread,
            pay_or_rec,
            notional,
            accrual_period,
            business_day_convention,
            holiday_convention,
            schedule_generation_rule,
            basis_on_leg_accrual_basis,
            reference_on_leg_accrual_basis,
            pay_offset,
            pay_business_day_convention,
            pay_holiday_convention,
            look_back_window,
            rate_cutoff,
            first_regular_date,
            next_to_last_date)

class ProductOvernightIndexCurrencyBasisSwapNonMTM(Product):

    _version = 1
    _product_type = "PRODUCT_XCCY_BASIS_SWAP_NON_MTM"

    # from convention — basis leg = B, reference leg = R

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        basis_leg_index: OvernightCompositeIndex,
        reference_leg_index: OvernightCompositeIndex,
        pay_or_rec: PayOrReceive, # basis leg
        basis_leg_notional: float,
        fx_index : FXIndex, # X^{r/b}(0): reference per 1 basis (e.g. USD per EUR)
        accrual_period : Period, # basis leg
        accrual_basis : Optional[ql.DayCounter]=None,
        spread: Optional[float]=0.0, # basis leg
        schedule_generation_rule : Optional[int]=ql.DateGeneration.Backward,
        business_day_convention : Optional[int]=ql.Unadjusted,
        holiday_convention : Optional[ql.Calendar]=ql.NullCalendar(),
        payment_offset: Optional[Period]=Period(ql.NoFrequency),
        payment_business_day_convention: Optional[int]=ql.Unadjusted,
        payment_holiday_convention: Optional[ql.Calendar]=ql.NullCalendar(),
        exchange_notional_at_start: Optional[bool]=True,
        exchange_notional_at_end: Optional[bool]=True,
        look_back_window : Optional[Period]=Period(ql.NoFrequency),
        rate_cutoff: Optional[Period] = Period(ql.NoFrequency),
        first_regular_date : Optional[Date]=Date(),
        next_to_last_date : Optional[Date]=Date(),
        end_of_month : Optional[bool]=None,
        # fine tuning
        reference_leg_accrual_period: Optional[ql.DayCounter]=None,
        reference_leg_accrual_basis : Optional[ql.DayCounter]=None,
        reference_leg_payment_offset: Optional[Period]=None,
        reference_leg_payment_business_day_convention: Optional[int]=None,
        reference_leg_payment_holidays: Optional[ql.Calendar]=None
    ) -> None:

        super().__init__()
        self.fx_index_ = fx_index
        self.basis_currency_ = self.currency_ = fx_index.quoted_ccy
        self.reference_currency_ = fx_index.base_ccy
        self.notional_ = self.basis_leg_notional_ = basis_leg_notional
        self.long_or_short_ = LongOrShort.LONG if self.notional_ >= 0 else LongOrShort.SHORT
        self.pay_or_rec_ = pay_or_rec
        self.exchange_notional_at_start_ = exchange_notional_at_start
        self.exchange_notional_at_end_ = exchange_notional_at_end
        self.accrual_period_ = accrual_period
        self.accrual_basis_ = accrual_basis
        self.end_of_month_ = end_of_month
        self.reference_leg_accrual_period_ = reference_leg_accrual_period
        self.reference_leg_accrual_basis_ = reference_leg_accrual_basis
        self.reference_leg_payment_offset_ = reference_leg_payment_offset
        self.reference_leg_payment_business_day_convention_ = reference_leg_payment_business_day_convention
        self.reference_leg_payment_holidays_ = reference_leg_payment_holidays

        ### basis on composite index
        self.basis_leg_ = ProductInterestRateStream(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=self.pay_or_rec_,
            fixed_rate_or_spread=spread,
            currency=self.basis_currency_,
            notional=basis_leg_notional,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            index=basis_leg_index,
            accrual_basis= self.accrual_basis_,
            accrual_period=self.accrual_period_,
            payment_date_or_offset=TermOrDate(payment_offset),
            payment_business_day_convention=payment_business_day_convention,
            payment_holiday_convention=payment_holiday_convention,
            look_back_window=look_back_window,
            rate_cutoff=rate_cutoff,
            schedule_generation_rule=schedule_generation_rule,
            end_of_month= end_of_month if end_of_month else basis_leg_index.index.end_of_month,
            first_regular_date=first_regular_date,
            next_to_last_date=next_to_last_date)
        ### reference on composite leg
        # notional needs to be rescaled
        # i.e., notional reference : N_r = N_b * X^{r/b}(0)
        self.reference_leg_ = ProductInterestRateStream(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec= PayOrReceive.reverse(self.pay_or_rec_),
            fixed_rate_or_spread=0.,
            currency=self.reference_currency_,
            notional=1.,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            index=reference_leg_index,
            accrual_basis= self.reference_leg_accrual_basis_ \
                if self.reference_leg_accrual_basis_ else self.accrual_basis_,
            accrual_period= self.reference_leg_accrual_period_ \
                if self.reference_leg_accrual_period_ else self.accrual_period_,
            payment_date_or_offset=TermOrDate(self.reference_leg_payment_offset_\
                if self.reference_leg_payment_offset_ else payment_offset),
            payment_business_day_convention=self.reference_leg_payment_business_day_convention_ \
                if self.reference_leg_payment_business_day_convention_ else payment_business_day_convention,
            payment_holiday_convention=self.reference_leg_payment_holidays_ \
                if self.reference_leg_payment_holidays_ else payment_holiday_convention,
            look_back_window=look_back_window,
            rate_cutoff=rate_cutoff,
            schedule_generation_rule=schedule_generation_rule,
            end_of_month= end_of_month if end_of_month else reference_leg_index.index.end_of_month,
            first_regular_date=first_regular_date,
            next_to_last_date=next_to_last_date)
        
        ### populate the basics
        self.first_date_ = min(self.basis_leg.first_date, self.reference_leg.first_date)
        self.last_date_ = min(self.basis_leg.last_date, self.reference_leg.last_date) 

    
    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def fx_index(self) -> FXIndex:
        return self.fx_index_

    @property
    def accrual_basis(self):
        return self.accrual_basis_
    
    @property
    def accrual_period(self):
        return self.accrual_period_

    @property
    def exchange_notional_at_start(self):
        return self.exchange_notional_at_start_
    
    @property
    def exchange_notional_at_end(self):
        return self.exchange_notional_at_end_

    @property
    def basis_leg(self) -> ProductInterestRateStream:
        return self.basis_leg_

    @property
    def reference_leg(self) -> ProductInterestRateStream:
        return self.reference_leg_
    
    @property
    def reference_leg_accrual_period(self) -> ql.DayCounter:
        return self.reference_leg_accrual_period_    

    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_

    @property
    def reference_leg_accrual_basis(self) -> ql.DayCounter:
        return self.reference_leg_accrual_basis_    

    def basis_leg_cash_flow(self, i: int) -> ProductOvernightIndexCompositeCashflow:
        assert 0 <= i < self.basis_leg.num_cashflows()
        return self.basis_leg.element(i)

    def reference_leg_cash_flow(self, i: int) -> ProductFixedAccrued:
        assert 0 <= i < self.reference_leg.num_cashflows()
        return self.reference_leg.element(i)

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.basis_leg.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.basis_leg.term_or_termination_date)
        content["BASIS_LEG_INDEX"] = self.basis_leg.index.index_name()
        content["REFERENCE_LEG_INDEX"] = self.reference_leg.index.index_name()
        content["PAY_OR_REC"] = self.basis_leg.pay_or_rec.to_string().upper()
        content["NOTIONAL"] = self.notional
        content["FX_INDEX"] = self.fx_index.index_name()
        content["ACCRUAL_PERIOD"] = Period.to_string(self.accrual_period)
        content["ACCRUAL_BASIS"] = AccrualBasis.to_string(self.accrual_basis)
        content["SPREAD"] = self.basis_leg.spread
        content["SCHEDULE GENERATION RULE"] = self.basis_leg.schedule_generation_rule
        content["BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.basis_leg.business_day_convention)
        content["HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.basis_leg.holiday_convention)
        content["PAYMENT_OFFSET"] = Period.to_string(self.basis_leg.payment_offset)
        content["PAY_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.basis_leg.payment_business_day_convention)
        content["PAY_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.basis_leg.payment_holiday_convention)
        content["EXCHANGE_AT_START"] = self.exchange_notional_at_start
        content["EXCHANGE_AT_END"] = self.exchange_notional_at_end    
        content["LOOK_BACK_WINDOW"] = Period.to_string(self.basis_leg.look_back_window)
        content["RATE_CUT_OFF"] = Period.to_string(self.basis_leg.rate_cutoff)
        content["FIRST_REGULAR_DATE"] = self.basis_leg.first_regular_date.ISO()
        content["NEXT_TO_LAST_DATE"] = self.basis_leg.next_to_last_date.ISO()
        content["END_OF_MONTH"] = self.end_of_month
        content["REFERENCE_LEG_ACCRUAL_PERIOD"] = Period.to_string(self.reference_leg.accrual_period)
        content["REFERENCE_LEG_ACCRUAL_BASIS"] = AccrualBasis.to_string(self.reference_leg.accrual_basis)
        content["REFERENCE_LEG_PAYMENT_OFFSET"] = Period.to_string(self.reference_leg.payment_offset)
        content["REFERENCE_LEG_PAY_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.reference_leg.payment_business_day_convention)
        content["REFERENCE_LEG_PAY_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.reference_leg.payment_holiday_convention)
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductOvernightIndexBasisSwap":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        basis_leg_index = IndexRegistry().get(input_dict["BASIS_LEG_INDEX"])
        reference_leg_index = IndexRegistry().get(input_dict["REFERENCE_LEG_INDEX"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        notional = float(input_dict["NOTIONAL"])
        fx_index = IndexRegistry().get(input_dict["FX_INDEX"])
        accrual_period = Period(input_dict["ACCRUAL_PERIOD"])
        accrual_basis = AccrualBasis.new(input_dict["ACCRUAL_BASIS"])
        spread = float(input_dict["SPREAD"])
        schedule_generation_rule = resolve_schedule_generation(input_dict["SCHEDULE GENERATION RULE"])
        business_day_convention = BusinessDayConvention.new(input_dict["BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["HOLIDAY_CONVENTION"])
        pay_offset = Period(input_dict["PAYMENT_OFFSET"])
        pay_business_day_convention = BusinessDayConvention.new(input_dict["PAY_BUSINESS_DAY_CONVENTION"])
        pay_holiday_convention = HolidayConvention.new(input_dict["PAY_HOLIDAY_CONVENTION"])
        exchange_at_start = bool(input_dict["EXCHANGE_AT_START"])
        exchange_at_end = bool(input_dict["EXCHANGE_AT_END"])
        look_back_window = Period(input_dict["LOOK_BACK_WINDOW"])
        rate_cutoff = Period(input_dict["RATE_CUT_OFF"])
        first_regular_date = Date(input_dict["FIRST_REGULAR_DATE"])
        next_to_last_date = Date(input_dict["NEXT_TO_LAST_DATE"])
        end_of_month = bool(input_dict["END_OF_MONTH"])
        #
        reference_leg_accrual_period = Period(input_dict["REFERENCE_LEG_ACCRUAL_PERIOD"])
        reference_leg_accrual_basis = AccrualBasis.new(input_dict["REFERENCE_LEG_ACCRUAL_BASIS"])
        reference_leg_pay_offset = Period(input_dict["REFERENCE_LEG_PAYMENT_OFFSET"])
        reference_leg_pay_business_day_convention = BusinessDayConvention.new(input_dict["REFERENCE_LEG_PAY_BUSINESS_DAY_CONVENTION"])
        reference_leg_pay_holiday_convention = HolidayConvention.new(input_dict["REFERENCE_LEG_PAY_HOLIDAY_CONVENTION"])
        
        return ProductOvernightIndexCurrencyBasisSwapNonMTM(
            effective_date,
            term_or_termination_date,
            basis_leg_index,
            reference_leg_index,
            pay_or_rec,
            notional,
            fx_index,
            accrual_period,
            accrual_basis,
            spread,
            schedule_generation_rule,
            business_day_convention,
            holiday_convention,
            pay_offset,
            pay_business_day_convention,
            pay_holiday_convention,
            exchange_at_start,
            exchange_at_end,
            look_back_window,
            rate_cutoff,
            first_regular_date,
            next_to_last_date,
            end_of_month,
            reference_leg_accrual_period,
            reference_leg_accrual_basis,
            reference_leg_pay_offset,
            reference_leg_pay_business_day_convention,
            reference_leg_pay_holiday_convention)

### ARITIFICIAL PRODUCT
    
class ProductGenericForward(Product):

    _version = 1
    _product_type = "PRODUCT_GENERIC_FORWARD"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec: PayOrReceive,
        currency : Currency,
        notional : float,
        coupon : float,
        index : Index,
        accrual_basis : Optional[ql.DayCounter]=AccrualBasis.new("ACTUAL/ACTUAL (ISDA)"),
        settlement_offset : Optional[Period]=ql.Period(ql.NoFrequency),
        business_day_convention : Optional[int]=ql.Unadjusted,
        holiday_convention : Optional[ql.Calendar]=ql.NullCalendar(),
        pay_date_or_offset : Optional[TermOrDate]=TermOrDate("0D"),
        payment_business_day_conv: Optional[int] = ql.Unadjusted,
        payment_holiday_conv: Optional[ql.Calendar] = ql.NullCalendar(),
        end_of_month : Optional[bool]=False,
        compounding_method : Optional[CompoundingMethod]=CompoundingMethod.CONTINUOUS
    ) -> None:

        super().__init__()
        self.compounding_method_ = compounding_method
        assert self.compounding_method_ in [CompoundingMethod.CONTINUOUS, CompoundingMethod.SIMPLE]
        self.effective_date_ = effective_date
        self.term_or_termination_date_ = term_or_termination_date
        self.pay_or_rec_ = pay_or_rec
        self.currency_ = currency
        self.notional_ = notional
        self.coupon_ = coupon
        self.index_ = index
        self.accrual_basis_ = accrual_basis
        self.settlement_offset_ = settlement_offset
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention
        self.pay_date_or_offset_ = pay_date_or_offset
        self.payment_business_day_convention_=payment_business_day_conv
        self.payment_holiday_convention_=payment_holiday_conv
        self.end_of_month_ = end_of_month

        # index type
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention

        # figure out termination date
        self.termination_date_: Date = None
        if self.term_or_termination_date_.is_term():
            self.termination_date_ = add_period(
                self.effective_date_,
                self.term_or_termination_date.get_term(),
                self.business_day_convention_,
                self.holiday_convention_,
                self.end_of_month_)
        else:
            self.termination_date_ = self.term_or_termination_date_.get_date()
        # figure payment date
        self.pay_date_ = None
        if self.pay_date_or_offset_.is_term():
            self.pay_date_ = add_period(
                self.termination_date_,
                self.pay_date_or_offset_.get_term(),
                self.payment_business_day_convention,
                self.payment_holiday_day_convention,
                self.end_of_month_)
        else:
            self.pay_date_ = self.pay_date_or_offset.get_date()

        # mandatory
        self.first_date_ = self.effective_date_
        self.last_date_ = self.pay_date_

    @property
    def effective_date(self) -> Date:
        return self.effective_date_
    
    @property
    def term_or_termination_date(self) -> TermOrDate:
        return self.term_or_termination_date_
    
    @property
    def termination_date(self) -> TermOrDate:
        return self.termination_date_
    
    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def coupon(self) -> float:
        return self.coupon_

    @property
    def index(self) -> Index:
        return self.index_
    
    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_
    
    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_

    @property
    def business_day_convention(self) -> int:
        return self.business_day_convention_
    
    @property
    def holiday_convention(self) -> int:
        return self.holiday_convention_

    @property
    def pay_date_or_offset(self) -> TermOrDate:
        return self.pay_date_or_offset_
    
    @property
    def pay_date(self) -> Date:
        return self.pay_date_
    
    @property
    def payment_business_day_convention(self) -> int:
        return self.payment_business_day_convention_
    
    @property
    def payment_holiday_day_convention(self) -> ql.Calendar:
        return self.payment_holiday_convention_
    
    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_

    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content ={}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.term_or_termination_date)
        content["PAY_OR_REC"] = self.pay_or_rec.to_string().upper()
        content["CURRENCY"] = self.currency.code()
        content["NOTIONAL"] = self.notional
        content["COUPON"] = self.coupon
        content["INDEX"] = self.index.index_name()
        content["ACCRUAL_BASIS"] = AccrualBasis.to_string(self.accrual_basis)
        content["SETTLEMENT_OFFSET"] = Period.to_string(self.settlement_offset)
        content["BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.business_day_convention)
        content["HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.holiday_convention)
        content["PAY_DATE_OR_OFFSET"] =  TermOrDate.to_string(self.pay_date_or_offset)
        content["PAY_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.payment_business_day_convention)
        content["PAY_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.payment_holiday_day_convention)
        content["END_OF_MONTH"] = self.end_of_month
        content["COMPOUNDING_METHOD"] = self.compounding_method.to_string()
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductGenericForward":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        coupon = float(input_dict["COUPON"])
        index = None
        if IndexRegistry().exists(input_dict["INDEX"]):
            index = IndexRegistry().get(input_dict["INDEX"])
        elif FundingIdentifierRegistry().exists(input_dict["INDEX"]):
            index = FundingIdentifierRegistry().get(input_dict["INDEX"])
        assert index
        accrual_basis = AccrualBasis.new(input_dict["ACCRUAL_BASIS"])
        settlement_offset = Period(input_dict["SETTLEMENT_OFFSET"])
        business_day_convention = BusinessDayConvention.new(input_dict["BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["HOLIDAY_CONVENTION"])
        pay_date_or_offset = TermOrDate(input_dict["PAY_DATE_OR_OFFSET"])
        pay_business_day_convention = BusinessDayConvention.new(input_dict["PAY_BUSINESS_DAY_CONVENTION"])
        pay_holiday_convention = HolidayConvention.new(input_dict["PAY_HOLIDAY_CONVENTION"])
        end_of_month = bool(input_dict["END_OF_MONTH"])
        compounding_method = CompoundingMethod.from_string(input_dict["COMPOUNDING_METHOD"])
        return ProductGenericForward(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=pay_or_rec,
            currency=currency,
            notional=notional,
            coupon=coupon,
            index=index,
            accrual_basis=accrual_basis,
            settlement_offset=settlement_offset,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            pay_date_or_offset=pay_date_or_offset,
            payment_business_day_conv=pay_business_day_convention,
            payment_holiday_conv=pay_holiday_convention,
            end_of_month=end_of_month,
            compounding_method=compounding_method)

class ProductGenericForwardSpread(Product):

    _version = 1
    _product_type = "PRODUCT_GENERIC_FORWARD_SPREAD"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec: PayOrReceive,
        currency : Currency,
        notional : float,
        spread : float,
        basis_index : Index,
        reference_index : Index,
        accrual_basis : Optional[ql.DayCounter]=AccrualBasis.new("ACTUAL/ACTUAL (ISDA)"),
        settlement_offset : Optional[Period]=ql.Period(ql.NoFrequency),
        business_day_convention : Optional[int]=ql.Unadjusted,
        holiday_convention : Optional[ql.Calendar]=ql.NullCalendar(),
        pay_date_or_offset : Optional[TermOrDate]=TermOrDate("0D"),
        payment_business_day_conv: Optional[int] = ql.Unadjusted,
        payment_holiday_conv: Optional[ql.Calendar] = ql.NullCalendar(),
        end_of_month : Optional[bool]=False,
        compounding_method : Optional[CompoundingMethod]=CompoundingMethod.CONTINUOUS,
        reference_leg_accrual_basis : Optional[ql.DayCounter]=None
    ) -> None:

        super().__init__()
        self.compounding_method_ = compounding_method
        assert self.compounding_method_ in [CompoundingMethod.CONTINUOUS, CompoundingMethod.SIMPLE]
        self.effective_date_ = effective_date
        self.term_or_termination_date_ = term_or_termination_date
        self.pay_or_rec_ = pay_or_rec
        self.currency_ = currency
        self.notional_ = notional
        self.spread_ = spread
        self.basis_index_ = basis_index
        self.reference_index_ = reference_index
        self.settlement_offset_ = settlement_offset
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention
        self.accrual_basis_ = accrual_basis
        self.pay_date_or_offset_ = pay_date_or_offset
        self.payment_business_day_convention_=payment_business_day_conv
        self.payment_holiday_convention_=payment_holiday_conv
        self.end_of_month_ = end_of_month
        self.reference_leg_accrual_basis_ = reference_leg_accrual_basis

        # index type
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention

        # figure out termination date
        self.termination_date_ = None
        if self.term_or_termination_date_.is_term():
            self.termination_date_ = add_period(
                self.effective_date_,
                self.term_or_termination_date.get_term(),
                self.business_day_convention_,
                self.holiday_convention_,
                self.end_of_month_)

        # figure payment date
        self.pay_date_ = None
        if self.pay_date_or_offset_.is_term():
            self.pay_date_ = add_period(
                self.termination_date_,
                self.pay_date_or_offset_.get_term(),
                self.payment_business_day_convention,
                self.payment_holiday_day_convention,
                self.end_of_month_)
        else:
            self.pay_date_ = self.pay_date_or_offset.get_date()

        # mandatory
        self.first_date_ = self.effective_date_
        self.last_date_ = self.pay_date_

    @property
    def effective_date(self) -> Date:
        return self.effective_date_
    
    @property
    def term_or_termination_date(self) -> TermOrDate:
        return self.term_or_termination_date_
    
    @property
    def termination_date(self) -> TermOrDate:
        return self.termination_date_
    
    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def spread(self) -> float:
        return self.spread_

    @property
    def basis_index(self) -> Index:
        return self.basis_index_
    
    @property
    def reference_index(self) -> Index:
        return self.reference_index_
    
    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_
    
    @property
    def settlement_offset(self) -> Period:
        return self.settlement_offset_
    
    @property
    def settlement_business_day_convention(self) -> int:
        return self.business_day_convention_

    @property
    def settlement_holiday_convention(self) -> ql.Calendar:
        return self.holiday_convention_

    @property
    def pay_date_or_offset(self) -> TermOrDate:
        return self.pay_date_or_offset_
    
    @property
    def pay_date(self) -> Date:
        return self.pay_date_
    
    @property
    def reference_leg_accrual_basis(self) -> ql.DayCounter:
        return self.reference_leg_accrual_basis_

    @property
    def payment_business_day_convention(self) -> int:
        return self.payment_business_day_convention_
    
    @property
    def payment_holiday_day_convention(self) -> ql.Calendar:
        return self.payment_holiday_convention_
    
    @property
    def end_of_month(self) -> bool:
        return self.end_of_month_

    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content ={}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.term_or_termination_date)
        content["PAY_OR_REC"] = self.pay_or_rec.to_string().upper()
        content["CURRENCY"] = self.currency.code()
        content["NOTIONAL"] = self.notional
        content["SPREAD"] = self.spread
        content["BASIS_INDEX"] = self.basis_index.index_name()
        content["REFERENCE_INDEX"] = self.reference_index.index_name()
        content["ACCRUAL_BASIS"] = AccrualBasis.to_string(self.accrual_basis)
        content["SETTLEMENT_OFFSET"] =  Period.to_string(self.settlement_offset_)
        content["SETTLEMENT_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.settlement_business_day_convention)
        content["SETTLEMENT_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.settlement_holiday_convention)
        content["PAY_DATE_OR_OFFSET"] =  TermOrDate.to_string(self.pay_date_or_offset)
        content["PAY_BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.payment_business_day_convention)
        content["PAY_HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.payment_holiday_day_convention)
        content["END_OF_MONTH"] = self.end_of_month
        content["COMPOUNDING_METHOD"] = self.compounding_method.to_string()
        content["REFERENCE_LEG_ACCRUAL_BASIS"] = AccrualBasis.to_string(self.reference_leg_accrual_basis)
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductGenericForwardSpread":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        spread = float(input_dict["SPREAD"])
        basis_index = reference_index = None
        if IndexRegistry().exists(input_dict["BASIS_INDEX"]):
            basis_index = IndexRegistry().get(input_dict["BASIS_INDEX"])
        elif FundingIdentifierRegistry().exists(input_dict["BASIS_INDEX"]):
            basis_index = FundingIdentifierRegistry().get(input_dict["BASIS_INDEX"])
        assert basis_index
        if IndexRegistry().exists(input_dict["REFERENCE_INDEX"]):
            reference_index = IndexRegistry().get(input_dict["REFERENCE_INDEX"])
        elif FundingIdentifierRegistry().exists(input_dict["REFERENCE_INDEX"]):
            reference_index = FundingIdentifierRegistry().get(input_dict["REFERENCE_INDEX"])
        assert reference_index
        accrual_basis = AccrualBasis.new(input_dict["ACCRUAL_BASIS"])
        settlement_offset = TermOrDate(input_dict["SETTLEMENT_OFFSET"])
        business_day_convention = BusinessDayConvention.new(input_dict["SETTLEMENT_BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["SETTLEMENT_HOLIDAY_CONVENTION"])
        pay_date_or_offset = TermOrDate(input_dict["PAY_DATE_OR_OFFSET"])
        pay_business_day_convention = BusinessDayConvention.new(input_dict["PAY_BUSINESS_DAY_CONVENTION"])
        pay_holiday_convention = HolidayConvention.new(input_dict["PAY_HOLIDAY_CONVENTION"])
        end_of_month = bool(input_dict["END_OF_MONTH"])
        compounding_method = CompoundingMethod.from_string(input_dict["COMPOUNDING_METHOD"])
        reference_leg_accrual_basis = AccrualBasis.new(input_dict["REFERENCE_LEG_ACCRUAL_BASIS"])
        return ProductGenericForwardSpread(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=pay_or_rec,
            currency=currency,
            notional=notional,
            spread=spread,
            basis_index=basis_index,
            reference_index=reference_index,
            accrual_basis=accrual_basis,
            settlement_offset=settlement_offset,
            business_day_convention=business_day_convention,
            holiday_convention=holiday_convention,
            pay_date_or_offset=pay_date_or_offset,
            payment_business_day_conv=pay_business_day_convention,
            payment_holiday_conv=pay_holiday_convention,
            end_of_month=end_of_month,
            compounding_method=compounding_method,
            reference_leg_accrual_basis=reference_leg_accrual_basis)

class ProductGenericSpread(Product):

    _version = 1
    _product_type = "PRODUCT_GENERIC_SPREAD"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec: PayOrReceive,
        currency : Currency,
        notional : float,
        spread : float,
        basis_data_convention : DataConvention,
        reference_data_convention : DataConvention) -> None:

        super().__init__()
        self.effective_date_ = effective_date
        self.term_or_termination_date_ = term_or_termination_date
        self.pay_or_rec_ = pay_or_rec
        self.currency_ = currency
        self.notional_ = notional
        self.spread_ = spread
        self.basis_data_convention_ = basis_data_convention
        self.reference_data_convention_ = reference_data_convention

        # data convention
        self.business_day_convention_ = ql.Preceding
        if hasattr(self.basis_data_convention_, "business_day_convention"):
            self.business_day_convention_ = self.basis_data_convention_.business_day_convention
        self.holiday_convention_ = ql.NullCalendar()
        if hasattr(self.basis_data_convention_, "holiday_convention"):
            self.holiday_convention_ = self.basis_data_convention_.holiday_convention

        # figure out termination date
        self.termination_date_ = None
        if self.term_or_termination_date_.is_term():
            self.termination_date_ : Date = add_period(
                self.effective_date_,
                self.term_or_termination_date_.get_term(),
                self.business_day_convention_,
                self.holiday_convention_)

        # mandatory
        self.first_date_ = self.effective_date_
        self.last_date_ = self.termination_date_

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
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def spread(self) -> float:
        return self.spread_

    @property
    def basis_data_convention(self) -> DataConvention:
        return self.basis_data_convention_
    
    @property
    def reference_data_convention(self) -> DataConvention:
        return self.reference_data_convention_
    
    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content ={}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.term_or_termination_date)
        content["PAY_OR_REC"] = self.pay_or_rec.to_string().upper()
        content["CURRENCY"] = self.currency.code()
        content["NOTIONAL"] = self.notional
        content["SPREAD"] = self.spread
        content["BASIS_DATA_CONVENTION"] = self.basis_data_convention.name
        content["REFERENCE_DATA_CONVENTION"] = self.reference_data_convention.name
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductGenericSpread":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        spread = float(input_dict["SPREAD"])
        basis_data_convention = reference_data_convention = None
        if DataConventionRegistry().exists(input_dict["BASIS_DATA_CONVENTION"]):
            basis_data_convention = DataConventionRegistry().get(input_dict["BASIS_DATA_CONVENTION"])
        if DataConventionRegistry().exists(input_dict["REFERENCE_DATA_CONVENTION"]):
            reference_data_convention = DataConventionRegistry().get(input_dict["REFERENCE_DATA_CONVENTION"])
        return ProductGenericSpread(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec=pay_or_rec,
            currency=currency,
            notional=notional,
            spread=spread,
            basis_data_convention=basis_data_convention,
            reference_data_convention=reference_data_convention)

class ProductIBORZeroSpread(Product):

    _version = 1
    _product_type = "PRODUCT_IBOR_ZERO_SPREAD"

    def __init__(
        self,
        termination_date : Date,
        pay_or_rec : PayOrReceive,
        currency : Currency,
        notional : float,
        spread : float,
        basis_index : Index, 
        reference_index : Index):

        super().__init__()
        self.termination_date_ = termination_date
        self.pay_or_rec_ = pay_or_rec
        self.currency_ = currency
        self.notional_ = notional
        self.spread_ = spread
        self.basis_index_ = basis_index
        self.reference_index_ = reference_index

        # mandatory
        self.last_date_ = self.termination_date_

    @property
    def termination_date(self) -> Date:
        return self.termination_date_
    
    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def spread(self) -> float:
        return self.spread_

    @property
    def basis_index(self) -> Index:
        return self.basis_index_
    
    @property
    def reference_index(self) -> Index:
        return self.reference_index_
    
    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content ={}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["TERMINATION_DATE"] = self.termination_date.ISO()
        content["PAY_OR_REC"] = self.pay_or_rec.to_string().upper()
        content["CURRENCY"] = self.currency.code()
        content["NOTIONAL"] = self.notional
        content["SPREAD"] = self.spread
        content["BASIS_INDEX"] = self.basis_index.index_name()
        content["REFERENCE_INDEX"] = self.reference_index.index_name()
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductIBORZeroSpread":
        termination_date = Date(input_dict["TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        spread = float(input_dict["SPREAD"])
        basis_index = reference_index = None
        if IndexRegistry().exists(input_dict["BASIS_INDEX"]):
            basis_index = IndexRegistry().get(input_dict["BASIS_INDEX"])
        elif FundingIdentifierRegistry().exists(input_dict["BASIS_INDEX"]):
            basis_index = FundingIdentifierRegistry().get(input_dict["BASIS_INDEX"])
        if IndexRegistry().exists(input_dict["REFERENCE_INDEX"]):
            reference_index = IndexRegistry().get(input_dict["REFERENCE_INDEX"])
        elif FundingIdentifierRegistry().exists(input_dict["REFERENCE_INDEX"]):
            reference_index = FundingIdentifierRegistry().get(input_dict["REFERENCE_INDEX"])

        return ProductIBORZeroSpread(
            termination_date=termination_date,
            pay_or_rec=pay_or_rec,
            currency=currency,
            notional=notional,
            spread=spread,
            basis_index=basis_index,
            reference_index=reference_index)

class ProductSwapSpreadBasisSwap(Product):

    _version = 1
    _product_type = "PRODUCT_SWAP_SPREAD_BASIS_SWAP"

    def __init__(
        self,
        effective_date: Date,
        term_or_termination_date: TermOrDate,
        pay_or_rec_basis_leg : PayOrReceive,
        currency : Currency,
        notional : float,
        spread : float,
        basis_swap_convention : DataConvention,
        reference_swap_convention : DataConvention,
        business_day_convention : Optional[BusinessDayConvention]=ql.Unadjusted,
        holiday_convention : Optional[HolidayConvention]=ql.NullCalendar()) -> None:

        super().__init__()
        self.effective_date_ = effective_date
        self.term_or_termination_date_ = term_or_termination_date
        self.pay_or_rec_ = pay_or_rec_basis_leg
        self.currency_ = currency
        self.notional_ = notional
        self.spread_ = spread
        self.basis_swap_conv_ = basis_swap_convention
        self.reference_swap_conv_ = reference_swap_convention
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention
        # mandatory
        self.first_date_ = self.effective_date_
        if term_or_termination_date.is_term():
            self.termination_date_ = add_period(
                effective_date,
                self.term_or_termination_date_.get_term(),
                business_day_convention,
                holiday_convention   
            )
        else:
            self.termination_date_ = self.term_or_termination_date_.get_date()
        self.last_date_ = self.termination_date_
    
    @property
    def effective_date(self) -> Date:
        return self.effective_date_

    @property
    def termination_date(self) -> Date:
        return self.termination_date_
    
    @property
    def term_or_termination_date(self) -> TermOrDate:
        return self.term_or_termination_date_

    @property
    def pay_or_rec(self) -> PayOrReceive:
        return self.pay_or_rec_

    @property
    def spread(self) -> float:
        return self.spread_

    @property
    def basis_swap_convention(self) -> DataConvention:
        return self.basis_swap_conv_
    
    @property
    def reference_swap_convention(self) -> DataConvention:
        return self.reference_swap_conv_
    
    @property
    def business_day_convention(self) -> int:
        return self.business_day_convention_
    
    @property
    def holiday_convention(self) -> ql.Calendar:
        return self.holiday_convention_
    
    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

    def serialize(self) -> dict:
        content ={}
        content["VERSION"] = self._version
        content["TYPE"] = self._product_type
        content["EFFECTIVE_DATE"] = self.effective_date.ISO()
        content["TERM_OR_TERMINATION_DATE"] = TermOrDate.to_string(self.term_or_termination_date)
        content["PAY_OR_REC"] = self.pay_or_rec.to_string().upper()
        content["CURRENCY"] = self.currency.code()
        content["NOTIONAL"] = self.notional
        content["SPREAD"] = self.spread
        content["BASIS_SWAP_CONVENTION"] = self.basis_swap_convention.name
        content["REFERENCE_SWAP_CONVENTION"] = self.reference_swap_convention.name
        content["BUSINESS_DAY_CONVENTION"] = BusinessDayConvention.to_string(self.business_day_convention)
        content["HOLIDAY_CONVENTION"] = HolidayConvention.to_string(self.holiday_convention)
        return content

    @classmethod
    def deserialize(cls, input_dict) -> "ProductSwapSpreadBasisSwap":
        effective_date = Date(input_dict["EFFECTIVE_DATE"])
        term_or_termination_date = TermOrDate(input_dict["TERM_OR_TERMINATION_DATE"])
        pay_or_rec = PayOrReceive.from_string(input_dict["PAY_OR_REC"])
        currency = Currency(input_dict["CURRENCY"])
        notional = float(input_dict["NOTIONAL"])
        spread = float(input_dict["SPREAD"])
        basis_swap_conv = DataConventionRegistry().get(input_dict["BASIS_SWAP_CONVENTION"])
        reference_swap_conv = DataConventionRegistry().get(input_dict["REFERENCE_SWAP_CONVENTION"])
        business_day_conv = BusinessDayConvention.new(input_dict["BUSINESS_DAY_CONVENTION"])
        holiday_convention = HolidayConvention.new(input_dict["HOLIDAY_CONVENTION"])

        return ProductSwapSpreadBasisSwap(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            pay_or_rec_basis_leg=pay_or_rec,
            currency=currency,
            notional=notional,
            spread=spread,
            basis_swap_convention=basis_swap_conv,
            reference_swap_convention=reference_swap_conv,
            business_day_convention=business_day_conv,
            holiday_convention=holiday_convention)

### Registry
#
ProductBuilderRegistry().register(ProductBulletCashflow._product_type, ProductBulletCashflow)
ProductBuilderRegistry().register(f"{ProductBulletCashflow._product_type}_DES", ProductBulletCashflow.deserialize)
ProductBuilderRegistry().register(ProductFixedAccrued._product_type, ProductFixedAccrued)
ProductBuilderRegistry().register(f"{ProductFixedAccrued._product_type}_DES", ProductFixedAccrued.deserialize)
ProductBuilderRegistry().register(ProductOvernightIndexCompositeCashflow._product_type, ProductOvernightIndexCompositeCashflow)
ProductBuilderRegistry().register(f"{ProductOvernightIndexCompositeCashflow._product_type}_DES", ProductOvernightIndexCompositeCashflow.deserialize)
ProductBuilderRegistry().register(ProductIBORIndexCashflow._product_type, ProductIBORIndexCashflow)
ProductBuilderRegistry().register(f"{ProductIBORIndexCashflow._product_type}_DES", ProductIBORIndexCashflow.deserialize)
ProductBuilderRegistry().register(ProductIBORCompoundingCashflow._product_type, ProductIBORCompoundingCashflow)
ProductBuilderRegistry().register(f"{ProductIBORCompoundingCashflow._product_type}_DES", ProductIBORCompoundingCashflow.deserialize)
ProductBuilderRegistry().register(ProductInterestRateStream._product_type, ProductInterestRateStream)
ProductBuilderRegistry().register(f"{ProductInterestRateStream._product_type}_DES", ProductInterestRateStream.deserialize)
#
ProductBuilderRegistry().register(ProductCashDeposit._product_type, ProductCashDeposit)
ProductBuilderRegistry().register(f"{ProductCashDeposit._product_type}_DES", ProductCashDeposit.deserialize)
ProductBuilderRegistry().register(ProductFRAOrFixing._product_type, ProductFRAOrFixing)
ProductBuilderRegistry().register(f"{ProductFRAOrFixing._product_type}_DES", ProductFRAOrFixing.deserialize)
ProductBuilderRegistry().register(ProductOvernightIndexFuture._product_type, ProductOvernightIndexFuture)
ProductBuilderRegistry().register(f"{ProductOvernightIndexFuture._product_type}_DES", ProductOvernightIndexFuture.deserialize)
ProductBuilderRegistry().register(ProductOvernightIndexSwap._product_type, ProductOvernightIndexSwap)
ProductBuilderRegistry().register(f"{ProductOvernightIndexSwap._product_type}_DES", ProductOvernightIndexSwap.deserialize)
ProductBuilderRegistry().register(ProductOISBasisSwap._product_type, ProductOISBasisSwap)
ProductBuilderRegistry().register(f"{ProductOISBasisSwap._product_type}_DES", ProductOISBasisSwap.deserialize)
ProductBuilderRegistry().register(ProductOvernightIndexCurrencyBasisSwapNonMTM._product_type, ProductOvernightIndexCurrencyBasisSwapNonMTM)
ProductBuilderRegistry().register(f"{ProductOvernightIndexCurrencyBasisSwapNonMTM._product_type}_DES", ProductOvernightIndexCurrencyBasisSwapNonMTM.deserialize)
#
ProductBuilderRegistry().register(ProductGenericForward._product_type, ProductGenericForward)
ProductBuilderRegistry().register(f"{ProductGenericForward._product_type}_DES", ProductGenericForward.deserialize)
ProductBuilderRegistry().register(ProductGenericForwardSpread._product_type, ProductGenericForwardSpread)
ProductBuilderRegistry().register(f"{ProductGenericForwardSpread._product_type}_DES", ProductGenericForwardSpread.deserialize)
ProductBuilderRegistry().register(ProductGenericSpread._product_type, ProductGenericSpread)
ProductBuilderRegistry().register(f"{ProductGenericSpread._product_type}_DES", ProductGenericSpread.deserialize)
ProductBuilderRegistry().register(ProductIBORZeroSpread._product_type, ProductIBORZeroSpread)
ProductBuilderRegistry().register(f"{ProductIBORZeroSpread._product_type}_DES", ProductIBORZeroSpread.deserialize)
ProductBuilderRegistry().register(ProductSwapSpreadBasisSwap._product_type, ProductSwapSpreadBasisSwap)
ProductBuilderRegistry().register(f"{ProductSwapSpreadBasisSwap._product_type}_DES", ProductSwapSpreadBasisSwap.deserialize)



from operator import index
import pickle
from re import I
from typing import List, Optional
# in-house
from fixedincomelib.date import *
from fixedincomelib.market import *
from fixedincomelib.product import *


def qfDisplayProduct(product: Product):
    visitor = ProductDisplayVisitor()
    product.accept(visitor)
    return visitor.display()

def qfWriteProductToFile(product: Product, path: str):
    this_dict = product.serialize()
    with open(path, "wb") as handle:
        pickle.dump(this_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return "DONE"

def qfReadProductFromFile(path: str):
    with open(path, "rb") as handle:
        this_dict = pickle.load(handle)
        prod_type = this_dict["TYPE"]
        func = ProductBuilderRegistry().get(f"{prod_type}_DES")
        return func(this_dict)

def qfCreateProductFromDataConvention(
    value_date: str, data_convention: str, axis1: str, values: float, **kwargs
):
    conv_obj = DataConventionRegistry().get(data_convention)
    return ProductFactory.create_product_from_data_convention(
        Date(value_date), axis1, conv_obj, values, **kwargs
    )

### PORTFOLIO PRODUCT
def qfCreatePortfolio(products: List[Product], weights: Optional[List[float]] = None) -> ProductPortfolio:
    return ProductPortfolio(products, weights)

### ATOMIC PRODUCTS (NO NEED TO SUPPORT FACTORY CREATION)
def qfCreateProductBulletCashflow(
    termination_date: str,
    currency: str,
    notional: float,
    long_or_short: str,
    payment_date_or_offset: Optional[str]=None
):
    return ProductBulletCashflow(
        Date(termination_date),
        Currency(currency),
        notional,
        LongOrShort.from_string(long_or_short),
        TermOrDate(payment_date_or_offset) if payment_date_or_offset else TermOrDate("0D")
    )

def qfCreateProducFixedAccrued(
    effective_date: str,
    term_or_termination_date: str,
    pay_or_rec : str,
    currency: str,
    notional: float,
    coupon : float,
    accrual_basis: str,
    business_day_convention : Optional[str]=None,
    holiday_convention : Optional[str]=None,
    payment_date_or_offset : Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None
):

    return ProductFixedAccrued(
        Date(effective_date),
        TermOrDate(term_or_termination_date),
        PayOrReceive.from_string(pay_or_rec),
        Currency(currency),
        notional,
        coupon,
        AccrualBasis.new(accrual_basis),
        BusinessDayConvention.new(business_day_convention) \
            if business_day_convention else ql.Unadjusted,
        HolidayConvention.new(holiday_convention) \
            if holiday_convention else ql.NullCalendar(),
        TermOrDate(payment_date_or_offset) \
            if payment_date_or_offset else TermOrDate("0D"),
        BusinessDayConvention.new(pay_business_day_convention) \
            if pay_business_day_convention else ql.Unadjusted,
        HolidayConvention.new(pay_holiday_convention) \
            if pay_holiday_convention else ql.NullCalendar()
    )

def qfCreateProductOvernightCompositeIndexCashflow(
    effective_date: str,
    term_or_terminatino_date: str,
    pay_or_rec : str,
    on_composite_index: str,
    spread : float,
    currency : str,
    notional: float,
    accrual_basis : Optional[str]=None,
    payment_date_or_offset : Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None,
    look_back_window : Optional[str]="0D",
    rate_cutoff : Optional[str]="0D"
):
    on_comp_index = IndexRegistry().get(on_composite_index)
    assert on_composite_index

    return ProductOvernightIndexCompositeCashflow(
        Date(effective_date),
        TermOrDate(term_or_terminatino_date),
        PayOrReceive.from_string(pay_or_rec),
        on_comp_index,
        spread,
        Currency(currency),
        notional,
        AccrualBasis.new(accrual_basis) if accrual_basis else None,
        TermOrDate(payment_date_or_offset) \
            if payment_date_or_offset else TermOrDate("0D"),
        BusinessDayConvention.new(pay_business_day_convention) \
            if pay_business_day_convention else ql.Unadjusted,
        HolidayConvention.new(pay_holiday_convention) \
            if pay_holiday_convention else ql.NullCalendar(),
        Period(look_back_window),
        Period(rate_cutoff)
    )

def qfCreateProductIborIndexCashflow(
    effective_date: str,
    term_or_terminatino_date: str,
    pay_or_rec : str,
    ibor_index: str,
    spread : float,
    currency : str,
    notional: float,
    accrual_basis : Optional[str]=None,
    payment_date_or_offset : Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None,
    pay_in_advance : Optional[bool]=False
):
    ibor_index_ = IndexRegistry().get(ibor_index)
    assert ibor_index_

    return ProductIBORIndexCashflow(
        Date(effective_date),
        TermOrDate(term_or_terminatino_date),
        PayOrReceive.from_string(pay_or_rec),
        ibor_index_,
        spread,
        Currency(currency),
        notional,
        AccrualBasis.new(accrual_basis) if accrual_basis else ql.SimpleDayCounter(),
        TermOrDate(payment_date_or_offset) \
            if payment_date_or_offset else TermOrDate("0D"),
        BusinessDayConvention.new(pay_business_day_convention) \
            if pay_business_day_convention else ql.Unadjusted,
        HolidayConvention.new(pay_holiday_convention) \
            if pay_holiday_convention else ql.NullCalendar(),
        pay_in_advance
    )

def qfCreateProductIborCompoundingCashflow(
    effective_date: str,
    term_or_terminatino_date: str,
    pay_or_rec : str,
    ibor_index: str,
    spread : float,
    currency : str,
    notional: float,
    calculation_period : str,
    leverage : Optional[float]=1.,
    payment_date_or_offset : Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None,
    compoundg_method : Optional[str]="flat_compound"
):
    ibor_index_ = IndexRegistry().get(ibor_index)
    assert ibor_index_

    return ProductIBORCompoundingCashflow(
        Date(effective_date),
        TermOrDate(term_or_terminatino_date),
        PayOrReceive.from_string(pay_or_rec),
        ibor_index_,
        spread,
        Currency(currency),
        notional,
        Period(calculation_period),
        leverage,
        TermOrDate(payment_date_or_offset) \
            if payment_date_or_offset else TermOrDate("0D"),
        BusinessDayConvention.new(pay_business_day_convention) \
            if pay_business_day_convention else ql.Unadjusted,
        HolidayConvention.new(pay_holiday_convention) \
            if pay_holiday_convention else ql.NullCalendar(),
        CompoundingMethod.from_string(compoundg_method)
    )

def qfCreateProductInterestRateStream(
    effective_date: str,
    term_or_terminatino_date: str,
    pay_or_rec : str,
    fixed_rate_or_spread : float,
    currency : str,
    notional: float,
    business_day_convention : str,
    holiday_convention : str,
    index: Optional[str]=None,
    leverage : Optional[float]=1.,
    accrual_basis : Optional[str]=None,
    accrual_period : Optional[str]=None,
    calculation_period : Optional[str]=None,
    pay_in_advance : Optional[bool]=False,
    payment_date_or_offset : Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None,
    compoundg_method : Optional[str]="flat_compound",
    look_back_window : Optional[str]="0D",
    rate_cutoff : Optional[str]="0D",
    schedule_generation_rule : Optional[str]="BACKWARD",
    end_of_month : Optional[bool]=False,
    first_regular_date : Optional[str]="",
    next_to_last_date : Optional[str]=""
):
    index_ = None
    if index:
        index_ = IndexRegistry().get(index)
        assert index_

    return ProductInterestRateStream(
        Date(effective_date),
        TermOrDate(term_or_terminatino_date),
        PayOrReceive.from_string(pay_or_rec),
        fixed_rate_or_spread,
        Currency(currency),
        notional,
        BusinessDayConvention.new(business_day_convention) \
            if business_day_convention else ql.Unadjusted,
        HolidayConvention.new(holiday_convention) \
            if holiday_convention else ql.NullCalendar(),
        index_,
        leverage,
        AccrualBasis.new(accrual_basis) if accrual_basis else ql.SimpleDayCounter(),
        Period(accrual_period) if accrual_period else Period(ql.NoFrequency),
        Period(calculation_period) if calculation_period else Period(ql.NoFrequency),
        pay_in_advance,
        TermOrDate(payment_date_or_offset) \
            if payment_date_or_offset else TermOrDate("0D"),
        BusinessDayConvention.new(pay_business_day_convention) \
            if pay_business_day_convention else ql.Unadjusted,
        HolidayConvention.new(pay_holiday_convention) \
            if pay_holiday_convention else ql.NullCalendar(),
        CompoundingMethod.from_string(compoundg_method),
        Period(look_back_window),
        Period(rate_cutoff),
        resolve_schedule_generation(schedule_generation_rule),
        end_of_month,
        Date(first_regular_date),
        Date(next_to_last_date)
    )

### CALIBRATION INSTRUMENTS
def qfCreateProductCashDeposit(
    effective_date: str,
    term_or_termination_date: str,
    pay_or_rec : str,
    currency: str,
    notional: float,
    coupon : float,
    accrual_basis: str,
    payment_date_or_offset : Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None
):

    return ProductCashDeposit(
        Date(effective_date),
        TermOrDate(term_or_termination_date),
        PayOrReceive.from_string(pay_or_rec),
        Currency(currency),
        notional,
        coupon,
        AccrualBasis.new(accrual_basis),
        TermOrDate(payment_date_or_offset) \
            if payment_date_or_offset else TermOrDate("0D"),
        BusinessDayConvention.new(pay_business_day_convention) \
            if pay_business_day_convention else ql.Unadjusted,
        HolidayConvention.new(pay_holiday_convention) \
            if pay_holiday_convention else ql.NullCalendar())

def qfCreateProductFRA(
    effective_date: str,
    term_or_termination_date: str,
    pay_or_rec : str,
    currency: str,
    notional: float,
    coupon : float,
    ibor_index : str,
    payment_date_or_offset : Optional[str]=None,
    fra_discounting_style : Optional[str]="ISDA"
):
    # only support ISDA for now
    assert fra_discounting_style.upper() == "ISDA"
    
    ibor = IndexRegistry().get(ibor_index)
    assert ibor

    return ProductFRAOrFixing(
        Date(effective_date),
        TermOrDate(term_or_termination_date),
        PayOrReceive.from_string(pay_or_rec),
        Currency(currency),
        notional,
        coupon,
        ibor, 
        TermOrDate(payment_date_or_offset) \
            if payment_date_or_offset else TermOrDate("0D"),
        fra_discounting_style)

def qfCreateProductOvernightIndexFuture(
    effective_date: str,
    term_or_termination_date: str,
    long_or_short: str,
    amount: float,
    on_comp_index : str,
    strike : float,
    pay_date_or_offset: str,
    pay_business_day_convention: Optional[str] = "F",
    pay_holiday_convention: Optional[str] = "USGS",
    contractual_notional: Optional[float] = 1000000.0,
    basis_point: Optional[float] = 25.0,
    lookback_window: Optional[str] = "0D",
    rate_cut_off_days_offset: Optional[str] = "0D"
) -> ProductOvernightIndexFuture:

    on_composite_index = IndexRegistry().get(on_comp_index)
    assert on_composite_index
    
    return ProductOvernightIndexFuture(
        Date(effective_date),
        TermOrDate(term_or_termination_date),
        LongOrShort.from_string(long_or_short),
        amount, 
        on_composite_index,
        strike,
        TermOrDate(pay_date_or_offset),
        BusinessDayConvention.new(pay_business_day_convention),
        HolidayConvention.new(pay_holiday_convention),
        contractual_notional,
        basis_point,
        Period(lookback_window),
        Period(rate_cut_off_days_offset)
    )

def qfCreateProductOvernightIndexSwap(
    effective_date: str,
    term_or_termination_date: str,    
    on_composite_index: str,
    fixed_rate: float,
    pay_or_rec: str,
    notional: float,
    accrual_period: str,
    accrual_basis: str,
    business_day_convention : Optional[str],
    holiday_convention : Optional[str],
    schedule_generation_rule : Optional[str]="BACKWARD",
    floating_leg_accrual_period: Optional[str] = None,
    payment_off_set: Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None,
    look_back_window: Optional[str] = "0D",
    rate_cutoff: Optional[str] = "0D",
    first_regular_date : Optional[str]="",
    next_to_last_date : Optional[str]=""
):
    
    on_composite_index_ = IndexRegistry().get(on_composite_index)
    assert on_composite_index_

    return ProductOvernightIndexSwap(
        Date(effective_date),
        TermOrDate(term_or_termination_date),
        on_composite_index_,
        fixed_rate,
        PayOrReceive.from_string(pay_or_rec),
        notional,
        Period(accrual_period),
        AccrualBasis.new(accrual_basis),
        BusinessDayConvention.new(business_day_convention),
        HolidayConvention.new(holiday_convention),
        resolve_schedule_generation(schedule_generation_rule),
        Period(floating_leg_accrual_period) \
            if floating_leg_accrual_period else Period(accrual_period),
        Period(payment_off_set) \
            if payment_off_set else Period("0D"),
        BusinessDayConvention.new(pay_business_day_convention) \
            if pay_business_day_convention else ql.Unadjusted,
        HolidayConvention.new(pay_holiday_convention) \
            if pay_holiday_convention else ql.NullCalendar(),
        Period(look_back_window),
        Period(rate_cutoff),
        Date(first_regular_date),
        Date(next_to_last_date))

def qfCreateProductOvernightIndexBasisSwap(
    effective_date: str,
    term_or_termination_date: str,
    on_composite_index: str,
    ibor_index: str,
    spread : float,
    pay_or_rec_on_composite_index_leg: str,
    notional: float,
    accrual_period: str,
    business_day_convention : str,
    holiday_convention : str,
    schedule_generation_rule : Optional[str]="BACKWARD",
    on_accrual_basis: Optional[str] = None,
    ibor_accrual_basis: Optional[str] = None,
    payment_off_set: Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None,
    look_back_window: Optional[str] = "0D",
    rate_cutoff: Optional[str] = "0D",
    first_regular_date : Optional[str]="",
    next_to_last_date : Optional[str]=""
):

    on_composite_index_ : OvernightCompositeIndex = IndexRegistry().get(on_composite_index)
    assert on_composite_index_
    ibor_index_ : IBORIndex = IndexRegistry().get(ibor_index)
    assert ibor_index_

    return ProductOvernightIndexBasisSwap(
        effective_date=Date(effective_date),
        term_or_termination_date=TermOrDate(term_or_termination_date),
        on_composite_index=on_composite_index_,
        ibor_index=ibor_index_,
        spread=spread,
        pay_or_rec_on_composite_index_leg=PayOrReceive.from_string(pay_or_rec_on_composite_index_leg),
        notional=notional,
        accrual_period=Period(accrual_period),
        business_day_convention=BusinessDayConvention.new(business_day_convention),
        holiday_convention=HolidayConvention.new(holiday_convention),
        schedule_generation_rule=resolve_schedule_generation(schedule_generation_rule),
        on_accrual_basis=AccrualBasis.new(on_accrual_basis) \
            if on_accrual_basis else None,
        ibor_accrual_basis=AccrualBasis.new(ibor_accrual_basis) \
            if ibor_accrual_basis else None,
        payment_off_set=Period(payment_off_set) \
            if payment_off_set else Period("0D"),
        pay_business_day_convention=BusinessDayConvention.new(pay_business_day_convention) \
            if pay_business_day_convention else ql.Unadjusted,
        pay_holiday_convention=HolidayConvention.new(pay_holiday_convention) \
            if pay_holiday_convention else ql.NullCalendar(),
        look_back_window=Period(look_back_window),
        rate_cutoff=Period(rate_cutoff),
        first_regular_date=Date(first_regular_date),
        next_to_last_date=Date(next_to_last_date))

def qfCreateProductOISBasisSwap(
    effective_date: str,
    term_or_termination_date: str,
    basis_leg_on_composite_index: str,
    reference_leg_on_composite_index: str,
    spread : float,
    basis_leg_pay_or_rec: str,
    notional: float,
    accrual_period: str,
    business_day_convention : str,
    holiday_convention : str,
    schedule_generation_rule : Optional[str]="BACKWARD",
    basis_leg_accrual_basis: Optional[str] = None,
    reference_leg_accrual_basis: Optional[str] = None,
    payment_off_set: Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None,
    look_back_window: Optional[str] = "0D",
    rate_cutoff: Optional[str] = "0D",
    first_regular_date : Optional[str]="",
    next_to_last_date : Optional[str]=""
):

    basis_leg_index : OvernightCompositeIndex = IndexRegistry().get(basis_leg_on_composite_index)
    assert basis_leg_index
    reference_leg_index : OvernightCompositeIndex = IndexRegistry().get(reference_leg_on_composite_index)
    assert reference_leg_index

    return ProductOISBasisSwap(
        effective_date=Date(effective_date),
        term_or_termination_date=TermOrDate(term_or_termination_date),
        basis_on_composite_index=basis_leg_index,
        reference_on_composite_index=reference_leg_index,
        spread=spread,
        pay_or_rec=PayOrReceive.from_string(basis_leg_pay_or_rec),
        notional=notional,
        accrual_period=Period(accrual_period),
        business_day_convention=BusinessDayConvention.new(business_day_convention),
        holiday_convention=HolidayConvention.new(holiday_convention),
        schedule_generation_rule=resolve_schedule_generation(schedule_generation_rule),
        basis_on_accrual_basis=AccrualBasis.new(basis_leg_accrual_basis) \
            if basis_leg_accrual_basis else None,
        reference_on_accrual_basis=AccrualBasis.new(reference_leg_accrual_basis) \
            if reference_leg_accrual_basis else None,
        payment_off_set=Period(payment_off_set) \
            if payment_off_set else Period("0D"),
        pay_business_day_convention=BusinessDayConvention.new(pay_business_day_convention) \
            if pay_business_day_convention else ql.Unadjusted,
        pay_holiday_convention=HolidayConvention.new(pay_holiday_convention) \
            if pay_holiday_convention else ql.NullCalendar(),
        look_back_window=Period(look_back_window),
        rate_cutoff=Period(rate_cutoff),
        first_regular_date=Date(first_regular_date),
        next_to_last_date=Date(next_to_last_date))

def qfCreateProductOvernightIndexCurrencyBasisSwapNonMTM(
    effective_date: str,
    term_or_termination_date: str,
    basis_leg_on_composite_index: str,
    reference_leg_on_composite_index: str,
    pay_or_rec: str,
    basis_leg_notional: float,
    fx_index: str,
    accrual_period: str,
    accrual_basis: Optional[str]=None,
    spread: Optional[float]=0.0,
    schedule_generation_rule: Optional[str]="BACKWARD",
    business_day_convention: Optional[str]=None,
    holiday_convention: Optional[str]=None,
    payment_offset: Optional[str]=None,
    payment_business_day_convention: Optional[str]=None,
    payment_holiday_convention: Optional[str]=None,
    exchange_notional_at_start: Optional[bool]=True,
    exchange_notional_at_end: Optional[bool]=True,
    look_back_window: Optional[str]="0D",
    rate_cutoff: Optional[str]="0D",
    first_regular_date: Optional[str]="",
    next_to_last_date: Optional[str]="",
    end_of_month: Optional[bool]=None,
    reference_leg_accrual_period: Optional[str]=None,
    reference_leg_accrual_basis: Optional[str]=None,
    reference_leg_payment_offset: Optional[str]=None,
    reference_leg_payment_business_day_convention: Optional[str]=None,
    reference_leg_payment_holidays: Optional[str]=None
) :
    
    basis_leg_index : OvernightCompositeIndex = IndexRegistry().get(basis_leg_on_composite_index)
    assert basis_leg_index
    reference_leg_index : OvernightCompositeIndex = IndexRegistry().get(reference_leg_on_composite_index)
    assert reference_leg_index
    fx_index_ : FXIndex = IndexRegistry().get(fx_index)
    assert fx_index_

    return ProductOvernightIndexCurrencyBasisSwapNonMTM(
        effective_date=Date(effective_date),
        term_or_termination_date=TermOrDate(term_or_termination_date),
        basis_leg_index=basis_leg_index,
        reference_leg_index=reference_leg_index,
        pay_or_rec=PayOrReceive.from_string(pay_or_rec),
        basis_leg_notional=basis_leg_notional,
        fx_index=fx_index_,
        accrual_period=Period(accrual_period),
        accrual_basis=AccrualBasis.new(accrual_basis) if accrual_basis else None,
        spread=spread,
        schedule_generation_rule=resolve_schedule_generation(schedule_generation_rule),
        business_day_convention=BusinessDayConvention.new(business_day_convention) \
            if business_day_convention else ql.Unadjusted,
        holiday_convention=HolidayConvention.new(holiday_convention) \
            if holiday_convention else ql.NullCalendar(),
        payment_offset=Period(payment_offset) \
            if payment_offset else Period(ql.NoFrequency),
        payment_business_day_convention=BusinessDayConvention.new(payment_business_day_convention) \
            if payment_business_day_convention else ql.Unadjusted,
        payment_holiday_convention=HolidayConvention.new(payment_holiday_convention) \
            if payment_holiday_convention else ql.NullCalendar(),
        exchange_notional_at_start=exchange_notional_at_start,
        exchange_notional_at_end=exchange_notional_at_end,
        look_back_window=Period(look_back_window),
        rate_cutoff=Period(rate_cutoff),
        first_regular_date=Date(first_regular_date),
        next_to_last_date=Date(next_to_last_date),
        end_of_month=end_of_month,
        reference_leg_accrual_period=Period(reference_leg_accrual_period) \
            if reference_leg_accrual_period else None,
        reference_leg_accrual_basis=AccrualBasis.new(reference_leg_accrual_basis) \
            if reference_leg_accrual_basis else None,
        reference_leg_payment_offset=Period(reference_leg_payment_offset) \
            if reference_leg_payment_offset else None,
        reference_leg_payment_business_day_convention=BusinessDayConvention.new(reference_leg_payment_business_day_convention) \
            if reference_leg_payment_business_day_convention else None,
        reference_leg_payment_holidays=HolidayConvention.new(reference_leg_payment_holidays) \
            if reference_leg_payment_holidays else None
    )

def qfCreateProductGenericForward(
    effective_date: str,
    term_or_termination_date: str,
    pay_or_rec: str,
    currency: str,
    notional: float,
    index : str,
    coupon : float,
    accrual_basis: Optional[str]=None,
    settlement_offset: Optional[str]=None,
    business_day_convention: Optional[str]=None,
    holiday_convention: Optional[str]=None,
    payment_date_or_offset: Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None,
    end_of_month: Optional[bool]=False,
    compounding_method: Optional[str]=CompoundingMethod.CONTINUOUS
):
    
    index_ = cast_to_index(index)
    assert index_

    return ProductGenericForward(
        Date(effective_date),
        TermOrDate(term_or_termination_date),
        PayOrReceive.from_string(pay_or_rec),
        Currency(currency),
        notional,
        coupon,
        index_,
        AccrualBasis.new(accrual_basis) if accrual_basis else None,
        Period(settlement_offset) if settlement_offset else Period("0D"),
        BusinessDayConvention.new(business_day_convention) if business_day_convention else ql.Unadjusted,
        HolidayConvention.new(holiday_convention) if holiday_convention else ql.NullCalendar(),
        TermOrDate(payment_date_or_offset) if payment_date_or_offset else TermOrDate("0D"),
        BusinessDayConvention.new(pay_business_day_convention) if pay_business_day_convention else ql.Unadjusted,
        HolidayConvention.new(pay_holiday_convention) if pay_holiday_convention else ql.NullCalendar(),
        end_of_month,
        compounding_method)

def qfCreateProductGenericForwardSpread(
    effective_date: str,
    term_or_termination_date: str,
    pay_or_rec: str,
    currency: str,
    notional: float, 
    spread : float,
    basis_index : str,
    reference_index : str,
    accrual_basis: Optional[str]=None,
    settlement_offset: Optional[str]=None,
    business_day_convention: Optional[str]=None,
    holiday_convention: Optional[str]=None,
    payment_date_or_offset: Optional[str]=None,
    pay_business_day_convention: Optional[str]=None,
    pay_holiday_convention: Optional[str]=None,
    end_of_month: Optional[bool]=False,
    compounding_method: Optional[str]=CompoundingMethod.CONTINUOUS,
    reference_accrual_basis: Optional[str]=None
):
    basis_index_ = cast_to_index(basis_index)
    assert basis_index_
    reference_index_ = cast_to_index(reference_index)
    assert reference_index_

    return ProductGenericForwardSpread(
        Date(effective_date),
        TermOrDate(term_or_termination_date),
        PayOrReceive.from_string(pay_or_rec),
        Currency(currency),
        notional,
        spread,
        basis_index_,
        reference_index_,
        AccrualBasis.new(accrual_basis) if accrual_basis else None,
        Period(settlement_offset) if settlement_offset else Period("0D"),
        BusinessDayConvention.new(business_day_convention) if business_day_convention else ql.Unadjusted,
        HolidayConvention.new(holiday_convention) if holiday_convention else ql.NullCalendar(),
        TermOrDate(payment_date_or_offset) if payment_date_or_offset else TermOrDate("0D"),
        BusinessDayConvention.new(pay_business_day_convention) if pay_business_day_convention else ql.Unadjusted,
        HolidayConvention.new(pay_holiday_convention) if pay_holiday_convention else ql.NullCalendar(),
        end_of_month,
        compounding_method,
        AccrualBasis.new(reference_accrual_basis) if reference_accrual_basis else None)

def qfCreateProductIBORZeroSpread(
    termination_date : str,  
    pay_or_rec : str,
    currency : str,
    notional : float,
    spread : float,
    basis_index : str,
    reference_index : str
):
    
    basis_index_ = cast_to_index(basis_index)
    reference_index_ = cast_to_index(reference_index)

    return ProductIBORZeroSpread(
        Date(termination_date),
        PayOrReceive.from_string(pay_or_rec),
        Currency(currency),
        notional,
        spread,
        basis_index_,
        reference_index_)

def qfCreateProductGenericSpread(
    effective_date : str,
    term_or_termination_date : str,
    pay_or_rec : str,
    currency : str,
    notional : float,
    spread : float,
    basis_data_convention : str,
    reference_data_convention : str
):
    basis_data_conv_ = DataConventionRegistry().get(basis_data_convention)
    assert basis_data_conv_
    reference_data_conv_ = DataConventionRegistry().get(reference_data_convention)
    assert reference_data_conv_

    return ProductGenericSpread(
        Date(effective_date),
        TermOrDate(term_or_termination_date),
        PayOrReceive.from_string(pay_or_rec),
        Currency(currency),
        notional,
        spread,
        basis_data_conv_,
        reference_data_conv_)

def qfCreateProductSwapSpreadBasisSwap(
    effective_date : str,
    term_or_termination_date : str,
    pay_or_rec : str,
    currency : str,
    notional : float,
    spread : float,
    basis_swap_convention : str,
    reference_swap_convention : str,
    business_day_convention : Optional[str]=None,
    holiday_convention : Optional[str]=None
):
    basis_swap_conv_ = DataConventionRegistry().get(basis_swap_convention)
    assert basis_swap_conv_
    reference_swap_conv_ = DataConventionRegistry().get(reference_swap_convention)
    assert reference_swap_conv_

    return ProductSwapSpreadBasisSwap(
        Date(effective_date),
        TermOrDate(term_or_termination_date),
        PayOrReceive.from_string(pay_or_rec),
        Currency(currency),
        notional,
        spread,
        basis_swap_conv_,
        reference_swap_conv_,
        BusinessDayConvention.new(business_day_convention) \
            if business_day_convention else ql.Unadjusted,
        HolidayConvention.new(holiday_convention) \
        if holiday_convention else ql.NullCalendar())
























# ### THIS IS NOT ACTIVATED

# # def qfCreateBondSpecs(key: str, parameters: dict) -> BondSpecs:

# #     # check if exists
# #     # if not, register(), and get()

# #     # otherwise, get()
# #     if not BondSpecsRegistry().exists(key):
# #         BondSpecsRegistry().register(key, parameters)

# #     return BondSpecsRegistry().get(key)

# # def qfCreateProductBond(name: str, trade_date: str, buy_sell: str, trade: float) -> ProductBond:

# #     bond_specs = BondSpecsRegistry().get(name)
# #     return ProductBond(
# #         name=name,
# #         bond_specs=bond_specs,
# #         trade_date=Date(trade_date),
# #         buy_sell=buy_sell,
# #         traded_price=trade,
# #     )

# # def qfCreateProductFXForward(
# #     termination_date: str,
# #     fx_pair: str,
# #     pay_or_rec: str,
# #     settlement_ccy: str,
# #     foreign_notional: float,
# #     strike: float,
# #     business_day_convention: Optional[str] = "",
# #     holiday_convention: Optional[str] = "",
# #     pay_offset: Optional[str] = "0D",
# # ):

# #     business_day_convention_obj = BusinessDayConvention("F")
# #     if business_day_convention != "":
# #         business_day_convention_obj = BusinessDayConvention(business_day_convention)

# #     holiday_day_convention_obj = HolidayConvention("USGS")
# #     if holiday_convention != "":
# #         holiday_day_convention_obj = HolidayConvention(holiday_convention)

# #     return ProductFxForward(
# #         Date(termination_date),
# #         fx_pair,
# #         PayOrReceive(pay_or_rec),
# #         Currency(settlement_ccy),
# #         foreign_notional,
# #         strike,
# #         business_day_convention_obj,
# #         holiday_day_convention_obj,
# #         Period(pay_offset))


# # def qfCreateProductRFRCapletFloorlet(
# #     effective_date: str,
# #     expiry_offset: str,
# #     term_or_termination_date: str,
# #     payment_date: str,
# #     on_index: str,
# #     strike: float,
# #     cap_or_floor: str,
# #     notional: float,
# #     accrual_basis: str,
# #     long_or_short: Optional[str] = "LONG",
# # ):

# #     return ProductRFRCapletFloorlet(
# #         effective_date=Date(effective_date),
# #         expiry_offset=Period(expiry_offset),
# #         term_or_termination_date=TermOrDate(term_or_termination_date),
# #         payment_date=Date(payment_date),
# #         on_index=on_index,
# #         strike=strike,
# #         notional=notional,
# #         cap_or_floor=CapOrFloor.from_string(cap_or_floor),
# #         accrual_basis=AccrualBasis(accrual_basis),
# #         long_or_short=LongOrShort.from_string(long_or_short),
# #     )

# # def qfCreateProductRFRCapFloor(
# #     effective_date: str,
# #     term_or_termination_date: str,
# #     on_index: str,
# #     strike: float,
# #     cap_or_floor: str,
# #     notional: float,
# #     accrual_period: str,
# #     accrual_basis: str,
# #     payment_offset: str,
# #     payment_business_day_convention: Optional[str] = "F",
# #     payment_holiday_convention: Optional[str] = "USGS",
# #     long_or_short: Optional[str] = "LONG",
# #     business_day_convention: Optional[str] = "MF",
# #     holiday_convention: Optional[str] = "USGS",
# # ):

# #     return ProductRFRCapFloor(
# #         effective_date=Date(effective_date),
# #         term_or_termination_date=TermOrDate(term_or_termination_date),
# #         on_index=on_index,
# #         strike=strike,
# #         notional=notional,
# #         cap_or_floor=CapOrFloor.from_string(cap_or_floor),
# #         accrual_period=Period(accrual_period),
# #         accrual_basis=AccrualBasis(accrual_basis),
# #         payment_offset=Period(payment_offset),
# #         payment_business_day_convention=BusinessDayConvention(payment_business_day_convention),
# #         payment_holiday_convention=HolidayConvention(payment_holiday_convention),
# #         long_or_short=LongOrShort.from_string(long_or_short),
# #         business_day_convention=BusinessDayConvention(business_day_convention),
# #         holiday_convention=HolidayConvention(holiday_convention),
# #     )

# # def qfCreateProductRFRSwaption(
# #     expiry_date: str,
# #     effective_date: str,
# #     term_or_termination_date: str,
# #     payment_off_set: str,
# #     on_index: str,
# #     strike: float,
# #     pay_or_rec: str,
# #     notional: float,
# #     accrual_period: str,
# #     accrual_basis: str,
# #     floating_leg_accrual_period: Optional[str] = None,
# #     pay_business_day_convention: Optional[str] = "F",
# #     pay_holiday_convention: Optional[str] = "USGS",
# #     spread: Optional[float] = 0.0,
# #     compounding_method: Optional[str] = "COMPOUND",
# #     long_or_short: Optional[str] = "LONG",
# # ):
# #     return ProductRFRSwaption(
# #         expiry_date=Date(expiry_date),
# #         effective_date=Date(effective_date),
# #         term_or_termination_date=TermOrDate(term_or_termination_date),
# #         payment_offset=Period(payment_off_set),
# #         on_index=on_index,
# #         strike=strike,
# #         pay_or_rec=PayOrReceive.from_string(pay_or_rec),
# #         notional=notional,
# #         accrual_period=Period(accrual_period),
# #         accrual_basis=AccrualBasis(accrual_basis),
# #         floating_leg_accrual_period=(
# #             None
# #             if floating_leg_accrual_period is None
# #             else Period(floating_leg_accrual_period)
# #         ),
# #         pay_business_day_convention=BusinessDayConvention(pay_business_day_convention),
# #         pay_holiday_convention=HolidayConvention(pay_holiday_convention),
# #         spread=spread,
# #         compounding_method=CompoundingMethod.from_string(compounding_method),
# #         long_or_short=LongOrShort.from_string(long_or_short),
# #     )

# ### THIS IS NOT ACTIVATED
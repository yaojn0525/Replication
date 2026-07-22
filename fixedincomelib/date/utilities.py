from typing import Optional
import pandas as pd
import QuantLib as ql
# in-house
from fixedincomelib.date.basics import (Date, Period)


def add_period(
    start_date : Date,
    term : Period,
    business_day_convention : int,
    holiday_convention : ql.Calendar,
    end_of_month : Optional[bool]=False) -> Date:

    return Date(holiday_convention.advance(start_date, term, business_day_convention, end_of_month))

def subtract_period(
    start_date : Date,
    term : Period,
    business_day_convention : int,
    holiday_convention : ql.Calendar,
    end_of_month : Optional[bool]=False) -> Date:

    return add_period(
        start_date, Period.negate_period(term), business_day_convention, holiday_convention, end_of_month
    )

def move_to_business_day(
    input_date: Date,
    business_day_convention: int,
    holiday_convention: ql.Calendar) -> Date:

    return Date(holiday_convention.adjust(input_date, business_day_convention))

def accrued(
    start_date: Date,
    end_date: Date,
    accrual_basis: Optional[ql.DayCounter] = ql.ActualActual(ql.ActualActual.ISDA),
    business_day_convention: Optional[int] = ql.Preceding,
    holiday_convention: Optional[ql.Calendar] = ql.NullCalendar()) -> float:
    
    adjusted_end_dt = move_to_business_day(end_date, business_day_convention, holiday_convention)
    return accrual_basis.yearFraction(start_date, adjusted_end_dt)

def is_business_day(input_date: Date, holiday_convention: ql.Calendar) -> bool:
    return holiday_convention.isBusinessDay(input_date)

def is_holiday(input_date: Date, holiday_convention: ql.Calendar) -> bool:
    return holiday_convention.isHoliday(input_date)

def is_end_of_month(input_date: Date, holiday_convention: ql.Calendar) -> bool:
    return holiday_convention.isEndOfMonth(input_date)

def end_of_month(input_date: Date, holiday_convention: ql.Calendar) -> Date:
    return holiday_convention.endOfMonth(input_date)

def make_schedule(
    start_date: Date,
    end_date: Date,
    accrual_period: Period,
    holiday_convention: ql.Calendar,
    business_day_convention: int,
    accrual_basis: ql.DayCounter,
    rule: Optional[int] = ql.DateGeneration.Backward,
    end_of_month: Optional[bool] = False,
    fix_in_arrear: Optional[bool] = False,
    fixing_offset: Optional[Period] = Period(ql.NoFrequency),
    payment_offset: Optional[Period] = Period(ql.NoFrequency),
    payment_business_day_convention: Optional[int] = ql.Following,
    payment_holiday_convention: Optional[ql.Calendar] = ql.NullCalendar(),
    first_regular_date : Optional[Date]=Date(),
    next_to_last_date : Optional[Date]=Date()) -> pd.DataFrame:

    assert rule in [ql.DateGeneration.Forward, ql.DateGeneration.Backward]
    
    # set up start date and end date of each period
    this_schedule = ql.Schedule(
        start_date,
        end_date,
        accrual_period,
        holiday_convention,
        business_day_convention,
        business_day_convention,
        rule,
        end_of_month,
        first_regular_date,
        next_to_last_date)

    # add fixing date and payment date
    start_dates = this_schedule.dates()[:-1]
    end_dates = this_schedule.dates()[1:]
    fixing_dates, payment_dates, accs = [], [], []
    for s, e in zip(start_dates, end_dates):
        f = s
        if fixing_offset.is_valid():
            f = add_period(
                e if fix_in_arrear else s, 
                fixing_offset, 
                business_day_convention, 
                holiday_convention)
        fixing_dates.append(f)
        p = e
        if payment_offset.is_valid():
            p = add_period(
                e, 
                payment_offset, 
                payment_business_day_convention, 
                payment_holiday_convention)
        payment_dates.append(p)
        accs.append(accrued(s, e, accrual_basis, business_day_convention, holiday_convention))

    # set up container
    df = pd.DataFrame(columns=["StartDate", "EndDate", "FixingDate", "PaymentDate", "Accrued"])
    df["StartDate"] = start_dates
    df["EndDate"] = end_dates
    df["FixingDate"] = fixing_dates
    df["PaymentDate"] = payment_dates
    df["Accrued"] = accs

    return df

def frequency_from_period(p: Period) -> float:
    freq = p.frequency()
    return float(freq)

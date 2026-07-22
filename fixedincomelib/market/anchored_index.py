# in-house
from fixedincomelib.market.basics import *
from fixedincomelib.market.indices import *
from fixedincomelib.market.interfaces import *
from fixedincomelib.market.indices import *

from abc import ABC, abstractmethod
from typing import Optional, List
import QuantLib as ql

### anchored index -- IBOR index
class AnchoredIborIndex(AnchoredIndex):

    def __init__(
        self,
        start_date: Date,
        term_or_termination_date: Date | Period,
        ibor_index: ql.IborIndex,
        compounding_method: CompoundingMethod,
        rate_cutoff: Optional[Period] = Period("0D"),
        look_back_window: Optional[Period] = Period("0D"),
        business_day_convention: Optional[BusinessDayConvention] = BusinessDayConvention.new("NONE"),
        holiday_convention: Optional[HolidayConvention] = HolidayConvention.new("NONE"),
        accrual_basis: Optional[ql.DayCounter] = None,
    ):

        # default to the index's own native day count (e.g. ACT/360 for SOFR/LIBOR) rather than
        # a hardcoded convention -- callers that compute tau off the same index's accrual_basis
        # (e.g. product.accrued) must match what this class actually compounds/discounts with.
        super().__init__(
            start_date,
            term_or_termination_date,
            ibor_index,
            accrual_basis=accrual_basis if accrual_basis is not None else ibor_index.accrual_basis,
        )
        self.rate_cutoff_ = rate_cutoff
        self.look_back_window_ = look_back_window
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention
        self.compounding_method_ = compounding_method

    @property
    def rate_cutoff(self) -> Period:
        return self.rate_cutoff_

    @property
    def look_back_window(self) -> Period:
        return self.look_back_window_

    @property
    def business_day_convention(self) -> BusinessDayConvention:
        return self.business_day_convention_

    @property
    def holiday_convention(self) -> HolidayConvention:
        return self.holiday_convention_

    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_


### anchored index -- overnight index
class AnchoredOvernightIndex(AnchoredIndex):

    def __init__(
        self,
        start_date: Date,
        end_date: Date,  # only take in date
        overnight_index: OvernightIndex,
        compounding_method: CompoundingMethod,
        rate_cutoff: Optional[Period] = Period("0D"),
        look_back_window: Optional[Period] = Period("0D"),
        business_day_convention: Optional[BusinessDayConvention] = BusinessDayConvention.new("NONE"),
        holiday_convention: Optional[HolidayConvention] = HolidayConvention.new("NONE"),
        accrual_basis: Optional[ql.DayCounter] = None,
    ):

        # default to the index's own native day count (e.g. ACT/360 for SOFR) rather than a
        # hardcoded convention -- see AnchoredIborIndex for why this must match callers that
        # compute tau off the same index's accrual_basis.
        super().__init__(
            start_date,
            end_date,
            overnight_index,
            accrual_basis=accrual_basis if accrual_basis is not None else overnight_index.accrual_basis,
        )
        self.rate_cutoff_ = rate_cutoff
        self.look_back_window_ = look_back_window
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention
        self.compounding_method_ = compounding_method

    @property
    def rate_cutoff(self) -> Period:
        return self.rate_cutoff_

    @property
    def look_back_window(self) -> Period:
        return self.look_back_window_

    @property
    def business_day_convention(self) -> BusinessDayConvention:
        return self.business_day_convention_

    @property
    def holiday_convention(self) -> HolidayConvention:
        return self.holiday_convention_

    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_


### anchored index -- Compound index
class AnchoredCompoundIborIndex(AnchoredIndex):

    def __init__(
        self,
        start_date: Date,
        term_or_termination_date: Date | Period,
        ibor_index: IBORIndex,
        compounding_method: CompoundingMethod,
        rate_cutoff: Optional[Period] = Period("0D"),
        look_back_window: Optional[Period] = Period("0D"),
        business_day_convention: Optional[BusinessDayConvention] = BusinessDayConvention.new("NONE"),
        holiday_convention: Optional[HolidayConvention] = HolidayConvention.new("NONE"),
        accrual_basis: Optional[ql.DayCounter] = None,
    ):

        # default to the index's own native day count (e.g. ACT/360 for LIBOR) rather than a
        # hardcoded convention -- see AnchoredIborIndex for why this must match callers that
        # compute tau off the same index's accrual_basis.
        super().__init__(
            start_date,
            term_or_termination_date,
            ibor_index,
            accrual_basis=accrual_basis if accrual_basis is not None else ibor_index.accrual_basis,
        )

        # assert term_or_termination_date is the end of n full calculation period(term) (n>1)

        index_term = ibor_index.term  #  length of the calculation period

        # check if it's a valid end date
        end_date = (
            add_period(
                start_date, term_or_termination_date, business_day_convention, holiday_convention
            )
            if isinstance(term_or_termination_date, ql.Period)
            else term_or_termination_date
        )
        n, current_date = 0, start_date
        while current_date < end_date:
            current_date = add_period(
                current_date, index_term, business_day_convention, holiday_convention
            )
            n += 1
        assert current_date == end_date, (
            f"term_or_termination_date must be an integer number of full {index_term} "
            f"calculation periods from start_date, with no residual"
        )
        assert n > 1, (
            f"AnchoredCompoundIborIndex requires more than one full {index_term} calculation "
            f"period; use AnchoredIborIndex for a single-period accrual"
        )

        self.num_periods_ = n
        self.rate_cutoff_ = rate_cutoff
        self.look_back_window_ = look_back_window
        self.business_day_convention_ = business_day_convention
        self.holiday_convention_ = holiday_convention
        self.compounding_method_ = compounding_method

    @property
    def num_periods(self) -> int:
        return self.num_periods_

    @property
    def rate_cutoff(self) -> Period:
        return self.rate_cutoff_

    @property
    def look_back_window(self) -> Period:
        return self.look_back_window_

    @property
    def business_day_convention(self) -> BusinessDayConvention:
        return self.business_day_convention_

    @property
    def holiday_convention(self) -> HolidayConvention:
        return self.holiday_convention_

    @property
    def compounding_method(self) -> CompoundingMethod:
        return self.compounding_method_
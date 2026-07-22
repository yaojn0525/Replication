from typing import Any
# in-house
from fixedincomelib.date import *
from fixedincomelib.market import *
from fixedincomelib.product.product_interfaces import *
from fixedincomelib.product.linear_products import *
from fixedincomelib.product.utilities import *

class ProductFactory:

    @classmethod
    def create_product_from_data_convention(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConvention,
        values: float,
        **kwargs: Any
    ):
        convention_obj: DataConvention = data_convention
        prod_type = convention_obj.type()
        func = ProductBuilderRegistry().get(prod_type)
        return func(value_date, axis1, convention_obj, values, **kwargs)

    @classmethod
    def create_cash_deposit(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionCashDeposit,
        values: float,
        **kwargs: Any
    ) -> ProductCashDeposit:
        
        effective_date = value_date
        term_or_effective_date, term_or_termnation_date = ProductFactory._tokenize_axis1(axis1)
        if term_or_termnation_date is None:
            # single axis
            term_or_termnation_date = term_or_effective_date
        else:
            # cross axes
            effective_date = term_or_effective_date.get_date()
            if term_or_effective_date.is_term():
                effective_date = add_period(
                    value_date, 
                    term_or_effective_date.get_term(),
                    data_convention.business_day_convention,
                    data_convention.holiday_convention,
                    data_convention.end_of_month)

        return ProductCashDeposit(
            effective_date,
            term_or_termnation_date,
            PayOrReceive.from_string('receive'),
            data_convention.currency,
            data_convention.notional,
            values,
            data_convention.accrual_basis)

    @classmethod
    def create_fra_or_fixing(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionFRAOrFixing,
        values: float,
        **kwargs: Any
    ) -> ProductFRAOrFixing:
        
        ibor_index : IBORIndex = data_convention.index
        term_or_effective_date, v = ProductFactory._tokenize_axis1(axis1)
        assert v is None
        effective_date = term_or_effective_date.get_date()
        if term_or_effective_date.is_term():
            effective_date = add_period_by_index(
                value_date, 
                term_or_effective_date.get_term(),
                ibor_index)

        return ProductFRAOrFixing(
            effective_date,
            TermOrDate(ibor_index.tenor()),
            PayOrReceive.from_string('receive'),
            ibor_index.currency,
            1e6,
            values,
            ibor_index)

    @classmethod
    def create_overnight_index_future(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionOvernightIndexFuture,
        values: float,
        **kwargs: Any,
    ) -> ProductOvernightIndexFuture:

        # it has to be yyyy-mm-dd x yyyy-mm-dd
        term_or_effective_date, term_or_termnation_date = ProductFactory._tokenize_axis1(axis1)
        if term_or_effective_date.is_term():
            raise Exception("Effective date is not valid.")
        if term_or_termnation_date is None:
            raise Exception("Termination date is missing.")

        # get composite index
        on_composite_index : OvernightCompositeIndex = data_convention.index

        return ProductOvernightIndexFuture(
            effective_date=term_or_effective_date.get_date(),
            term_or_termination_date=term_or_termnation_date,
            long_or_short=LongOrShort.LONG,
            amount=kwargs.get("amount", 1.0),
            on_composite_index=on_composite_index,
            strike=values,
            pay_date_or_offset=TermOrDate(data_convention.payment_offset),
            payment_business_day_conv=data_convention.payment_business_day_convention,
            payment_holiday_conv=data_convention.payment_holiday_convention,
            contractual_notional=data_convention.contractual_notional,
            basis_point=data_convention.basis_point,
            look_back_window=Period(kwargs.get("lookback window", "0D")),
            rates_cutoff=Period(kwargs.get("rates cutoff", "0D")))
    
    @classmethod
    def create_overnight_index_swap(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionOvernightIndexSwap,
        values: float,
        **kwargs: Any,
    ) -> ProductOvernightIndexSwap:

        term_or_effective_date, term_or_termination_date = ProductFactory._tokenize_axis1(axis1)
        if not term_or_termination_date:
            # spot starting (e.g., 5Y)
            effective_date = add_period(
                value_date, 
                data_convention.settlement_offset, 
                ql.Preceding, # i think so !
                data_convention.settlement_holiday_convention)
            term_or_termination_date = term_or_effective_date
        else:
            # forwad starting
            if term_or_effective_date.is_term():
                # e.g., 1Y x  ????
                this_date = add_period(
                    value_date, 
                    data_convention.settlement_offset, 
                    ql.Preceding, # i think so !
                    data_convention.settlement_holiday_convention)
                effective_date = add_period(
                    this_date,
                    term_or_effective_date.get_term(),
                    ql.Preceding, # i think so !
                    data_convention.settlement_holiday_convention)
            else:
                # e.g., YYYY-MM-DD x ????
                effective_date = term_or_effective_date.get_date()

        return ProductOvernightIndexSwap(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            on_composite_index=data_convention.index,
            fixed_rate=values,
            pay_or_rec=PayOrReceive.from_string(kwargs.get("pay_or_rec", "receive")),
            notional=data_convention.notional,
            accrual_period=data_convention.accrual_period,
            accrual_basis=data_convention.accrual_basis,
            business_day_convention=data_convention.payment_business_day_conv,
            holiday_convention=data_convention.payment_holiday_conv,
            schedule_generation_rule=ql.DateGeneration.Backward,
            floating_leg_accrual_period=data_convention.accrual_period,
            payment_off_set=data_convention.payment_offset,
            pay_business_day_convention=data_convention.payment_business_day_conv,
            pay_holiday_convention=data_convention.payment_holiday_conv)

    @classmethod
    def create_overnight_index_basis_swap(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionOvernightIndexBasisSwap,
        values: float,
        **kwargs: Any,
    ) -> ProductOvernightIndexBasisSwap:

        term_or_effective_date, term_or_termination_date = ProductFactory._tokenize_axis1(axis1)
        if not term_or_termination_date:
            # spot starting (e.g., 5Y)
            effective_date = add_period(
                value_date, 
                data_convention.settlement_offset, 
                ql.Preceding, # i think so !
                data_convention.settlement_holiday_convention)
            term_or_termination_date = term_or_effective_date
        else:
            # forwad starting
            if term_or_effective_date.is_term():
                # e.g., 1Y x  ????
                this_date = add_period(
                    value_date, 
                    data_convention.settlement_offset, 
                    ql.Preceding, # i think so !
                    data_convention.settlement_holiday_convention)
                effective_date = add_period(
                    this_date,
                    term_or_effective_date.get_term(),
                    ql.Preceding, # i think so !
                    data_convention.settlement_holiday_convention)
            else:
                # e.g., YYYY-MM-DD x ????
                effective_date = term_or_effective_date.get_date()

        return ProductOvernightIndexBasisSwap(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            on_composite_index=data_convention.on_index,
            ibor_index=data_convention.ibor_index,
            spread=values,
            pay_or_rec_on_composite_index_leg=PayOrReceive.from_string(kwargs.get("pay_or_rec", "receive")),
            notional=data_convention.notional,
            accrual_period=data_convention.accrual_period,
            business_day_convention=data_convention.on_index.index.payment_business_day_conv,
            holiday_convention=data_convention.on_index.index.payment_holiday_conv(),
            schedule_generation_rule=ql.DateGeneration.Backward,
            on_accrual_basis=data_convention.on_index.index.accrual_basis,
            ibor_accrual_basis=data_convention.ibor_index.accrual_basis,
            payment_off_set=data_convention.payment_offset,
            pay_business_day_convention=data_convention.payment_business_day_convention,
            pay_holiday_convention=data_convention.payment_holiday_convention)

    @classmethod
    def create_ois_basis_swap(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionOISBasisSwap,
        values: float,
        **kwargs: Any,
    ) -> ProductOISBasisSwap:

        term_or_effective_date, term_or_termination_date = ProductFactory._tokenize_axis1(axis1)
        if not term_or_termination_date:
            # spot starting (e.g., 5Y)
            effective_date = add_period(
                value_date, 
                data_convention.settlement_offset, 
                ql.Preceding, # i think so !
                data_convention.settlement_holiday_convention)
            term_or_termination_date = term_or_effective_date
        else:
            # forwad starting
            if term_or_effective_date.is_term():
                # e.g., 1Y x  ????
                this_date = add_period(
                    value_date, 
                    data_convention.settlement_offset, 
                    ql.Preceding, # i think so !
                    data_convention.settlement_holiday_convention)
                effective_date = add_period(
                    this_date,
                    term_or_effective_date.get_term(),
                    ql.Preceding, # i think so !
                    data_convention.settlement_holiday_convention)
            else:
                # e.g., YYYY-MM-DD x ????
                effective_date = term_or_effective_date.get_date()

        return ProductOISBasisSwap(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            basis_on_composite_index=data_convention.basis_on_index,
            reference_on_composite_index=data_convention.reference_on_index,
            spread=values,
            pay_or_rec=PayOrReceive.from_string(kwargs.get("pay_or_rec", "receive")),
            notional=data_convention.notional,
            accrual_period=data_convention.basis_accrual_period,
            business_day_convention=data_convention.basis_on_index.index.payment_business_day_conv,
            holiday_convention=data_convention.basis_on_index.index.payment_holiday_conv(),
            schedule_generation_rule=ql.DateGeneration.Backward,
            basis_on_accrual_basis=data_convention.basis_on_index.index.accrual_basis,
            reference_on_accrual_basis=data_convention.reference_on_index.index.accrual_basis,
            payment_off_set=data_convention.payment_offset,
            pay_business_day_convention=data_convention.payment_business_day_convention,
            pay_holiday_convention=data_convention.payment_holiday_convention)

    @classmethod
    def create_cross_currency_basis_swap_non_mtm(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: "DataConventionOvernightIndexCurrencyBasisSwap",
        values: float,
        **kwargs: Any,
    ) -> "ProductOvernightIndexCurrencyBasisSwapNonMTM":

        term_or_effective_date, term_or_termination_date = ProductFactory._tokenize_axis1(axis1)
        if not term_or_termination_date:
            # spot starting (e.g., 5Y)
            effective_date = add_period(
                value_date, 
                data_convention.settlement_offset, 
                ql.Preceding, # i think so !
                data_convention.settlement_holiday_convention)
            term_or_termination_date = term_or_effective_date
        else:
            # forwad starting
            if term_or_effective_date.is_term():
                # e.g., 1Y x  ????
                this_date = add_period(
                    value_date, 
                    data_convention.settlement_offset, 
                    ql.Preceding, # i think so !
                    data_convention.settlement_holiday_convention)
                effective_date = add_period(
                    this_date,
                    term_or_effective_date.get_term(),
                    ql.Preceding, # i think so !
                    data_convention.settlement_holiday_convention)
            else:
                # e.g., YYYY-MM-DD x ????
                effective_date = term_or_effective_date.get_date()

        basis_ccy = data_convention.basis_currency.code()
        ref_ccy = data_convention.reference_currency.code()
        try:
            fx_index = IndexRegistry().get(f"{basis_ccy}-{ref_ccy}")
        except:
            fx_index = IndexRegistry().get(f"{ref_ccy}-{basis_ccy}")

        return ProductOvernightIndexCurrencyBasisSwapNonMTM(
            effective_date=effective_date,
            term_or_termination_date=term_or_termination_date,
            basis_leg_index=data_convention.basis_on_index,
            reference_leg_index=data_convention.reference_on_index,
            pay_or_rec=PayOrReceive.from_string(kwargs.get("pay_or_rec", "receive")),
            basis_leg_notional=data_convention.basis_notional,
            fx_index=fx_index,
            accrual_period=data_convention.basis_accrual_period,
            accrual_basis=data_convention.basis_on_index.index.accrual_basis,
            spread=values,
            schedule_generation_rule=ql.DateGeneration.Backward,
            business_day_convention=data_convention.basis_on_index.index.payment_business_day_conv,
            holiday_convention=data_convention.basis_on_index.index.payment_holiday_conv(),
            payment_offset=data_convention.basis_payment_offset,
            payment_business_day_convention=data_convention.basis_on_index.index.payment_business_day_conv,
            payment_holiday_convention=data_convention.basis_on_index.index.payment_holiday_conv(),
            exchange_notional_at_start=True,
            exchange_notional_at_end=True,
            reference_leg_accrual_period=data_convention.reference_accrual_period,
            reference_leg_accrual_basis=data_convention.reference_on_index.index.accrual_basis,
            reference_leg_payment_offset=data_convention.reference_payment_offset,
            reference_leg_payment_business_day_convention=data_convention.reference_on_index.index.payment_business_day_conv,
            reference_leg_payment_holidays=data_convention.reference_on_index.index.payment_holiday_conv())
    
    @classmethod
    def create_generic_forward(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionGenericForward,
        values: float,
        **kwargs: Any
    ) -> ProductGenericForward:
        
        term_or_effective_date, term_or_termination_date = ProductFactory._tokenize_axis1(axis1)
        if not term_or_termination_date:
            # spot starting (e.g., 5Y)
            effective_date = add_period(
                value_date, 
                data_convention.settlement_offset, 
                data_convention.business_day_convention,
                data_convention.settlement_holiday_convention,
                data_convention.end_of_month)
            term_or_termination_date = term_or_effective_date
        else:
            # forwad starting
            if term_or_effective_date.is_term():
                # e.g., 1Y x  ????
                this_date = add_period(
                    value_date, 
                    data_convention.settlement_offset, 
                    data_convention.business_day_convention,
                    data_convention.settlement_holiday_convention,
                    data_convention.end_of_month)
                effective_date = add_period(
                    this_date,
                    term_or_effective_date.get_term(),
                    data_convention.business_day_convention,
                    data_convention.settlement_holiday_convention,
                    data_convention.end_of_month)
            else:
                # e.g., YYYY-MM-DD x ????
                effective_date = term_or_effective_date.get_date()

        return ProductGenericForward(
            effective_date,
            term_or_effective_date,
            PayOrReceive.from_string("receive"),
            data_convention.currency,
            data_convention.notional,
            values,
            data_convention.index,
            data_convention.accrual_basis,
            data_convention.settlement_offset,
            data_convention.business_day_convention,
            data_convention.holiday_convention,
            TermOrDate("0D"),
            data_convention.business_day_convention,
            data_convention.holiday_convention,
            data_convention.end_of_month,
            data_convention.compounding_method)

    @classmethod
    def create_generic_forward_spread(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionGenericForwardSpread,
        values: float,
        **kwargs: Any
    ) -> ProductGenericForwardSpread:
        
        term_or_effective_date, term_or_termination_date = ProductFactory._tokenize_axis1(axis1)
        if not term_or_termination_date:
            # spot starting (e.g., 5Y)
            effective_date = add_period(
                value_date, 
                data_convention.settlement_offset, 
                data_convention.settlement_business_day_convention,
                data_convention.settlement_holiday_convention,
                data_convention.end_of_month)
            term_or_termination_date = term_or_effective_date
        else:
            # forwad starting
            if term_or_effective_date.is_term():
                # e.g., 1Y x  ????
                this_date = add_period(
                    value_date, 
                    data_convention.settlement_offset, 
                    data_convention.settlement_business_day_convention,
                    data_convention.settlement_holiday_convention,
                    data_convention.end_of_month)
                effective_date = add_period(
                    this_date,
                    term_or_effective_date.get_term(),
                    data_convention.settlement_business_day_convention,
                    data_convention.settlement_holiday_convention,
                    data_convention.end_of_month)
            else:
                # e.g., YYYY-MM-DD x ????
                effective_date = term_or_effective_date.get_date()

        return ProductGenericForwardSpread(
            effective_date,
            term_or_effective_date,
            PayOrReceive.from_string("receive"),
            data_convention.basis_currency,
            data_convention.basis_notional,
            values,
            data_convention.basis_index,
            data_convention.reference_index,
            data_convention.basis_accrual_basis,
            data_convention.settlement_offset,
            data_convention.settlement_business_day_convention,
            data_convention.settlement_holiday_convention,
            TermOrDate("0D"),
            data_convention.payment_business_day_convention,
            data_convention.payment_holiday_convention,
            data_convention.end_of_month,
            data_convention.compounding_method,
            data_convention.reference_accrual_basis_)

    @classmethod
    def create_generic_spread(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionGenericSpread,
        values: float,
        **kwargs: Any
    ) -> ProductGenericSpread:
        
        # data convention
        business_day_convention = ql.Preceding
        holiday_convention = ql.NullCalendar()
        if hasattr(data_convention.target_data_convention, "business_day_convention"):
            business_day_convention = data_convention.target_data_convention.business_day_convention
        holiday_convention = ql.NullCalendar()
        if hasattr(data_convention.target_data_convention, "holiday_convention"):
            holiday_convention = data_convention.target_data_convention.holiday_convention
        settlement_offset = Period("0D")
        if hasattr(data_convention.target_data_convention, "settlement_offset"):
            settlement_offset = data_convention.target_data_convention.settlement_offset

        term_or_effective_date, term_or_termination_date = ProductFactory._tokenize_axis1(axis1)
        if not term_or_termination_date:
            # spot starting (e.g., 5Y)
            effective_date = add_period(
                value_date, 
                settlement_offset, 
                business_day_convention,
                holiday_convention)
            term_or_termination_date = term_or_effective_date
        else:
            # forwad starting
            if term_or_effective_date.is_term():
                # e.g., 1Y x  ????
                this_date = add_period(
                    value_date, 
                    settlement_offset, 
                    business_day_convention,
                    holiday_convention)
                effective_date = add_period(
                    this_date,
                    term_or_effective_date.get_term(),
                    business_day_convention,
                    holiday_convention)
            else:
                # e.g., YYYY-MM-DD x ????
                effective_date = term_or_effective_date.get_date()

        return ProductGenericSpread(
            effective_date,
            term_or_effective_date,
            PayOrReceive.from_string("receive"),
            data_convention.currency,
            data_convention.notional,
            values,
            data_convention.target_data_convention,
            data_convention.reference_data_convention)

    @classmethod
    def create_zero_spread_product(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionIborSpreadZeroRate,
        values: float,
        **kwargs: Any,
    ) -> ProductIBORZeroSpread:

        term_or_termination_date, _ = ProductFactory._tokenize_axis1(axis1)
        ibor_index : IBORIndex = data_convention.basis_ibor_index

        termination_date = None
        if term_or_termination_date.is_term():
            termination_date = add_period(
                value_date, 
                term_or_termination_date.get_term(), 
                ibor_index.payment_business_day_conv,
                ibor_index.settlement_holiday)
        else:
            termination_date = term_or_termination_date.get_date()

        return ProductIBORZeroSpread(
            termination_date,
            PayOrReceive.from_string('receive'),
            ibor_index.currency,
            kwargs.get("notional", 1e4),
            values,
            data_convention.basis_ibor_index,
            data_convention.reference_index)

    @classmethod
    def create_swap_spread_basis_swap(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionSwapSpreadBasisSwap,
        values: float,
        **kwargs: Any
    ) -> ProductSwapSpreadBasisSwap:
        
        # data convention
        business_day_convention = ql.Preceding
        holiday_convention = data_convention.settlement_holiday_convention
        if hasattr(data_convention.basis_swap, "payment_holiday_convention"):
            holiday_convention = data_convention.basis_swap.payment_holiday_convention
        settlement_offset = data_convention.settlement_offset

        term_or_effective_date, term_or_termination_date = ProductFactory._tokenize_axis1(axis1)
        if not term_or_termination_date:
            # spot starting (e.g., 5Y)
            effective_date = add_period(
                value_date, 
                settlement_offset, 
                business_day_convention,
                holiday_convention)
            term_or_termination_date = term_or_effective_date
        else:
            # forwad starting
            if term_or_effective_date.is_term():
                # e.g., 1Y x  ????
                this_date = add_period(
                    value_date, 
                    settlement_offset, 
                    business_day_convention,
                    holiday_convention)
                effective_date = add_period(
                    this_date,
                    term_or_effective_date.get_term(),
                    business_day_convention,
                    holiday_convention)
            else:
                # e.g., YYYY-MM-DD x ????
                effective_date = term_or_effective_date.get_date()

        return ProductSwapSpreadBasisSwap(
            effective_date,
            term_or_effective_date,
            PayOrReceive.from_string("receive"),
            data_convention.currency,
            data_convention.notional,
            values,
            data_convention.basis_swap,
            data_convention.reference_swap,
            business_day_convention,
            holiday_convention)

    ### utilities
    @staticmethod
    def _tokenize_axis1(axis1: str):

        axis1 = axis1.strip()
        if "x" in axis1.lower():
            tokens = axis1.replace("X", "x").split("x")
            return TermOrDate(tokens[0].strip()), TermOrDate(tokens[1].strip())
        else:
            return TermOrDate(axis1), None


### support product factory
ProductBuilderRegistry().register(DataConventionCashDeposit.type(), ProductFactory.create_cash_deposit)
ProductBuilderRegistry().register(DataConventionFRAOrFixing.type(), ProductFactory.create_fra_or_fixing)
ProductBuilderRegistry().register(DataConventionOvernightIndexFuture.type(), ProductFactory.create_overnight_index_future)
ProductBuilderRegistry().register(DataConventionOvernightIndexSwap.type(), ProductFactory.create_overnight_index_swap)
ProductBuilderRegistry().register(DataConventionOvernightIndexBasisSwap.type(), ProductFactory.create_overnight_index_basis_swap)
ProductBuilderRegistry().register(DataConventionOISBasisSwap.type(), ProductFactory.create_ois_basis_swap)
ProductBuilderRegistry().register(DataConventionOvernightIndexCurrencyBasisSwap.type(), ProductFactory.create_cross_currency_basis_swap_non_mtm)
ProductBuilderRegistry().register(DataConventionGenericForward.type(), ProductFactory.create_generic_forward)
ProductBuilderRegistry().register(DataConventionGenericForwardSpread.type(), ProductFactory.create_generic_forward_spread)
ProductBuilderRegistry().register(DataConventionGenericSpread.type(), ProductFactory.create_generic_spread)
ProductBuilderRegistry().register(DataConventionIborSpreadZeroRate.type(), ProductFactory.create_zero_spread_product)
ProductBuilderRegistry().register(DataConventionSwapSpreadBasisSwap.type(), ProductFactory.create_swap_spread_basis_swap)

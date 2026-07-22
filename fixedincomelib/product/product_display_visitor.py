import pandas as pd
from functools import singledispatchmethod
# in-house
from fixedincomelib.product.linear_products import *
from fixedincomelib.product.product_portfolio import ProductPortfolio
from fixedincomelib.product.product_interfaces import Product, ProductVisitor

class ProductDisplayVisitor(ProductVisitor):

    def __init__(self) -> None:
        super().__init__()
        self.nvps_ = []

    @singledispatchmethod
    def visit(self, product: Product):
        raise NotImplementedError(f"No visitor for {Product._product_type}")

    def display(self) -> pd.DataFrame:
        return pd.DataFrame(self.nvps_, columns=["Name", "Value"])

    def _common_items(self, product: Product):
        self.nvps_ = [
            ["Product Type", product.product_type],
            ["Notional", product.notional],
            ["Currency", product.currency.code()],
            ["Long Or Short", product.long_or_short.to_string().upper()],
        ]

    ### helper product
    @visit.register
    def _(self, product: ProductBulletCashflow):
        self._common_items(product)
        self.nvps_.append(["Termination Date", product.termination_date.ISO()])
        self.nvps_.append(["Payment Date Or Offset", TermOrDate.to_string(product.pay_date_or_payment_offset)])

    @visit.register
    def _(self, product: ProductFixedAccrued):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date_)])
        self.nvps_.append(["Pay Or Receive", PayOrReceive.to_string(product.pay_or_rec).upper()])
        self.nvps_.append(["Accrual Basis", AccrualBasis.to_string(product.accrual_basis)])
        self.nvps_.append(["Coupon", product.fixed_rate])
        self.nvps_.append(["Business Day Convention", BusinessDayConvention.to_string(product.business_day_convention)])
        self.nvps_.append(["Holiday Convention", HolidayConvention.to_string(product.holiday_convention)])
        self.nvps_.append(["Payment Date Or Offset", TermOrDate.to_string(product.pay_date_or_payment_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.payment_holiday_convention)])

    @visit.register
    def _(self, product: ProductOvernightIndexCompositeCashflow):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Pay Or Receive", PayOrReceive.to_string(product.pay_or_rec).upper()])
        self.nvps_.append(["ON Composite Index", product.index.index_name()])
        self.nvps_.append(["Spread", product.spread])
        self.nvps_.append(["Accrual Basis", AccrualBasis.to_string(product.accrual_basis) if product.accrual_basis else "NONE"])
        self.nvps_.append(["Payment Date Or Offset", TermOrDate.to_string(product.pay_date_or_payment_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.payment_holiday_convention)])
        self.nvps_.append(["Rate Cutoff", Period.to_string(product.rate_cutoff)])
        self.nvps_.append(["Lookback Window", Period.to_string(product.look_back_window)])

    @visit.register
    def _(self, product: ProductIBORIndexCashflow):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Pay Or Receive", PayOrReceive.to_string(product.pay_or_rec).upper()])
        self.nvps_.append(["IBOR Index", product.index.index_name()])
        self.nvps_.append(["Spread", product.spread])
        self.nvps_.append(["Accrual Basis", AccrualBasis.to_string(product.accrual_basis) if product.accrual_basis else "NONE"])
        self.nvps_.append(["Payment Date Or Offset", TermOrDate.to_string(product.pay_date_or_payment_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.payment_holiday_convention)])
        self.nvps_.append(["Pay In Advance", product.pay_in_advance])

    @visit.register
    def _(self, product: ProductIBORCompoundingCashflow):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Pay Or Receive", PayOrReceive.to_string(product.pay_or_rec).upper()])
        self.nvps_.append(["IBOR Index", product.index.index_name()])
        self.nvps_.append(["Spread", product.spread])
        self.nvps_.append(["Leverage", product.leverage])
        self.nvps_.append(["Calculation Period", product.calculation_period])
        self.nvps_.append(["Payment Date Or Offset", TermOrDate.to_string(product.pay_date_or_payment_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.payment_holiday_convention)])
        self.nvps_.append(["Compounding Method", product.compounding_method.to_string().upper()])

    ### calibration instruments
    @visit.register
    def _(self, product : ProductCashDeposit):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Pay Or Receive", product.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Coupon", product.fixed_rate])
        self.nvps_.append(["Accrual Basis", AccrualBasis.to_string(product.accrual_basis)])
        self.nvps_.append(["Payment Date Or Offset", TermOrDate.to_string(product.pay_date_or_payment_offset)])
        self.nvps_.append(["Business Day Convention", BusinessDayConvention.to_string(product.business_day_convention)])
        self.nvps_.append(["Holiday Convention", HolidayConvention.to_string(product.holiday_convention)])

    @visit.register
    def _(self, product : ProductFRAOrFixing):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Pay Or Receive", product.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Currency", product.currency.code()])
        self.nvps_.append(["Currency", product.notional])
        self.nvps_.append(["Coupon", product.coupon])
        self.nvps_.append(["IBOR Index", product.index.index_name()])
        self.nvps_.append(["Payment Date Or Offset", TermOrDate.to_string(product.pay_date_or_payment_offset)])
        self.nvps_.append(["FRA Discounting Style", product.fra_discounting_style])

    @visit.register
    def _(self, product: ProductOvernightIndexFuture):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Termination Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Long Or Short", product.long_or_short.to_string()])
        self.nvps_.append(["Amount", product.amount])
        self.nvps_.append(["ON Composite Index", product.index.index_name()])
        self.nvps_.append(["Strike", product.strike])
        self.nvps_.append(["Payment Date Or Offset", Period.to_string(product.payment_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.payment_holiday_convention)])
        self.nvps_.append(["Contractual Notional", product.contractual_notional])
        self.nvps_.append(["Basis Point", product.basis_point])        
        self.nvps_.append(["Lookback Window", Period.to_string(product.look_back_window)])
        self.nvps_.append(["Rate CutOff", Period.to_string(product.rate_cutoff)])

    @visit.register
    def _(self, product: ProductOvernightIndexSwap):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.fixed_leg.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.fixed_leg.term_or_termination_date)])
        self.nvps_.append(["Overnight Composite Index", product.floating_leg.index.index_name()])
        self.nvps_.append(['Fixed Rate', product.fixed_leg.fixed_rate])
        self.nvps_.append(["Pay Or Receive", product.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Notional", product.fixed_leg.notional])
        self.nvps_.append(["Accrual Period", Period.to_string(product.fixed_leg.accrual_period)])
        self.nvps_.append(["Accrual Basis", AccrualBasis.to_string(product.fixed_leg.accrual_basis)])
        self.nvps_.append(["Business Day Convention", BusinessDayConvention.to_string(product.fixed_leg.business_day_convention)])
        self.nvps_.append(["Holiday Convention", HolidayConvention.to_string(product.fixed_leg.holiday_convention)])
        self.nvps_.append(["Schedule Generation Rule", product.fixed_leg.schedule_generation_rule])
        self.nvps_.append(["Floating Leg Accrual Period", Period.to_string(product.floating_leg.accrual_period)])
        self.nvps_.append(["Payment Offset", Period.to_string(product.fixed_leg.payment_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.fixed_leg.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.fixed_leg.payment_holiday_convention)])
        self.nvps_.append(["Lookback Window", Period.to_string(product.floating_leg.look_back_window)])
        self.nvps_.append(["Rate CutOff", Period.to_string(product.floating_leg.rate_cutoff)])
        self.nvps_.append(["First Regular Date", product.fixed_leg.first_regular_date.ISO()])
        self.nvps_.append(["Next To Last Date", product.fixed_leg.next_to_last_date.ISO()])

    @visit.register
    def _(self, product: ProductOvernightIndexBasisSwap):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.on_composite_index_leg.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.on_composite_index_leg.term_or_termination_date)])
        self.nvps_.append(["ON Composite Index", product.on_composite_index_leg.index.index_name()])
        self.nvps_.append(["IBOR Index", product.ibor_index_leg.index.index_name()])
        self.nvps_.append(["Spread", product.on_composite_index_leg.spread])
        self.nvps_.append(["Pay Or Receive ON Composite Index", product.pay_or_rec_on_composite_index_leg.to_string().upper()])
        self.nvps_.append(["Notional", product.on_composite_index_leg.notional])
        self.nvps_.append(["Accrual Period", Period.to_string(product.on_composite_index_leg.accrual_period)])
        self.nvps_.append(["Business Day Convention", BusinessDayConvention.to_string(product.on_composite_index_leg.business_day_convention)])
        self.nvps_.append(["Holiday Convention", HolidayConvention.to_string(product.on_composite_index_leg.holiday_convention)])
        self.nvps_.append(["Schedule Generation Rule", product.on_composite_index_leg.schedule_generation_rule])
        self.nvps_.append(["ON Leg Accrual Basis", AccrualBasis.to_string(product.on_composite_index_leg.accrual_basis)])
        self.nvps_.append(["IBOR LegAccrual Basis", AccrualBasis.to_string(product.ibor_index_leg.accrual_basis)])
        self.nvps_.append(["Payment Offset", Period.to_string(product.on_composite_index_leg.payment_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.on_composite_index_leg.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.on_composite_index_leg.payment_holiday_convention)])
        self.nvps_.append(["Lookback Window", Period.to_string(product.on_composite_index_leg.look_back_window)])
        self.nvps_.append(["Rate CutOff", Period.to_string(product.on_composite_index_leg.rate_cutoff)])
        self.nvps_.append(["First Regular Date", product.on_composite_index_leg.first_regular_date.ISO()])
        self.nvps_.append(["Next To Last Date", product.on_composite_index_leg.next_to_last_date.ISO()])

    @visit.register
    def _(self, product: ProductOISBasisSwap):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.basis_leg.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.basis_leg.term_or_termination_date)])
        self.nvps_.append(["Basis ON Composite Index", product.basis_leg.index.index_name()])
        self.nvps_.append(["Reference ON Composite Index", product.reference_leg.index.index_name()])
        self.nvps_.append(["Spread", product.basis_leg.spread])
        self.nvps_.append(["Pay Or Receive", product.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Notional", product.basis_leg.notional])
        self.nvps_.append(["Accrual Period", Period.to_string(product.basis_leg.accrual_period)])
        self.nvps_.append(["Business Day Convention", BusinessDayConvention.to_string(product.basis_leg.business_day_convention)])
        self.nvps_.append(["Holiday Convention", HolidayConvention.to_string(product.basis_leg.holiday_convention)])
        self.nvps_.append(["Schedule Generation Rule", product.basis_leg.schedule_generation_rule])
        self.nvps_.append(["Basis Leg Accrual Basis", AccrualBasis.to_string(product.basis_leg.accrual_basis)])
        self.nvps_.append(["Reference Leg LegAccrual Basis", AccrualBasis.to_string(product.reference_leg.accrual_basis)])
        self.nvps_.append(["Payment Offset", Period.to_string(product.basis_leg.payment_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.basis_leg.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.basis_leg.payment_holiday_convention)])
        self.nvps_.append(["Lookback Window", Period.to_string(product.basis_leg.look_back_window)])
        self.nvps_.append(["Rate CutOff", Period.to_string(product.basis_leg.rate_cutoff)])
        self.nvps_.append(["First Regular Date", product.basis_leg.first_regular_date.ISO()])
        self.nvps_.append(["Next To Last Date", product.basis_leg.next_to_last_date.ISO()])

    @visit.register
    def _(self, product: ProductOvernightIndexCurrencyBasisSwapNonMTM):
        self.nvps_ = [
            ["Product Type", product.product_type],
            ["Currency (Basis)", product.currency.code()],
            ["Long Or Short", product.long_or_short.to_string().upper()],
        ]
        self.nvps_.append(["Effective Date", product.basis_leg.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.basis_leg.term_or_termination_date)])
        self.nvps_.append(["Basis Leg Index", product.basis_leg.index.index_name()])
        self.nvps_.append(["Reference Leg Index", product.reference_leg.index.index_name()])
        self.nvps_.append(["Pay Or Receive", product.basis_leg.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Notional (Basis Leg)", product.basis_leg.notional])
        self.nvps_.append(["FX Index", product.fx_index.index_name()])
        self.nvps_.append(["Accrual Period", Period.to_string(product.basis_leg.accrual_period)])
        self.nvps_.append(["Accrual Basis", AccrualBasis.to_string(product.basis_leg.accrual_basis)])
        self.nvps_.append(["Spread", product.basis_leg.spread])
        self.nvps_.append(["Schedule Generation Rule", resolve_schedule_generation(product.basis_leg.schedule_generation_rule)])
        self.nvps_.append(["Business Day Convention", BusinessDayConvention.to_string(product.basis_leg.business_day_convention)])
        self.nvps_.append(["Holiday Convention", HolidayConvention.to_string(product.basis_leg.holiday_convention)])
        self.nvps_.append(["Payment Offset", Period.to_string(product.basis_leg.payment_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.basis_leg.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.basis_leg.payment_holiday_convention)])
        self.nvps_.append(["Exchange At Start", bool(product.exchange_notional_at_start)])
        self.nvps_.append(["Exchange At End", bool(product.exchange_notional_at_end)])
        self.nvps_.append(["Lookback Window", Period.to_string(product.basis_leg.look_back_window)])
        self.nvps_.append(["Rate CutOff", Period.to_string(product.basis_leg.rate_cutoff)])
        self.nvps_.append(["First Regular Date", product.basis_leg.first_regular_date.ISO()])
        self.nvps_.append(["Next To Last Date", product.basis_leg.next_to_last_date.ISO()])
        self.nvps_.append(["End of Month", product.end_of_month])
        self.nvps_.append(["Reference Leg Accrual Period", Period.to_string(product.reference_leg_accrual_period)])
        self.nvps_.append(["Reference Leg Accrual Basis", AccrualBasis.to_string(product.reference_leg_accrual_basis)])
        self.nvps_.append(["Reference Leg Payment Offset", Period.to_string(product.reference_leg.payment_offset)])
        self.nvps_.append(["Reference Leg Payment Business Day Convention", BusinessDayConvention.to_string(product.reference_leg.payment_business_day_convention)])
        self.nvps_.append(["Reference Leg Payment Holiday Convention", HolidayConvention.to_string(product.reference_leg.payment_holiday_convention)])

    @visit.register
    def _(self, product: ProductGenericForward):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Pay Or Rec", product.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Currency", product.currency.code()])
        self.nvps_.append(["Notional", product.notional])
        self.nvps_.append(["Coupon", product.coupon])
        self.nvps_.append(["Index", product.index.index_name()])
        self.nvps_.append(["Accrual Basis", AccrualBasis.to_string(product.accrual_basis)])
        self.nvps_.append(["Settlement Offset", Period.to_string(product.settlement_offset)])
        self.nvps_.append(["Business Day Convention", BusinessDayConvention.to_string(product.business_day_convention)])
        self.nvps_.append(["Holiday Convention", HolidayConvention.to_string(product.holiday_convention)])
        self.nvps_.append(["Pay Date Or Offset", TermOrDate.to_string(product.pay_date_or_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.payment_holiday_day_convention)])
        self.nvps_.append(["End Of Month", product.end_of_month])
        self.nvps_.append(["Compounding Method", product.compounding_method.to_string().upper()])

    @visit.register
    def _(self, product: ProductGenericForwardSpread):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Pay Or Rec", product.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Currency", product.currency.code()])
        self.nvps_.append(["Notional", product.notional])
        self.nvps_.append(["Spread", product.spread])
        self.nvps_.append(["Basis Index", product.basis_index.index_name()])
        self.nvps_.append(["Reference Index", product.reference_index.index_name()])
        self.nvps_.append(["Accrual Basis", AccrualBasis.to_string(product.accrual_basis)])
        self.nvps_.append(["Settlement Offset", Period.to_string(product.settlement_offset)])
        self.nvps_.append(["Business Day Convention", BusinessDayConvention.to_string(product.settlement_business_day_convention)])
        self.nvps_.append(["Holiday Convention", HolidayConvention.to_string(product.settlement_holiday_convention)])
        self.nvps_.append(["Pay Date Or Offset", TermOrDate.to_string(product.pay_date_or_offset)])
        self.nvps_.append(["Payment Business Day Convention", BusinessDayConvention.to_string(product.payment_business_day_convention)])
        self.nvps_.append(["Payment Holiday Convention", HolidayConvention.to_string(product.payment_holiday_day_convention)])
        self.nvps_.append(["End Of Month", product.end_of_month])
        self.nvps_.append(["Compounding Method", product.compounding_method.to_string().upper()])
        self.nvps_.append(["Reference Leg Accrual Basis", AccrualBasis.to_string(product.reference_leg_accrual_basis)])

    @visit.register
    def _(self, product: ProductGenericSpread):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Pay Or Rec", product.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Currency", product.currency.code()])
        self.nvps_.append(["Notional", product.notional])
        self.nvps_.append(["Spread", product.spread])
        self.nvps_.append(["Basis Data Convention", product.basis_data_convention.name])
        self.nvps_.append(["Reference Data Convention", product.basis_data_convention.name])

    @visit.register
    def _(self, product: ProductIBORZeroSpread):
        self._common_items(product)
        self.nvps_.append(["Termination Date", product.termination_date.ISO()])
        self.nvps_.append(["Pay Or Rec", product.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Currency", product.currency.code()])
        self.nvps_.append(["Notional", product.notional])
        self.nvps_.append(["Spread", product.spread])
        self.nvps_.append(["Basis Index", product.basis_index.index_name()])
        self.nvps_.append(["Reference Index", product.reference_index.index_name()])

    @visit.register
    def _(self, product: ProductSwapSpreadBasisSwap):
        self._common_items(product)
        self.nvps_.append(["Effective Date", product.effective_date.ISO()])
        self.nvps_.append(["Term Or Termination Date", TermOrDate.to_string(product.term_or_termination_date)])
        self.nvps_.append(["Pay Or Rec", product.pay_or_rec.to_string().upper()])
        self.nvps_.append(["Currency", product.currency.code()])
        self.nvps_.append(["Notional", product.notional])
        self.nvps_.append(["Spread", product.spread])
        self.nvps_.append(["Basis Swap Convention", product.basis_swap_convention.name])
        self.nvps_.append(["Reference Swap Convention", product.reference_swap_convention.name])
        self.nvps_.append(["Business Day Convention", BusinessDayConvention.to_string(product.business_day_convention)])
        self.nvps_.append(["Holiday Convention", HolidayConvention.to_string(product.holiday_convention)])

    @visit.register
    def _(self, product: ProductPortfolio):
        self.nvps_.append(["Product Type", product.product_type])
        for i in range(product.num_elemnts):
            self.nvps_.append([f"Product {i} Type", product.element(i).product_type])
            self.nvps_.append([f"Product {i} Weight", product.weight(i)])

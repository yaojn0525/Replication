import QuantLib as ql
import numpy as np
import torch
from typing import Optional, List

# in-house
from fixedincomelib.date import *
from fixedincomelib.market import *
from fixedincomelib.product import *
from fixedincomelib.valuation import *
from fixedincomelib.valuation.valuation_engine_portfolio import ValuationEngineProductPortfolio
from fixedincomelib.yield_curve.yield_curve_model import YieldCurve
from fixedincomelib.yield_curve.valuation_engine_analytics import *


def _to_float(x) -> float:
    return float(x.detach()) if isinstance(x, torch.Tensor) else float(x)


## valuation engine for atomic products
### Product Fixed Accrued
class ValuationEngineProductFixedAccrued(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductFixedAccrued,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_date_ = product.payment_date
        self.coupon_ = product.fixed_rate
        self.tau_ = product.accrued
        self.notional_ = abs(product.notional)
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0

        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_: FundingIdentifier = self.funding_vp_.get_funding_index(self.currency_)

        self.df_ = 0.0
        self.settlement_amount_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        # undiscounted payoff: notional * tau * coupon
        settlement_amount = self.sign_ * self.notional_ * self.tau_ * self.coupon_

        if self.value_date_ > self.payment_date_:
            self.value_ = 0.0
            self.cash_ = 0.0
            self.df_ = 0.0
        elif self.value_date_ == self.payment_date_:
            self.value_ = settlement_amount
            self.cash_ = _to_float(settlement_amount)
            self.df_ = 1.0
        else:
            casted_yc: YieldCurve = self.model_
            self.df_ = casted_yc.discount_factor(
                self.funding_index_, self.payment_date_, calc_grad=True
            )
            self.value_ = settlement_amount * self.df_
            self.cash_ = 0.0

        self.settlement_amount_ = settlement_amount

    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        this_cf.add_row(
            0,
            self.product_.product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.payment_date_,
            _to_float(self.settlement_amount_),
            _to_float(self.value_),
            _to_float(self.df_),
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrued=self.tau_,
            index_or_fixed="FIXED",
            index_value=self.coupon_,
        )

        return this_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, self.cash_)
        return report

    def par_rate_or_spread(self) -> float:
        return self.coupon_

    def pv01(self) -> float:
        return self.sign_ * self.notional_ * self.tau_ * _to_float(self.df_) * 1e-4

    # def grad_at_par(self) -> np.ndarray:
    #     casted_yc: YieldCurve = self.model_
    #     return casted_yc.get_gradient(reset=False)


### Product Overnight Index Composite Cashflow
class ValuationEngineProductOvernightIndexCompositeCashflow(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductOvernightIndexCompositeCashflow,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        # get info from product
        self.currency_ = product.currency
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_date_ = product.payment_date
        self.spread_ = product.spread
        self.leverage_ = product.leverage
        self.tau_ = product.accrued
        self.notional_ = abs(product.notional)
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0

        self.on_composite_index_: OvernightCompositeIndex = product.index
        self.on_index_: OvernightIndex = self.on_composite_index_.index

        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        casted_yc: YieldCurve = self.model_

        # discounted (a plain cashflow settling once on payment_date_, like the FRA)
        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_: FundingIdentifier = self.funding_vp_.get_funding_index(self.currency_)

        self.anchored_index_: AnchoredOvernightIndex = AnchoredOvernightIndex(
            self.effective_date_,
            self.termination_date_,
            self.on_index_,
            self.on_composite_index_.compounding_method,
            rate_cutoff=product.rate_cutoff,
            look_back_window=product.look_back_window,
            business_day_convention=self.on_composite_index_.business_day_conv,
            holiday_convention=self.on_composite_index_.payment_holiday_conv,
        )
        self.index_engine_: ValuationEngineAnalyticsCompositeIndex = (
            ValuationEngineAnalyticsCompositeIndex(casted_yc, self.anchored_index_, self.vpc_)
        )

        self.forward_rate_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        self.index_engine_.calculate_value()
        self.forward_rate_ = self.index_engine_.value

        # undiscounted payoff: notional * tau * (leverage * compounded rate + spread)
        settlement_amount = (
            self.sign_
            * self.notional_
            * self.tau_
            * (self.leverage_ * self.forward_rate_ + self.spread_)
        )

        # PV and cash
        if self.value_date_ > self.payment_date_:
            self.value_ = 0.0
            self.cash_ = 0.0
            self.df_ = 0.0
        elif self.value_date_ == self.payment_date_:
            self.value_ = settlement_amount
            self.cash_ = _to_float(settlement_amount)
            self.df_ = 1.0
        else:
            casted_yc: YieldCurve = self.model_
            self.df_ = casted_yc.discount_factor(
                self.funding_index_, self.payment_date_, calc_grad=True
            )
            self.value_ = settlement_amount * self.df_
            self.cash_ = 0.0

        self.settlement_amount_ = settlement_amount

    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        this_cf.add_row(
            0,
            self.product_.product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.payment_date_,
            _to_float(self.settlement_amount_),
            _to_float(self.value_),
            _to_float(self.df_),
            fixing_date=self.termination_date_,
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrued=self.tau_,
            index_or_fixed=self.on_index_.index_name(),
            index_value=_to_float(self.forward_rate_),
        )

        return this_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, self.cash_)
        return report

    def par_rate_or_spread(self) -> float:
        return _to_float(self.forward_rate_)

    def pv01(self) -> float:
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            (dv_df,) = torch.autograd.grad(self.value_, self.forward_rate_, retain_graph=True)
            return float(dv_df) * 1e-4
        return 0.0

    # def grad_at_par(self) -> np.ndarray:
    #     casted_yc: YieldCurve = self.model_
    #     if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
    #         self.forward_rate_.backward(retain_graph=True)
    #         return casted_yc.get_gradient(reset=True)
    #     return casted_yc.get_gradient(reset=False)


### Product Ibor Index Cashflow
class ValuationEngineProductIBORIndexCashflow(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductIBORIndexCashflow,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_date_ = product.payment_date
        self.spread_ = product.spread
        self.leverage_ = product.leverage
        self.tau_ = product.accrued
        self.notional_ = abs(product.notional)
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0

        self.ibor_index_: IBORIndex = product.index

        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        casted_yc: YieldCurve = self.model_

        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_: FundingIdentifier = self.funding_vp_.get_funding_index(self.currency_)

        self.anchored_index_: AnchoredIborIndex = AnchoredIborIndex(
            self.effective_date_,
            self.termination_date_,
            self.ibor_index_,
            CompoundingMethod.SIMPLE,
            business_day_convention=product.payment_business_day_convention,
            holiday_convention=product.payment_holiday_convention,
        )
        self.index_engine_: ValuationEngineAnalyticsIborIndex = ValuationEngineAnalyticsIborIndex(
            casted_yc, self.anchored_index_, self.vpc_
        )

        self.forward_rate_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        self.index_engine_.calculate_value()
        self.forward_rate_ = self.index_engine_.value

        # undiscounted payoff: notional * tau * (leverage * index rate + spread)
        settlement_amount = (
            self.sign_
            * self.notional_
            * self.tau_
            * (self.leverage_ * self.forward_rate_ + self.spread_)
        )

        # PV and cash
        if self.value_date_ > self.payment_date_:
            self.value_ = 0.0
            self.cash_ = 0.0
            self.df_ = 0.0
        elif self.value_date_ == self.payment_date_:
            self.value_ = settlement_amount
            self.cash_ = _to_float(settlement_amount)
            self.df_ = 1.0
        else:
            casted_yc: YieldCurve = self.model_
            self.df_ = casted_yc.discount_factor(
                self.funding_index_, self.payment_date_, calc_grad=True
            )
            self.value_ = settlement_amount * self.df_
            self.cash_ = 0.0

        self.settlement_amount_ = settlement_amount

    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        casted_product: ProductIBORIndexCashflow = self.product_
        this_cf.add_row(
            0,
            self.product_.product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.payment_date_,
            _to_float(self.settlement_amount_),
            _to_float(self.value_),
            _to_float(self.df_),
            fixing_date=casted_product.fixing_date,
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrued=self.tau_,
            index_or_fixed=self.ibor_index_.index_name(),
            index_value=_to_float(self.forward_rate_),
        )

        return this_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, self.cash_)
        return report

    def par_rate_or_spread(self) -> float:
        return _to_float(self.forward_rate_)

    def pv01(self) -> float:
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            (dv_df,) = torch.autograd.grad(self.value_, self.forward_rate_, retain_graph=True)
            return float(dv_df) * 1e-4
        return 0.0

    # def grad_at_par(self) -> np.ndarray:
    #     casted_yc: YieldCurve = self.model_
    #     if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
    #         self.forward_rate_.backward(retain_graph=True)
    #         return casted_yc.get_gradient(reset=True)
    #     return casted_yc.get_gradient(reset=False)


### Product IBOR Compounding Cashflow
class ValuationEngineProductIBORCompoundingCashflow(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductIBORCompoundingCashflow,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_date_ = product.payment_date
        self.spread_ = product.spread
        self.leverage_ = product.leverage
        self.tau_ = product.accrued
        self.notional_ = abs(product.notional)
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0

        self.ibor_index_: IBORIndex = product.index

        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        casted_yc: YieldCurve = self.model_

        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_: FundingIdentifier = self.funding_vp_.get_funding_index(self.currency_)

        self.anchored_index_: AnchoredCompoundIborIndex = AnchoredCompoundIborIndex(
            self.effective_date_,
            self.termination_date_,
            self.ibor_index_,
            product.compounding_method,
            business_day_convention=product.payment_business_day_convention,
            holiday_convention=product.payment_holiday_convention,
        )
        self.index_engine_: ValuationEngineAnalyticsCompoundIborIndex = (
            ValuationEngineAnalyticsCompoundIborIndex(casted_yc, self.anchored_index_, self.vpc_)
        )

        self.forward_rate_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):
        self.index_engine_.calculate_value()
        self.forward_rate_ = self.index_engine_.value
        settlement_amount = (
            self.sign_
            * self.notional_
            * self.tau_
            * (self.leverage_ * self.forward_rate_ + self.spread_)
        )

        # PV and cash
        if self.value_date_ > self.payment_date_:
            self.value_ = 0.0
            self.cash_ = 0.0
            self.df_ = 0.0
        elif self.value_date_ == self.payment_date_:
            self.value_ = settlement_amount
            self.cash_ = _to_float(settlement_amount)
            self.df_ = 1.0
        else:
            casted_yc: YieldCurve = self.model_
            self.df_ = casted_yc.discount_factor(
                self.funding_index_, self.payment_date_, calc_grad=True
            )
            self.value_ = settlement_amount * self.df_
            self.cash_ = 0.0

        self.settlement_amount_ = settlement_amount

    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        this_cf.add_row(
            0,
            self.product_.product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.payment_date_,
            _to_float(self.settlement_amount_),
            _to_float(self.value_),
            _to_float(self.df_),
            fixing_date=self.termination_date_,
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrued=self.tau_,
            index_or_fixed=self.ibor_index_.index_name(),
            index_value=_to_float(self.forward_rate_),
        )

        return this_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, self.cash_)
        return report

    def par_rate_or_spread(self) -> float:
        return _to_float(self.forward_rate_)

    def pv01(self) -> float:
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            (dv_df,) = torch.autograd.grad(self.value_, self.forward_rate_, retain_graph=True)
            return float(dv_df) * 1e-4
        return 0.0

    # def grad_at_par(self) -> np.ndarray:
    #     casted_yc: YieldCurve = self.model_
    #     if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
    #         self.forward_rate_.backward(retain_graph=True)
    #         return casted_yc.get_gradient(reset=True)
    #     return casted_yc.get_gradient(reset=False)


### Product Interest Rate Stream
class ValuationEngineProductInterestRateStream(ValuationEngineProductPortfolio):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductInterestRateStream,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.rate_or_spread_ = (
            product.fixed_rate if product.fixed_rate is not None else product.spread
        )
        self.annuity_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        super().calculate_value()

        self.value_ = self.aggregated_value_[self.currency_]
        self.cash_ = self.aggregated_cash_[self.currency_]

        annuity = 0.0
        for engine in self.engines_:
            annuity = annuity + engine.sign_ * engine.notional_ * engine.tau_ * engine.df_
        self.annuity_ = annuity

    def par_rate_or_spread(self) -> float:
        return self.rate_or_spread_ - _to_float(self.value_) / _to_float(self.annuity_)

    def pv01(self) -> float:
        return _to_float(self.annuity_) * 1e-4

    # def grad_at_par(self) -> np.ndarray:
    #     casted_yc: YieldCurve = self.model_
    #     has_graph = (isinstance(self.value_, torch.Tensor) and self.value_.requires_grad) or (
    #         isinstance(self.annuity_, torch.Tensor) and self.annuity_.requires_grad
    #     )
    #     if not has_graph:
    #         return casted_yc.get_gradient(reset=False)
    #     par = self.rate_or_spread_ - self.value_ / self.annuity_
    #     par.backward(retain_graph=True)
    #     return casted_yc.get_gradient(reset=True)


### Product Overnight Index Swap
class ValuationEngineProductOvernightIndexSwap(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductOvernightIndexSwap,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.fixed_rate_ = product.fixed_leg.fixed_rate

        # each leg is already an interest-rate-stream product with its own pay_or_rec
        # (opposite between the two legs, see ProductOvernightIndexSwap.__init__), so the
        # two leg engines' PVs are already signed consistently -- no extra leg-sign
        # multiplication is needed on top, unlike the archived numpy-risk swap engine.
        self.fixed_leg_engine_: ValuationEngineProductInterestRateStream = (
            ValuationEngineProductInterestRateStream(
                model, valuation_parameters_collection, product.fixed_leg, request
            )
        )
        self.floating_leg_engine_: ValuationEngineProductInterestRateStream = (
            ValuationEngineProductInterestRateStream(
                model, valuation_parameters_collection, product.floating_leg, request
            )
        )

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        self.fixed_leg_engine_.calculate_value()
        self.floating_leg_engine_.calculate_value()

        self.value_ = self.fixed_leg_engine_.value_ + self.floating_leg_engine_.value_
        self.cash_ = self.fixed_leg_engine_.cash_ + self.floating_leg_engine_.cash_

    # def get_risk(self, gradient=None) -> None:

    #     local_grad = np.zeros_like(self.model_.get_gradient(reset=False))

    #     fixed_grad = np.zeros_like(local_grad)
    #     self.fixed_leg_engine_.get_risk(gradient=fixed_grad)
    #     local_grad += fixed_grad

    #     float_grad = np.zeros_like(local_grad)
    #     self.floating_leg_engine_.get_risk(gradient=float_grad)
    #     local_grad += float_grad

    #     if gradient is None:
    #         return

    #     gradient[:] = local_grad

    def create_cash_flows_report(self) -> CashflowsReport:

        swap_cf = CashflowsReport()
        for leg_id, engine in enumerate((self.fixed_leg_engine_, self.floating_leg_engine_)):
            leg_cf = engine.create_cash_flows_report()
            for row in leg_cf.content:
                row_dict = dict(zip(leg_cf.schema, row))
                swap_cf.add_row(
                    leg_id,
                    row_dict[CFReportColumns.PRODUCT_TYPE.to_string()],
                    row_dict[CFReportColumns.VALUATION_ENGINE_TYPE.to_string()],
                    row_dict[CFReportColumns.NOTIONAL.to_string()],
                    row_dict[CFReportColumns.PAY_OR_RECEIVE.to_string()],
                    row_dict[CFReportColumns.PAY_DATE.to_string()],
                    row_dict[CFReportColumns.FORECASTED_AMOUNT.to_string()],
                    row_dict[CFReportColumns.PV.to_string()],
                    row_dict[CFReportColumns.DF.to_string()],
                    fixing_date=row_dict.get(CFReportColumns.FIXING_DATE.to_string()),
                    start_date=row_dict.get(CFReportColumns.START_DATE.to_string()),
                    end_date=row_dict.get(CFReportColumns.END_DATE.to_string()),
                    accrued=row_dict.get(CFReportColumns.ACCRUED.to_string()),
                    index_or_fixed=row_dict.get(CFReportColumns.INDEX_OR_FIXED.to_string()),
                    index_value=row_dict.get(CFReportColumns.INDEX_VALUE.to_string()),
                )

        return swap_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, _to_float(self.cash_))
        return report

    def par_rate_or_spread(self) -> float:
        # PV(fixed_rate) = floating_leg.value_ + fixed_rate * fixed_leg.annuity_ is affine in
        # the fixed rate (the floating leg carries no dependency on it), so the par fixed rate
        # that zeroes the swap's total PV is fixed_rate_ - value_ / fixed_leg.annuity_ -- same
        # identity ValuationEngineProductInterestRateStream.par_rate_or_spread uses for a
        # single leg, applied here against the swap's total (both-legs) value.
        return self.fixed_rate_ - _to_float(self.value_) / _to_float(
            self.fixed_leg_engine_.annuity_
        )

    def pv01(self) -> float:
        return _to_float(self.fixed_leg_engine_.annuity_) * 1e-4


### Product Overnight Index Basis Swap
class ValuationEngineProductOvernightIndexBasisSwap(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductOvernightIndexBasisSwap,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.spread_ = product.on_composite_index_leg.spread

        self.on_leg_engine_: ValuationEngineProductInterestRateStream = (
            ValuationEngineProductInterestRateStream(
                model, valuation_parameters_collection, product.on_composite_index_leg, request
            )
        )
        self.ibor_leg_engine_: ValuationEngineProductInterestRateStream = (
            ValuationEngineProductInterestRateStream(
                model, valuation_parameters_collection, product.ibor_index_leg, request
            )
        )

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        self.on_leg_engine_.calculate_value()
        self.ibor_leg_engine_.calculate_value()

        self.value_ = self.on_leg_engine_.value_ + self.ibor_leg_engine_.value_
        self.cash_ = self.on_leg_engine_.cash_ + self.ibor_leg_engine_.cash_

    # def get_risk(self, gradient=None) -> None:

    #     local_grad = np.zeros_like(self.model_.get_gradient(reset=False))

    #     on_leg_grad = np.zeros_like(local_grad)
    #     self.on_leg_engine_.get_risk(gradient=on_leg_grad)
    #     local_grad += on_leg_grad

    #     ibor_leg_grad = np.zeros_like(local_grad)
    #     self.ibor_leg_engine_.get_risk(gradient=ibor_leg_grad)
    #     local_grad += ibor_leg_grad

    #     if gradient is None:
    #         return

    #     gradient[:] = local_grad

    def create_cash_flows_report(self) -> CashflowsReport:

        swap_cf = CashflowsReport()
        for leg_id, engine in enumerate((self.on_leg_engine_, self.ibor_leg_engine_)):
            leg_cf = engine.create_cash_flows_report()
            for row in leg_cf.content:
                row_dict = dict(zip(leg_cf.schema, row))
                swap_cf.add_row(
                    leg_id,
                    row_dict[CFReportColumns.PRODUCT_TYPE.to_string()],
                    row_dict[CFReportColumns.VALUATION_ENGINE_TYPE.to_string()],
                    row_dict[CFReportColumns.NOTIONAL.to_string()],
                    row_dict[CFReportColumns.PAY_OR_RECEIVE.to_string()],
                    row_dict[CFReportColumns.PAY_DATE.to_string()],
                    row_dict[CFReportColumns.FORECASTED_AMOUNT.to_string()],
                    row_dict[CFReportColumns.PV.to_string()],
                    row_dict[CFReportColumns.DF.to_string()],
                    fixing_date=row_dict.get(CFReportColumns.FIXING_DATE.to_string()),
                    start_date=row_dict.get(CFReportColumns.START_DATE.to_string()),
                    end_date=row_dict.get(CFReportColumns.END_DATE.to_string()),
                    accrued=row_dict.get(CFReportColumns.ACCRUED.to_string()),
                    index_or_fixed=row_dict.get(CFReportColumns.INDEX_OR_FIXED.to_string()),
                    index_value=row_dict.get(CFReportColumns.INDEX_VALUE.to_string()),
                )

        return swap_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, _to_float(self.cash_))
        return report

    def par_rate_or_spread(self) -> float:
        return self.spread_ - _to_float(self.value_) / _to_float(self.on_leg_engine_.annuity_)

    def pv01(self) -> float:
        return _to_float(self.on_leg_engine_.annuity_) * 1e-4


### Product OIS Basis Swap
class ValuationEngineProductOISBasisSwap(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductOISBasisSwap,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.spread_ = product.basis_leg.spread

        self.basis_leg_engine_: ValuationEngineProductInterestRateStream = (
            ValuationEngineProductInterestRateStream(
                model, valuation_parameters_collection, product.basis_leg, request
            )
        )
        self.reference_leg_engine_: ValuationEngineProductInterestRateStream = (
            ValuationEngineProductInterestRateStream(
                model, valuation_parameters_collection, product.reference_leg, request
            )
        )

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        self.basis_leg_engine_.calculate_value()
        self.reference_leg_engine_.calculate_value()

        self.value_ = self.basis_leg_engine_.value_ + self.reference_leg_engine_.value_
        self.cash_ = self.basis_leg_engine_.cash_ + self.reference_leg_engine_.cash_

    # def get_risk(self, gradient=None) -> None:

    #     local_grad = np.zeros_like(self.model_.get_gradient(reset=False))

    #     basis_leg_grad = np.zeros_like(local_grad)
    #     self.basis_leg_engine_.get_risk(gradient=basis_leg_grad)
    #     local_grad += basis_leg_grad

    #     reference_leg_grad = np.zeros_like(local_grad)
    #     self.reference_leg_engine_.get_risk(gradient=reference_leg_grad)
    #     local_grad += reference_leg_grad

    #     if gradient is None:
    #         return

    #     gradient[:] = local_grad

    def create_cash_flows_report(self) -> CashflowsReport:

        swap_cf = CashflowsReport()
        for leg_id, engine in enumerate((self.basis_leg_engine_, self.reference_leg_engine_)):
            leg_cf = engine.create_cash_flows_report()
            for row in leg_cf.content:
                row_dict = dict(zip(leg_cf.schema, row))
                swap_cf.add_row(
                    leg_id,
                    row_dict[CFReportColumns.PRODUCT_TYPE.to_string()],
                    row_dict[CFReportColumns.VALUATION_ENGINE_TYPE.to_string()],
                    row_dict[CFReportColumns.NOTIONAL.to_string()],
                    row_dict[CFReportColumns.PAY_OR_RECEIVE.to_string()],
                    row_dict[CFReportColumns.PAY_DATE.to_string()],
                    row_dict[CFReportColumns.FORECASTED_AMOUNT.to_string()],
                    row_dict[CFReportColumns.PV.to_string()],
                    row_dict[CFReportColumns.DF.to_string()],
                    fixing_date=row_dict.get(CFReportColumns.FIXING_DATE.to_string()),
                    start_date=row_dict.get(CFReportColumns.START_DATE.to_string()),
                    end_date=row_dict.get(CFReportColumns.END_DATE.to_string()),
                    accrued=row_dict.get(CFReportColumns.ACCRUED.to_string()),
                    index_or_fixed=row_dict.get(CFReportColumns.INDEX_OR_FIXED.to_string()),
                    index_value=row_dict.get(CFReportColumns.INDEX_VALUE.to_string()),
                )

        return swap_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, _to_float(self.cash_))
        return report

    def par_rate_or_spread(self) -> float:
        # PV(spread) = reference_leg.value_ + spread * basis_leg_engine_.annuity_.
        return self.spread_ - _to_float(self.value_) / _to_float(self.basis_leg_engine_.annuity_)

    def pv01(self) -> float:
        return _to_float(self.basis_leg_engine_.annuity_) * 1e-4


### Product Overnight Index Future
class ValuationEngineProductOvernightIndexFuture(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductOvernightIndexFuture,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        # get info from product
        self.currency_ = product.currency
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_date_ = product.payment_date
        self.strike_ = product.strike
        self.notional_ = product.notional
        self.on_composite_index_: OvernightCompositeIndex = product.index
        self.on_index_: OvernightIndex = self.on_composite_index_.index

        self.vpc_: ValuationParametersCollection = valuation_parameters_collection

        self.cashflow_engine_: ValuationEngineProductOvernightIndexCompositeCashflow = (
            ValuationEngineProductOvernightIndexCompositeCashflow(
                model, self.vpc_, product, request
            )
        )

        self.forward_rate_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def _previous_business_day(self, as_of: Date) -> Date:
        return subtract_period(
            as_of, Period("1D"), ql.Preceding, self.on_index_.payment_holiday_conv
        )

    def calculate_value(self):

        # notional * (F - K), undiscounted -- a future is margined, not present-valued
        self.cashflow_engine_.calculate_value()
        self.forward_rate_ = self.cashflow_engine_.forward_rate_
        self.value_ = self.notional_ * (self.forward_rate_ - self.strike_)

        #  margined/MTM instrument, so cash is realized daily as the
        # variation margin -- notional * (today's market price - yesterday's)
        if self.value_date_ > self.payment_date_:
            self.cash_ = 0.0
            return

        if self.value_date_ == self.effective_date_:
            # nothing to mark against yet on trade date
            self.cash_ = 0.0
            return

        prev_date = self._previous_business_day(self.value_date_)
        prev_engine: ValuationEngineProductOvernightIndexCompositeCashflow = (
            ValuationEngineProductOvernightIndexCompositeCashflow(
                self.model_, self.vpc_, self.product_, self.request_
            )
        )
        prev_engine.index_engine_.value_date_ = prev_date
        prev_engine.calculate_value()
        prev_value = self.notional_ * (prev_engine.forward_rate_ - self.strike_)

        self.cash_ = _to_float(self.value_) - _to_float(prev_value)

    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        sign = 1.0 if self.notional_ >= 0 else -1.0
        this_cf.add_row(
            0,
            self.product_.product_type,
            self.val_engine_type(),
            abs(self.notional_),
            sign,
            self.payment_date_,
            _to_float(self.value_),
            _to_float(self.value_),
            1.0,
            fixing_date=self.termination_date_,
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            index_or_fixed=self.on_index_.index_name(),
            index_value=_to_float(self.forward_rate_),
        )

        return this_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, self.cash_)
        return report

    def par_rate_or_spread(self) -> float:
        return _to_float(self.forward_rate_)

    def pv01(self) -> float:
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            (dv_df,) = torch.autograd.grad(self.value_, self.forward_rate_, retain_graph=True)
            return float(dv_df) * 1e-4
        return self.notional_ * 1e-4

    # def grad_at_par(self) -> np.ndarray:
    #     casted_yc: YieldCurve = self.model_
    #     if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
    #         self.forward_rate_.backward(retain_graph=True)
    #         return casted_yc.get_gradient(reset=True)
    #     return casted_yc.get_gradient(reset=False)


### FRA / Fixing
class ValuationEngineProductFRAOrFixing(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductFRAOrFixing,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        # TODO: only ISDA discounting is supported for FRAs now
        assert product.fra_discounting_style.upper() == "ISDA"

        self.currency_ = product.currency
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_date_ = product.payment_date
        self.coupon_ = product.coupon
        self.tau_ = product.accrued
        self.notional_ = abs(product.notional)
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0
        self.index_: IBORIndex = product.index

        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_: FundingIdentifier = self.funding_vp_.get_funding_index(self.currency_)

        self.wrapped_engine_: ValuationEngineProductIBORIndexCashflow = (
            ValuationEngineProductIBORIndexCashflow(model, self.vpc_, product, request)
        )

        self.forward_rate_ = 0.0
        self.df_ = 0.0
        self.settlement_amount_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        self.wrapped_engine_.calculate_value()
        self.forward_rate_ = self.wrapped_engine_.forward_rate_

        # undiscounted payoff: notional * tau * (F - K)
        settlement_amount = (
            self.sign_ * self.notional_ * self.tau_ * (self.forward_rate_ - self.coupon_)
        )

        if self.value_date_ > self.payment_date_:
            self.value_ = 0.0
            self.cash_ = 0.0
            self.df_ = 0.0
        elif self.value_date_ == self.payment_date_:
            self.value_ = settlement_amount
            self.cash_ = _to_float(settlement_amount)
            self.df_ = 1.0
        else:
            casted_yc: YieldCurve = self.model_
            self.df_ = casted_yc.discount_factor(
                self.funding_index_, self.payment_date_, calc_grad=True
            )
            # PV = P(t,T) * N * (F - K) * tau / (1 + F*tau) for a true (early-settling) FRA

            early_settlement_df = 1.0 / (1.0 + self.forward_rate_ * self.tau_)
            self.value_ = settlement_amount * self.df_ * early_settlement_df

            self.cash_ = 0.0

        self.settlement_amount_ = settlement_amount

    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        casted_product: ProductFRAOrFixing = self.product_
        this_cf.add_row(
            0,
            self.product_.product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.payment_date_,
            _to_float(self.settlement_amount_),
            _to_float(self.value_),
            _to_float(self.df_),
            fixing_date=casted_product.fixing_date,
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrued=self.tau_,
            index_or_fixed=self.index_.index_name(),
            index_value=_to_float(self.forward_rate_),
        )

        return this_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, self.cash_)
        return report

    def par_rate_or_spread(self) -> float:
        return _to_float(self.forward_rate_)

    def pv01(self) -> float:
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            (dv_df,) = torch.autograd.grad(self.value_, self.forward_rate_, retain_graph=True)
            return float(dv_df) * 1e-4
        return 0.0


### Cash Deposit
class ValuationEngineProductCashDeposit(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductCashDeposit,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        # a pure fixed cashflow -- no index, no anchored-index engine, only curve dependency
        # is the funding/discount curve itself.
        self.currency_ = product.currency
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_date_ = product.payment_date
        self.coupon_ = product.fixed_rate
        self.tau_ = product.accrued
        self.notional_ = abs(product.notional)
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0

        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_: FundingIdentifier = self.funding_vp_.get_funding_index(self.currency_)

        self.df_ = 0.0
        self.df_effective_ = 0.0
        self.settlement_amount_ = 0.0
        self.principal_amount_ = 0.0
        self.maturity_value_ = 0.0
        self.principal_value_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        casted_yc: YieldCurve = self.model_

        # maturity leg: principal + accrued interest, paid on payment_date_ --
        # PV_maturity = sign * notional * (1 + coupon*tau) * DF(payment_date)
        settlement_amount = self.sign_ * self.notional_ * (1.0 + self.tau_ * self.coupon_)
        if self.value_date_ > self.payment_date_:
            maturity_value = 0.0
            maturity_cash = 0.0
            self.df_ = 0.0
        elif self.value_date_ == self.payment_date_:
            maturity_value = settlement_amount
            maturity_cash = _to_float(settlement_amount)
            self.df_ = 1.0
        else:
            self.df_ = casted_yc.discount_factor(
                self.funding_index_, self.payment_date_, calc_grad=True
            )
            maturity_value = settlement_amount * self.df_
            maturity_cash = 0.0

        # funding leg: principal exchanged in the opposite direction on effective_date_ --
        # only still live (part of a forward PV) while the deposit hasn't started yet
        # (value_date_ < effective_date_); once it has started, that exchange is sunk and
        # drops out of a forward PV. df_effective_ is still computed unconditionally
        # (always calc_grad=True, per the shared-state discount_factor footgun) since
        # par_rate_or_spread/pv01 read it regardless of whether the leg is currently live.
        principal_amount = -self.sign_ * self.notional_
        principal_value = 0.0
        principal_cash = 0.0
        self.df_effective_ = casted_yc.discount_factor(
            self.funding_index_, self.effective_date_, calc_grad=True
        )
        if self.value_date_ < self.effective_date_:
            principal_value = principal_amount * self.df_effective_
        elif self.value_date_ == self.effective_date_:
            principal_value = principal_amount
            principal_cash = _to_float(principal_amount)

        self.value_ = maturity_value + principal_value
        self.cash_ = maturity_cash + principal_cash
        self.settlement_amount_ = settlement_amount
        self.principal_amount_ = principal_amount
        self.maturity_value_ = maturity_value
        self.principal_value_ = principal_value

    def create_cash_flows_report(self) -> CashflowsReport:
        cf = CashflowsReport()
        cf.add_row(
            0,
            self.product_.product_type,
            self.val_engine_type(),
            self.notional_,
            -self.sign_,
            self.effective_date_,
            _to_float(self.principal_amount_),
            _to_float(self.principal_value_),
            _to_float(self.df_effective_),
            start_date=self.effective_date_,
            end_date=self.effective_date_,
            index_or_fixed="FIXED",
            index_value=self.coupon_,
        )
        cf.add_row(
            1,
            self.product_.product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.payment_date_,
            _to_float(self.settlement_amount_),
            _to_float(self.maturity_value_),
            _to_float(self.df_),
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrued=self.tau_,
            index_or_fixed="FIXED",
            index_value=self.coupon_,
        )

        return cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, self.cash_)
        return report

    def par_rate_or_spread(self) -> float:
        # curve-implied simple rate that zeros the two-leg PV:
        # (1 + coupon*tau) * DF(payment) = DF(effective)  =>  coupon = (DF(effective)/DF(payment) - 1) / tau
        return (_to_float(self.df_effective_) / _to_float(self.df_) - 1.0) / self.tau_

    def pv01(self) -> float:
        # coupon_ is a plain float, never wrapped in a tensor here -- no graph node to
        # differentiate through, so this is a closed form rather than an autograd call.
        return self.sign_ * self.notional_ * self.tau_ * _to_float(self.df_) * 1e-4


### Zero Spread
class ValuationEngineProductZeroSpread(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductIBORZeroSpread,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.termination_date_ = product.termination_date
        self.notional_ = product.notional
        self.spread_ = product.spread
        self.basis_index_: Index = product.basis_index
        self.reference_index_: Index = product.reference_index
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0
        self.time_to_expiry_ = accrued(self.value_date_, self.termination_date_)

        self.df_basis_ = 0.0
        self.df_reference_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        if self.value_date_ > self.termination_date_:
            raise Exception("ProductIBORZeroSpread has to be outright.")

        casted_yc: YieldCurve = self.model_
        self.df_reference_ = casted_yc.discount_factor(
            self.reference_index_, self.termination_date_, calc_grad=True
        )
        self.df_basis_ = casted_yc.discount_factor(
            self.basis_index_, self.termination_date_, calc_grad=True
        )

        self.value_ = self.sign_ * self.notional_ * (
            self.df_reference_ / self.df_basis_
            - np.exp(-self.spread_ * self.time_to_expiry_)
        )
        self.cash_ = 0.0

    def create_cash_flows_report(self) -> CashflowsReport:
        raise Exception("ProductIBORZeroSpread does not support cashflow report")

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, self.cash_)
        return report

    def par_rate_or_spread(self) -> float:
        df_ratio = _to_float(self.df_reference_) / _to_float(self.df_basis_)
        return -1.0 / self.time_to_expiry_ * np.log(df_ratio)

    def pv01(self) -> float:
        return (
            self.sign_
            * self.notional_
            * self.time_to_expiry_
            * np.exp(-self.spread_ * self.time_to_expiry_)
            * 1e-4
        )


## ARITIFICIAL PRODUCT

### Product Generic Forward
class ValuationEngineProductGenericForward(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductGenericForward,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_date_ = product.pay_date
        self.coupon_ = product.coupon
        self.notional_ = abs(product.notional)
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0
        self.index_: Index = product.index
        self.compounding_method_ = product.compounding_method

        self.tau_ = accrued(
            self.effective_date_,
            self.termination_date_,
            product.accrual_basis,
            product.business_day_convention,
            product.holiday_convention,
        )

        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_: FundingIdentifier = self.funding_vp_.get_funding_index(self.currency_)

        self.forward_rate_ = 0.0
        self.df_ = 0.0
        self.settlement_amount_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        casted_yc: YieldCurve = self.model_

        df_effective = casted_yc.discount_factor(self.index_, self.effective_date_, calc_grad=True)
        df_termination = casted_yc.discount_factor(
            self.index_, self.termination_date_, calc_grad=True
        )
        growth = df_effective / df_termination

        if self.compounding_method_ == CompoundingMethod.CONTINUOUS:
            self.forward_rate_ = torch.log(growth) / self.tau_
        else:
            self.forward_rate_ = (growth - 1.0) / self.tau_

        # undiscounted payoff: notional * tau * (F - K)
        settlement_amount = (
            self.sign_ * self.notional_ * self.tau_ * (self.forward_rate_ - self.coupon_)
        )

        if self.value_date_ > self.payment_date_:
            self.value_ = 0.0
            self.cash_ = 0.0
            self.df_ = 0.0
        elif self.value_date_ == self.payment_date_:
            self.value_ = settlement_amount
            self.cash_ = _to_float(settlement_amount)
            self.df_ = 1.0
        else:
            self.df_ = casted_yc.discount_factor(
                self.funding_index_, self.payment_date_, calc_grad=True
            )
            self.value_ = settlement_amount * self.df_
            self.cash_ = 0.0

        self.settlement_amount_ = settlement_amount

    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        this_cf.add_row(
            0,
            self.product_.product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.payment_date_,
            _to_float(self.settlement_amount_),
            _to_float(self.value_),
            _to_float(self.df_),
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrued=self.tau_,
            index_or_fixed=self.index_.index_name(),
            index_value=_to_float(self.forward_rate_),
        )

        return this_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, self.cash_)
        return report

    def par_rate_or_spread(self) -> float:
        return _to_float(self.forward_rate_)

    def pv01(self) -> float:
        return self.sign_ * self.notional_ * self.tau_ * _to_float(self.df_) * 1e-4


### Product Generic Spread
class ValuationEngineProductGenericSpread(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductGenericSpread,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.notional_ = product.notional
        self.spread_ = product.spread
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0

        axis1 = f"{product.effective_date.ISO()} x {product.termination_date.ISO()}"

        target_product: Product = ProductFactory.create_product_from_data_convention(
            model.value_date, axis1, product.basis_data_convention, 0.0
        )
        reference_product: Product = ProductFactory.create_product_from_data_convention(
            model.value_date, axis1, product.reference_data_convention, -product.spread
        )

        self.target_engine_: (
            ValuationEngineProduct
        ) = ValuationEngineProductRegistry().new_valuation_engine(
            model, target_product, valuation_parameters_collection, request
        )
        self.reference_engine_: (
            ValuationEngineProduct
        ) = ValuationEngineProductRegistry().new_valuation_engine(
            model, reference_product, valuation_parameters_collection, request
        )

        self.reference_notional_ = reference_product.notional
        self.reference_currency_ = reference_product.currency
        self.scale_ = self.notional_ / self.reference_notional_

        # ratio_ (computed in calculate_value as reference_pv01/target_pv01) combines T's and
        # R's PV01s directly with no FX adjustment between them, then gets scaled by the single
        # fx_ = fx(reference_ccy -> product.currency) below -- that's only a valid currency
        # conversion for the whole (scale_*fx_*ratio_) coefficient applied to target_value_raw
        # if T and R are denominated in the same currency to begin with. Assert it rather than
        # silently mispricing a genuine cross-currency spread.
        self.target_currency_ = target_product.currency
        assert self.target_currency_.code() == self.reference_currency_.code(), (
            f"ValuationEngineProductGenericSpread requires basis/reference to share a currency "
            f"(got {self.target_currency_.code()} vs {self.reference_currency_.code()}) -- ratio_ "
            f"combines their PV01s with no FX adjustment between them."
        )

        self.fx_ = 1.0
        self.ratio_ = 0.0
        self.spread_pv01_unit_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def _fx_rate(self, from_currency: Currency, to_currency: Currency) -> float:
        if from_currency.code() == to_currency.code():
            return 1.0
        casted_yc: YieldCurve = self.model_
        try:
            fx_index = IndexRegistry().get(f"{from_currency.code()}-{to_currency.code()}")
            return _to_float(casted_yc.fx_rate(fx_index))
        except Exception:
            fx_index = IndexRegistry().get(f"{to_currency.code()}-{from_currency.code()}")
            return 1.0 / _to_float(casted_yc.fx_rate(fx_index))

    def calculate_value(self):

        self.target_engine_.calculate_value()
        self.reference_engine_.calculate_value()

        reference_value_raw = _to_float(self.reference_engine_.value)
        target_value_raw = _to_float(self.target_engine_.value)
        reference_pv01_raw = _to_float(self.reference_engine_.pv01())
        target_pv01_raw = _to_float(self.target_engine_.pv01())

        self.fx_ = self._fx_rate(self.reference_currency_, self.currency_)
        self.ratio_ = reference_pv01_raw / target_pv01_raw

        self.value_ = (
            self.sign_
            * self.scale_
            * self.fx_
            * (reference_value_raw - self.ratio_ * target_value_raw)
        )
        self.cash_ = (
            self.sign_
            * self.scale_
            * self.fx_
            * (
                _to_float(self.reference_engine_.cash)
                - self.ratio_ * _to_float(self.target_engine_.cash)
            )
        )

        self.spread_pv01_unit_ = -self.sign_ * self.scale_ * self.fx_ * reference_pv01_raw / 1e-4

    # def create_cash_flows_report(self) -> CashflowsReport:

    #     cf = CashflowsReport()
    #     reference_contribution = (
    #         self.sign_ * self.scale_ * self.fx_ * _to_float(self.reference_engine_.value)
    #     )
    #     target_contribution = _to_float(self.value_) - reference_contribution
    #     cf.add_row(
    #         0,
    #         self.target_engine_.product_.product_type,
    #         self.target_engine_.val_engine_type(),
    #         self.notional_,
    #         self.sign_,
    #         self.product_.termination_date,
    #         target_contribution,
    #         target_contribution,
    #         1.0,
    #         start_date=self.product_.effective_date,
    #         end_date=self.product_.termination_date,
    #         index_or_fixed=self.product_.basis_data_convention.name,
    #         index_value=0.0,
    #     )
    #     cf.add_row(
    #         1,
    #         self.reference_engine_.product_.product_type,
    #         self.reference_engine_.val_engine_type(),
    #         self.notional_,
    #         -self.sign_,
    #         self.product_.termination_date,
    #         reference_contribution,
    #         reference_contribution,
    #         1.0,
    #         start_date=self.product_.effective_date,
    #         end_date=self.product_.termination_date,
    #         index_or_fixed=self.product_.reference_data_convention.name,
    #         index_value=-self.spread_,
    #     )
    #     return cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, _to_float(self.value_))
        report.set_cash(self.currency_, _to_float(self.cash_))
        return report

    def par_rate_or_spread(self) -> float:
        return self.spread_ - _to_float(self.value_) / _to_float(self.spread_pv01_unit_)

    def pv01(self) -> float:
        # -PV01_r * Fx
        return _to_float(self.spread_pv01_unit_) * 1e-4


### Product Generic Forward Spread
class ValuationEngineProductGenericForwardSpread(ValuationEngineProductGenericSpread):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductGenericForwardSpread,
        request: ValuationRequest,
    ):
        ValuationEngineProduct.__init__(self, model, valuation_parameters_collection, product, request)

        self.currency_ = product.currency
        self.notional_ = product.notional
        self.spread_ = product.spread
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0

        reference_accrual_basis = (
            product.reference_leg_accrual_basis
            if product.reference_leg_accrual_basis is not None
            else product.accrual_basis
        )

        common_kwargs = dict(
            effective_date=product.effective_date,
            term_or_termination_date=TermOrDate(product.termination_date),
            pay_or_rec=PayOrReceive.RECEIVE,
            notional=product.notional,
            settlement_offset=product.settlement_offset,
            business_day_convention=product.settlement_business_day_convention,
            holiday_convention=product.settlement_holiday_convention,
            pay_date_or_offset=product.pay_date_or_offset,
            payment_business_day_conv=product.payment_business_day_convention,
            payment_holiday_conv=product.payment_holiday_day_convention,
            end_of_month=product.end_of_month,
            compounding_method=product.compounding_method,
        )

        target_product: Product = ProductGenericForward(
            coupon=0.0,
            index=product.basis_index,
            currency=product.basis_index.currency,
            accrual_basis=product.accrual_basis,
            **common_kwargs,
        )
        reference_product: Product = ProductGenericForward(
            coupon=-product.spread,
            index=product.reference_index,
            currency=product.reference_index.currency,
            accrual_basis=reference_accrual_basis,
            **common_kwargs,
        )

        self.target_engine_: (
            ValuationEngineProduct
        ) = ValuationEngineProductRegistry().new_valuation_engine(
            model, target_product, valuation_parameters_collection, request
        )
        self.reference_engine_: (
            ValuationEngineProduct
        ) = ValuationEngineProductRegistry().new_valuation_engine(
            model, reference_product, valuation_parameters_collection, request
        )

        self.reference_notional_ = reference_product.notional
        self.reference_currency_ = reference_product.currency
        self.scale_ = self.notional_ / self.reference_notional_

        self.target_currency_ = target_product.currency
        assert self.target_currency_.code() == self.reference_currency_.code(), (
            f"ValuationEngineProductGenericForwardSpread requires basis_index/reference_index to "
            f"share a currency (got {self.target_currency_.code()} vs "
            f"{self.reference_currency_.code()}) -- ratio_ combines their PV01s with no FX "
            f"adjustment between them."
        )

        self.fx_ = 1.0
        self.ratio_ = 0.0
        self.spread_pv01_unit_ = 0.0

    def calculate_value(self):
        super().calculate_value()
        # ValuationEngineProductGenericSpread.calculate_value()'s spread_pv01_unit_ assumes the
        # reference leg's own pv01() is d(PV)/d(the coupon it was built with) -- true for a
        # swap/cashflow-style leg (coupon sits on the receive side, so par_rate_or_spread solves
        # for that same coupon and pv01() = +d(PV)/d(coupon)). A ProductGenericForward leg (what
        # this subclass always builds) has the opposite relationship: PV = notional*tau*df*(F-K),
        # so pv01() = +d(PV)/d(F) = -d(PV)/d(K), and since K = -spread here, d(PV)/d(spread) =
        # +pv01() with NO extra sign flip -- the base class's leading minus sign is wrong for this
        # leg type. Flip it back here rather than in the base class, since the base class's own
        # (swap-based) formula is independently verified correct for its own use case.
        self.spread_pv01_unit_ = -self.spread_pv01_unit_

    def create_cash_flows_report(self) -> CashflowsReport:
        cf = CashflowsReport()
        reference_contribution = (
            self.sign_ * self.scale_ * self.fx_ * _to_float(self.reference_engine_.value)
        )
        target_contribution = _to_float(self.value_) - reference_contribution
        cf.add_row(
            0,
            self.target_engine_.product_.product_type,
            self.target_engine_.val_engine_type(),
            self.notional_,
            self.sign_,
            self.product_.pay_date,
            target_contribution,
            target_contribution,
            1.0,
            start_date=self.product_.effective_date,
            end_date=self.product_.termination_date,
            index_or_fixed=self.product_.basis_index.index_name(),
            index_value=0.0,
        )
        cf.add_row(
            1,
            self.reference_engine_.product_.product_type,
            self.reference_engine_.val_engine_type(),
            self.notional_,
            -self.sign_,
            self.product_.pay_date,
            reference_contribution,
            reference_contribution,
            1.0,
            start_date=self.product_.effective_date,
            end_date=self.product_.termination_date,
            index_or_fixed=self.product_.reference_index.index_name(),
            index_value=-self.spread_,
        )
        return cf


### Registry
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductOvernightIndexCompositeCashflow._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductOvernightIndexCompositeCashflow,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductOvernightIndexFuture._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductOvernightIndexFuture,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductFRAOrFixing._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductFRAOrFixing,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductCashDeposit._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductCashDeposit,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductFixedAccrued._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductFixedAccrued,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductIBORIndexCashflow._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductIBORIndexCashflow,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductIBORCompoundingCashflow._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductIBORCompoundingCashflow,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductInterestRateStream._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductInterestRateStream,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductOvernightIndexSwap._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductOvernightIndexSwap,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductOvernightIndexBasisSwap._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductOvernightIndexBasisSwap,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductOISBasisSwap._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductOISBasisSwap,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductGenericSpread._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductGenericSpread,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductGenericForward._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductGenericForward,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductGenericForwardSpread._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductGenericForwardSpread,
)
ValuationEngineProductRegistry().register(
    (
        YieldCurve._model_type.to_string(),
        ProductIBORZeroSpread._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductZeroSpread,
)

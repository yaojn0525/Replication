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

    def grad_at_par(self) -> np.ndarray:
        casted_yc: YieldCurve = self.model_
        return casted_yc.get_gradient(reset=False)


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

    def grad_at_par(self) -> np.ndarray:
        casted_yc: YieldCurve = self.model_
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            self.forward_rate_.backward(retain_graph=True)
            return casted_yc.get_gradient(reset=True)
        return casted_yc.get_gradient(reset=False)


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

    def grad_at_par(self) -> np.ndarray:
        casted_yc: YieldCurve = self.model_
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            self.forward_rate_.backward(retain_graph=True)
            return casted_yc.get_gradient(reset=True)
        return casted_yc.get_gradient(reset=False)


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

    def grad_at_par(self) -> np.ndarray:
        casted_yc: YieldCurve = self.model_
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            self.forward_rate_.backward(retain_graph=True)
            return casted_yc.get_gradient(reset=True)
        return casted_yc.get_gradient(reset=False)


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

    def grad_at_par(self) -> np.ndarray:
        casted_yc: YieldCurve = self.model_
        has_graph = (isinstance(self.value_, torch.Tensor) and self.value_.requires_grad) or (
            isinstance(self.annuity_, torch.Tensor) and self.annuity_.requires_grad
        )
        if not has_graph:
            return casted_yc.get_gradient(reset=False)
        par = self.rate_or_spread_ - self.value_ / self.annuity_
        par.backward(retain_graph=True)
        return casted_yc.get_gradient(reset=True)


# TODO: change
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
        casted_yc: YieldCurve = self.model_

        self.anchored_index_: AnchoredOvernightIndex = AnchoredOvernightIndex(
            self.effective_date_,
            self.termination_date_,
            self.on_index_,
            self.on_composite_index_.compounding_method,
            rate_cutoff=product.rate_cutoff,
            look_back_window=product.look_back_window,
            business_day_convention=product.payment_business_day_convention,
            holiday_convention=product.payment_holiday_convention,
        )
        self.index_engine_: ValuationEngineAnalyticsCompositeIndex = (
            ValuationEngineAnalyticsCompositeIndex(casted_yc, self.anchored_index_, self.vpc_)
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

        # PV: notional * (F - K)
        self.index_engine_.calculate_value()
        self.forward_rate_ = self.index_engine_.value
        self.value_ = self.notional_ * (self.forward_rate_ - self.strike_)

        # cash: this is a margined/MTM instrument, so cash is realized daily as the
        # variation margin -- notional * (today's market price - yesterday's) -- up to and
        # including the settlement (payment) date; once settled there is nothing left to mark.
        if self.value_date_ > self.payment_date_:
            self.cash_ = 0.0
            return

        if self.value_date_ == self.effective_date_:
            # nothing to mark against yet on trade date
            self.cash_ = 0.0
            return

        prev_date = self._previous_business_day(self.value_date_)
        casted_yc: YieldCurve = self.model_
        prev_engine: ValuationEngineAnalyticsCompositeIndex = (
            ValuationEngineAnalyticsCompositeIndex(casted_yc, self.anchored_index_, self.vpc_)
        )
        prev_engine.value_date_ = prev_date
        prev_engine.calculate_value()
        prev_value = self.notional_ * (prev_engine.value - self.strike_)

        self.cash_ = _to_float(self.value_) - _to_float(prev_value)

    # def get_risk(self, gradient=None) -> None:

    #     if isinstance(self.value_, torch.Tensor) and self.value_.requires_grad:
    #         self.value_.backward(retain_graph=True)

    #     casted_yc: YieldCurve = self.model_
    #     local_grad = casted_yc.get_gradient(reset=True)

    #     if gradient is None:
    #         return

    #     gradient[:] = local_grad

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

    ### gradient of the par rate (forward_rate_) wrt the curve's state data -- used for
    ### calibration jacobians when this future is used as a calibration instrument.
    def grad_at_par(self) -> np.ndarray:
        casted_yc: YieldCurve = self.model_
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            self.forward_rate_.backward(retain_graph=True)
            return casted_yc.get_gradient(reset=True)
        return casted_yc.get_gradient(reset=False)


### FRA
class ValuationEngineProductFRAOrFixing(ValuationEngineProduct):

    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductFRAOrFixing,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        # get info from product
        self.currency_ = product.currency
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_date_ = product.payment_date
        self.coupon_ = product.coupon
        self.tau_ = product.accrued
        self.notional_ = abs(product.notional)
        self.sign_ = 1.0 if product.pay_or_rec == PayOrReceive.RECEIVE else -1.0
        self.discounting_style_ = product.fra_discounting_style.upper()
        self.is_on_ = product.is_on
        self.index_: IBORIndex | OvernightIndex = product.index

        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        casted_yc: YieldCurve = self.model_

        # discounted (unlike the future, an FRA/fixing settles once, off the funding curve)
        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_: FundingIdentifier = self.funding_vp_.get_funding_index(self.currency_)

        self.anchored_index_: AnchoredOvernightIndex | AnchoredIborIndex
        self.index_engine_: (
            ValuationEngineAnalyticsCompositeIndex | ValuationEngineAnalyticsIborIndex
        )
        if self.is_on_:
            casted_overnight_index: OvernightIndex = self.index_
            self.anchored_index_ = AnchoredOvernightIndex(
                self.effective_date_,
                self.termination_date_,
                casted_overnight_index,
                CompoundingMethod.COMPOUND,
                business_day_convention=product.payment_business_day_convention,
                holiday_convention=product.payment_holiday_convention,
            )
            self.index_engine_ = ValuationEngineAnalyticsCompositeIndex(
                casted_yc, self.anchored_index_, self.vpc_
            )
        else:
            casted_ibor_index: IBORIndex = self.index_
            self.anchored_index_ = AnchoredIborIndex(
                self.effective_date_,
                self.termination_date_,
                casted_ibor_index,
                CompoundingMethod.SIMPLE,
                business_day_convention=product.payment_business_day_convention,
                holiday_convention=product.payment_holiday_convention,
            )
            self.index_engine_ = ValuationEngineAnalyticsIborIndex(
                casted_yc, self.anchored_index_, self.vpc_
            )

        self.forward_rate_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        self.index_engine_.calculate_value()
        self.forward_rate_ = self.index_engine_.value

        # undiscounted payoff at the natural period end: notional * tau * (F - K)
        raw_payoff = self.notional_ * self.tau_ * (self.forward_rate_ - self.coupon_)

        # a *FRA* settles early (payment_date_ < termination_date_) and so discounts the
        # payoff back from termination_date_ to payment_date_ using the FRA-style factor
        # 1 / (1 + d*tau) -- d is the floating rate itself under ISDA, the fixed coupon
        # under AFMA. Used purely as a "PRODUCT_FRA_OR_FIXING" (payment_date_ ==
        # termination_date_, e.g. from the default 0D pay offset), there's nothing to
        # adjust for -- it behaves like a plain fixing/coupon cashflow.
        if self.payment_date_ < self.termination_date_:
            rate_for_discounting = (
                self.forward_rate_ if self.discounting_style_ == "ISDA" else self.coupon_
            )
            settlement_amount = raw_payoff / (1.0 + rate_for_discounting * self.tau_)
        else:
            settlement_amount = raw_payoff

        settlement_amount = self.sign_ * settlement_amount

        # cash and PV: nothing paid or owed once settled; a plain bullet cashflow otherwise --
        # value is the settlement amount discounted from payment_date_ to value_date_, cash is
        # the realized amount exactly on payment_date_ (no daily MTM, unlike the future).
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

    # def get_risk(self, gradient=None) -> None:

    #     if isinstance(self.value_, torch.Tensor) and self.value_.requires_grad:
    #         self.value_.backward(retain_graph=True)

    #     casted_yc: YieldCurve = self.model_
    #     local_grad = casted_yc.get_gradient(reset=True)

    #     if gradient is None:
    #         return

    #     gradient[:] = local_grad

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

    ### gradient of the par rate (forward_rate_) wrt the curve's state data -- used for
    ### calibration jacobians when this FRA is used as a calibration instrument.
    def grad_at_par(self) -> np.ndarray:
        casted_yc: YieldCurve = self.model_
        if isinstance(self.forward_rate_, torch.Tensor) and self.forward_rate_.requires_grad:
            self.forward_rate_.backward(retain_graph=True)
            return casted_yc.get_gradient(reset=True)
        return casted_yc.get_gradient(reset=False)


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

        # get info from product -- a cash deposit has no index at all (pure fixed cashflow),
        # so unlike the future/FRA there's no anchored-index engine here: its only curve
        # dependency is the funding/discount curve itself.
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

        self.df_effective_ = 0.0
        self.df_payment_ = 0.0
        self.par_rate_ = 0.0

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        casted_yc: YieldCurve = self.model_

        # redemption leg: principal + interest, due at payment_date_
        redemption_amount = self.notional_ * (1.0 + self.coupon_ * self.tau_)
        if self.value_date_ > self.payment_date_:
            redemption_pv, redemption_cash, self.df_payment_ = 0.0, 0.0, 0.0
        elif self.value_date_ == self.payment_date_:
            redemption_pv, redemption_cash, self.df_payment_ = (
                redemption_amount,
                redemption_amount,
                1.0,
            )
        else:
            self.df_payment_ = casted_yc.discount_factor(
                self.funding_index_, self.payment_date_, calc_grad=True
            )
            redemption_pv, redemption_cash = redemption_amount * self.df_payment_, 0.0

        if self.value_date_ < self.effective_date_:
            self.df_effective_ = casted_yc.discount_factor(
                self.funding_index_, self.effective_date_, calc_grad=True
            )
            funding_pv, funding_cash = self.notional_ * self.df_effective_, 0.0
        elif self.value_date_ == self.effective_date_:
            funding_pv, funding_cash, self.df_effective_ = self.notional_, self.notional_, 1.0
        else:
            funding_pv, funding_cash, self.df_effective_ = 0.0, 0.0, 0.0

        self.value_ = self.sign_ * (redemption_pv - funding_pv)
        self.cash_ = self.sign_ * (_to_float(redemption_cash) - _to_float(funding_cash))

        if self.value_date_ > self.payment_date_:
            self.par_rate_ = self.coupon_
        else:
            self.par_rate_ = (self.df_effective_ / self.df_payment_ - 1.0) / self.tau_

    # def get_risk(self, gradient=None) -> None:

    #     if isinstance(self.value_, torch.Tensor) and self.value_.requires_grad:
    #         self.value_.backward(retain_graph=True)

    #     casted_yc: YieldCurve = self.model_
    #     local_grad = casted_yc.get_gradient(reset=True)

    #     if gradient is None:
    #         return

    #     gradient[:] = local_grad

    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        this_cf.add_row(
            0,
            self.product_.product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.payment_date_,
            self.notional_ * (1.0 + self.coupon_ * self.tau_),
            _to_float(self.value_),
            _to_float(self.df_payment_),
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
        return _to_float(self.par_rate_)

    def pv01(self) -> float:
        return self.sign_ * self.notional_ * self.tau_ * _to_float(self.df_payment_) * 1e-4

    def grad_at_par(self) -> np.ndarray:
        casted_yc: YieldCurve = self.model_
        if isinstance(self.par_rate_, torch.Tensor) and self.par_rate_.requires_grad:
            self.par_rate_.backward(retain_graph=True)
            return casted_yc.get_gradient(reset=True)
        return casted_yc.get_gradient(reset=False)


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
# ValuationEngineProductRegistry().register(
#     (
#         YieldCurve._model_type.to_string(),
#         ProductOvernightIndexSwap._product_type,
#         AnalyticValParam._vp_type,
#     ),
#     ValuationEngineProductOvernightIndexSwap,
# )

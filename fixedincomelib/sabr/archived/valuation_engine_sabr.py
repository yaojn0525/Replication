from typing import Any, Dict
from fixedincomelib.analytics.archived.european_options import CallOrPut, SimpleMetrics
from fixedincomelib.analytics.archived.sabr import SabrMetrics
from fixedincomelib.date import *
from fixedincomelib.sabr.archived import sabr_parameters
from fixedincomelib.sabr.archived.utilities import SABRPriceAndRiskCalculator
from fixedincomelib.valuation.archived import *
from fixedincomelib.sabr.archived.sabr_model import *
from fixedincomelib.yield_curve import *
from fixedincomelib.product import *
from fixedincomelib.sabr.archived.sabr_model import SABRModel
from fixedincomelib.yield_curve.archived.valuation_engine import ValuationEngineProductRfrSwap
# from fixedincomelib.date.utilities import accrued
# import warnings


class ValuationEngineRFRCapletFloorlet(ValuationEngineProduct):

    def __init__(
        self,
        model: SABRModel,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductRFRCapletFloorlet,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)
        
        # get info from product
        self.currency_ = product.currency
        self.expiry_date_ = product.expiry_date_ # need this
        self.effective_date_ = product.effective_date_
        self.termination_date_ = product.termination_date # term or termination date
        self.pay_date_ = product.payment_date # paydate
        self.sign_ = 1.0 if product.long_or_short == LongOrShort.LONG else -1.0
        self.notional_ = product.notional
        self.strike_ = product.strike
        self.overnight_index_ = product.on_index_
        self.cap_or_floor_ = product.cap_or_floor_
        self.accrual_ = product.accrual_
        self.call_or_put_ = (CallOrPut.CALL if self.cap_or_floor_ == CapOrFloor.CAP else CallOrPut.PUT)

        # | ------------ |  --  | ------------| --- |
        # 0              T_e  T_s           T_m   T_p
        # resolve valuation parameters (csa discounting)
        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_ = self.funding_vp_.get_funding_index(self.currency_)

        # initialise fwd rate engine        
        tortd = TermOrDate(self.termination_date_.ISO())
        self.index_engine_ = ValuationEngineAnalyticsCompositeIndex(
            self.model_,
            self.vpc_,
            self.overnight_index_,
            self.effective_date_,
            tortd,
            CompoundingMethod.COMPOUND,
        )

        self.df_ = 1.0
        self.forward_ = None
        self.option_value_ = 0.0
        self.time_to_expiry_ = 0.0
        self.tenor_ = self.accrual_
        self.sabr_result_ = {}
        self.first_order_risk_ = {}
     
    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        # What do we want to achieve here ?
        # | ------------ |  --  | ------------| --- |
        # 0              T_e  T_s           T_m   T_p
        
        # pricing formula under T^m-Forward measure is:
        #
        # V = df(0, t_p) * \tau * E^{T_m}[(R(T) - K)]
        #
        # where R(0) = self.index_engine_.calculateValue => get value
        #       \tau = acc(t_s, t_m)

        self.value_ = 0.0
        self.cash_ = 0.0
        self.df_ = 1.0
        self.forward_ = None
        self.option_value_ = 0.0
        self.time_to_expiry_ = 0.0
        self.tenor_ = self.accrual_
        self.sabr_result_ = {}

        if self.value_date_ <= self.pay_date_:
            scaler = self.sign_ * self.notional_

            # get forward compounded overnight rate over [T_s, T_m]
            self.index_engine_.calculate_value()
            self.forward_ = self.index_engine_.value()

            # case 0: t = T_p, payoff is cash today
            if self.value_date_ == self.pay_date_:
                if self.call_or_put_ == CallOrPut.CALL:
                    self.option_value_ = max(self.forward_ - self.strike_, 0.0)
                else:
                    self.option_value_ = max(self.strike_ - self.forward_, 0.0)
                self.cash_ = scaler * self.accrual_ * self.option_value_
                self.value_ = self.cash_
                return
            
            # before payment date, discount back from T_p:
            self.df_ = self.model_.discount_factor(self.funding_index_, self.pay_date_)

            # case 1: if t >= T_e, there is no optionality, you have to compute intrinsic value
            #         and the time t value is the discounted intrinsic value
            if self.value_date_ >= self.expiry_date_:
                if self.call_or_put_ == CallOrPut.CALL:
                    self.option_value_ = max(self.forward_ - self.strike_, 0.0)
                else:
                    self.option_value_ = max(self.strike_ - self.forward_, 0.0)

            # case 2: if t < T_E, there is optionality, that means, you need to use SABRCalculator
            #         to calculate   E^{T_m}[(R(T) - K)]
            else:
                self.time_to_expiry_ = accrued(self.value_date_, self.expiry_date_)
                self.tenor_ = self.accrual_

                self.sabr_calculator_ = SABRPriceAndRiskCalculator(
                    self.model_,
                    self.vpc_,
                    IndexRegistry().get("SOFR-1B-CAPFLOOR"),
                    self.forward_,
                    self.strike_,
                    self.time_to_expiry_,
                    self.tenor_,
                    self.call_or_put_,
                    calc_risk=True
                )

                self.sabr_result_ = self.sabr_calculator_.calculate_value()
                self.option_value_ = self.sabr_result_[SimpleMetrics.PV]
            
            self.value_ = scaler * self.df_ * self.accrual_ * self.option_value_

    def calculate_first_order_risk(self, gradient=None, scaler = 1.0, accumulate = False):

        if self.value_ is None:
            self.calculate_value()

        local_grad = []
        self.model_.resize_gradient(local_grad)

        # default: zero risk if already after payment
        if self.value_date_ > self.pay_date_:
            if gradient is None:
                gradient = []
            self.model_.resize_gradient(gradient)
            if not accumulate:
                for i in range(len(gradient)):
                    gradient[i] = 0.0 * gradient[i]
            return
        
        # V = sign * notional * accrual * df * SABR(F, \sigma, \beta, \nu, \rho)
        total_scaler = scaler * self.sign_ * self.notional_ * self.accrual_

        # case 0: value date == payment date: no discounting risk, only forward / intrinsic risk
        if self.value_date_ == self.pay_date_:
            if self.call_or_put_ == CallOrPut.CALL:
                doption_dforward = 1.0 if self.forward_ > self.strike_ else 0.0
            else:
                doption_dforward = -1.0 if self.forward_ < self.strike_ else 0.0

            self.index_engine_.calculate_risk(
                local_grad,
                total_scaler * doption_dforward,
                True
            )

        # case 1: expiry passed but payment not yet reached: intrinsic payoff discounted back
        # V = total_scaler * df * intrinsic(forward)
        elif self.value_date_ >= self.expiry_date_:
        
            # 1.1) let's take care of discounting risk first
            # dV/dDF = total_scaler * intrinsic_value
            dv_ddf = total_scaler * self.option_value_ # SABR
            funding_model: YieldCurve = self.model_
            funding_model.discount_factor_gradient_wrt_state(
                self.funding_index_,
                self.pay_date_,
                local_grad,
                dv_ddf,
                True)
            
            # 1.2) forward risk through intrinsic payoff
            if self.call_or_put_ == CallOrPut.CALL:
                doption_dforward = 1.0 if self.forward_ > self.strike_ else 0.0
            else:
                doption_dforward = -1.0 if self.forward_ < self.strike_ else 0.0

            dv_dforward = total_scaler * self.df_ * doption_dforward
            self.index_engine_.calculate_risk(
                local_grad,
                dv_dforward,
                True
            )
        
        # case 2: before expiry
        # V = total_scaler * df * SABR(F, sigma, beta, nu, rho)
        else:
            # 2.1) discount factor risk: dV/dDF = total_scaler * option_value
            dv_ddf = total_scaler * self.option_value_ # SABR
            funding_model: YieldCurve = self.model_
            funding_model.discount_factor_gradient_wrt_state(
                self.funding_index_,
                self.pay_date_,
                local_grad,
                dv_ddf,
                True)
            # 2.2) forward delta risk: dV/dF = total_scaler * df * dOption/dF
            dv_dforward = total_scaler * self.df_ * self.sabr_result_[SimpleMetrics.DELTA]
            self.index_engine_.calculate_risk(
                local_grad,
                dv_dforward,
                True)
            # 2.3) SABR parameter risk projected back to SABR state
            # calculate dV/dSabr and pushe them back to model internal state
            dv_dsabr = total_scaler * self.df_
            v = self.sabr_calculator_.calculate_risk(
                local_grad, 
                dv_dsabr
            )
        
        if gradient is None:
            gradient = []
        self.model_.resize_gradient(gradient)

        if accumulate:
            for i in range(len(gradient)):
                gradient[i] += local_grad[i]
        else:
            gradient[:] = local_grad
        self.first_order_risk_ = gradient
    
    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        this_cf.add_row(
            0,
            self.product_._product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.pay_date_,
            self.value_ / self.df_ if self.df_ != 0.0 else 0.0,
            self.value_,
            self.df_,
            fixing_date=self.expiry_date_,
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrued=self.accrual_,
            index_or_fixed=self.overnight_index_.name(),
            index_value=self.forward_,
        )
        return this_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, self.value_)
        report.set_cash(self.currency_, self.cash_)
        return report

class ValuationEngineRFRSwaption(ValuationEngineProduct):

    def __init__(
        self,
        model: SABRModel,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductRFRSwaption,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)
        
        # get info from product
        self.currency_ = product.currency
        self.expiry_date_ = product.expiry_date
        self.effective_date_ = product.effective_date
        self.termination_date_ = product.termination_date
        self.payment_offset_ = product.payment_offset
        self.on_index_ = product.on_index
        self.on_index_str_ = product.on_index_str
        self.notional_ = product.notional
        self.strike_ = product.strike
        self.pay_or_rec_ = product.pay_or_rec
        self.accrual_period_ = product.accrual_period
        self.floating_leg_accrual_period_ = product.floating_leg_accrual_period
        self.accrual_basis_ = product.accrual_basis
        self.spread_ = product.spread
        self.compounding_method_ = product.compounding_method
        self.sign_ = 1.0 if product.long_or_short == LongOrShort.LONG else -1.0
        self.swap_tenor_ = product.swap_tenor
        self.call_or_put_ = (CallOrPut.CALL if self.pay_or_rec_ == PayOrReceive.PAY else CallOrPut.PUT)

        self.underlying_swap_ = product.underlying_swap

        # resolve valuation parameters (csa discounting)
        self.vpc_: ValuationParametersCollection = valuation_parameters_collection
        assert self.vpc_.has_vp_type(FundingIndexParameter._vp_type)
        self.funding_vp_: FundingIndexParameter = self.vpc_.get_vp_from_build_method_collection(
            FundingIndexParameter._vp_type
        )
        self.funding_index_ = self.funding_vp_.get_funding_index(self.currency_)

        # initialise underlying swap engine   
        self.swap_engine_ = ValuationEngineProductRfrSwap(
            self.model_.sub_model_,
            self.vpc_,
            self.underlying_swap_,
            self.request_
        ) 
             
        self.value_ = None
        self.cash_ = 0.0
        self.swap_value_ = 0.0
        self.forward_swap_rate_ = 0.0
        self.annuity_ = 0.0

        self.option_value_ = 0.0
        self.time_to_expiry_ = 0.0
        self.tenor_ = self.swap_tenor_
        self.sabr_result_ = {}
        self.first_order_risk_ = {}
     
    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):
        self.value_ = 0.0
        self.cash_ = 0.0
        self.swap_value_ = 0.0
        self.forward_swap_rate_ = 0.0
        self.annuity_ = 0.0
        self.option_value_ = 0.0
        self.time_to_expiry_ = 0.0
        self.tenor_ = self.swap_tenor_
        self.sabr_result_ = {}

        self.swap_engine_.calculate_value()
        self.swap_value_ = self.swap_engine_.value_
        self.forward_swap_rate_ = self.swap_engine_.par_rate_or_spread_
        self.annuity_ = self.swap_engine_.annuity_

        # Case 1: expiry reached or passed
        # No optionality left. Physically settled swaption intrinsic value is max(PV of underlying swap, 0).
        if self.value_date_ >= self.expiry_date_:
            self.value_ = self.sign_ * max(self.swap_value_, 0.0)
            self.cash_ = 0.0
            self.option_value_ = max(self.swap_value_, 0.0) / self.notional_ if self.notional_ != 0.0 else 0.0
            return
        
        # Case 2: before expiry
        # Swaption value = sign * notional * annuity * option(S, K, sigma, T)
        self.time_to_expiry_ = accrued(self.value_date_, self.expiry_date_)
        self.tenor_ = self.swap_tenor_
        self.sabr_calculator_ = SABRPriceAndRiskCalculator(
                    self.model_,
                    self.vpc_,
                    IndexRegistry().get("SOFR-1B-SWAPTION"),
                    self.forward_swap_rate_,
                    self.strike_,
                    self.time_to_expiry_,
                    self.tenor_,
                    self.call_or_put_,
                    calc_risk=True
                )
        self.sabr_result_ = self.sabr_calculator_.calculate_value()
        self.option_value_ = self.sabr_result_[SimpleMetrics.PV]
        self.value_ = self.sign_ * self.notional_ * self.annuity_ * self.option_value_
        self.cash_ = 0.0

    def calculate_first_order_risk(self, gradient=None, scaler = 1.0, accumulate = False):

        if self.value_ is None:
            self.calculate_value()

        local_grad = []
        self.model_.resize_gradient(local_grad)

        # After expiry: intrinsic = max(V_swap, 0)
        # Only underlying swap risk survives, and only if in the money
        if self.value_date_ >= self.expiry_date_:
            if self.swap_value_ > 0.0:
                swap_grad = []
                self.model_.sub_model_.resize_gradient(swap_grad)

                self.swap_engine_.calculate_first_order_risk(
                    swap_grad,
                    scaler * self.sign_,
                    False
                )
                # merge YC sub-model blocks into SABRModel blocks
                for i in range(self.model_.sub_model_.num_components):
                    local_grad[i] += swap_grad[i]

        # Before expiry:
        # V = sign * N * A * Option(S, K, sigma)
        # dV = sign*N*[ Option*dA + A*Delta*dS + A*dOption/dSABR ]
        else:
            total_scaler = scaler * self.sign_ * self.notional_
            # 1) annuity risk
            # fixed leg PV: V_fixed = notional * fixed_rate * annuity
            # dA = dV_fixed / (notional * fixed_rate)
            # contribution to swaption risk: total_scaler * option_value * dA
            fixed_rate_underlying = self.underlying_swap_.fixed_rate_
            if abs(self.notional_) > 0.0 and abs(fixed_rate_underlying) > 0.0:
                annuity_grad = []
                self.model_.sub_model_.resize_gradient(annuity_grad)

                annuity_scaler = total_scaler * self.option_value_ / (self.notional_ * fixed_rate_underlying)

                self.swap_engine_.fixed_leg_engine_.calculate_first_order_risk(
                    annuity_grad,
                    scaler=annuity_scaler,
                    accumulate=False,
                )

                for i in range(self.model_.sub_model_.num_components):
                    local_grad[i] += annuity_grad[i]
            
            # 2) forward swap rate delta risk
            # contribution: total_scaler * annuity * delta * dF
            par_grad = self.swap_engine_.grad_at_par()
            forward_scaler = total_scaler * self.annuity_ * self.sabr_result_[SimpleMetrics.DELTA]

            for i in range(self.model_.sub_model_.num_components):
                local_grad[i] += forward_scaler * par_grad[i]

            # 3) SABR parameter risk
            # contribution: total_scaler * annuity * dOption/d(SABR state)
            self.sabr_calculator_.calculate_risk(
                local_grad,
                total_scaler * self.annuity_,
            )
        
        if gradient is None:
            gradient = []
        self.model_.resize_gradient(gradient)

        if accumulate:
            for i in range(len(gradient)):
                gradient[i] += local_grad[i]
        else:
            gradient[:] = local_grad
        self.first_order_risk_ = gradient
    
    def create_cash_flows_report(self) -> CashflowsReport:
        this_cf = CashflowsReport()
        this_cf.add_row(
            0,
            self.product_._product_type,
            self.val_engine_type(),
            self.notional_,
            self.sign_,
            self.expiry_date_,
            self.value_,
            self.value_,
            1.0,
            fixing_date=self.expiry_date_,
            start_date=self.effective_date_,
            end_date=self.termination_date_,
            accrued=self.annuity_,
            index_or_fixed=self.on_index_.name(),
            index_value=self.forward_swap_rate_,
        )
        return this_cf

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currency_)
        report.set_pv(self.currency_, self.value_)
        report.set_cash(self.currency_, self.cash_)
        return report
    

_SABR_ENGINE_MAP = {
    ProductRFRCapletFloorlet._product_type:     ValuationEngineRFRCapletFloorlet,
    ProductRFRSwaption._product_type:           ValuationEngineRFRSwaption
}

for prod_type, eng_cls in _SABR_ENGINE_MAP.items():
    ValuationEngineProductRegistry().register(
        (SABRModel._model_type.to_string(), prod_type, AnalyticValParam._vp_type),
        eng_cls,
    )
     


# class ValuationEngineIborCapFloorlet(ValuationEngine):

#     def __init__(self, model: SabrModel, valuation_parameters: Dict[str, Any], product: ProductIborCapFloorlet) -> None:
#         super().__init__(model, valuation_parameters, product)
#         self.yieldCurve   = model.subModel
#         raw = valuation_parameters.get("SABR_METHOD")
#         method_input = raw.lower() if isinstance(raw, str) else ""
#         if method_input in ("top-down", "bottom-up"):
#             warnings.warn(
#                 f"SABR_METHOD='{raw}' is not allowed for Ibor products; "
#                 "forcing standard Hagan SABR.",
#                 UserWarning
#             )
#         self.sabrCalc = SABRCalculator(model, method=None)
#         self.currencyCode = product.currency.value.code()
#         self.accrualStart = product.accrualStart
#         self.accrualEnd   = product.accrualEnd
#         self.strikeRate   = product.strike
#         self.optionType   = product.optionType
#         self.notional     = product.notional
#         self.buyOrSell    = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.

#     def calculateValue(self) -> None:
#         expiry_t = accrued(self.valueDate, self.accrualStart)
#         tenor_t  = accrued(self.accrualStart, self.accrualEnd)

#         forward_rate    = self.yieldCurve.forward(
#             self.product.index,
#             self.accrualStart,
#             self.accrualEnd,
#         )
#         discount_factor = self.yieldCurve.discountFactor(self.product.index, self.accrualEnd)

#         price = self.sabrCalc.option_price(
#             index       = self.product.index,
#             expiry      = expiry_t,
#             tenor       = tenor_t,
#             forward     = forward_rate,
#             strike      = self.strikeRate,
#             option_type = self.optionType,
#         )

#         accrual_factor = accrued(self.accrualStart, self.accrualEnd)
#         pv = self.notional * discount_factor * accrual_factor * price *  self.buyOrSell

#         self.value_ = [self.currencyCode, pv]

# ValuationEngineRegistry().insert(
#     SabrModel.MODEL_TYPE,
#     ProductIborCapFloorlet.prodType,
#     ValuationEngineIborCapFloorlet
# )

# class ValuationEngineOvernightCapFloorlet(ValuationEngine):

#     def __init__(self, model: SabrModel, valuation_parameters: Dict[str, Any], product: ProductOvernightCapFloorlet) -> None:
#         super().__init__(model, valuation_parameters, product)
#         self.yieldCurve   = model.subModel
#         raw = valuation_parameters.get("SABR_METHOD")
#         sabr_method = raw.lower() if isinstance(raw, str) else "" 
#         prod_flag   = "CAPLET"   if sabr_method=="top-down" else None
#         self.sabrCalc     = SABRCalculator(
#             model,
#             method  = valuation_parameters.get("SABR_METHOD", None),
#             product = product,
#             product_type = prod_flag 
#         )
#         self.currencyCode = product.currency.value.code()
#         self.accrualStart = product.effectiveDate
#         self.accrualEnd   = product.maturityDate
#         self.strikeRate   = product.strike
#         self.optionType   = product.optionType
#         self.notional     = product.notional
#         self.buyOrSell    = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.

#     def calculateValue(self) -> None:
#         expiry_t = accrued(self.valueDate, self.accrualStart)        
#         tenor_t  = accrued(self.accrualStart, self.accrualEnd)

#         forward_rate    = self.yieldCurve.forward(
#             self.product.index,
#             self.accrualStart,
#             self.accrualEnd,
#         )
#         discount_factor = self.yieldCurve.discountFactor(self.product.index, self.accrualEnd)

#         price = self.sabrCalc.option_price(
#             index       = self.product.index,
#             expiry      = expiry_t,
#             tenor       = tenor_t,
#             forward     = forward_rate,
#             strike      = self.strikeRate,
#             option_type = self.optionType,
#         )

#         accrual_factor = accrued(self.accrualStart, self.accrualEnd)
#         pv = self.notional * discount_factor * accrual_factor * price *  self.buyOrSell

#         self.value_ = [self.currencyCode, pv]

# ValuationEngineRegistry().insert(
#     SabrModel.MODEL_TYPE,
#     ProductOvernightCapFloorlet.prodType,
#     ValuationEngineOvernightCapFloorlet
# )

# class ValuationEngineIborCapFloor(ValuationEngine):

#     def __init__(
#         self,
#         model: SabrModel,
#         valuation_parameters: Dict[str, Any],
#         product: ProductIborCapFloor,
#     ) -> None:
#         super().__init__(model, valuation_parameters, product)
#         self.currencyCode = product.currency.value.code()
#         self.caplets      = product.capStream
#         self.engines = [ValuationEngineIborCapFloorlet(model, valuation_parameters, caplet) for caplet in self.caplets.products]

#     def calculateValue(self) -> None:
#         total_pv = 0.0
#         for engine in self.engines:
#             engine.calculateValue()
#             _, pv = engine.value_
#             total_pv += pv
#         self.value_ = [self.currencyCode, total_pv]

# ValuationEngineRegistry().insert(
#     SabrModel.MODEL_TYPE,
#     ProductIborCapFloor.prodType,
#     ValuationEngineIborCapFloor
# )

# class ValuationEngineOvernightCapFloor(ValuationEngine):

#     def __init__(
#         self,
#         model: SabrModel,
#         valuation_parameters: Dict[str, Any],
#         product: ProductOvernightCapFloor,
#     ) -> None:
#         super().__init__(model, valuation_parameters, product)
#         self.currencyCode = product.currency.value.code()
#         self.caplets      = product.capStream
#         self.engines = [ ValuationEngineOvernightCapFloorlet(model, valuation_parameters, caplet) for caplet in self.caplets.products]

#     def calculateValue(self) -> None:
#         total_pv = 0.0
#         for engine in self.engines:
#             engine.calculateValue()
#             _, pv = engine.value_
#             total_pv += pv
#         self.value_ = [self.currencyCode, total_pv]

# ValuationEngineRegistry().insert(
#     SabrModel.MODEL_TYPE,
#     ProductOvernightCapFloor.prodType,
#     ValuationEngineOvernightCapFloor
# )

# class ValuationEngineIborSwaption(ValuationEngine):

#     def __init__(
#         self,
#         model: SabrModel,
#         valuation_parameters: Dict[str, Any],
#         product: ProductIborSwaption,
#     ) -> None:
#         super().__init__(model, valuation_parameters, product)
#         self.yieldCurve   = model.subModel
#         raw = valuation_parameters.get("SABR_METHOD")
#         method_input = raw.lower() if isinstance(raw, str) else ""
#         if method_input in ("top-down", "bottom-up"):
#             warnings.warn(
#                 f"SABR_METHOD='{raw}' is not allowed for Ibor products; "
#                 "forcing standard Hagan SABR.",
#                 UserWarning
#             )
#         self.sabrCalc = SABRCalculator(model, method=None)
#         self.swap          = product.swap
#         self.expiry        = product.expiryDate
#         self.notional      = product.notional
#         self.buyOrSell     = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.
#         self.currencyCode  = self.swap.currency.value.code()
#         self.strikeRate    = self.swap.fixedRate
#         self.optionType = product.optionType
#         self.optionFlag = 'CAP'   if self.optionType == 'PAYER' else 'FLOOR'

#     def calculateValue(self) -> None:
#         t_exp = accrued(self.valueDate, self.expiry)
#         t_ten = accrued(self.swap.firstDate, self.swap.lastDate)

#         ir_vp = {"FUNDING INDEX": self.swap.index}
#         ir_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap)
#         ir_engine.calculateValue()
#         forward_swap_rate = ir_engine.parRate()
#         swap_annuity      = ir_engine.annuity()

#         price = self.sabrCalc.option_price(
#             index       = self.swap.index,
#             expiry      = t_exp,
#             tenor       = t_ten,
#             forward     = forward_swap_rate,
#             strike      = self.strikeRate,
#             option_type = self.optionFlag,
#         )

#         pv = self.notional * swap_annuity * price *  self.buyOrSell
#         self.value_ = [self.currencyCode, pv]

# ValuationEngineRegistry().insert(
#     SabrModel.MODEL_TYPE,
#     ProductIborSwaption.prodType,
#     ValuationEngineIborSwaption
# )

# class ValuationEngineOvernightSwaption(ValuationEngine):

#     def __init__(self, model: SabrModel, valuation_parameters: Dict[str, Any], product: ProductOvernightSwaption) -> None:
#         super().__init__(model, valuation_parameters, product)
#         self.yieldCurve   = model.subModel
#         raw = valuation_parameters.get("SABR_METHOD")
#         method_input = raw.lower() if isinstance(raw, str) else ""
#         if method_input in ("top-down", "bottom-up"):
#             warnings.warn(
#                 f"SABR_METHOD='{raw}' is not allowed for Overnight Swaptions; "
#                 "forcing standard Hagan SABR.",
#                 UserWarning
#             )
#         self.sabrCalc = SABRCalculator(model, method=None)
#         self.swap          = product.swap
#         self.expiry        = product.expiryDate
#         self.notional      = product.notional
#         self.buyOrSell     = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.
#         self.currencyCode  = self.swap.currency.value.code()
#         self.strikeRate    = self.swap.fixedRate
#         self.optionType = product.optionType
#         self.optionFlag = 'CAP'   if self.optionType == 'PAYER' else 'FLOOR'

#     def calculateValue(self) -> None:
#         t_exp = accrued(self.valueDate, self.expiry)
#         t_ten = accrued(self.swap.firstDate, self.swap.lastDate)

#         ir_vp = {"FUNDING INDEX": self.swap.index}
#         ir_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap)
#         ir_engine.calculateValue()
#         forward_swap_rate = ir_engine.parRate()
#         swap_annuity      = ir_engine.annuity()

#         price = self.sabrCalc.option_price(
#             index       = self.swap.index,
#             expiry      = t_exp,
#             tenor       = t_ten,
#             forward     = forward_swap_rate,
#             strike      = self.strikeRate,
#             option_type = self.optionFlag,
#         )

#         pv = self.notional * swap_annuity * price * self.buyOrSell
#         self.value_ = [self.currencyCode, pv]

# ValuationEngineRegistry().insert(
#     SabrModel.MODEL_TYPE,
#     ProductOvernightSwaption.prodType,
#     ValuationEngineOvernightSwaption
# )


# _SABR_ENGINE_MAP = {
#     ProductIborCapFloorlet.prodType:       ValuationEngineIborCapFloorlet,
#     ProductOvernightCapFloorlet.prodType:  ValuationEngineOvernightCapFloorlet,
#     ProductIborCapFloor.prodType:          ValuationEngineIborCapFloor,
#     ProductOvernightCapFloor.prodType:     ValuationEngineOvernightCapFloor,
#     ProductIborSwaption.prodType:          ValuationEngineIborSwaption,
#     ProductOvernightSwaption.prodType:     ValuationEngineOvernightSwaption,
# }

# for prod_type, eng_cls in _SABR_ENGINE_MAP.items():
#     ValuationEngineRegistry().insert(
#         SabrModel.MODEL_TYPE,
#         prod_type,
#         eng_cls
#     )
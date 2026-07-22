from re import I

import QuantLib as ql
import numpy as np
import torch
from typing import Optional, List
from fixedincomelib.date import *
from fixedincomelib.market import *
from fixedincomelib.valuation import *
from fixedincomelib.utilities import InterpolatorFactory
from fixedincomelib.yield_curve.yield_curve_model import YieldCurve


### Overnight Anchored Index Valuation Engine Analytics
class ValuationEngineAnalyticsCompositeIndex(ValuationEngineAnalyticsAnchoredIndex):

    def __init__(
        self,
        model: YieldCurve,
        anchored_index: AnchoredOvernightIndex,
        valuation_parameters_collection: ValuationParametersCollection,
    ) -> None:

        assert (
            type(anchored_index) is AnchoredOvernightIndex
        ), "anchored_index must be an instance of AnchoredOvernightIndex"

        super().__init__(model, anchored_index, valuation_parameters_collection)
        self.value_h_ = 0.0
        self.value_f_ = 0.0
        self.value_ = 0.0

    ### aggregate a sequence of known daily fixings into a single compounded rate over [tau_h].
    ### dispatched on compounding method (dict lookup instead of an if/elif chain).
    ## geometric(compound): prod
    ## arithmetic: dot
    _AGGREGATORS = {
        CompoundingMethod.COMPOUND: lambda taus, rates, tau: (torch.prod(1.0 + taus * rates) - 1.0)
        / tau,
        CompoundingMethod.ARITHMETIC: lambda taus, rates, tau: torch.dot(taus, rates) / tau,
    }

    def calculate_value(self):

        idx: AnchoredOvernightIndex = self.anchored_index_
        index: OvernightIndex = idx.index
        index_name = index.index_name()
        bdc = idx.business_day_convention
        hol = idx.holiday_convention

        # end date of the accrual period must land on a business day
        if index.from_ql:
            end_date = index.fixingDate(idx.term_or_termination_date)
        else:
            end_date = move_to_business_day(idx.term_or_termination_date, bdc, hol)
        start_date = idx.start_date

        # daily (business-day-spaced) accrual schedule T_0=start_date, ..., T_n=end_date
        accrual_dates = [start_date]
        cur_date = start_date
        while cur_date < end_date:
            cur_date = add_period(cur_date, Period("1D"), bdc, hol)
            accrual_dates.append(cur_date)

        # rate cutoff
        cutoff_date = subtract_period(end_date, idx.rate_cutoff, bdc, hol)

        # look back
        taus, rates, known = [], [], []
        for t_s, t_e in zip(accrual_dates[:-1], accrual_dates[1:]):
            obs_date = subtract_period(min(t_s, cutoff_date), idx.look_back_window, bdc, hol)
            taus.append(accrued(t_s, t_e, idx.accrual_basis, bdc, hol))
            is_known = obs_date <= self.value_date_
            known.append(is_known)
            rates.append(
                IndexFixingsManager().get_fixing(index_name, obs_date) if is_known else 0.0
            )

        taus_t = torch.tensor(taus, dtype=torch.float64)
        rates_t = torch.tensor(rates, dtype=torch.float64)
        known_t = torch.tensor(known, dtype=torch.bool)

        tau_h = taus_t[known_t].sum()
        tau_f = taus_t.sum() - tau_h

        # realized leg: compounded from known historical fixings
        self.value_h_ = (
            self._AGGREGATORS[idx.compounding_method](taus_t[known_t], rates_t[known_t], tau_h)
            if tau_h > 0
            else torch.tensor(0.0, dtype=torch.float64)
        )

        # forward leg
        if tau_f > 0:
            first_unknown = int(known_t.sum())
            df_dates = accrual_dates[first_unknown:]

            if idx.compounding_method == CompoundingMethod.COMPOUND:
                # geometric compounding telescopes: prod_i(1 + tau_i*L_i) = prod_i(df_i/df_{i+1})
                # = df_first/df_last, so the per-day discount factors and product are unneeded.
                df_first = self.model_.discount_factor(index, df_dates[0], calc_grad=True)
                df_last = self.model_.discount_factor(index, df_dates[-1], calc_grad=True)
                self.value_f_ = (df_first / df_last - 1.0) / tau_f
            else:
                forward_taus = taus_t[first_unknown:]
                dfs = [self.model_.discount_factor(index, d, calc_grad=True) for d in df_dates]
                forward_rates = torch.stack(
                    [(dfs[i] / dfs[i + 1] - 1.0) / forward_taus[i] for i in range(len(dfs) - 1)]
                )
                self.value_f_ = self._AGGREGATORS[idx.compounding_method](
                    forward_taus, forward_rates, tau_f
                )
        else:
            self.value_f_ = torch.tensor(0.0, dtype=torch.float64)

        # combine per Rx = (1 + tau_h * Rx_h)(1 + tau_f * Rx_f) - 1, all over tau
        tau = tau_h + tau_f
        self.value_ = ((1.0 + tau_h * self.value_h_) * (1.0 + tau_f * self.value_f_) - 1.0) / tau

    def calculate_risk(self) -> None:

        pass

    @property
    def value_h(self) -> float:
        return self.value_h_

    @property
    def value_f(self) -> float:
        return self.value_f_

    @property
    def value(self) -> float:
        return self.value_


### IBOR Anchored Index Valuation Engine Analytics
class ValuationEngineAnalyticsIborIndex(ValuationEngineAnalyticsAnchoredIndex):

    def __init__(
        self,
        model: YieldCurve,
        anchored_index: AnchoredIborIndex,
        valuation_parameters_collection: ValuationParametersCollection,
    ) -> None:

        assert (
            type(anchored_index) is AnchoredIborIndex
        ), "anchored_index must be an instance of AnchoredIborIndex"

        super().__init__(model, anchored_index, valuation_parameters_collection)

        analytic_vp = valuation_parameters_collection.get_vp_from_build_method_collection(
            AnalyticValParam._vp_type
        )
        self.interp_method_ = analytic_vp.interpolation_method
        self.extrap_method_ = analytic_vp.extrapolation_method

        self.value_h_ = 0.0
        self.value_f_ = 0.0
        self.value_ = 0.0

    ### only handles the common, market-traded tenor: the anchored index's own accrual
    ### period must equal its index's native term. Irregular (stub/extended) periods are
    ### delegated to _calculate_irregular_period_value.
    def calculate_value(self):

        idx: AnchoredIborIndex = self.anchored_index_
        index: IBORIndex = idx.index
        index_name = index.index_name()
        bdc = idx.business_day_convention
        hol = idx.holiday_convention
        start_date = idx.start_date

        end_date = (
            add_period(start_date, idx.term_or_termination_date, bdc, hol)
            if isinstance(idx.term_or_termination_date, ql.Period)
            else move_to_business_day(idx.term_or_termination_date, bdc, hol)
        )
        requested_tau = accrued(start_date, end_date, idx.accrual_basis, bdc, hol)

        native_end_date = add_period(start_date, index.term, bdc, hol)
        native_tau = accrued(start_date, native_end_date, idx.accrual_basis, bdc, hol)

        if requested_tau != native_tau:
            self._calculate_irregular_period_value(start_date, requested_tau)
            return

        if index.from_ql:
            fixing_date = index.fixingDate(start_date)
        else:
            fixing_date = subtract_period(start_date, idx.look_back_window, bdc, hol)

        is_known = fixing_date <= self.value_date_

        if is_known:
            # in valuation parameter, we can say something like this
            # when fixing of today is not available, we can imply from the curve
            # spot fixing :
            #   - R_0 = (DF(0, 0) / DF(0, T_0) - 1) / tau_0
            rate = IndexFixingsManager().get_fixing(index_name, fixing_date)
        else:
            casted_yc: YieldCurve = self.model_
            df_t0 = casted_yc.discount_factor(index, start_date, calc_grad=True)
            df_te = casted_yc.discount_factor(index, native_end_date, calc_grad=True)
            rate = (df_t0 / df_te - 1.0) / native_tau

        self.value_h_ = rate if is_known else 0.0
        self.value_f_ = rate if not is_known else 0.0
        self.value_ = rate

    ### irregular (stub/extended) periods
    def _calculate_irregular_period_value(self, start_date: Date, requested_tau: float):
        idx: AnchoredIborIndex = self.anchored_index_
        bdc = idx.business_day_convention
        hol = idx.holiday_convention

        family_taus, family_rates = self._family_tenor_rates(start_date, bdc, hol)
        assert (
            len(family_taus) > 0
        ), f"model has no calibrated tenor for the index family of {idx.index.index_name()}"

        interpolator = InterpolatorFactory.create_1d_interpolator(
            family_taus, family_rates, self.interp_method_, self.extrap_method_
        )
        rate = interpolator.interpolate(requested_tau)

        fixing_date = subtract_period(start_date, idx.look_back_window, bdc, hol)
        is_known = fixing_date <= self.value_date_

        self.value_h_ = rate if is_known else 0.0
        self.value_f_ = rate if not is_known else 0.0
        self.value_ = rate

    ### every IBOR component the model currently holds whose index shares the requested
    ### index's family (its registry name with the exact native-term suffix stripped),
    ### paired with that tenor's own native rate. Sorted ascending by tau for interpolation.
    def _family_tenor_rates(self, start_date: Date, bdc, hol):
        idx: AnchoredIborIndex = self.anchored_index_
        index = idx.index
        family_prefix = index.index_name()[: -len(Period.to_string(index.term))].rstrip("-")

        taus, rates = [], []
        for component in self.model_.components_.values():
            sibling_index: IBORIndex = component.build_method.target_index
            if not isinstance(sibling_index, IBORIndex):
                continue
            sibling_prefix = sibling_index.index_name()[
                : -len(Period.to_string(sibling_index.term))
            ].rstrip("-")
            if sibling_prefix != family_prefix:
                continue

            sibling_anchored_index = AnchoredIborIndex(
                start_date,
                sibling_index.term,
                sibling_index,
                idx.compounding_method,
                rate_cutoff=idx.rate_cutoff,
                look_back_window=idx.look_back_window,
                business_day_convention=bdc,
                holiday_convention=hol,
            )
            sibling_engine = ValuationEngineAnalyticsIborIndex(
                self.model_, sibling_anchored_index, self.valuation_parameters_collection_
            )
            sibling_engine.calculate_value()

            sibling_end_date = add_period(start_date, sibling_index.term, bdc, hol)
            taus.append(accrued(start_date, sibling_end_date, idx.accrual_basis, bdc, hol))
            value = sibling_engine.value
            rates.append(float(value.detach()) if isinstance(value, torch.Tensor) else float(value))

        order = sorted(range(len(taus)), key=lambda i: taus[i])
        return [taus[i] for i in order], [rates[i] for i in order]

    def calculate_risk(self):
        pass

    @property
    def value_h(self) -> float:
        return self.value_h_

    @property
    def value_f(self) -> float:
        return self.value_f_

    @property
    def value(self) -> float:
        return self.value_


### Compound IBOR Anchored Index Valuation Engine Analytics
class ValuationEngineAnalyticsCompoundIborIndex(ValuationEngineAnalyticsAnchoredIndex):

    def __init__(
        self,
        model: YieldCurve,
        anchored_index: AnchoredCompoundIborIndex,
        valuation_parameters_collection: ValuationParametersCollection,
    ) -> None:

        assert (
            type(anchored_index) is AnchoredCompoundIborIndex
        ), "anchored_index must be an instance of AnchoredCompoundIborIndex"

        super().__init__(model, anchored_index, valuation_parameters_collection)
        self.value_h_ = 0.0
        self.value_f_ = 0.0
        self.value_ = 0.0

    ### geometric compounding of (1 + alpha_i * L_i) over a leg
    _AGGREGATORS = {
        CompoundingMethod.SPREAD_EXCLUSIVE_COMPOUND: lambda taus, rates, tau: (
            torch.prod(1.0 + taus * rates) - 1.0
        )
        / tau,
    }

    @staticmethod
    def _flat_compound_amount(
        taus: torch.Tensor, rates: torch.Tensor, carry_in: torch.Tensor
    ) -> torch.Tensor:
        # compoundPeriodAmount_i = alpha_i * (L_i + spread) + compoundPeriodAmount_{i-1} * alpha_i * L_i,
        # i.e. the cumulative amount compounds forward by the same (1 + alpha_i * L_i) factor
        # every period (no product spread ever reaches this analytics layer -- callers apply
        # their spread once, after the compounded rate is derived, e.g.
        # ValuationEngineProductIBORCompoundingCashflow), so this telescopes to the closed form
        # below. (1 + total) = (1 + carry_in) * prod_i(1 + alpha_i * L_i).
        if taus.numel() == 0:  # number of elements
            return carry_in
        return (1.0 + carry_in) * torch.prod(1.0 + taus * rates) - 1.0

    def calculate_value(self):

        idx: AnchoredCompoundIborIndex   = self.anchored_index_
        index: IBORIndex = idx.index
        index_name = index.index_name()
        bdc = idx.business_day_convention
        hol = idx.holiday_convention
        start_date = idx.start_date

        # the anchored index's own accrual end date
        end_date = (
            add_period(start_date, idx.term_or_termination_date, bdc, hol)
            if isinstance(idx.term_or_termination_date, ql.Period)
            else move_to_business_day(idx.term_or_termination_date, bdc, hol)
        )

        native_term = index.term
        calc_dates = [start_date]
        cur_date = start_date
        while cur_date < end_date:
            cur_date = add_period(cur_date, native_term, bdc, hol)
            calc_dates.append(cur_date)

        # rate cutoff
        cutoff_date = subtract_period(end_date, idx.rate_cutoff, bdc, hol)

        taus, known = [], []
        for t_s, t_e in zip(calc_dates[:-1], calc_dates[1:]):
            obs_date = subtract_period(min(t_s, cutoff_date), idx.look_back_window, bdc, hol)
            taus.append(accrued(t_s, t_e, idx.accrual_basis, bdc, hol))
            known.append(obs_date <= self.value_date_)

        first_unknown = known.index(False) if False in known else len(known)

        known_taus_t = torch.tensor(taus[:first_unknown], dtype=torch.float64)
        known_rates_t = torch.tensor(
            [
                IndexFixingsManager().get_fixing(
                    index_name,
                    subtract_period(
                        min(calc_dates[i], cutoff_date), idx.look_back_window, bdc, hol
                    ),
                )
                for i in range(first_unknown)
            ],
            dtype=torch.float64,
        )
        unknown_taus = taus[first_unknown:]
        unknown_bounds = calc_dates[first_unknown:]

        tau_h = known_taus_t.sum() if first_unknown > 0 else torch.tensor(0.0, dtype=torch.float64)
        tau_f = sum(unknown_taus)
        tau = tau_h + tau_f

        method = idx.compounding_method
        zero = torch.tensor(0.0, dtype=torch.float64)

        if method == CompoundingMethod.SPREAD_EXCLUSIVE_COMPOUND:
            aggregator = self._AGGREGATORS[method]
            self.value_h_ = aggregator(known_taus_t, known_rates_t, tau_h) if tau_h > 0 else zero
            casted_yc: YieldCurve = self.model_
            if tau_f > 0:
                df_t0 = casted_yc.discount_factor(index, unknown_bounds[0], calc_grad=True)
                df_te = casted_yc.discount_factor(index, unknown_bounds[-1], calc_grad=True)
                self.value_f_ = (df_t0 / df_te - 1.0) / tau_f
            else:
                self.value_f_ = zero
            # Rx = (1 + tau_h * Rx_h)(1 + tau_f * Rx_f) - 1, all over tau -- exact for
            # geometric compounding since the historical/forward legs factor the product
            self.value_ = (
                (1.0 + tau_h * self.value_h_) * (1.0 + tau_f * self.value_f_) - 1.0
            ) / tau

        elif method == CompoundingMethod.FLAT_COMPOUND:

            amount_h = self._flat_compound_amount(known_taus_t, known_rates_t, zero)
            self.value_h_ = amount_h / tau_h if tau_h > 0 else zero

            casted_yc: YieldCurve = self.model_
            if tau_f > 0:
                unknown_taus_t = torch.tensor(unknown_taus, dtype=torch.float64)
                unknown_rates_t = torch.stack(
                    [
                        (
                            casted_yc.discount_factor(index, t_s, calc_grad=True)
                            / casted_yc.discount_factor(index, t_e, calc_grad=True)
                            - 1.0
                        )
                        / tau_i
                        for t_s, t_e, tau_i in zip(
                            unknown_bounds[:-1], unknown_bounds[1:], unknown_taus
                        )
                    ]
                )
                self.value_f_ = (
                    self._flat_compound_amount(unknown_taus_t, unknown_rates_t, zero) / tau_f
                )
                amount_total = self._flat_compound_amount(unknown_taus_t, unknown_rates_t, amount_h)
            else:
                self.value_f_ = zero
                amount_total = amount_h

            self.value_ = amount_total / tau

        else:
            raise ValueError(
                f"Unsupported compounding method for AnchoredCompoundIborIndex: {method}"
            )

    def calculate_risk(self):
        pass

    @property
    def value_h(self) -> float:
        return self.value_h_

    @property
    def value_f(self) -> float:
        return self.value_f_

    @property
    def value(self) -> float:
        return self.value_


### Registry
# ValuationEngineAnalyticIndexRegistry().register((YieldCurve._model_type.to_string(), ql.OvernightIndex.__name__), ValuationEngineAnalyticsOvernightIndex)

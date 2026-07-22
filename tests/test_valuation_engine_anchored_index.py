"""
Level 5 (valuation engine), atomic layer: correctness tests for
`AnchoredIborIndex` / `AnchoredOvernightIndex` / `AnchoredCompoundIborIndex`
(fixedincomelib/market/anchored_index.py) and their matching `ValuationEngineAnalytics*`
engines (fixedincomelib/yield_curve/valuation_engine_analytics.py).

unittest.TestCase conversion of tests/test_valuation_engine_anchored_index.ipynb, per
.claude/skills/test_valuation_engine.md. These are atomic computational primitives (a single
accrual period's compounded/simple rate), not tradable products -- unlike the product-level
valuation engines (ValuationEngineProduct*), which stay notebook-style for their narrative
walkthrough value, this layer is mechanical/deterministic and gets a flat pytest file, matching
the Level 1 (building-blocks) convention.

pytest auto-discoverable (test_*.py). Several tests build on the same evolving curve/fixing
state rather than being fully isolated (mirroring the original notebook's cell-execution order),
so test method names are numbered (test_01a_..., test_01b_..., ...) to pin unittest's
alphabetical ordering to that same sequence -- do not reorder or rename methods without
checking whether a later test depends on fixings/state a numerically-earlier one seeds.
"""

import sys
import os
import unittest

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(".."))

import numpy as np
import pandas as pd
import torch

from fixedincomelib import *
from fixedincomelib.yield_curve.valuation_engine_analytics import (
    ValuationEngineAnalyticsIborIndex,
    ValuationEngineAnalyticsCompositeIndex,
    ValuationEngineAnalyticsCompoundIborIndex,
)
from fixedincomelib.valuation.valuation_parameters import ValuationParametersCollection, AnalyticValParam


LIBOR_NAME = "USD-LIBOR-BBA-3M"


def set_libor_fixings(fixing_map: dict) -> None:
    """Resets the in-memory fixing map for USD-LIBOR-BBA-3M and seeds it directly, so tests
    are self-contained rather than depending on a machine-local fixing-source CSV."""
    if IndexFixingsManager().exists(LIBOR_NAME):
        qfRemoveIndexFixings(LIBOR_NAME)
    IndexFixingsManager()._map.setdefault(LIBOR_NAME, {})
    dates = [d.ISO() for d in fixing_map]
    values = list(fixing_map.values())
    qfInsertIndexFixing(LIBOR_NAME, dates, values)


def closed_form_spread_exclusive_compound(bounds, index, model, biz_conv, hol_conv):
    """Independent closed-form geometric compound, computed without touching the engine's
    own aggregation code."""
    taus, rates = [], []
    for t_s, t_e in zip(bounds[:-1], bounds[1:]):
        tau_i = accrued(t_s, t_e, index.accrual_basis, biz_conv, hol_conv)
        df_s = model.discount_factor(index, t_s, calc_grad=True)
        df_e = model.discount_factor(index, t_e, calc_grad=True)
        rates.append((df_s / df_e - 1.0) / tau_i)
        taus.append(tau_i)
    prod = 1.0
    for tau_i, rate_i in zip(taus, rates):
        prod *= 1.0 + tau_i * rate_i
    return (prod - 1.0) / sum(taus)


def gradient_block(model, grad, component_name):
    offsets = np.cumsum([0] + model.gradient_lengths_)
    pos = model.component_order_.index(component_name)
    return grad[offsets[pos] : offsets[pos + 1]]


class AnchoredIndexValuationEngineTestCase(unittest.TestCase):
    """
    Shared fixture: a small synthetic USD LIBOR-3M curve (SOFR-1B OIS projection,
    SOFR-1B-FLAT discounting, USD-LIBOR-BBA-3M projection discounted off SOFR-1B-FLAT --
    exactly how a LIBOR curve is built against OIS discounting in practice), built once for
    the whole suite since every test in this file reads (but does not rebuild) it.
    """

    @classmethod
    def setUpClass(cls):
        DataConventionRegistry().register(
            "USD-LIBOR-3M-IFR",
            {
                "type": "INSTANTANEOUS FORWARD RATE",
                "convention": {"index": "USD-LIBOR-BBA-3M"},
            },
        )

        bm_list = [
            qfCreateBuildMethod(
                "YC_OVERNIGHT_INDEX_ELEMENT",
                {"TARGET": "SOFR-1B", "INSTANTANEOUS FORWARD RATE": "USD-SOFR-OIS-1B-IFR"},
            ),
            qfCreateBuildMethod(
                "YC_FUNDING_ELEMENT",
                {
                    "TARGET": "SOFR-1B-FLAT",
                    "REFERENCE": "SOFR-1B",
                    "INSTANTANEOUS FORWARD RATE": "USD-SOFR-OIS-1B-FLAT-IFR",
                },
            ),
            qfCreateBuildMethod(
                "YC_IBOR_ELEMENT",
                {"TARGET": "USD-LIBOR-BBA-3M", "INSTANTANEOUS FORWARD RATE": "USD-LIBOR-3M-IFR"},
            ),
            qfCreateBuildMethod(
                "YC_COMMON",
                {"TARGET": "USD", "FUNDING PARAMETERS": "SOFR-1B-FLAT", "SOLVER METHOD": "BRENT"},
            ),
        ]
        cls.build_method_collection = qfCreateModelBuildMethodCollection(bm_list)

        cls.data_type = "INSTANTANEOUS FORWARD RATE"
        cls.tenors = ["3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"]

        cls.sofr_ifr = pd.DataFrame(index=cls.tenors)
        cls.sofr_ifr["values"] = [0.0430] * len(cls.tenors)  # flat 4.30% IFR curve

        cls.flat_ifr = pd.DataFrame(index=["1Y", "10Y", "30Y"])
        cls.flat_ifr["values"] = [0.0, 0.0, 0.0]

        cls.libor_ifr = pd.DataFrame(index=cls.tenors)
        cls.libor_ifr["values"] = [0.0500] * len(cls.tenors)  # flat 5.00% IFR curve

        data_collection = qfCreateDataCollection(
            [
                qfCreateData1D(cls.data_type, "USD-SOFR-OIS-1B-IFR", cls.sofr_ifr),
                qfCreateData1D(cls.data_type, "USD-SOFR-OIS-1B-FLAT-IFR", cls.flat_ifr),
                qfCreateData1D(cls.data_type, "USD-LIBOR-3M-IFR", cls.libor_ifr),
            ]
        )

        cls.value_date = "2026-06-25"
        cls.yc_usd = qfCreateModel(cls.value_date, "YIELD_CURVE", data_collection, cls.build_method_collection)

        cls.libor_index = IndexRegistry().get(LIBOR_NAME)
        cls.overnight_index = IndexRegistry().get("SOFR-1B")
        cls.native_term = cls.libor_index.term
        cls.biz_conv = BusinessDayConvention.new("F")
        cls.hol_conv = HolidayConvention.new("USGS")
        cls.vpc = ValuationParametersCollection([])

    def build_model_with_bump(self, component_ifr_name: str, epsilon: float):
        ifr_frames = {
            "USD-SOFR-OIS-1B-IFR": self.sofr_ifr,
            "USD-SOFR-OIS-1B-FLAT-IFR": self.flat_ifr,
            "USD-LIBOR-3M-IFR": self.libor_ifr,
        }
        bumped = []
        for name, df in ifr_frames.items():
            df_i = df.copy()
            if name == component_ifr_name:
                df_i["values"] = df_i["values"] + epsilon
            bumped.append(qfCreateData1D(self.data_type, name, df_i))
        data_collection_bumped = qfCreateDataCollection(bumped)
        return qfCreateModel(self.value_date, "YIELD_CURVE", data_collection_bumped, self.build_method_collection)

    # --- Test 1: fully forward-looking compound period, SPREAD_EXCLUSIVE_COMPOUND ---
    # Two native 3M periods, both starting after value_date, so both resets are curve-implied
    # (value_h == 0). Compare .value against an independently-computed closed-form geometric
    # compound built directly from yc_usd.discount_factor.

    def test_01_fully_forward_looking_compound_period_matches_closed_form(self):
        s1 = Date("2026-07-06")
        t1 = add_period(s1, self.native_term, self.biz_conv, self.hol_conv)
        e1 = add_period(t1, self.native_term, self.biz_conv, self.hol_conv)

        idx_1 = AnchoredCompoundIborIndex(
            s1,
            e1,
            self.libor_index,
            CompoundingMethod("spread_exclusive_compound"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )
        self.assertEqual(idx_1.num_periods, 2)

        engine_1 = ValuationEngineAnalyticsCompoundIborIndex(self.yc_usd, idx_1, self.vpc)
        engine_1.calculate_value()

        self.assertIsInstance(engine_1.value, torch.Tensor)
        self.assertTrue(engine_1.value.requires_grad)
        self.assertEqual(float(engine_1.value_h), 0.0)

        expected_1 = closed_form_spread_exclusive_compound(
            [s1, t1, e1], self.libor_index, self.yc_usd, self.biz_conv, self.hol_conv
        )
        self.assertAlmostEqual(float(engine_1.value.detach()), float(expected_1.detach()), delta=1e-10)

    # --- Test 2: fully historical (matured) compound period, FLAT_COMPOUND ---
    # Two native 3M periods ending well before value_date, with a flat 4.25% historical fixing
    # series, so the whole compound is realized (value_f == 0). Compare .value against an
    # independently-computed closed-form recursive compound,
    # amount_i = alpha_i * L_i * (1 + amount_{i-1}).

    def test_02_fully_historical_matured_period_flat_compound(self):
        s2 = Date("2025-11-01")
        m2 = add_period(s2, self.native_term, self.biz_conv, self.hol_conv)
        e2 = add_period(m2, self.native_term, self.biz_conv, self.hol_conv)

        flat_fixings = {}
        d = Date("2025-10-25")
        while d <= Date("2025-11-04"):
            if self.hol_conv.isBusinessDay(d):
                flat_fixings[d] = 0.0425
            d = Date(d + 1)
        flat_fixings[s2] = 0.0425
        flat_fixings[m2] = 0.0425
        set_libor_fixings(flat_fixings)

        idx_2 = AnchoredCompoundIborIndex(
            s2,
            e2,
            self.libor_index,
            CompoundingMethod("flat_compound"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )
        self.assertEqual(idx_2.num_periods, 2)

        engine_2 = ValuationEngineAnalyticsCompoundIborIndex(self.yc_usd, idx_2, self.vpc)
        engine_2.calculate_value()

        self.assertEqual(float(engine_2.value_f), 0.0)

        tau_0 = accrued(s2, m2, idx_2.accrual_basis, self.biz_conv, self.hol_conv)
        tau_1 = accrued(m2, e2, idx_2.accrual_basis, self.biz_conv, self.hol_conv)
        amount_0 = tau_0 * 0.0425
        amount_1 = tau_1 * 0.0425 * (1.0 + amount_0)
        expected_2 = amount_1 / (tau_0 + tau_1)

        self.assertAlmostEqual(float(engine_2.value), expected_2, delta=1e-10)

    # --- Test 3: period straddling value_date, SPREAD_EXCLUSIVE_COMPOUND ---
    # Per the model doc, each calculation period's rate is pinned to a single fixing date at
    # the period's start, regardless of where value_date falls within that period. Here the
    # first 3M period starts before value_date (known, real fixing) while the second starts
    # after it (forward, curve-implied): confirms value_h, value_f, and the combination
    # formula value = ((1 + tau_h*value_h)(1 + tau_f*value_f) - 1) / tau.

    def test_03_period_straddling_value_date(self):
        s3 = Date("2026-05-01")
        m3 = add_period(s3, self.native_term, self.biz_conv, self.hol_conv)
        e3 = add_period(m3, self.native_term, self.biz_conv, self.hol_conv)
        self.assertTrue(s3 < Date(self.value_date) < m3, "value_date must fall inside the first period")

        set_libor_fixings({s3: 0.0480})

        idx_3 = AnchoredCompoundIborIndex(
            s3,
            e3,
            self.libor_index,
            CompoundingMethod("spread_exclusive_compound"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )

        engine_3 = ValuationEngineAnalyticsCompoundIborIndex(self.yc_usd, idx_3, self.vpc)
        engine_3.calculate_value()

        self.assertAlmostEqual(float(engine_3.value_h), 0.0480, delta=1e-10)

        tau_h = accrued(s3, m3, idx_3.accrual_basis, self.biz_conv, self.hol_conv)
        df_m3 = self.yc_usd.discount_factor(self.libor_index, m3, calc_grad=True)
        df_e3 = self.yc_usd.discount_factor(self.libor_index, e3, calc_grad=True)
        tau_f = accrued(m3, e3, idx_3.accrual_basis, self.biz_conv, self.hol_conv)
        expected_value_f = (df_m3 / df_e3 - 1.0) / tau_f
        self.assertAlmostEqual(
            float(engine_3.value_f.detach()), float(expected_value_f.detach()), delta=1e-10
        )

        tau_total = tau_h + tau_f
        combined = (
            (1.0 + tau_h * engine_3.value_h) * (1.0 + tau_f * engine_3.value_f) - 1.0
        ) / tau_total
        self.assertAlmostEqual(float(engine_3.value.detach()), float(combined.detach()), delta=1e-10)

    # --- Test 4: rate cutoff ---
    # Four native 3M periods (a 1Y schedule), fully matured before value_date, with a ramping
    # daily fixing series. A rate_cutoff of 4M lands strictly between the 3rd and 4th period
    # boundaries, so it pulls the last period's observation date back to an earlier
    # (lower-fixed) date instead of its own period-start date -- the cutoff-adjusted compound
    # should therefore be strictly lower than the uncapped one.

    def test_04_rate_cutoff(self):
        s4 = Date("2025-06-01")
        bounds_4 = [s4]
        cur = s4
        for _ in range(4):
            cur = add_period(cur, self.native_term, self.biz_conv, self.hol_conv)
            bounds_4.append(cur)
        e4 = bounds_4[-1]
        self.assertTrue(Date(e4) < Date(self.value_date), "schedule must be fully matured")

        ramp_fixings = {}
        d = Date("2025-05-20")
        rate = 0.0100
        while d <= e4:
            if self.hol_conv.isBusinessDay(d):
                ramp_fixings[d] = rate
                rate += 0.0005
            d = Date(d + 1)
        set_libor_fixings(ramp_fixings)

        idx_no_cutoff = AnchoredCompoundIborIndex(
            s4,
            e4,
            self.libor_index,
            CompoundingMethod("spread_exclusive_compound"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )
        idx_with_cutoff = AnchoredCompoundIborIndex(
            s4,
            e4,
            self.libor_index,
            CompoundingMethod("spread_exclusive_compound"),
            rate_cutoff=Period("4M"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )

        engine_no_cutoff = ValuationEngineAnalyticsCompoundIborIndex(self.yc_usd, idx_no_cutoff, self.vpc)
        engine_no_cutoff.calculate_value()

        engine_with_cutoff = ValuationEngineAnalyticsCompoundIborIndex(self.yc_usd, idx_with_cutoff, self.vpc)
        engine_with_cutoff.calculate_value()

        self.assertLess(float(engine_with_cutoff.value), float(engine_no_cutoff.value))

    # --- Test 5: AnchoredCompoundIborIndex constructor validation ---
    # The constructor should reject an accrual period that isn't an integer number of full
    # native calculation periods, and reject a single-period (n == 1) schedule --
    # AnchoredIborIndex already covers that case.

    def test_05_constructor_validation(self):
        s5 = Date("2026-01-05")
        t5 = add_period(s5, self.native_term, self.biz_conv, self.hol_conv)

        # not an integer number of full 3M periods (5 extra business days past one period)
        bad_end = add_period(t5, Period("5D"), self.biz_conv, self.hol_conv)
        with self.assertRaises(AssertionError):
            AnchoredCompoundIborIndex(
                s5,
                bad_end,
                self.libor_index,
                CompoundingMethod("spread_exclusive_compound"),
                business_day_convention=self.biz_conv,
                holiday_convention=self.hol_conv,
            )

        # exactly one full period (n == 1) -- should be rejected too
        with self.assertRaises(AssertionError):
            AnchoredCompoundIborIndex(
                s5,
                t5,
                self.libor_index,
                CompoundingMethod("spread_exclusive_compound"),
                business_day_convention=self.biz_conv,
                holiday_convention=self.hol_conv,
            )

    # --- Test 6: varying per-period rates, both compounding methods ---
    # Tests 2 and 4 used a flat fixing series, which doesn't discriminate strongly between
    # compounding methods (or between correct/incorrect period ordering). Here four native 3M
    # periods get four distinct fixings (4.10%, 4.55%, 4.80%, 5.12%), fully matured, and both
    # SPREAD_EXCLUSIVE_COMPOUND and FLAT_COMPOUND are checked against independently-computed
    # closed-form values (not by re-deriving the engine's own formula) on the same
    # schedule/fixings. The two methods should also disagree with each other under varying
    # rates -- if they happened to match, that would indicate the two code paths are
    # accidentally computing the same thing.

    def test_06_varying_rates_both_compounding_methods(self):
        s6 = Date("2025-01-06")
        bounds_6 = [s6]
        cur = s6
        for _ in range(4):
            cur = add_period(cur, self.native_term, self.biz_conv, self.hol_conv)
            bounds_6.append(cur)
        e6 = bounds_6[-1]
        self.assertTrue(Date(e6) < Date(self.value_date), "schedule must be fully matured")

        varying_rates = [0.0410, 0.0455, 0.0480, 0.0512]
        set_libor_fixings({t_s: r for t_s, r in zip(bounds_6[:-1], varying_rates)})

        taus_6 = [
            accrued(t_s, t_e, self.libor_index.accrual_basis, self.biz_conv, self.hol_conv)
            for t_s, t_e in zip(bounds_6[:-1], bounds_6[1:])
        ]

        # independent closed-form references, computed without touching the engine's own code
        prod = 1.0
        for tau_i, rate_i in zip(taus_6, varying_rates):
            prod *= 1.0 + tau_i * rate_i
        expected_spread_exclusive = (prod - 1.0) / sum(taus_6)

        amount = 0.0
        for tau_i, rate_i in zip(taus_6, varying_rates):
            amount = tau_i * rate_i * (1.0 + amount)
        expected_flat = amount / sum(taus_6)

        idx_6_spread_exclusive = AnchoredCompoundIborIndex(
            s6,
            e6,
            self.libor_index,
            CompoundingMethod("spread_exclusive_compound"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )
        idx_6_flat = AnchoredCompoundIborIndex(
            s6,
            e6,
            self.libor_index,
            CompoundingMethod("flat_compound"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )

        engine_6_spread_exclusive = ValuationEngineAnalyticsCompoundIborIndex(
            self.yc_usd, idx_6_spread_exclusive, self.vpc
        )
        engine_6_spread_exclusive.calculate_value()

        engine_6_flat = ValuationEngineAnalyticsCompoundIborIndex(self.yc_usd, idx_6_flat, self.vpc)
        engine_6_flat.calculate_value()

        self.assertAlmostEqual(
            float(engine_6_spread_exclusive.value), expected_spread_exclusive, delta=1e-10
        )
        self.assertAlmostEqual(float(engine_6_flat.value), expected_flat, delta=1e-10)
        self.assertGreater(
            abs(float(engine_6_spread_exclusive.value) - float(engine_6_flat.value)), 1e-6
        )

    # --- Test 7: gradient flow (.value is genuinely torch-differentiable end to end) ---
    # A fully forward-looking period's .value should carry a working autograd graph back to
    # the curve's own state data, not just a requires_grad=True flag with a dead graph. Calling
    # .backward() and harvesting yc_usd.get_gradient() should show a nonzero gradient in the
    # USD-LIBOR-BBA-3M projection component's state data block -- and, as a bonus correctness
    # check, exactly zero gradient in the SOFR-1B / SOFR-1B-FLAT discounting-curve blocks,
    # since a plain forward LIBOR rate is a ratio of discount factors off the same curve and
    # the discounting/funding leg cancels out of that ratio entirely.

    def test_07_gradient_flow(self):
        s7 = Date("2026-07-06")
        t7 = add_period(s7, self.native_term, self.biz_conv, self.hol_conv)
        e7 = add_period(t7, self.native_term, self.biz_conv, self.hol_conv)

        idx_7 = AnchoredCompoundIborIndex(
            s7,
            e7,
            self.libor_index,
            CompoundingMethod("spread_exclusive_compound"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )
        engine_7 = ValuationEngineAnalyticsCompoundIborIndex(self.yc_usd, idx_7, self.vpc)
        engine_7.calculate_value()
        engine_7.value.backward()

        grad = self.yc_usd.get_gradient(reset=True)
        offsets = np.cumsum([0] + self.yc_usd.gradient_lengths_)
        blocks = {
            name: grad[offsets[i] : offsets[i + 1]]
            for i, name in enumerate(self.yc_usd.component_order_)
        }

        self.assertTrue(
            np.any(np.abs(blocks["USD-LIBOR-BBA-3M"]) > 0),
            "expected a nonzero gradient in the LIBOR projection block",
        )
        self.assertTrue(
            np.all(blocks["SOFR-1B"] == 0.0), "discounting curve should cancel out of a plain forward rate"
        )
        self.assertTrue(
            np.all(blocks["SOFR-1B-FLAT"] == 0.0),
            "discounting curve should cancel out of a plain forward rate",
        )

    # --- Test 8: gradient correctness across all three anchored index types ---
    # Test 7 only checked *where* the gradient is nonzero/zero. These check the *magnitude*,
    # via a finite-difference (parallel-bump) check against the analytic autograd gradient,
    # for all three engines. Since our test curves are flat (a single repeated IFR value
    # across tenors), bumping every node of a curve by the same epsilon is a parallel shift --
    # the finite-difference estimate (value(bumped) - value(base)) / epsilon should equal the
    # sum of the analytic gradient over that curve's whole state-data block. Each sub-test also
    # asserts the gradient is exactly zero in the other curves' blocks: with this particular
    # build (YC_IBOR_ELEMENT given no REFERENCE INDEX), USD-LIBOR-BBA-3M has no dependency edge
    # on SOFR-1B/SOFR-1B-FLAT at all, and SOFR-1B itself has no reference either -- so each
    # engine's gradient should be confined to its own curve's block, not just numerically small
    # elsewhere.

    EPS = 1e-6
    GRAD_TOL = 1e-4

    def test_08a_gradient_correctness_ibor_index(self):
        s8a = Date("2026-07-06")
        e8a = add_period(s8a, self.native_term, self.biz_conv, self.hol_conv)
        idx_8a = AnchoredIborIndex(
            s8a,
            e8a,
            self.libor_index,
            CompoundingMethod("simple"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )

        engine_8a = ValuationEngineAnalyticsIborIndex(self.yc_usd, idx_8a, self.vpc)
        engine_8a.calculate_value()
        base_8a = float(engine_8a.value.detach())
        engine_8a.value.backward()
        grad_8a = self.yc_usd.get_gradient(reset=True)
        libor_block_8a = gradient_block(self.yc_usd, grad_8a, "USD-LIBOR-BBA-3M")
        sofr_block_8a = gradient_block(self.yc_usd, grad_8a, "SOFR-1B")

        yc_bumped_8a = self.build_model_with_bump("USD-LIBOR-3M-IFR", self.EPS)
        engine_8a_bumped = ValuationEngineAnalyticsIborIndex(yc_bumped_8a, idx_8a, self.vpc)
        engine_8a_bumped.calculate_value()
        fd_8a = (float(engine_8a_bumped.value.detach()) - base_8a) / self.EPS
        analytic_8a = float(np.sum(libor_block_8a))

        self.assertLess(abs(fd_8a - analytic_8a), self.GRAD_TOL)
        self.assertTrue(np.all(sofr_block_8a == 0.0))

    def test_08b_gradient_correctness_overnight_index(self):
        s8b = Date("2026-07-06")
        e8b = add_period(s8b, Period("1M"), self.biz_conv, self.hol_conv)
        idx_8b = AnchoredOvernightIndex(
            s8b,
            e8b,
            self.overnight_index,
            CompoundingMethod("compound"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )

        engine_8b = ValuationEngineAnalyticsCompositeIndex(self.yc_usd, idx_8b, self.vpc)
        engine_8b.calculate_value()
        base_8b = float(engine_8b.value.detach())
        engine_8b.value.backward()
        grad_8b = self.yc_usd.get_gradient(reset=True)
        sofr_block_8b = gradient_block(self.yc_usd, grad_8b, "SOFR-1B")
        libor_block_8b = gradient_block(self.yc_usd, grad_8b, "USD-LIBOR-BBA-3M")
        flat_block_8b = gradient_block(self.yc_usd, grad_8b, "SOFR-1B-FLAT")

        yc_bumped_8b = self.build_model_with_bump("USD-SOFR-OIS-1B-IFR", self.EPS)
        engine_8b_bumped = ValuationEngineAnalyticsCompositeIndex(yc_bumped_8b, idx_8b, self.vpc)
        engine_8b_bumped.calculate_value()
        fd_8b = (float(engine_8b_bumped.value.detach()) - base_8b) / self.EPS
        analytic_8b = float(np.sum(sofr_block_8b))

        self.assertLess(abs(fd_8b - analytic_8b), self.GRAD_TOL)
        self.assertTrue(np.all(libor_block_8b == 0.0))
        self.assertTrue(np.all(flat_block_8b == 0.0))

    def test_08c_gradient_correctness_compound_ibor_index(self):
        s8c = Date("2026-07-06")
        t8c = add_period(s8c, self.native_term, self.biz_conv, self.hol_conv)
        e8c = add_period(t8c, self.native_term, self.biz_conv, self.hol_conv)

        yc_bumped_8c = self.build_model_with_bump("USD-LIBOR-3M-IFR", self.EPS)

        for method_name in ["spread_exclusive_compound", "flat_compound"]:
            idx_8c = AnchoredCompoundIborIndex(
                s8c,
                e8c,
                self.libor_index,
                CompoundingMethod(method_name),
                business_day_convention=self.biz_conv,
                holiday_convention=self.hol_conv,
            )

            engine_8c = ValuationEngineAnalyticsCompoundIborIndex(self.yc_usd, idx_8c, self.vpc)
            engine_8c.calculate_value()
            base_8c = float(engine_8c.value.detach())
            engine_8c.value.backward()
            grad_8c = self.yc_usd.get_gradient(reset=True)
            libor_block_8c = gradient_block(self.yc_usd, grad_8c, "USD-LIBOR-BBA-3M")
            sofr_block_8c = gradient_block(self.yc_usd, grad_8c, "SOFR-1B")

            engine_8c_bumped = ValuationEngineAnalyticsCompoundIborIndex(yc_bumped_8c, idx_8c, self.vpc)
            engine_8c_bumped.calculate_value()
            fd_8c = (float(engine_8c_bumped.value.detach()) - base_8c) / self.EPS
            analytic_8c = float(np.sum(libor_block_8c))

            self.assertLess(abs(fd_8c - analytic_8c), self.GRAD_TOL, msg=f"method={method_name}")
            self.assertTrue(np.all(sofr_block_8c == 0.0), msg=f"method={method_name}")

    # --- Test 9: ValuationEngineAnalyticsIborIndex (single-period IBOR) ---
    # calculate_value only handles the common, market-traded tenor directly (the anchored
    # period's tau equals the underlying index's own native term). An irregular
    # (stub/extended) period is delegated to _calculate_irregular_period_value, which brackets
    # the requested tenor with whichever native IBOR tenors the model actually has calibrated
    # for that index's family, gets each bracketing tenor's own rate via a circular call back
    # into calculate_value, and interpolates purely on rates (never on discount factors) using
    # the interpolation/extrapolation method carried on the ValuationParametersCollection.
    #
    # 9a exercises the common-tenor path (forward-looking and historical) on the existing
    # 3M-only yc_usd curve. 9b builds a small 1M/3M/6M LIBOR family curve and exercises the
    # irregular-tenor path: linear interpolation strictly between two calibrated tenors, and
    # flat extrapolation past the longest one.

    def test_09a_common_tenor_forward_and_historical(self):
        s9a = Date("2026-07-06")
        e9a = add_period(s9a, self.native_term, self.biz_conv, self.hol_conv)

        idx_9a_fwd = AnchoredIborIndex(
            s9a,
            e9a,
            self.libor_index,
            CompoundingMethod("simple"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )
        engine_9a_fwd = ValuationEngineAnalyticsIborIndex(self.yc_usd, idx_9a_fwd, self.vpc)
        engine_9a_fwd.calculate_value()

        tau_9a = accrued(s9a, e9a, idx_9a_fwd.accrual_basis, self.biz_conv, self.hol_conv)
        df_s9a = self.yc_usd.discount_factor(self.libor_index, s9a, calc_grad=True)
        df_e9a = self.yc_usd.discount_factor(self.libor_index, e9a, calc_grad=True)
        expected_9a_fwd = (df_s9a / df_e9a - 1.0) / tau_9a

        self.assertAlmostEqual(
            float(engine_9a_fwd.value.detach()), float(expected_9a_fwd.detach()), delta=1e-10
        )
        self.assertEqual(float(engine_9a_fwd.value_h), 0.0)

        s9a_hist = Date("2025-11-01")
        e9a_hist = add_period(s9a_hist, self.native_term, self.biz_conv, self.hol_conv)
        # for a from_ql index (USD-LIBOR-BBA-3M is), the engine looks up the fixing at the
        # index's own native QuantLib fixingDate (e.g. the real T-2 LIBOR settlement lag), not
        # a plain look_back_window subtraction -- seed at that exact date so the lookup finds
        # it. A non-from_ql index would instead use subtract_period(start_date,
        # idx.look_back_window, bdc, hol).
        self.assertTrue(self.libor_index.from_ql)
        fixing_date_9a = self.libor_index.fixingDate(s9a_hist)
        set_libor_fixings({fixing_date_9a: 0.0495})

        idx_9a_hist = AnchoredIborIndex(
            s9a_hist,
            e9a_hist,
            self.libor_index,
            CompoundingMethod("simple"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )
        engine_9a_hist = ValuationEngineAnalyticsIborIndex(self.yc_usd, idx_9a_hist, self.vpc)
        engine_9a_hist.calculate_value()

        self.assertAlmostEqual(float(engine_9a_hist.value), 0.0495, delta=1e-10)
        self.assertEqual(float(engine_9a_hist.value_f), 0.0)

    def test_09b_irregular_tenor_interpolation_and_extrapolation(self):
        # build a small 1M/3M/6M LIBOR family curve -- USD-LIBOR-BBA-1M/-3M/-6M are all already
        # registered in static_files/indices.yaml, so no new indices are needed, just three
        # more YC_IBOR_ELEMENT build methods, one per tenor, each calibrated off its own flat
        # INSTANTANEOUS FORWARD RATE (distinct rates per tenor so an interpolated result is
        # visibly different from either endpoint).
        DataConventionRegistry().register(
            "USD-LIBOR-BBA-1M-IFR",
            {"type": "INSTANTANEOUS FORWARD RATE", "convention": {"index": "USD-LIBOR-BBA-1M"}},
        )
        DataConventionRegistry().register(
            "USD-LIBOR-BBA-6M-IFR",
            {"type": "INSTANTANEOUS FORWARD RATE", "convention": {"index": "USD-LIBOR-BBA-6M"}},
        )

        bm_list_multi = [
            qfCreateBuildMethod(
                "YC_OVERNIGHT_INDEX_ELEMENT",
                {"TARGET": "SOFR-1B", "INSTANTANEOUS FORWARD RATE": "USD-SOFR-OIS-1B-IFR"},
            ),
            qfCreateBuildMethod(
                "YC_FUNDING_ELEMENT",
                {
                    "TARGET": "SOFR-1B-FLAT",
                    "REFERENCE": "SOFR-1B",
                    "INSTANTANEOUS FORWARD RATE": "USD-SOFR-OIS-1B-FLAT-IFR",
                },
            ),
            qfCreateBuildMethod(
                "YC_IBOR_ELEMENT",
                {"TARGET": "USD-LIBOR-BBA-1M", "INSTANTANEOUS FORWARD RATE": "USD-LIBOR-BBA-1M-IFR"},
            ),
            qfCreateBuildMethod(
                "YC_IBOR_ELEMENT",
                {"TARGET": "USD-LIBOR-BBA-3M", "INSTANTANEOUS FORWARD RATE": "USD-LIBOR-3M-IFR"},
            ),
            qfCreateBuildMethod(
                "YC_IBOR_ELEMENT",
                {"TARGET": "USD-LIBOR-BBA-6M", "INSTANTANEOUS FORWARD RATE": "USD-LIBOR-BBA-6M-IFR"},
            ),
            qfCreateBuildMethod(
                "YC_COMMON",
                {"TARGET": "USD", "FUNDING PARAMETERS": "SOFR-1B-FLAT", "SOLVER METHOD": "BRENT"},
            ),
        ]
        build_method_collection_multi = qfCreateModelBuildMethodCollection(bm_list_multi)

        libor_1m_ifr = pd.DataFrame(index=self.tenors)
        libor_1m_ifr["values"] = [0.0470] * len(self.tenors)  # flat 4.70% IFR curve

        libor_6m_ifr = pd.DataFrame(index=self.tenors)
        libor_6m_ifr["values"] = [0.0530] * len(self.tenors)  # flat 5.30% IFR curve

        data_collection_multi = qfCreateDataCollection(
            [
                qfCreateData1D(self.data_type, "USD-SOFR-OIS-1B-IFR", self.sofr_ifr),
                qfCreateData1D(self.data_type, "USD-SOFR-OIS-1B-FLAT-IFR", self.flat_ifr),
                qfCreateData1D(self.data_type, "USD-LIBOR-BBA-1M-IFR", libor_1m_ifr),
                qfCreateData1D(self.data_type, "USD-LIBOR-3M-IFR", self.libor_ifr),
                qfCreateData1D(self.data_type, "USD-LIBOR-BBA-6M-IFR", libor_6m_ifr),
            ]
        )

        yc_usd_multi = qfCreateModel(
            self.value_date, "YIELD_CURVE", data_collection_multi, build_method_collection_multi
        )
        libor_6m_index = IndexRegistry().get("USD-LIBOR-BBA-6M")

        vpc_linear = ValuationParametersCollection(
            [
                AnalyticValParam(
                    {"INTERPOLATION METHOD": "LINEAR", "EXTRAPOLATION METHOD": "FLAT"}
                )
            ]
        )

        def native_rate(model, index, start_date, biz_conv, hol_conv):
            end_date = add_period(start_date, index.term, biz_conv, hol_conv)
            tau = accrued(start_date, end_date, index.accrual_basis, biz_conv, hol_conv)
            df_s = model.discount_factor(index, start_date, calc_grad=True)
            df_e = model.discount_factor(index, end_date, calc_grad=True)
            return tau, float((df_s / df_e - 1.0).detach() / tau)

        s9b = Date("2026-07-06")
        tau_3m, rate_3m = native_rate(yc_usd_multi, self.libor_index, s9b, self.biz_conv, self.hol_conv)
        tau_6m, rate_6m = native_rate(yc_usd_multi, libor_6m_index, s9b, self.biz_conv, self.hol_conv)

        # strictly between the 3M and 6M native tenors -- should linearly blend their rates
        idx_9b_interp = AnchoredIborIndex(
            s9b,
            Period("4M"),
            self.libor_index,
            CompoundingMethod("simple"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )
        engine_9b_interp = ValuationEngineAnalyticsIborIndex(yc_usd_multi, idx_9b_interp, vpc_linear)
        engine_9b_interp.calculate_value()

        e9b_interp = add_period(s9b, Period("4M"), self.biz_conv, self.hol_conv)
        tau_req = accrued(s9b, e9b_interp, idx_9b_interp.accrual_basis, self.biz_conv, self.hol_conv)
        expected_interp = rate_3m + (rate_6m - rate_3m) * (tau_req - tau_3m) / (tau_6m - tau_3m)

        self.assertAlmostEqual(float(engine_9b_interp.value), expected_interp, delta=1e-10)
        self.assertTrue(rate_3m < float(engine_9b_interp.value) < rate_6m)

        # beyond the longest available tenor (6M) -- should flat-extrapolate to the 6M rate
        idx_9b_extrap = AnchoredIborIndex(
            s9b,
            Period("9M"),
            self.libor_index,
            CompoundingMethod("simple"),
            business_day_convention=self.biz_conv,
            holiday_convention=self.hol_conv,
        )
        engine_9b_extrap = ValuationEngineAnalyticsIborIndex(yc_usd_multi, idx_9b_extrap, vpc_linear)
        engine_9b_extrap.calculate_value()

        self.assertAlmostEqual(float(engine_9b_extrap.value), rate_6m, delta=1e-10)


if __name__ == "__main__":
    unittest.main()

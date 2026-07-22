"""
Level 1 (building-blocks) correctness tests for the `Index` static-data layer:
`IBORIndex`, `OvernightIndex`, `OvernightCompositeIndex`, `FXIndex`
(fixedincomelib/market/indices.py), dispatched via `IndexRegistry`
(fixedincomelib/market/indices.py / fixedincomelib/utilities/utils.py).

unittest.TestCase conversion of tests/0_1_test_indices_fi_fixings.ipynb, per
.claude/skills/test_building_blocks.md section 1 ("Static data instances").

pytest auto-discoverable (test_*.py, unlike tests/unittest_interpolator.py which is
deliberately named to be excluded from auto-discovery).
"""

import sys
import os
import unittest

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath('..'))

import yaml
import QuantLib as ql

from fixedincomelib import *
from fixedincomelib.market.indices import (
    IBORIndex, OvernightIndex, OvernightCompositeIndex, FXIndex,
)
from fixedincomelib.market.basics import (
    Currency, BusinessDayConvention, HolidayConvention, AccrualBasis, CompoundingMethod,
)
from fixedincomelib.date.basics import Period


def assert_raises(exc_type, fn, *args, **kwargs):
    """Mirrors the notebook's assert_raises helper for the construction-contract tests."""
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:
        raise AssertionError(f"expected {exc_type}, got {type(e)}: {e}")
    raise AssertionError(f"expected {exc_type}, but construction succeeded")


class IndexFixturesTestCase(unittest.TestCase):
    """
    Shared fixture base: loads the process-wide IndexRegistry singleton and an
    independently-parsed copy of static_files/indices.yaml once per test run
    (cwd is already tests/, set at module import time above).
    """

    @classmethod
    def setUpClass(cls):
        cls.registry = IndexRegistry()
        with open("../static_files/indices.yaml", "r") as f:
            cls.raw_indices = yaml.safe_load(f)


# ---------------------------------------------------------------------------
# 1. IndexRegistry is a process-wide singleton, loaded from static_files/indices.yaml
# ---------------------------------------------------------------------------

class TestIndexRegistrySingleton(IndexFixturesTestCase):

    def test_singleton_identity(self):
        self.assertIs(IndexRegistry(), IndexRegistry())

    def test_yaml_source_nonempty(self):
        self.assertGreater(len(self.raw_indices), 0)


# ---------------------------------------------------------------------------
# 2. Subclass dispatch matches the yaml `type` field, for every entry in indices.yaml
# ---------------------------------------------------------------------------

class TestSubclassDispatch(IndexFixturesTestCase):

    EXPECTED_CLASS = {
        "IBOR INDEX": IBORIndex,
        "OVERNIGHT INDEX": OvernightIndex,
        "OVERNIGHT COMPOSITE INDEX": OvernightCompositeIndex,
        "FX INDEX": FXIndex,
    }

    def test_subclass_dispatch_all_yaml_entries(self):
        seen_types = set()
        for name, content in self.raw_indices.items():
            yaml_type = content["type"]
            seen_types.add(yaml_type)
            obj = self.registry.get(name)
            with self.subTest(name=name):
                self.assertIsInstance(
                    obj, self.EXPECTED_CLASS[yaml_type],
                    f"{name}: expected {self.EXPECTED_CLASS[yaml_type]}, got {type(obj)}",
                )
                self.assertEqual(
                    obj.type(), yaml_type,
                    f"{name}: .type() = {obj.type()!r} != yaml type {yaml_type!r}",
                )
                self.assertEqual(
                    obj.index_name(), name.upper(),
                    f"{name}: .index_name() = {obj.index_name()!r} != {name.upper()!r}",
                )
        # sanity: we actually exercised all four subclasses, not e.g. an empty/degenerate yaml
        self.assertEqual(seen_types, set(self.EXPECTED_CLASS.keys()))


# ---------------------------------------------------------------------------
# 3. Property types are domain objects, not raw strings
# ---------------------------------------------------------------------------
#
# Note a real subtlety (not a bug): on the `from_ql` branch, IBORIndex.currency /
# OvernightIndex.currency come straight from the wrapped QuantLib index's own
# `.currency()` call, so they're a bare `ql.Currency`, not the fixedincomelib
# `Currency` subclass. On the explicit-convention branch (and for FXIndex, which is
# always explicit-only), `.currency` / `.base_ccy` / `.quoted_ccy` / `.premium_ccy` are
# constructed via `Currency(v)` and so *are* the wrapper subclass. Both are always at
# least `ql.Currency`, which is the invariant every downstream caller can rely on; the
# tests below check both the universal (ql.Currency) and per-branch (Currency subclass)
# contracts explicitly so this distinction doesn't silently regress either way.

class TestPropertyTypes(IndexFixturesTestCase):

    def test_property_types_ibor_from_ql(self):
        ibor_ql = self.registry.get("USD-LIBOR-BBA-3M")
        self.assertIsInstance(ibor_ql, IBORIndex)
        self.assertIsInstance(ibor_ql.currency, ql.Currency)
        self.assertIsInstance(ibor_ql.term, Period)
        self.assertIsInstance(ibor_ql.term, ql.Period)
        self.assertIsInstance(ibor_ql.accrual_basis, ql.DayCounter)
        self.assertIsInstance(ibor_ql.payment_business_day_conv, int)
        self.assertIn(ibor_ql.payment_business_day_conv, BusinessDayConvention.BDC_MAP.values())
        self.assertIsInstance(ibor_ql.payment_holiday_conv, ql.Calendar)
        self.assertIsInstance(ibor_ql.end_of_month, bool)

    def test_property_types_ibor_explicit(self):
        ibor_explicit = self.registry.get("USD-TERM-SOFR-PROXY-1M")
        self.assertIsInstance(ibor_explicit, IBORIndex)
        self.assertIsInstance(ibor_explicit.currency, Currency)  # explicit branch: wrapper subclass
        self.assertIsInstance(ibor_explicit.currency, ql.Currency)
        self.assertIsInstance(ibor_explicit.term, Period)
        self.assertIsInstance(ibor_explicit.accrual_basis, ql.DayCounter)
        self.assertIsInstance(ibor_explicit.payment_business_day_conv, int)
        self.assertIsInstance(ibor_explicit.payment_holiday_conv, ql.Calendar)
        self.assertIsInstance(ibor_explicit.settlement_offset, Period)

    def test_property_types_overnight_from_ql(self):
        on_ql = self.registry.get("SOFR-1B")
        self.assertIsInstance(on_ql, OvernightIndex)
        self.assertIsInstance(on_ql.currency, ql.Currency)
        self.assertIsInstance(on_ql.term, Period)
        self.assertIsInstance(on_ql.accrual_basis, ql.DayCounter)
        self.assertIsInstance(on_ql.payment_business_day_conv, int)
        self.assertIsInstance(on_ql.payment_holiday_conv, ql.Calendar)

    def test_property_types_overnight_explicit(self):
        on_explicit = self.registry.get("USD-Term SOFR Base-1B")
        self.assertIsInstance(on_explicit, OvernightIndex)
        self.assertIsInstance(on_explicit.currency, Currency)
        self.assertIsInstance(on_explicit.accrual_basis, ql.DayCounter)
        self.assertIsInstance(on_explicit.payment_business_day_conv, int)
        self.assertIsInstance(on_explicit.payment_holiday_conv, ql.Calendar)
        self.assertIsInstance(on_explicit.settlement_offset, Period)

    def test_property_types_overnight_composite(self):
        composite = self.registry.get("USD-SOFR-COMPOUND")
        self.assertIsInstance(composite, OvernightCompositeIndex)
        self.assertIsInstance(composite.index, OvernightIndex)
        self.assertIsInstance(composite.compounding_method, CompoundingMethod)
        self.assertIsInstance(composite.currency, ql.Currency)
        self.assertIsInstance(composite.accrual_basis, ql.DayCounter)
        self.assertIsInstance(composite.payment_business_day_conv, int)
        self.assertIsInstance(composite.payment_holiday_conv, ql.Calendar)

    def test_property_types_fx(self):
        fx = self.registry.get("GBP-USD")
        self.assertIsInstance(fx, FXIndex)
        self.assertIsInstance(fx.base_ccy, Currency)
        self.assertIsInstance(fx.base_ccy, ql.Currency)
        self.assertIsInstance(fx.quoted_ccy, Currency)
        self.assertIsInstance(fx.premium_ccy, Currency)
        self.assertIsInstance(fx.base_business_day_conv, int)
        self.assertIsInstance(fx.quoted_business_day_conv, int)
        self.assertIsInstance(fx.base_holidays, ql.Calendar)
        self.assertIsInstance(fx.quoted_holidays, ql.Calendar)
        self.assertIsInstance(fx.base_fixing_offset, Period)
        self.assertIsInstance(fx.quoted_fixing_offset, Period)


# ---------------------------------------------------------------------------
# 4. Round-trip against the yaml source -- from_ql branch
# ---------------------------------------------------------------------------
#
# For entries where `convention` is a bare QuantLib index name (a str), the independent
# oracle is the QuantLib object itself: constructing e.g. ql.USDLibor(Period("3M"))
# directly and comparing its native properties against what IBORIndex/OvernightIndex
# populated.

class TestRoundTripFromQl(IndexFixturesTestCase):

    def test_round_trip_ibor_from_ql_usd_libor_3m(self):
        self.assertIsInstance(self.raw_indices["USD-LIBOR-BBA-3M"]["convention"], str)
        ibor_ql = self.registry.get("USD-LIBOR-BBA-3M")
        oracle_ibor = ql.USDLibor(ql.Period("3M"))
        self.assertEqual(ibor_ql.currency.code(), oracle_ibor.currency().code())
        self.assertEqual(oracle_ibor.currency().code(), "USD")
        self.assertEqual(ibor_ql.term, Period("3M"))
        self.assertEqual(ibor_ql.accrual_basis, oracle_ibor.dayCounter())
        self.assertEqual(ibor_ql.payment_business_day_conv, oracle_ibor.businessDayConvention())
        self.assertEqual(ibor_ql.payment_holiday_conv, oracle_ibor.fixingCalendar())
        self.assertEqual(ibor_ql.end_of_month, oracle_ibor.endOfMonth())
        self.assertTrue(ibor_ql.from_ql)

    def test_round_trip_overnight_from_ql_sofr(self):
        self.assertIsInstance(self.raw_indices["SOFR-1B"]["convention"], str)
        on_ql = self.registry.get("SOFR-1B")
        oracle_on = ql.Sofr()
        self.assertEqual(on_ql.currency.code(), oracle_on.currency().code())
        self.assertEqual(oracle_on.currency().code(), "USD")
        self.assertEqual(on_ql.term, Period("1D"))
        self.assertEqual(on_ql.accrual_basis, oracle_on.dayCounter())
        self.assertEqual(on_ql.payment_business_day_conv, oracle_on.businessDayConvention())
        self.assertEqual(on_ql.payment_holiday_conv, oracle_on.fixingCalendar())
        self.assertTrue(on_ql.from_ql)

    def test_round_trip_ibor_from_ql_gbp_libor_6m(self):
        # a second currency/index family, to make sure this isn't a USD-only coincidence
        self.assertIsInstance(self.raw_indices["GBP-LIBOR-BBA-6M"]["convention"], str)
        gbp_ibor = self.registry.get("GBP-LIBOR-BBA-6M")
        oracle_gbp = ql.GBPLibor(ql.Period("6M"))
        self.assertEqual(gbp_ibor.currency.code(), "GBP")
        self.assertEqual(gbp_ibor.accrual_basis, oracle_gbp.dayCounter())
        self.assertEqual(gbp_ibor.payment_business_day_conv, oracle_gbp.businessDayConvention())
        self.assertEqual(gbp_ibor.payment_holiday_conv, oracle_gbp.fixingCalendar())


# ---------------------------------------------------------------------------
# 5. Round-trip against the yaml source -- explicit-convention branch
# ---------------------------------------------------------------------------
#
# For entries where `convention` is an explicit dict, the independent oracle is the
# yaml text itself, re-parsed and pushed through the .new(...) convention factories
# directly (not the IBORIndex/OvernightIndex/FXIndex constructors under test). Note
# `term` is a top-level key on the entry (sibling of `convention`), not nested inside
# `convention` itself.

class TestRoundTripExplicit(IndexFixturesTestCase):

    def test_round_trip_ibor_explicit_term_sofr_proxy(self):
        entry = self.raw_indices["USD-TERM-SOFR-PROXY-1M"]
        conv = entry["convention"]
        self.assertIsInstance(conv, dict)
        obj = self.registry.get("USD-TERM-SOFR-PROXY-1M")
        self.assertFalse(obj.from_ql)
        self.assertEqual(obj.currency.code(), Currency(conv["currency"]).code())
        self.assertEqual(Currency(conv["currency"]).code(), "USD")
        self.assertEqual(obj.term, Period(entry["term"]))
        self.assertEqual(obj.accrual_basis, AccrualBasis.new(conv["accrual basis"]))
        self.assertEqual(
            obj.payment_business_day_conv,
            BusinessDayConvention.new(conv["payment businessday convention"]),
        )
        self.assertEqual(
            obj.payment_holiday_conv, HolidayConvention.new(conv["payment holiday convention"])
        )
        self.assertEqual(obj.end_of_month, bool(conv["end of month"]))
        self.assertEqual(obj.settlement_offset, Period(conv["settlement offset"]))
        self.assertEqual(obj.settlement_holiday, HolidayConvention.new(conv["settlement holiday"]))

    def test_round_trip_overnight_explicit_term_sofr_base(self):
        conv2 = self.raw_indices["USD-Term SOFR Base-1B"]["convention"]
        self.assertIsInstance(conv2, dict)
        obj2 = self.registry.get("USD-Term SOFR Base-1B")
        self.assertFalse(obj2.from_ql)
        self.assertEqual(obj2.currency.code(), "USD")
        self.assertEqual(obj2.accrual_basis, AccrualBasis.new(conv2["accrual basis"]))
        self.assertEqual(
            obj2.payment_business_day_conv,
            BusinessDayConvention.new(conv2["payment businessday convention"]),
        )
        self.assertEqual(
            obj2.payment_holiday_conv, HolidayConvention.new(conv2["payment holiday convention"])
        )
        self.assertEqual(obj2.settlement_offset, Period(conv2["settlement offset"]))
        self.assertEqual(obj2.settlement_holiday, HolidayConvention.new(conv2["settlement holiday"]))

    def test_round_trip_fx_explicit_gbp_usd(self):
        # FXIndex (always explicit): GBP-USD -- payment holiday conv is a *joint* calendar (LON,NYC)
        conv_fx = self.raw_indices["GBP-USD"]["convention"]
        fx = self.registry.get("GBP-USD")
        self.assertEqual(fx.base_ccy.code(), Currency(conv_fx["base currency"]).code())
        self.assertEqual(Currency(conv_fx["base currency"]).code(), "GBP")
        self.assertEqual(
            fx.base_business_day_conv, BusinessDayConvention.new(conv_fx["base businessday convention"])
        )
        self.assertEqual(fx.base_holidays, HolidayConvention.new(conv_fx["base holidays"]))
        self.assertEqual(fx.base_fixing_offset, Period(conv_fx["base fixing offset"]))
        self.assertEqual(fx.quoted_ccy.code(), "USD")
        self.assertEqual(
            fx.quoted_business_day_conv,
            BusinessDayConvention.new(conv_fx["quoted businessday convention"]),
        )
        # assert the yaml's "LON,NYC" really produced a *joint* calendar combining both,
        # not just LON
        self.assertEqual(fx.quoted_holidays, HolidayConvention.new("LON,NYC"))
        self.assertNotEqual(fx.quoted_holidays, HolidayConvention.new("LON"))
        self.assertEqual(fx.quoted_fixing_offset, Period(conv_fx["quoted fixing offset"]))
        self.assertEqual(fx.premium_ccy.code(), conv_fx["premium currency"])


# ---------------------------------------------------------------------------
# 6. from_ql flag and its effect on settlement_offset
# ---------------------------------------------------------------------------
#
# A real corner case in IBORIndex.__init__/OvernightIndex.__init__: on the from_ql
# branch, upper_content["SETTLEMENT OFFSET"] is set to the *display* string
# "NOT_USED"/"NOT USED", but self.settlement_offset_ itself is never assigned on that
# branch and stays at its None default. So .settlement_offset is None for
# from_ql-constructed indices even though the constructor never errors -- assert this
# is exactly what happens, not that it's simply unset or defaults to some sentinel
# Period.

class TestFromQlSettlementOffset(IndexFixturesTestCase):

    def test_from_ql_ibor_settlement_offset_is_none(self):
        ibor_ql = self.registry.get("USD-LIBOR-BBA-3M")
        self.assertTrue(ibor_ql.from_ql)
        self.assertIsNone(ibor_ql.settlement_offset)

    def test_from_ql_overnight_settlement_offset_is_none(self):
        on_ql = self.registry.get("SOFR-1B")
        self.assertTrue(on_ql.from_ql)
        self.assertIsNone(on_ql.settlement_offset)

    def test_explicit_settlement_offset_populated(self):
        ibor_explicit = self.registry.get("USD-TERM-SOFR-PROXY-1M")
        self.assertFalse(ibor_explicit.from_ql)
        self.assertIsInstance(ibor_explicit.settlement_offset, Period)
        self.assertEqual(ibor_explicit.settlement_offset, Period("2D"))


# ---------------------------------------------------------------------------
# 7. OvernightCompositeIndex delegation
# ---------------------------------------------------------------------------
#
# OvernightCompositeIndex.index resolves self.index_ (the raw yaml string) through
# IndexRegistry().get(...) lazily via the property, and every other property
# (currency/accrual_basis/payment_business_day_conv/payment_holiday_conv/from_ql)
# delegates to that resolved index rather than storing its own copy.

class TestOvernightCompositeDelegation(IndexFixturesTestCase):

    def test_compound_delegates_to_underlying_sofr_1b(self):
        sofr_1b = self.registry.get("SOFR-1B")
        compound = self.registry.get("USD-SOFR-COMPOUND")
        self.assertIs(compound.index, sofr_1b)  # same registry object, not a re-parsed copy
        self.assertEqual(compound.compounding_method, CompoundingMethod.COMPOUND)
        self.assertIs(compound.currency, sofr_1b.currency)
        self.assertEqual(compound.accrual_basis, sofr_1b.accrual_basis)
        self.assertEqual(compound.payment_business_day_conv, sofr_1b.payment_business_day_conv)
        self.assertEqual(compound.payment_holiday_conv, sofr_1b.payment_holiday_conv)
        self.assertEqual(compound.from_ql, sofr_1b.from_ql)

    def test_average_compounding_method_arithmetic(self):
        sofr_1b = self.registry.get("SOFR-1B")
        average = self.registry.get("USD-SOFR-AVERAGE")
        self.assertIs(average.index, sofr_1b)
        self.assertEqual(average.compounding_method, CompoundingMethod.ARITHMETIC)

    def test_composite_underlying_distinct_index_entries(self):
        # SOFR-1D and SOFR-1B are deliberately distinct entries
        sofr_1b = self.registry.get("SOFR-1B")
        avg_1d = self.registry.get("USD-SOFR-AVG")
        self.assertIs(avg_1d.index, self.registry.get("SOFR-1D"))
        self.assertIsNot(avg_1d.index, sofr_1b)
        self.assertEqual(avg_1d.compounding_method, CompoundingMethod.ARITHMETIC)

    def test_composite_delegates_through_explicit_convention_underlying(self):
        # explicit-convention underlying index, to cover that branch through the composite too
        term_sofr_compound = self.registry.get("USD-Term SOFR Base-COMPOUND")
        term_sofr_base = self.registry.get("USD-Term SOFR Base-1B")
        self.assertIs(term_sofr_compound.index, term_sofr_base)
        self.assertFalse(term_sofr_compound.from_ql)
        self.assertFalse(term_sofr_base.from_ql)
        self.assertEqual(term_sofr_compound.settlement_offset, term_sofr_base.settlement_offset)
        self.assertEqual(term_sofr_compound.settlement_offset, Period("0D"))


# ---------------------------------------------------------------------------
# 8. Uppercase-key lookup identity invariant
# ---------------------------------------------------------------------------
#
# Registry.get/Registry.exists (and IndexRegistry.get's override) uppercase the lookup
# key before indexing into self._map. Confirm differently-cased lookups of the *same*
# index return the identical object (`is`, not just `==`), for the exact mixed-case
# name CLAUDE.md's bug log flags as having silently broken before
# (USD-Federal Funds-H.15-1B), plus a couple of other mixed-case names actually
# present in the yaml.

class TestUppercaseKeyIdentity(IndexFixturesTestCase):

    MIXED_CASE_NAMES = [
        "USD-Federal Funds-H.15-1B",  # exact case CLAUDE.md flags as having broken before
        "USD-Term SOFR Base-1B",
        "EuroSTR-1B",
        "SOFR-1B",                     # already all-caps -- should still round-trip
    ]

    def test_uppercase_key_identity(self):
        for name in self.MIXED_CASE_NAMES:
            with self.subTest(name=name):
                self.assertIn(
                    name, self.raw_indices,
                    f"{name} must actually exist in indices.yaml for this check to mean anything",
                )
                canonical = self.registry.get(name)
                upper = self.registry.get(name.upper())
                lower = self.registry.get(name.lower())
                self.assertIs(canonical, upper, f"{name}: upper-case lookup returned a different object")
                self.assertIs(canonical, lower, f"{name}: lower-case lookup returned a different object")
                self.assertTrue(self.registry.exists(name.lower()))
                self.assertTrue(self.registry.exists(name.upper()))


# ---------------------------------------------------------------------------
# 9. Native QuantLib base methods raise (documented gotcha, not a bug)
# ---------------------------------------------------------------------------
#
# IBORIndex/OvernightIndex subclass ql.IborIndex/ql.OvernightIndex for typing only --
# Index.__init__ (the plain-Python mixin) is the only base constructor ever called, so
# the inherited native QuantLib methods have no real C++ state behind them. Pin this
# down as an explicit regression check: these calls must keep raising TypeError, and
# callers must keep using .payment_business_day_conv / .payment_holiday_conv / .term
# instead.

class TestNativeQuantLibMethodsRaise(IndexFixturesTestCase):

    def test_ibor_native_methods_raise_type_error(self):
        ibor = self.registry.get("USD-LIBOR-BBA-3M")
        for native_call in (ibor.businessDayConvention, ibor.fixingCalendar, ibor.tenor):
            with self.subTest(native_call=native_call):
                with self.assertRaises(
                    TypeError,
                    msg=f"{native_call} unexpectedly succeeded -- native QL base state now exists?",
                ):
                    native_call()

    def test_overnight_native_methods_raise_type_error(self):
        on = self.registry.get("SOFR-1B")
        for native_call in (on.businessDayConvention, on.fixingCalendar):
            with self.subTest(native_call=native_call):
                with self.assertRaises(
                    TypeError,
                    msg=f"{native_call} unexpectedly succeeded -- native QL base state now exists?",
                ):
                    native_call()


# ---------------------------------------------------------------------------
# 10. Construction contract is enforced (required fields / field counts)
# ---------------------------------------------------------------------------
#
# Not just "construction succeeds" -- confirm malformed content is rejected rather than
# silently producing a partially-populated object. IBORIndex requires both "term" and
# "convention" keys; FXIndex asserts its convention dict has exactly 9 fields.

class TestConstructionContract(IndexFixturesTestCase):

    def test_ibor_missing_term_raises(self):
        assert_raises(AssertionError, IBORIndex, "TEST-MISSING-TERM", {"convention": "USDLibor"})

    def test_ibor_missing_convention_raises(self):
        assert_raises(AssertionError, IBORIndex, "TEST-MISSING-CONVENTION", {"term": "3M"})

    def test_overnight_missing_convention_raises(self):
        assert_raises(AssertionError, OvernightIndex, "TEST-ON-MISSING-CONVENTION", {})

    def test_composite_missing_convention_raises(self):
        assert_raises(AssertionError, OvernightCompositeIndex, "TEST-COMPOSITE-MISSING", {})

    def test_fx_incomplete_convention_raises(self):
        incomplete_fx_convention = dict(self.raw_indices["GBP-USD"]["convention"])
        incomplete_fx_convention.pop("premium currency")
        self.assertEqual(len(incomplete_fx_convention), 8)
        assert_raises(
            AssertionError, FXIndex, "TEST-FX-INCOMPLETE", {"convention": incomplete_fx_convention}
        )

    def test_fx_complete_convention_constructs(self):
        # positive control: the correct field count constructs successfully
        full_fx_convention = dict(self.raw_indices["GBP-USD"]["convention"])
        self.assertEqual(len(full_fx_convention), 9)
        ok_fx = FXIndex("TEST-FX-COMPLETE", {"convention": full_fx_convention})
        self.assertEqual(ok_fx.base_ccy.code(), "GBP")


# ---------------------------------------------------------------------------
# 11. IndexRegistry.get on an unknown key
# ---------------------------------------------------------------------------
#
# IndexRegistry.get overrides the base Registry.get with its own message but keeps the
# same uppercase-then-lookup contract; confirm a genuinely-absent key still raises
# rather than returning None or a stale cached value.

class TestUnknownKeyLookup(IndexFixturesTestCase):

    def test_get_unknown_key_raises(self):
        assert_raises(Exception, self.registry.get, "NOT-A-REAL-INDEX-XYZ")

    def test_exists_unknown_key_returns_false(self):
        self.assertFalse(self.registry.exists("NOT-A-REAL-INDEX-XYZ"))


if __name__ == '__main__':
    unittest.main()

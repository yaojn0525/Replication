"""
Level 1 (building-blocks) correctness tests for the `DataConvention` static-data layer:
~26 `DataConvention` subclasses in fixedincomelib/market/data_conventions.py, dispatched via
`DataConventionRegistry` (same file / fixedincomelib/utilities/utils.py), base contract in
fixedincomelib/market/interfaces.py:DataConvention.__init__.

Per .claude/skills/test_building_blocks.md section 2 ("Data conventions"). Structural/style
template: tests/test_indices_fixings.py (section 1 of the same skill doc).

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
from fixedincomelib.market.data_conventions import (
    DataConventionInstantaneousForwardRate,
    DataConventionFRAOrFixing,
    DataConventionOvernightIndexFuture,
    DataConventionOvernightIndexSwap,
    DataConventionOvernightIndexBasisSwap,
    DataConventionOISBasisSwap,
    DataConventionOvernightIndexCurrencyBasisSwap,
    DataConventionOISIBORCurrencyBasisSwap,
    DataConventionGenericForward,
    DataConventionGenericForwardSpread,
    DataConventionIborSpreadZeroRate,
    DataConventionGenericSpread,
    DataConventionFRN,
    DataConventionSwapSpreadBasisSwap,
    DataConventionFXRateIndex,
    DataConventionCashDeposit,
    DataConventionIBORFuture,
    DataConventionSwap,
    DataConventionBasisSwap,
    DataConventionCurrencyBasisSwap,
    DataConventionOvernightIndexFRASpread,
    DataConventionCompoundSwap,
    DataConventionCompoundBasisSwap,
    DataConventionJump,
    DataConventionSwaption,
    DataConventionCapFloor,
)
from fixedincomelib.market.indices import IBORIndex, OvernightIndex, OvernightCompositeIndex, FXIndex
from fixedincomelib.market.funding_identifiers import FundingIdentifier
from fixedincomelib.market.basics import (
    Currency, BusinessDayConvention, HolidayConvention, AccrualBasis, CompoundingMethod,
)
from fixedincomelib.date.basics import Period


def assert_raises(exc_type, fn, *args, **kwargs):
    """Mirrors tests/test_indices_fixings.py's assert_raises helper."""
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:
        raise AssertionError(f"expected {exc_type}, got {type(e)}: {e}")
    raise AssertionError(f"expected {exc_type}, but construction succeeded")


# Every DataConvention subclass registered in DataConventionRegFunction, keyed by its
# yaml `type` string. Built by reading fixedincomelib/market/data_conventions.py's
# registration block directly, not guessed -- 26 classes total (GENERIC SPREAD has no
# entry in the current static_files/data_conventions.yaml, everything else does).
TYPE_TO_CLASS = {
    "INSTANTANEOUS FORWARD RATE": DataConventionInstantaneousForwardRate,
    "FRA OR FIXING": DataConventionFRAOrFixing,
    "OVERNIGHT INDEX FUTURE": DataConventionOvernightIndexFuture,
    "OVERNIGHT INDEX SWAP": DataConventionOvernightIndexSwap,
    "OVERNIGHT INDEX BASIS SWAP": DataConventionOvernightIndexBasisSwap,
    "OIS BASIS SWAP": DataConventionOISBasisSwap,
    "OVERNIGHT INDEX CURRENCY BASIS SWAP": DataConventionOvernightIndexCurrencyBasisSwap,
    "OIS IBOR CURRENCY BASIS SWAP": DataConventionOISIBORCurrencyBasisSwap,
    "GENERIC FORWARD": DataConventionGenericForward,
    "GENERIC FORWARD SPREAD": DataConventionGenericForwardSpread,
    "IBOR SPREAD ZERO RATE": DataConventionIborSpreadZeroRate,
    "GENERIC SPREAD": DataConventionGenericSpread,
    "FLOATING RATE NOTE": DataConventionFRN,
    "SWAP SPREAD BASIS SWAP": DataConventionSwapSpreadBasisSwap,
    "FX RATE INDEX": DataConventionFXRateIndex,
    "CASH DEPOSIT": DataConventionCashDeposit,
    "IBOR FUTURE": DataConventionIBORFuture,
    "SWAP": DataConventionSwap,
    "BASIS SWAP": DataConventionBasisSwap,
    "CURRENCY BASIS SWAP": DataConventionCurrencyBasisSwap,
    "OVERNIGHT INDEX FRA SPREAD": DataConventionOvernightIndexFRASpread,
    "COMPOUND SWAP": DataConventionCompoundSwap,
    "COMPOUND BASIS SWAP": DataConventionCompoundBasisSwap,
    "SWAPTION": DataConventionSwaption,
    "CAPFLOOR": DataConventionCapFloor,
    "JUMP": DataConventionJump,
}

# Types actually present in static_files/data_conventions.yaml as of writing (169 entries).
# GENERIC SPREAD is deliberately absent -- covered instead via ad hoc .register(...) in
# TestNestedDataConventionLookup, per the source comment on DataConventionGenericSpread
# ("no meaningful example in yaml, will add later").
TYPES_PRESENT_IN_YAML = set(TYPE_TO_CLASS.keys()) - {"GENERIC SPREAD"}


class DataConventionFixturesTestCase(unittest.TestCase):
    """
    Shared fixture base: loads the process-wide DataConventionRegistry singleton and an
    independently-parsed copy of static_files/data_conventions.yaml once per test run
    (cwd is already tests/, set at module import time above).
    """

    @classmethod
    def setUpClass(cls):
        cls.registry = DataConventionRegistry()
        with open("../static_files/data_conventions.yaml", "r") as f:
            cls.raw_conventions = yaml.safe_load(f)
        # first yaml entry (name, convention-dict) seen for each `type`, in file order --
        # used as the representative entry for field-count / property-type tests below.
        cls.first_entry_by_type = {}
        for name, content in cls.raw_conventions.items():
            cls.first_entry_by_type.setdefault(content["type"], (name, content["convention"]))


# ---------------------------------------------------------------------------
# 1. DataConventionRegistry is a process-wide singleton, loaded from
#    static_files/data_conventions.yaml
# ---------------------------------------------------------------------------

class TestDataConventionRegistrySingleton(DataConventionFixturesTestCase):

    def test_singleton_identity(self):
        self.assertIs(DataConventionRegistry(), DataConventionRegistry())

    def test_yaml_source_has_169_entries(self):
        self.assertEqual(len(self.raw_conventions), 169)

    def test_registry_register_shape_requires_type_and_convention_nested_fields(self):
        # skill doc point 5: {type: ..., convention: {...fields...}} -- fields nested
        # under "convention", confirmed against the yaml's own on-disk shape.
        for name, content in self.raw_conventions.items():
            self.assertIn("type", content)
            self.assertIn("convention", content)
            self.assertIsInstance(content["convention"], dict)


# ---------------------------------------------------------------------------
# 2. Subclass dispatch matches the yaml `type` field, for every entry in
#    data_conventions.yaml (skill doc point 6: every entry gets at least one
#    instance test)
# ---------------------------------------------------------------------------

class TestSubclassDispatchAllYamlEntries(DataConventionFixturesTestCase):

    def test_subclass_dispatch_all_yaml_entries(self):
        seen_types = set()
        for name, content in self.raw_conventions.items():
            yaml_type = content["type"]
            seen_types.add(yaml_type)
            obj = self.registry.get(name)
            with self.subTest(name=name):
                self.assertIsInstance(
                    obj, TYPE_TO_CLASS[yaml_type],
                    f"{name}: expected {TYPE_TO_CLASS[yaml_type]}, got {type(obj)}",
                )
                self.assertEqual(
                    obj.type(), yaml_type,
                    f"{name}: .type() = {obj.type()!r} != yaml type {yaml_type!r}",
                )
                self.assertEqual(
                    obj.name, name.upper(),
                    f"{name}: .name = {obj.name!r} != {name.upper()!r}",
                )
        # sanity: every type we know how to dispatch (except GENERIC SPREAD, which has
        # no yaml entry) was actually exercised, and nothing unexpected showed up.
        self.assertEqual(seen_types, TYPES_PRESENT_IN_YAML)

    def test_display_all_data_conventions_matches_registry_contents(self):
        # Registry.__new__ / DataConventionRegistry are process-wide singletons (per
        # the skill doc's shared-setup note), so other test classes in this same run
        # may have ad hoc-registered extra TEST-* entries by the time this runs --
        # assert every yaml-sourced entry is present (superset), not exact equality,
        # to stay order-independent within the suite.
        df = self.registry.display_all_data_conventions()
        self.assertGreaterEqual(len(df), len(self.raw_conventions))
        self.assertTrue(
            {name.upper() for name in self.raw_conventions.keys()}.issubset(set(df["Name"]))
        )


# ---------------------------------------------------------------------------
# 3. Field count is enforced exactly (skill doc point 1): every subclass raises
#    ValueError if len(content) != valid_count. Positive control (full field set
#    constructs) and negative control (one field removed raises) for a
#    representative entry of every type present in the yaml.
# ---------------------------------------------------------------------------

class TestFieldCountContract(DataConventionFixturesTestCase):

    def test_field_count_enforced_for_every_type_present_in_yaml(self):
        for type_str in sorted(TYPES_PRESENT_IN_YAML):
            cls_ = TYPE_TO_CLASS[type_str]
            name, full_content = self.first_entry_by_type[type_str]
            with self.subTest(type=type_str, name=name):
                # positive control: the correct field count constructs successfully
                # (also confirms the direct-construction path, not just via registry)
                ok = cls_(name, dict(full_content))
                self.assertIsInstance(ok, cls_)
                # negative control: drop one field -> ValueError
                dropped_key = next(iter(full_content))
                short_content = {k: v for k, v in full_content.items() if k != dropped_key}
                assert_raises(ValueError, cls_, f"{name}-MISSING-{dropped_key}", short_content)

    def test_field_count_error_message_reports_expected_and_actual_counts(self):
        name, full_content = self.first_entry_by_type["CASH DEPOSIT"]
        short_content = dict(list(full_content.items())[:-1])
        try:
            DataConventionCashDeposit(name, short_content)
            self.fail("expected ValueError")
        except ValueError as e:
            self.assertIn(str(len(full_content)), str(e))
            self.assertIn(str(len(short_content)), str(e))


# ---------------------------------------------------------------------------
# 4. Property types / values per subclass, per skill doc point 2: Period for
#    offsets/tenors, Currency for currency fields, float for notional/basis point,
#    ql.DayCounter via AccrualBasis.new for accrual basis, int via
#    BusinessDayConvention.new for BDC fields, ql.Calendar via HolidayConvention.new
#    for holiday fields, resolved Index/FundingIdentifier object (not raw string)
#    for index-reference fields. One TestCase per subclass, oracle values re-derived
#    from the raw yaml via the same factory functions (.new(...)), not hardcoded
#    QuantLib internals.
# ---------------------------------------------------------------------------

class TestPropertyTypesInstantaneousForwardRate(DataConventionFixturesTestCase):

    def test_index_resolves_through_index_registry(self):
        conv = self.registry.get("USD-SOFR-OIS-1B-IFR")
        raw = self.raw_conventions["USD-SOFR-OIS-1B-IFR"]["convention"]
        self.assertIsInstance(conv.index, OvernightIndex)
        self.assertIs(conv.index, IndexRegistry().get(raw["index"]))


class TestPropertyTypesFRAOrFixing(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "USD-LIBOR-BBA-1M-FRA"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertIsInstance(conv.currency, Currency)
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertIsInstance(conv.notional, float)
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertIsInstance(conv.index, IBORIndex)
        self.assertIs(conv.index, IndexRegistry().get(raw["index"]))
        self.assertEqual(conv.accrual_basis, AccrualBasis.new(raw["accrual basis"]))
        self.assertIsInstance(conv.payment_business_day_conv, int)
        self.assertEqual(
            conv.payment_business_day_conv,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(conv.payment_holiday_conv, HolidayConvention.new(raw["payment holiday convention"]))
        self.assertEqual(conv.fra_style, raw["fra style"])
        self.assertIsInstance(conv.end_of_month, bool)
        self.assertEqual(conv.end_of_month, bool(raw["end of month"]))

    def test_fra_style_only_accepts_isda_or_afma(self):
        name = "USD-LIBOR-BBA-1M-FRA"
        raw = dict(self.raw_conventions[name]["convention"])
        raw["fra style"] = "BOGUS"
        assert_raises(AssertionError, DataConventionFRAOrFixing, "TEST-FRA-BAD-STYLE", raw)


class TestPropertyTypesOvernightIndexFuture(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "SOFR-FUTURE-1M"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertIsInstance(conv.currency, Currency)
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertIsInstance(conv.contractual_notional, float)
        self.assertEqual(conv.contractual_notional, float(raw["contractual notional"]))
        self.assertIsInstance(conv.index, OvernightCompositeIndex)
        self.assertIs(conv.index, IndexRegistry().get(raw["index"]))
        self.assertEqual(conv.rate_cutoff, Period(raw["rate cutoff"]))
        self.assertIsInstance(conv.payment_business_day_convention, int)
        self.assertEqual(
            conv.payment_business_day_convention,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(
            conv.payment_holiday_convention, HolidayConvention.new(raw["payment holiday convention"])
        )
        # payment_offset / basis_point: see TestSuspectedLibraryBugs -- the yaml uses
        # "payment_offset"/"basis_point" (underscore) but the class only recognizes
        # "PAYMENT OFFSET"/"BASIS POINT" (space), so these are None for every entry of
        # this type today. Pinned there, not asserted as correct here.


class TestPropertyTypesOvernightIndexSwap(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "USD-SOFR-OIS"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertEqual(conv.accrual_period, Period(raw["accrual period"]))
        self.assertEqual(conv.accrual_basis, AccrualBasis.new(raw["accrual basis"]))
        self.assertIsInstance(conv.index, OvernightCompositeIndex)
        self.assertIs(conv.index, IndexRegistry().get(raw["index"]))
        self.assertEqual(conv.rate_cutoff, Period(raw["rate cutoff"]))
        self.assertEqual(conv.payment_offset, Period(raw["payment offset"]))
        self.assertEqual(
            conv.payment_business_day_conv,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(conv.payment_holiday_conv, HolidayConvention.new(raw["payment holiday convention"]))


class TestPropertyTypesOvernightIndexBasisSwap(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "USD-SOFR-COMPOUND-OVER-USD-LIBOR-BBA-3M-BASIS-SWAP"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertIsInstance(conv.on_index, OvernightCompositeIndex)
        self.assertIs(conv.on_index, IndexRegistry().get(raw["overnight composite index"]))
        self.assertEqual(conv.rate_cutoff, Period(raw["rate cutoff"]))
        self.assertIsInstance(conv.ibor_index, IBORIndex)
        self.assertIs(conv.ibor_index, IndexRegistry().get(raw["ibor index"]))
        self.assertEqual(conv.payment_offset, Period(raw["payment offset"]))
        self.assertEqual(
            conv.payment_business_day_convention,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        # yaml declares "NYC,LON" -- confirm it's a real joint calendar, not just NYC
        self.assertEqual(
            conv.payment_holiday_convention, HolidayConvention.new(raw["payment holiday convention"])
        )
        self.assertNotEqual(conv.payment_holiday_convention, HolidayConvention.new("NYC"))
        self.assertEqual(conv.accrual_period, Period(raw["accrual period"]))


class TestPropertyTypesOISBasisSwap(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "USD-SOFR-AVG-OVER-USD-SOFR-AVERAGE-BASIS-SWAP"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertIsInstance(conv.basis_on_index, OvernightCompositeIndex)
        self.assertIs(conv.basis_on_index, IndexRegistry().get(raw["basis overnight composite index"]))
        self.assertEqual(conv.rate_cutoff, Period(raw["rate cutoff"]))
        self.assertIsInstance(conv.reference_on_index, OvernightCompositeIndex)
        self.assertIs(
            conv.reference_on_index, IndexRegistry().get(raw["reference overnight composite index"])
        )
        self.assertIsNot(conv.basis_on_index, conv.reference_on_index)
        self.assertEqual(conv.payment_offset, Period(raw["payment offset"]))
        self.assertEqual(
            conv.payment_business_day_convention,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(
            conv.payment_holiday_convention, HolidayConvention.new(raw["payment holiday convention"])
        )
        self.assertEqual(conv.basis_accrual_period, Period(raw["basis accrual period"]))
        self.assertEqual(conv.reference_accrual_period, Period(raw["reference accrual period"]))


class TestPropertyTypesOvernightIndexCurrencyBasisSwap(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "CAD-CORRA-COMPOUND-3M-OVER-USD-SOFR-COMPOUND-3M-OVERNIGHT-INDEX-CBS"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertIsInstance(conv.mark_notional_to_market, str)
        self.assertEqual(conv.mark_notional_to_market, raw["mark notional to market"])
        self.assertEqual(
            conv.fx_rate_fixing_holiday_convention,
            HolidayConvention.new(raw["fx rate fixing holiday convention"]),
        )
        self.assertEqual(conv.fx_rate_fixing_offset, Period(raw["fx rate fixing offset"]))
        self.assertIsInstance(conv.basis_currency, Currency)
        self.assertEqual(conv.basis_currency.code(), raw["basis currency"])
        self.assertEqual(conv.basis_notional, float(raw["basis notional"]))
        self.assertIsInstance(conv.basis_on_index, OvernightCompositeIndex)
        self.assertIs(conv.basis_on_index, IndexRegistry().get(raw["basis overnight composite index"]))
        self.assertEqual(conv.basis_accrual_period, Period(raw["basis accrual period"]))
        self.assertEqual(conv.basis_payment_offset, Period(raw["basis payment offset"]))
        self.assertEqual(conv.reference_currency.code(), raw["reference currency"])
        self.assertIsInstance(conv.reference_on_index, OvernightCompositeIndex)
        self.assertIs(
            conv.reference_on_index, IndexRegistry().get(raw["reference overnight composite index"])
        )
        self.assertEqual(conv.reference_accrual_period, Period(raw["reference accrual period"]))
        self.assertEqual(conv.reference_payment_offset, Period(raw["reference payment offset"]))


class TestPropertyTypesGenericForward(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "USD-LIBOR-BBA-3M-FLAT-FWD"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        # "index" here (USD-LIBOR-BBA-3M-FLAT) only exists in FundingIdentifierRegistry,
        # not IndexRegistry -- exercises the fallback branch, see
        # TestIndexReferenceRegistryFallback below for the explicit assertion.
        self.assertIsInstance(conv.index, FundingIdentifier)
        self.assertEqual(conv.accrual_basis, AccrualBasis.new(raw["accrual basis"]))
        self.assertEqual(
            conv.business_day_convention, BusinessDayConvention.new(raw["payment business day convention"])
        )
        self.assertEqual(conv.holiday_convention, HolidayConvention.new(raw["payment holiday convention"]))
        self.assertEqual(conv.end_of_month, bool(raw["end of month"]))
        self.assertIsInstance(conv.compounding_method, CompoundingMethod)
        self.assertEqual(conv.compounding_method, CompoundingMethod.from_string(raw["compounding method"]))


class TestPropertyTypesGenericForwardSpread(DataConventionFixturesTestCase):

    def test_property_types_and_values_not_affected_by_the_known_bug(self):
        # basis_currency / basis_notional / reference_accrual_basis are broken --
        # see TestSuspectedLibraryBugs. Everything else on this class is fine.
        name = "CAD-OVER-USD-GFS"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_business_day_convention,
            BusinessDayConvention.new(raw["settlement business day convention"]),
        )
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        # basis index / reference index: neither "CAD" nor "USD" exist in
        # IndexRegistry, only FundingIdentifierRegistry -- exercises the fallback
        # branch for this class too.
        self.assertIsInstance(conv.basis_index, FundingIdentifier)
        self.assertIs(conv.basis_index, FundingIdentifierRegistry().get(raw["basis index"]))
        self.assertIsInstance(conv.reference_index, FundingIdentifier)
        self.assertIs(conv.reference_index, FundingIdentifierRegistry().get(raw["reference index"]))
        self.assertEqual(conv.basis_accrual_basis, AccrualBasis.new(raw["basis accrual basis"]))
        self.assertEqual(
            conv.payment_business_day_convention,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(
            conv.payment_holiday_convention, HolidayConvention.new(raw["payment holiday convention"])
        )
        self.assertEqual(conv.end_of_month, bool(raw["end of month"]))
        self.assertEqual(conv.compounding_method, CompoundingMethod.from_string(raw["compounding method"]))


class TestPropertyTypesIborSpreadZeroRate(DataConventionFixturesTestCase):

    def test_basis_ibor_index_and_reference_index(self):
        name = "USD-Federal Funds-H.15-1B-OVER-USD-Federal Funds H.15-1B-FLAT-ISZR"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertIsInstance(conv.basis_ibor_index, OvernightIndex)
        self.assertIs(conv.basis_ibor_index, IndexRegistry().get(raw["basis ibor index"]))
        # reference_index here (...-FLAT) only exists in FundingIdentifierRegistry --
        # fallback branch, see TestIndexReferenceRegistryFallback too.
        self.assertIsInstance(conv.reference_index, FundingIdentifier)
        self.assertIs(conv.reference_index, FundingIdentifierRegistry().get(raw["reference index"]))


class TestPropertyTypesFRN(DataConventionFixturesTestCase):

    def test_property_types_and_values_not_affected_by_the_known_bug(self):
        # .index is broken (always None) -- see TestSuspectedLibraryBugs.
        name = "USD-LIBOR-BBA-3M-FRN"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertEqual(
            conv.payment_business_day_convention,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(
            conv.payment_holiday_convention, HolidayConvention.new(raw["payment holiday convention"])
        )


class TestPropertyTypesFXRateIndex(DataConventionFixturesTestCase):

    def test_fx_index_resolves_through_index_registry(self):
        # GBP-USD is the correctly-keyed entry ("fx index": "GBP-USD"); USD-CAD /
        # USD-JPY are broken -- see TestSuspectedLibraryBugs.
        name = "GBP-USD"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertIsInstance(conv.fx_index, FXIndex)
        self.assertIs(conv.fx_index, IndexRegistry().get(raw["fx index"]))


class TestPropertyTypesCashDeposit(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "USD-CASH-DEPOSIT"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertEqual(conv.accrual_basis, AccrualBasis.new(raw["accrual basis"]))
        self.assertEqual(
            conv.business_day_convention, BusinessDayConvention.new(raw["payment business day convention"])
        )
        self.assertEqual(conv.holiday_convention, HolidayConvention.new(raw["payment holiday convention"]))
        self.assertEqual(conv.end_of_month, bool(raw["end of month"]))


class TestPropertyTypesIBORFuture(DataConventionFixturesTestCase):

    def test_property_types_and_values_not_affected_by_the_known_bug(self):
        # .currency is broken (raises AttributeError) -- see TestSuspectedLibraryBugs.
        name = "AUDBB"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertEqual(conv.contractual_notional, float(raw["contractual notional"]))
        self.assertIsInstance(conv.ibor_index, IBORIndex)
        self.assertIs(conv.ibor_index, IndexRegistry().get(raw["ibor index"]))
        self.assertEqual(conv.accrual_basis, AccrualBasis.new(raw["accrual basis"]))
        self.assertEqual(
            conv.business_day_convention, BusinessDayConvention.new(raw["payment business day convention"])
        )
        self.assertEqual(conv.holiday_convention, HolidayConvention.new(raw["payment holiday convention"]))
        self.assertEqual(conv.basis_point_value_type, raw["basis point value type"])
        self.assertEqual(conv.basis_point_value, float(raw["basis point value"]))


class TestPropertyTypesSwap(DataConventionFixturesTestCase):

    def test_property_types_and_values_not_affected_by_the_known_bug(self):
        # .index is broken (always None for this entry) -- see TestSuspectedLibraryBugs.
        name = "USD-SWAP-SEMI-BOND"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertEqual(conv.accrual_period, Period(raw["accrual period"]))
        self.assertEqual(conv.accrual_basis, AccrualBasis.new(raw["accrual basis"]))
        self.assertEqual(
            conv.payment_business_day_conv,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(conv.payment_holiday_conv, HolidayConvention.new(raw["payment holiday convention"]))
        self.assertEqual(
            conv.value_date_as_first_fixing_date, bool(raw["value date as first fixing date"])
        )


class TestPropertyTypesBasisSwap(DataConventionFixturesTestCase):

    def test_property_types_and_values_not_affected_by_the_known_bug(self):
        # .reference_index is broken for this entry (yaml key typo) -- see
        # TestSuspectedLibraryBugs.
        name = "USD-LIBOR-BBA-1M-OVER-USD-LIBOR-BBA-3M-BASIS-SWAP"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertIsInstance(conv.basis_index, IBORIndex)
        self.assertIs(conv.basis_index, IndexRegistry().get(raw["basis ibor index"]))
        self.assertEqual(
            conv.payment_business_day_conv,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(conv.payment_holiday_conv, HolidayConvention.new(raw["payment holiday convention"]))


class TestPropertyTypesCurrencyBasisSwap(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "GBP-LIBOR-BBA-3M-OVER-CAD-BA-3M-CBS"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        # this entry's 11 fields don't happen to include "settlement offset" (the
        # class enforces field *count*, not field *identity* -- valid_count=11 is
        # satisfied by the 11 fields this entry actually supplies), so
        # settlement_offset legitimately stays at its None default here.
        self.assertNotIn("settlement offset", raw)
        self.assertIsNone(conv.settlement_offset)
        # .mark_notional_to_market: no property getter at all on this class (unlike
        # its siblings OvernightIndexCurrencyBasisSwap / OISIBORCurrencyBasisSwap) --
        # see TestSuspectedLibraryBugs.
        self.assertFalse(hasattr(conv, "mark_notional_to_market"))
        self.assertEqual(conv.mark_notional_to_market_, raw["mark notional to market"])
        self.assertEqual(
            conv.fx_rate_holiday_convention, HolidayConvention.new(raw["fx rate holiday convention"])
        )
        self.assertEqual(conv.fx_rate_fixing_offset, Period(raw["fx rate fixing offset"]))
        self.assertEqual(conv.basis_currency.code(), raw["basis currency"])
        self.assertEqual(conv.basis_notional, float(raw["basis notional"]))
        self.assertIsInstance(conv.basis_index, IBORIndex)
        self.assertIs(conv.basis_index, IndexRegistry().get(raw["basis ibor index"]))
        self.assertEqual(conv.reference_currency.code(), raw["reference currency"])
        self.assertIsInstance(conv.reference_index, IBORIndex)
        self.assertIs(conv.reference_index, IndexRegistry().get(raw["reference ibor index"]))
        self.assertEqual(
            conv.payment_business_day_conv,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(conv.payment_holiday_conv, HolidayConvention.new(raw["payment holiday convention"]))


class TestPropertyTypesOvernightIndexFRASpread(DataConventionFixturesTestCase):

    def test_nested_lookup_covered_in_nested_lookup_section(self):
        # see TestNestedDataConventionLookup for the fra_data_convention /
        # ois_data_convention lazy-resolution assertions
        name = "AUD-AONIA-COMPOUND-OVER-AUD-LIBOR-BBA-3M-FRA-SPREAD"
        conv = self.registry.get(name)
        self.assertIsInstance(conv, DataConventionOvernightIndexFRASpread)


class TestPropertyTypesCompoundSwap(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "CAD-BA-3M-COMPOUND-SWAP-SEMI-ACT365F"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertIsInstance(conv.ibor_index, IBORIndex)
        self.assertIs(conv.ibor_index, IndexRegistry().get(raw["index"]))
        self.assertEqual(conv.ibor_payment_period, Period(raw["payment period"]))
        self.assertEqual(conv.accrual_period, Period(raw["accrual period"]))
        self.assertEqual(conv.accrual_basis, AccrualBasis.new(raw["accrual basis"]))
        self.assertEqual(
            conv.payment_business_day_conv,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(conv.payment_holiday_conv, HolidayConvention.new(raw["payment holiday convention"]))


class TestPropertyTypesCompoundBasisSwap(DataConventionFixturesTestCase):

    def test_property_types_and_values(self):
        name = "CAD-BA-1M-OVER-CAD-BA-3M-COMPOUND-BASIS-SWAP"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.settlement_offset, Period(raw["settlement offset"]))
        self.assertEqual(
            conv.settlement_holiday_convention, HolidayConvention.new(raw["settlement holiday convention"])
        )
        self.assertEqual(conv.currency.code(), raw["currency"])
        self.assertEqual(conv.notional, float(raw["notional"]))
        self.assertIsInstance(conv.basis_ibor_index, IBORIndex)
        self.assertIs(conv.basis_ibor_index, IndexRegistry().get(raw["basis index"]))
        self.assertEqual(conv.basis_ibor_payment_period, Period(raw["basis payment period"]))
        self.assertIsInstance(conv.compound_method, CompoundingMethod)
        self.assertEqual(conv.compound_method, CompoundingMethod.from_string(raw["compound method"]))
        self.assertIsInstance(conv.reference_ibor_index, IBORIndex)
        self.assertIs(conv.reference_ibor_index, IndexRegistry().get(raw["reference index"]))
        self.assertEqual(
            conv.payment_business_day_conv,
            BusinessDayConvention.new(raw["payment business day convention"]),
        )
        self.assertEqual(conv.payment_holiday_conv, HolidayConvention.new(raw["payment holiday convention"]))


class TestPropertyTypesSwaptionAndCapFloor(DataConventionFixturesTestCase):

    def test_index_resolves_but_payment_conventions_are_broken(self):
        # payment_business_day_conv / payment_holiday_conv are broken for both
        # entries (yaml key typo) -- see TestSuspectedLibraryBugs. .index is fine.
        for name, expected_cls in [
            ("USD-SOFR-COMPOUND-SWAPTION", DataConventionSwaption),
            ("USD-SOFR-COMPOUND-CAPFLOOR", DataConventionCapFloor),
        ]:
            with self.subTest(name=name):
                conv = self.registry.get(name)
                raw = self.raw_conventions[name]["convention"]
                self.assertIsInstance(conv, expected_cls)
                self.assertIsInstance(conv.index, OvernightCompositeIndex)
                self.assertIs(conv.index, IndexRegistry().get(raw["index"]))


class TestPropertyTypesJump(DataConventionFixturesTestCase):

    def test_index_resolves_but_jump_size_is_broken(self):
        # .jump_size is broken (yaml key typo) -- see TestSuspectedLibraryBugs.
        name = "USD-SOFR-JUMP"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertIsInstance(conv.index, OvernightIndex)
        self.assertIs(conv.index, IndexRegistry().get(raw["index"]))


# ---------------------------------------------------------------------------
# 5. Index-reference fields resolve through the correct registry (skill doc
#    point 3): DataConventionInstantaneousForwardRate, DataConventionGenericForward,
#    DataConventionIborSpreadZeroRate try IndexRegistry first, then fall back to
#    FundingIdentifierRegistry. DataConventionFRAOrFixing only checks IndexRegistry
#    (no fallback support at all).
# ---------------------------------------------------------------------------

class TestIndexReferenceRegistryFallback(DataConventionFixturesTestCase):

    def test_instantaneous_forward_rate_index_registry_branch(self):
        conv = self.registry.get("USD-SOFR-OIS-1B-IFR")  # index: SOFR-1B -- in IndexRegistry
        self.assertTrue(IndexRegistry().exists("SOFR-1B"))
        self.assertIsInstance(conv.index, OvernightIndex)

    def test_instantaneous_forward_rate_funding_identifier_fallback_branch(self):
        conv = self.registry.get("USD-SOFR-OIS-1B-FLAT-IFR")  # index: SOFR-1B-FLAT
        self.assertFalse(IndexRegistry().exists("SOFR-1B-FLAT"))
        self.assertTrue(FundingIdentifierRegistry().exists("SOFR-1B-FLAT"))
        self.assertIsInstance(conv.index, FundingIdentifier)
        self.assertIs(conv.index, FundingIdentifierRegistry().get("SOFR-1B-FLAT"))

    def test_generic_forward_funding_identifier_fallback_branch(self):
        conv = self.registry.get("USD-LIBOR-BBA-3M-FLAT-FWD")  # index: USD-LIBOR-BBA-3M-FLAT
        self.assertFalse(IndexRegistry().exists("USD-LIBOR-BBA-3M-FLAT"))
        self.assertTrue(FundingIdentifierRegistry().exists("USD-LIBOR-BBA-3M-FLAT"))
        self.assertIsInstance(conv.index, FundingIdentifier)

    def test_ibor_spread_zero_rate_both_branches(self):
        conv = self.registry.get(
            "USD-Federal Funds-H.15-1B-OVER-USD-Federal Funds H.15-1B-FLAT-ISZR"
        )
        # basis_ibor_index: IndexRegistry-only field (no fallback in the source)
        self.assertTrue(IndexRegistry().exists("USD-Federal Funds-H.15-1B"))
        self.assertIsInstance(conv.basis_ibor_index, OvernightIndex)
        # reference_index: falls back to FundingIdentifierRegistry
        self.assertFalse(IndexRegistry().exists("USD-Federal Funds-H.15-1B-FLAT"))
        self.assertTrue(FundingIdentifierRegistry().exists("USD-Federal Funds-H.15-1B-FLAT"))
        self.assertIsInstance(conv.reference_index, FundingIdentifier)

    def test_fra_or_fixing_has_no_funding_identifier_fallback(self):
        # DataConventionFRAOrFixing.index only ever calls IndexRegistry().get(v) --
        # no exists()-guarded fallback branch exists in the source at all. Confirm
        # feeding it a FundingIdentifier-only name raises rather than silently
        # resolving through FundingIdentifierRegistry.
        raw = dict(self.raw_conventions["USD-LIBOR-BBA-1M-FRA"]["convention"])
        raw["index"] = "SOFR-1B-FLAT"  # only in FundingIdentifierRegistry
        self.assertFalse(IndexRegistry().exists("SOFR-1B-FLAT"))
        assert_raises(Exception, DataConventionFRAOrFixing, "TEST-FRA-BAD-INDEX", raw)


# ---------------------------------------------------------------------------
# 6. Nested convention lookups resolve lazily via property, not stored at
#    construction time (skill doc point 4): DataConventionSwapSpreadBasisSwap,
#    DataConventionOvernightIndexFRASpread (both have real yaml entries),
#    DataConventionGenericSpread (no yaml entry -- covered here via ad hoc
#    .register(...), which also exercises skill doc point 5's registration shape).
# ---------------------------------------------------------------------------

class TestNestedDataConventionLookup(DataConventionFixturesTestCase):

    def test_swap_spread_basis_swap_basis_and_reference_swap_resolve_lazily(self):
        name = "USD-SOFR-OIS-OVER-USD-OIS-BASIS-SWAP"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        # the raw content only ever stores the *string* name (upper-cased) --
        # confirm the property call is what actually produces a live object
        self.assertEqual(conv.content_["BASIS SWAP"], raw["basis swap"].upper())
        self.assertIsInstance(conv.basis_swap, DataConvention)
        self.assertIsInstance(conv.basis_swap, DataConventionOvernightIndexSwap)
        self.assertIs(conv.basis_swap, self.registry.get(raw["basis swap"]))
        self.assertIsInstance(conv.reference_swap, DataConventionOvernightIndexSwap)
        self.assertIs(conv.reference_swap, self.registry.get(raw["reference swap"]))
        self.assertIsNot(conv.basis_swap, conv.reference_swap)

    def test_overnight_index_fra_spread_fra_and_ois_data_convention_resolve_lazily(self):
        name = "AUD-AONIA-COMPOUND-OVER-AUD-LIBOR-BBA-3M-FRA-SPREAD"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertIsInstance(conv.fra_data_convention, DataConventionFRAOrFixing)
        self.assertIs(conv.fra_data_convention, self.registry.get(raw["fra data convention"]))
        self.assertIsInstance(conv.ois_data_convention, DataConventionOvernightIndexSwap)
        self.assertIs(conv.ois_data_convention, self.registry.get(raw["ois data convention"]))

    def test_generic_spread_ad_hoc_registration_and_lazy_resolution(self):
        # GENERIC SPREAD has no entry in static_files/data_conventions.yaml (per the
        # source comment on DataConventionGenericSpread) -- register one ad hoc,
        # test-only key, linking two conventions that already exist in the registry.
        key = "TEST-GENERIC-SPREAD-CASH-VS-FRA"
        content = {
            "type": "GENERIC SPREAD",
            "convention": {
                "target data convention": "USD-CASH-DEPOSIT",
                "reference data convention": "USD-LIBOR-BBA-1M-FRA",
            },
        }
        self.registry.register(key, content)
        conv = self.registry.get(key)
        self.assertIsInstance(conv, DataConventionGenericSpread)
        self.assertIsInstance(conv.target_data_convention, DataConventionCashDeposit)
        self.assertIs(conv.target_data_convention, self.registry.get("USD-CASH-DEPOSIT"))
        self.assertIsInstance(conv.reference_data_convention, DataConventionFRAOrFixing)
        self.assertIs(conv.reference_data_convention, self.registry.get("USD-LIBOR-BBA-1M-FRA"))
        # re-registering the same key must not raise (Registry.register's base
        # implementation has the duplicate-key ValueError commented out)
        self.registry.register(key, content)


# ---------------------------------------------------------------------------
# 7. Registry-level record shape for ad hoc registration (skill doc point 5):
#    DataConventionRegistry().register(name, content) expects
#    {type: ..., convention: {...fields...}}, fields nested under "convention".
# ---------------------------------------------------------------------------

class TestAdHocRegistration(DataConventionFixturesTestCase):

    def test_register_with_correct_nested_shape_constructs_and_resolves(self):
        key = "TEST-CASH-DEPOSIT-AD-HOC"
        content = {
            "type": "CASH DEPOSIT",
            "convention": {
                "settlement offset": "2D",
                "settlement holiday convention": "LON",
                "currency": "USD",
                "notional": 5_000_000,
                "accrual basis": "ACTUAL/360",
                "payment business day convention": "MF",
                "payment holiday convention": "NYC,LON",
                "end of month": True,
            },
        }
        self.registry.register(key, content)
        conv = self.registry.get(key)
        self.assertIsInstance(conv, DataConventionCashDeposit)
        self.assertEqual(conv.currency.code(), "USD")
        self.assertEqual(conv.notional, 5_000_000.0)
        self.assertEqual(conv.settlement_offset, Period("2D"))
        # uppercase-key lookup invariant (same Registry base as IndexRegistry etc.)
        self.assertIs(self.registry.get(key.lower()), conv)

    def test_register_without_nested_convention_key_raises(self):
        key = "TEST-MALFORMED-NO-CONVENTION-KEY"
        malformed = {"type": "CASH DEPOSIT"}  # fields not nested under "convention"
        assert_raises(KeyError, self.registry.register, key, malformed)

    def test_register_duplicate_key_does_not_raise_and_last_write_wins(self):
        key = "TEST-DUPLICATE-KEY-TOLERANCE"
        content_v1 = {
            "type": "CASH DEPOSIT",
            "convention": {
                "settlement offset": "2D",
                "settlement holiday convention": "LON",
                "currency": "USD",
                "notional": 1_000_000,
                "accrual basis": "ACTUAL/360",
                "payment business day convention": "MF",
                "payment holiday convention": "NYC",
                "end of month": False,
            },
        }
        content_v2 = {
            "type": "CASH DEPOSIT",
            "convention": {
                "settlement offset": "2D",
                "settlement holiday convention": "LON",
                "currency": "GBP",
                "notional": 2_000_000,
                "accrual basis": "ACTUAL/360",
                "payment business day convention": "MF",
                "payment holiday convention": "NYC",
                "end of month": False,
            },
        }
        self.registry.register(key, content_v1)
        self.registry.register(key, content_v2)  # must not raise
        self.assertEqual(self.registry.get(key).currency.code(), "GBP")


# ---------------------------------------------------------------------------
# 8. Suspected library bugs found while building this suite.
#
# NOT fixed here -- per the test-writing-agent's hard boundary, write access to
# fixedincomelib/ and static_files/ is reserved for the user's explicit request.
# Each test below asserts the *contractually intended* behavior and is marked
# @unittest.expectedFailure, so:
#   - the suite stays green today (an expected failure is not a suite failure),
#   - the moment someone fixes the underlying bug, the test flips to an
#     *unexpected pass* (a real failure) rather than silently staying "correct",
#     which is the signal to delete the expectedFailure decorator.
# See the final report for file:line references and full bug descriptions.
# ---------------------------------------------------------------------------

class TestSuspectedLibraryBugs(DataConventionFixturesTestCase):

    @unittest.expectedFailure
    def test_ibor_future_currency_property_should_not_double_wrap(self):
        # DataConventionIBORFuture.currency (data_conventions.py:1292) does
        # `return Currency(self.currency_)`, but self.currency_ is already a
        # Currency instance (set via `self.currency_ = Currency(v)` at construction)
        # -- Currency.__init__ calls ccy_str.upper() on its argument, which raises
        # AttributeError for a Currency object instead of a str. Affects both IBOR
        # FUTURE entries in the yaml (AUDBB, EURUDOLLAR).
        conv = self.registry.get("AUDBB")
        self.assertIsInstance(conv.currency, Currency)
        self.assertEqual(conv.currency.code(), "AUD")

    @unittest.expectedFailure
    def test_frn_index_property_should_resolve(self):
        # DataConventionFRN.__init__ (data_conventions.py:1039), the "INDEX" branch
        # assigns `self.basis_index_` (an attribute never declared/read anywhere
        # else in the class) instead of the declared `self.index_`. The `.index`
        # property always returns None as a result. Affects both FLOATING RATE NOTE
        # entries (USD-LIBOR-BBA-3M-FRN, SONIA-1B-FRN).
        conv = self.registry.get("USD-LIBOR-BBA-3M-FRN")
        raw = self.raw_conventions["USD-LIBOR-BBA-3M-FRN"]["convention"]
        self.assertIsInstance(conv.index, IBORIndex)
        self.assertIs(conv.index, IndexRegistry().get(raw["index"]))

    @unittest.expectedFailure
    def test_generic_forward_spread_basis_currency_and_notional_should_resolve(self):
        # DataConventionGenericForwardSpread.__init__ (data_conventions.py:855-858),
        # the "BASIS CURRENCY"/"BASIS NOTIONAL" branches assign to the undeclared
        # `self.currency_`/`self.notional_` instead of the declared
        # `self.basis_currency_`/`self.basis_notional_`. `.basis_currency` /
        # `.basis_notional` are always None. Affects the one GENERIC FORWARD SPREAD
        # entry in the yaml (CAD-OVER-USD-GFS).
        conv = self.registry.get("CAD-OVER-USD-GFS")
        raw = self.raw_conventions["CAD-OVER-USD-GFS"]["convention"]
        self.assertIsInstance(conv.basis_currency, Currency)
        self.assertEqual(conv.basis_currency.code(), raw["basis currency"])
        self.assertEqual(conv.basis_notional, float(raw["basis notional"]))

    @unittest.expectedFailure
    def test_generic_forward_spread_reference_accrual_basis_should_resolve(self):
        # Same class, data_conventions.py:877-878: "REFERENCE ACCRUAL BASIS" assigns
        # to the undeclared `self.accrual_basis_` instead of the declared
        # `self.reference_accrual_basis_`. `.reference_accrual_basis` is always None.
        conv = self.registry.get("CAD-OVER-USD-GFS")
        raw = self.raw_conventions["CAD-OVER-USD-GFS"]["convention"]
        self.assertEqual(conv.reference_accrual_basis, AccrualBasis.new(raw["reference accrual basis"]))

    @unittest.expectedFailure
    def test_overnight_index_future_payment_offset_and_basis_point_should_resolve(self):
        # static_files/data_conventions.yaml: all 8 OVERNIGHT INDEX FUTURE entries
        # (SOFR-FUTURE-1M, SOFR-FUTURE-3M, FEDFUNDS-FUTURE, CORRA-FUTURE-3M,
        # SONIA-FUTURE-3M, EONIA-FUTURE, AONIA-FUTURE, TONA-FUTURE-3M) use the yaml
        # keys "payment_offset"/"basis_point" (underscore), but
        # DataConventionOvernightIndexFuture only recognizes "PAYMENT
        # OFFSET"/"BASIS POINT" (space) -- so .payment_offset / .basis_point are
        # None for every entry of this type.
        conv = self.registry.get("SOFR-FUTURE-1M")
        raw = self.raw_conventions["SOFR-FUTURE-1M"]["convention"]
        self.assertEqual(conv.payment_offset, Period(raw["payment_offset"]))
        self.assertEqual(conv.basis_point, float(raw["basis_point"]))

    @unittest.expectedFailure
    def test_swaption_and_capfloor_payment_conventions_should_resolve(self):
        # static_files/data_conventions.yaml: USD-SOFR-COMPOUND-SWAPTION and
        # USD-SOFR-COMPOUND-CAPFLOOR both use "payment_business_day_convention" /
        # "payment_holiday_convention" (underscore), but
        # DataConventionSwaption/DataConventionCapFloor only recognize "PAYMENT
        # BUSINESS DAY CONVENTION" / "PAYMENT HOLIDAY CONVENTION" (space) -- so both
        # properties are None for both entries.
        conv = self.registry.get("USD-SOFR-COMPOUND-SWAPTION")
        raw = self.raw_conventions["USD-SOFR-COMPOUND-SWAPTION"]["convention"]
        self.assertEqual(
            conv.payment_business_day_conv,
            BusinessDayConvention.new(raw["payment_business_day_convention"]),
        )
        self.assertEqual(
            conv.payment_holiday_conv, HolidayConvention.new(raw["payment_holiday_convention"])
        )

    @unittest.expectedFailure
    def test_jump_size_should_resolve(self):
        # static_files/data_conventions.yaml: USD-SOFR-JUMP uses "jump_size"
        # (underscore), but DataConventionJump only recognizes "JUMP SIZE" (space)
        # -- .jump_size is always None.
        conv = self.registry.get("USD-SOFR-JUMP")
        raw = self.raw_conventions["USD-SOFR-JUMP"]["convention"]
        self.assertEqual(conv.jump_size, float(raw["jump_size"]))

    @unittest.expectedFailure
    def test_ois_ibor_currency_basis_swap_ibor_side_fields_should_resolve(self):
        # static_files/data_conventions.yaml: AUD-LIBOR-BBA-3M-OVER-USD-SOFR-
        # COMPOUND-3M-OIS-IBOR-CBS uses "basis notional"/"basis overnight composite
        # index"/"basis accrual period"/"basis payment offset", but
        # DataConventionOISIBORCurrencyBasisSwap expects "IBOR NOTIONAL"/"IBOR
        # OVERNIGHT COMPOSITE INDEX"/"IBOR ACCRUAL PERIOD"/"IBOR PAYMENT OFFSET" --
        # so ibor_notional / ibor_on_index / ibor_accrual_period /
        # ibor_payment_offset are all None.
        name = "AUD-LIBOR-BBA-3M-OVER-USD-SOFR-COMPOUND-3M-OIS-IBOR-CBS"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertEqual(conv.ibor_notional, float(raw["basis notional"]))
        self.assertIsInstance(conv.ibor_on_index, IBORIndex)
        self.assertIs(conv.ibor_on_index, IndexRegistry().get(raw["basis overnight composite index"]))
        self.assertEqual(conv.ibor_accrual_period, Period(raw["basis accrual period"]))
        self.assertEqual(conv.ibor_payment_offset, Period(raw["basis payment offset"]))

    @unittest.expectedFailure
    def test_basis_swap_reference_index_should_resolve(self):
        # static_files/data_conventions.yaml: USD-LIBOR-BBA-1M-OVER-USD-LIBOR-BBA-3M-
        # BASIS-SWAP has the key "r4eference ibor index" (typo: "4" for "e"), so it
        # never matches DataConventionBasisSwap's "REFERENCE IBOR INDEX" branch --
        # .reference_index is None even though the field count (8) still matches.
        name = "USD-LIBOR-BBA-1M-OVER-USD-LIBOR-BBA-3M-BASIS-SWAP"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertIn("r4eference ibor index", raw)  # documents the typo exists today
        self.assertIsInstance(conv.reference_index, IBORIndex)
        self.assertIs(conv.reference_index, IndexRegistry().get(raw["r4eference ibor index"]))

    @unittest.expectedFailure
    def test_swap_index_should_resolve(self):
        # static_files/data_conventions.yaml: USD-SWAP-SEMI-BOND uses the key
        # "index", but DataConventionSwap expects "IBOR INDEX" -- .index is None.
        name = "USD-SWAP-SEMI-BOND"
        conv = self.registry.get(name)
        raw = self.raw_conventions[name]["convention"]
        self.assertIsInstance(conv.index, IBORIndex)
        self.assertIs(conv.index, IndexRegistry().get(raw["index"]))

    @unittest.expectedFailure
    def test_currency_basis_swap_mark_notional_to_market_property_should_exist(self):
        # DataConventionCurrencyBasisSwap (data_conventions.py ~1486-1573) stores
        # self.mark_notional_to_market_ (from the "MARK NOTIONAL TO MARKET" key,
        # correctly populated) but never defines a `mark_notional_to_market`
        # property to read it back -- unlike its siblings
        # DataConventionOvernightIndexCurrencyBasisSwap and
        # DataConventionOISIBORCurrencyBasisSwap, which both expose it. Callers can
        # only reach the value via the private `_` attribute today.
        conv = self.registry.get("GBP-LIBOR-BBA-3M-OVER-CAD-BA-3M-CBS")
        raw = self.raw_conventions["GBP-LIBOR-BBA-3M-OVER-CAD-BA-3M-CBS"]["convention"]
        self.assertEqual(conv.mark_notional_to_market, raw["mark notional to market"])

    @unittest.expectedFailure
    def test_fx_rate_index_usd_cad_and_usd_jpy_should_resolve(self):
        # static_files/data_conventions.yaml: USD-CAD and USD-JPY (type FX RATE
        # INDEX) both use the key "type" (e.g. {"type": "USD-CAD"}) instead of
        # "fx index", so DataConventionFXRateIndex's "FX INDEX" branch never fires
        # -- .fx_index is None for both entries. (GBP-USD, EUR-USD, AUD-USD use the
        # correct "fx index" key and work fine -- see TestPropertyTypesFXRateIndex.)
        for name in ["USD-CAD", "USD-JPY"]:
            with self.subTest(name=name):
                conv = self.registry.get(name)
                raw = self.raw_conventions[name]["convention"]
                self.assertIn("type", raw)  # documents the typo exists today
                self.assertIsInstance(conv.fx_index, FXIndex)


if __name__ == '__main__':
    unittest.main()

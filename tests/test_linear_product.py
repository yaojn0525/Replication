import sys
import os
import unittest

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath('..'))

from fixedincomelib import (
    Date,
    LongOrShort,
    ProductZeroSpread,
    qfCreateProductOvernightIndexFuture,
    qfCreateProductOvernightIndexSwap,
    qfCreateProductOvernightIndexBasisSwap,
    qfCreateProductOISBasisSwap,
    qfCreateProductCrossCurrencyBasisSwapNonMTM,
    qfCreateProductFromDataConvention,
    qfDisplayProduct,
    qfWriteProductToFile,
    qfReadProductFromFile,
)


class TestProductOvernightIndexFuture(unittest.TestCase):

    def test_parametric(self):
        prod = qfCreateProductOvernightIndexFuture(
            '2026-03-26', '2026-06-26', 'SOFR-1B', 'pay', 1e4, 'ACT/360', '3M'
        )
        self.assertEqual(prod.effective_date.ISO(), '2026-03-26')
        self.assertEqual(prod.termination_date.ISO(), '2026-06-26')
        self.assertEqual(prod.on_index.name(), 'SOFRON Actual/360')
        self.assertEqual(prod.pay_or_rec.to_string().upper(), 'PAY')
        self.assertEqual(prod.amount, 1e4)
        self.assertEqual(prod.strike, 0.0)
        self.assertGreaterEqual(prod.notional, 0.0)
        self.assertEqual(prod.long_or_short.to_string().upper(), 'LONG')

    def test_display(self):
        prod = qfCreateProductOvernightIndexFuture(
            '2026-03-26', '2026-06-26', 'SOFR-1B', 'pay', 1e4, 'ACT/360', '3M'
        )
        df = qfDisplayProduct(prod)
        self.assertEqual(
            df.loc[df['Name'] == 'Product Type', 'Value'].iloc[0],
            'PRODUCT_OVERNIGHT_INDEX_FUTURE',
        )

    def test_serialization_roundtrip(self):
        prod = qfCreateProductOvernightIndexFuture(
            '2026-03-26', '2026-06-26', 'SOFR-1B', 'pay', 1e4, 'ACT/360', '3M'
        )
        path = 'product_oi_future.pickle'
        qfWriteProductToFile(prod, path)
        try:
            prod_back = qfReadProductFromFile(path)
            self.assertEqual(prod_back.termination_date.ISO(), prod.termination_date.ISO())
            self.assertEqual(prod_back.amount, prod.amount)
        finally:
            os.remove(path)

    def test_from_data_convention(self):
        prod = qfCreateProductFromDataConvention(
            '2025-09-25', 'SOFR-FUTURE-3M', '2025-09-25x2025-12-25', 0.0
        )
        self.assertEqual(prod.product_type, 'PRODUCT_OVERNIGHT_INDEX_FUTURE')
        self.assertEqual(prod.effective_date.ISO(), '2025-09-25')
        self.assertEqual(prod.termination_date.ISO(), '2025-12-25')


class TestProductOvernightIndexSwap(unittest.TestCase):

    def test_parametric(self):
        prod = qfCreateProductOvernightIndexSwap(
            '2025-05-25', '2Y', '2D', 'SOFR-1B', 0.04, 'pay', 1e6, '1Y', 'ACT/360'
        )
        self.assertEqual(prod.effective_date.ISO(), '2025-05-25')
        self.assertEqual(prod.termination_date.ISO(), '2027-05-25')
        self.assertEqual(prod.fixed_rate, 0.04)
        self.assertEqual(prod.pay_or_rec.to_string().upper(), 'PAY')
        self.assertEqual(prod.notional, 1e6)
        self.assertEqual(prod.long_or_short.to_string().upper(), 'LONG')

    def test_legs(self):
        prod = qfCreateProductOvernightIndexSwap(
            '2025-05-25', '2Y', '2D', 'SOFR-1B', 0.04, 'pay', 1e6, '1Y', 'ACT/360'
        )
        floating_cf = prod.floating_leg_cash_flow(0)
        fixed_cf = prod.fixed_leg_cash_flow(0)
        self.assertEqual(floating_cf.product_type, 'PRODUCT_OVERNIGHT_INDEX_CASHFLOW')
        self.assertEqual(fixed_cf.product_type, 'PRODUCT_FIXED_ACCRUED')

    def test_serialization_roundtrip(self):
        prod = qfCreateProductOvernightIndexSwap(
            '2025-05-25', '2Y', '2D', 'SOFR-1B', 0.04, 'pay', 1e6, '1Y', 'ACT/360'
        )
        path = 'product_oi_swap.pickle'
        qfWriteProductToFile(prod, path)
        try:
            prod_back = qfReadProductFromFile(path)
            self.assertEqual(prod_back.fixed_rate, prod.fixed_rate)
            self.assertEqual(prod_back.notional, prod.notional)
        finally:
            os.remove(path)

    def test_from_data_convention(self):
        prod = qfCreateProductFromDataConvention(
            '2025-09-25', 'USD-SOFR-OIS', '5Y', 0.03
        )
        self.assertEqual(prod.product_type, 'PRODUCT_OVERNIGHT_INDEX_SWAP')
        self.assertEqual(prod.fixed_rate, 0.03)
        self.assertEqual(prod.termination_date.ISO(), '2030-09-25')

    def test_from_data_convention_notional_override(self):
        # regression test: ProductFactory.create_overnight_index_swap used to read
        # kwargs.get("notinoal", ...) (typo), silently ignoring this kwarg.
        prod = qfCreateProductFromDataConvention(
            '2025-09-25', 'USD-SOFR-OIS', '5Y', 0.03, notional=5e6
        )
        self.assertEqual(prod.notional, 5e6)


class TestProductOvernightIndexBasisSwap(unittest.TestCase):

    def test_parametric_oi_vs_oi(self):
        prod = qfCreateProductOvernightIndexBasisSwap(
            '2025-05-25', '2Y', '2D', 1e6, 'SOFR-1B', 'FF-1B',
            0.001, 'pay', '3M', '3M', 'ACT/360', '0D',
        )
        self.assertEqual(prod.on_index_str_1, 'SOFR-1B')
        self.assertEqual(prod.on_index_str_2, 'FF-1B')
        self.assertEqual(prod.spread, 0.001)
        self.assertEqual(prod.notional, 1e6)

    def test_parametric_oi_vs_ibor(self):
        # leg 2 is a genuine IBOR index (custom IborIndex wrapper, not a true ql index).
        # ProductOvernightIndexCashflow must detect this and adapt accordingly.
        prod = qfCreateProductOvernightIndexBasisSwap(
            '2025-05-25', '2Y', '2D', 1e6, 'SOFR-1B', 'USD-TERM-SOFR-3M',
            0.001, 'pay', '3M', '3M', 'ACT/360', '0D',
        )
        leg1_cf = prod.floating_leg_1_cash_flow(0)
        leg2_cf = prod.floating_leg_2_cash_flow(0)
        self.assertEqual(leg1_cf.on_index.name(), 'SOFRON Actual/360')
        self.assertEqual(leg2_cf.on_index.name(), 'USD-TERM-SOFR-3M')
        self.assertTrue(leg2_cf.is_ibor_index)
        self.assertFalse(leg1_cf.is_ibor_index)

    def test_serialization_roundtrip(self):
        prod = qfCreateProductOvernightIndexBasisSwap(
            '2025-05-25', '2Y', '2D', 1e6, 'SOFR-1B', 'FF-1B',
            0.001, 'pay', '3M', '3M', 'ACT/360', '0D',
        )
        path = 'product_oi_basis_swap.pickle'
        qfWriteProductToFile(prod, path)
        try:
            prod_back = qfReadProductFromFile(path)
            self.assertEqual(prod_back.spread, prod.spread)
            self.assertEqual(prod_back.notional, prod.notional)
        finally:
            os.remove(path)

    def test_from_data_convention_oi_vs_ibor(self):
        prod = qfCreateProductFromDataConvention(
            '2025-09-25',
            'USD-SOFR-COMPOUND-OVER-USD-TERM-SOFR-3M-BASIS-SWAP',
            '5Y',
            0.001,
        )
        self.assertEqual(prod.product_type, 'PRODUCT_OVERNIGHT_INDEX_BASIS_SWAP')
        leg2_cf = prod.floating_leg_2_cash_flow(0)
        self.assertTrue(leg2_cf.is_ibor_index)
        self.assertEqual(leg2_cf.on_index.name(), 'USD-TERM-SOFR-3M')

    def test_from_data_convention_notional_override(self):
        prod = qfCreateProductFromDataConvention(
            '2025-09-25',
            'USD-SOFR-COMPOUND-OVER-USD-TERM-SOFR-3M-BASIS-SWAP',
            '5Y',
            0.001,
            notional=3e6,
        )
        self.assertEqual(prod.notional, 3e6)


class TestProductOISBasisSwap(unittest.TestCase):

    def test_parametric(self):
        prod = qfCreateProductOISBasisSwap(
            '2025-05-25', '2Y', '2D', 1e6, 'FF-1B', 'SOFR-1B',
            0.001, 'pay', '3M', '3M', 'ACT/360', '0D',
        )
        self.assertEqual(prod.on_index_str_1, 'FF-1B')
        self.assertEqual(prod.on_index_str_2, 'SOFR-1B')
        self.assertEqual(prod.spread, 0.001)
        self.assertEqual(prod.notional, 1e6)

    def test_legs(self):
        prod = qfCreateProductOISBasisSwap(
            '2025-05-25', '2Y', '2D', 1e6, 'FF-1B', 'SOFR-1B',
            0.001, 'pay', '3M', '3M', 'ACT/360', '0D',
        )
        leg1_cf = prod.floating_leg_1_cash_flow(0)
        leg2_cf = prod.floating_leg_2_cash_flow(0)
        self.assertFalse(leg1_cf.is_ibor_index)
        self.assertFalse(leg2_cf.is_ibor_index)

    def test_serialization_roundtrip(self):
        prod = qfCreateProductOISBasisSwap(
            '2025-05-25', '2Y', '2D', 1e6, 'FF-1B', 'SOFR-1B',
            0.001, 'pay', '3M', '3M', 'ACT/360', '0D',
        )
        path = 'product_ois_basis_swap.pickle'
        qfWriteProductToFile(prod, path)
        try:
            prod_back = qfReadProductFromFile(path)
            self.assertEqual(prod_back.spread, prod.spread)
            self.assertEqual(prod_back.notional, prod.notional)
        finally:
            os.remove(path)

    def test_from_data_convention(self):
        prod = qfCreateProductFromDataConvention(
            '2025-09-25', 'USD-FF-3M-OVER-USD-SOFR-OIS-3M', '5Y', 0.001
        )
        self.assertEqual(prod.product_type, 'PRODUCT_OIS_BASIS_SWAP')
        self.assertEqual(prod.on_index_str_1, 'FF-1B')
        self.assertEqual(prod.on_index_str_2, 'SOFR-1B')

    def test_from_data_convention_notional_override(self):
        # regression test: ProductFactory.create_ois_basis_swap used to read
        # kwargs.get("notinoal", ...) (typo), silently ignoring this kwarg.
        prod = qfCreateProductFromDataConvention(
            '2025-09-25', 'USD-FF-3M-OVER-USD-SOFR-OIS-3M', '5Y', 0.001, notional=2e6
        )
        self.assertEqual(prod.notional, 2e6)


class TestProductOvernightIndexCurrencyBasisSwapNonMTM(unittest.TestCase):

    def test_parametric(self):
        prod = qfCreateProductCrossCurrencyBasisSwapNonMTM(
            '2025-05-25', '5Y', 'EONIA-1B', 'SOFR-1B', 'pay', 1e7, 1.08, None,
            0.001, True, '2D', 'TARGET', '3M', '3M', 'ACT/360', 'ACT/360', '0D', '0D',
        )
        self.assertEqual(prod.basis_index_str, 'EONIA-1B')
        self.assertEqual(prod.reference_index_str, 'SOFR-1B')
        self.assertEqual(prod.reference_notional, 1e7)
        self.assertAlmostEqual(prod.basis_notional, 1e7 / 1.08)

    def test_notional_exchanges(self):
        prod = qfCreateProductCrossCurrencyBasisSwapNonMTM(
            '2025-05-25', '5Y', 'EONIA-1B', 'SOFR-1B', 'pay', 1e7, 1.08, None,
            0.001, True, '2D', 'TARGET', '3M', '3M', 'ACT/360', 'ACT/360', '0D', '0D',
        )
        self.assertIsNotNone(prod.notional_exchange_start_b)
        self.assertIsNotNone(prod.notional_exchange_end_r)

    def test_serialization_roundtrip(self):
        prod = qfCreateProductCrossCurrencyBasisSwapNonMTM(
            '2025-05-25', '5Y', 'EONIA-1B', 'SOFR-1B', 'pay', 1e7, 1.08, None,
            0.001, True, '2D', 'TARGET', '3M', '3M', 'ACT/360', 'ACT/360', '0D', '0D',
        )
        path = 'product_xccy_basis_swap.pickle'
        qfWriteProductToFile(prod, path)
        try:
            prod_back = qfReadProductFromFile(path)
            self.assertEqual(prod_back.reference_notional, prod.reference_notional)
            self.assertEqual(prod_back.basis_spread, prod.basis_spread)
        finally:
            os.remove(path)

    def test_from_data_convention(self):
        prod = qfCreateProductFromDataConvention(
            '2025-09-25',
            'GBP-SONIA-COMPOUND-3M-OVER-USD-SOFR-COMPOUND-3M',
            '5Y',
            0.001,
            fx_spot_r_per_b_0=1.25,
            reference_notional=1e7,
        )
        self.assertEqual(prod.product_type, 'PRODUCT_XCCY_BASIS_SWAP_NON_MTM')
        self.assertEqual(prod.basis_index_str, 'SONIA-1B')
        self.assertEqual(prod.reference_index_str, 'SOFR-1B')
        self.assertEqual(prod.reference_notional, 1e7)
        self.assertAlmostEqual(prod.basis_notional, 1e7 / 1.25)


class TestProductZeroSpread(unittest.TestCase):

    def test_parametric(self):
        prod = ProductZeroSpread(
            Date('2026-05-26'), 'SOFR-1B', 'FF-1B', 0.001, 1e6,
            LongOrShort.from_string('LONG'),
        )
        self.assertEqual(prod.basis_index_str, 'SOFR-1B')
        self.assertEqual(prod.reference_index_str, 'FF-1B')
        self.assertEqual(prod.zero_rate, 0.001)
        self.assertEqual(prod.notional, 1e6)
        self.assertEqual(prod.long_or_short.to_string().upper(), 'LONG')

    def test_serialization_roundtrip(self):
        prod = ProductZeroSpread(
            Date('2026-05-26'), 'SOFR-1B', 'FF-1B', 0.001, 1e6,
            LongOrShort.from_string('LONG'),
        )
        path = 'product_zero_spread.pickle'
        qfWriteProductToFile(prod, path)
        try:
            prod_back = qfReadProductFromFile(path)
            self.assertEqual(prod_back.zero_rate, prod.zero_rate)
            self.assertEqual(prod_back.notional, prod.notional)
        finally:
            os.remove(path)

    def test_from_data_convention_not_supported(self):
        # known pre-existing data gap: no named ZERO SPREAD convention in
        # data_conventions.json currently resolves through IndexRegistry (missing
        # -CALIB/-FLAT indices, or a bare currency code used as reference_index).
        with self.assertRaises(Exception):
            qfCreateProductFromDataConvention(
                '2025-09-25', 'SOFR-1B-OVER-USD-ZERO-SPREAD', '5Y', 0.001
            )


if __name__ == '__main__':
    unittest.main()

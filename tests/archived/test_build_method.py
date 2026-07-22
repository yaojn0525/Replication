import sys
import os
import unittest
import tempfile
import pandas as pd

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath('..'))

from fixedincomelib import (
    qfCreateBuildMethod,
    qfDisplayModelBuildMethod,
    qfWriteBuildMethodToFile,
    qfReadBuildMethodFromFile,
    qfCreateModelBuildMethodCollection,
    qfWriteBuildMethodCollectionToFile,
    qfReadBuildMethodCollectionFromFile,
    qfDisplayModelBuildMethodCollection,
)


class TestQfCreateBuildMethod(unittest.TestCase):

    def test_yield_curve_index(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_INDEX', {
            'TARGET': 'SOFR-1B',
            'OVERNIGHT INDEX FUTURE': 'SOFR-FUTURE-3M',
            'OVERNIGHT INDEX SWAP': 'USD-SOFR-OIS',
            'INSTANTANEOUS FORWARD RATE': 'USD-SOFR-IFR',
        })
        self.assertEqual(bm.type, 'YIELD_CURVE_INDEX')
        self.assertEqual(bm.target, 'SOFR-1B')
        self.assertEqual(bm['OVERNIGHT INDEX FUTURE'], 'SOFR-FUTURE-3M')
        self.assertEqual(bm['OVERNIGHT INDEX SWAP'], 'USD-SOFR-OIS')
        self.assertEqual(bm['INSTANTANEOUS FORWARD RATE'], 'USD-SOFR-IFR')
        self.assertEqual(bm['SWAP'], '')
        self.assertEqual(bm['FIXING'], '')
        self.assertEqual(bm['LIBOR FUTURE'], '')
        self.assertEqual(bm['OVERNIGHT INDEX BASIS SWAP'], '')
        self.assertEqual(bm['CROSS CURRENCY BASIS SWAP NON MTM'], '')
        self.assertEqual(bm['INTERPOLATION METHOD'], 'PIECEWISE_CONSTANT_LEFT_CONTINUOUS')
        self.assertEqual(bm['EXTRAPOLATION METHOD'], 'FLAT')

    def test_yield_curve_fx(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_FX', {
            'TARGET': 'EUR-USD',
            'FX SPOT RATE': 'EUR-USD',
        })
        self.assertEqual(bm.type, 'YIELD_CURVE_FX')
        self.assertEqual(bm.target, 'EUR-USD')
        self.assertEqual(bm['FX SPOT RATE'], 'EUR-USD')
        self.assertEqual(bm['INTERPOLATION METHOD'], 'PIECEWISE_CONSTANT_LEFT_CONTINUOUS')
        self.assertEqual(bm['EXTRAPOLATION METHOD'], 'FLAT')

    def test_yield_curve_funding(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_FUNDING', {
            'TARGET': 'USD',
            'SPREAD ZERO RATE': 'USD-SPREAD-ZR',
            'REFERENCE INDEX': 'SOFR-1B',
        })
        self.assertEqual(bm.type, 'YIELD_CURVE_FUNDING')
        self.assertEqual(bm.target, 'USD')
        self.assertEqual(bm['SPREAD ZERO RATE'], 'USD-SPREAD-ZR')
        self.assertEqual(bm['REFERENCE INDEX'], 'SOFR-1B')
        self.assertEqual(bm['BOND FIXED'], '')
        self.assertEqual(bm['CROSS CURRENCY BASIS SWAP NON MTM'], '')
        self.assertEqual(bm['INTERPOLATION METHOD'], 'PIECEWISE_CONSTANT_LEFT_CONTINUOUS')
        self.assertEqual(bm['EXTRAPOLATION METHOD'], 'FLAT')

    def test_yield_curve_common(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_COMMON', {
            'TARGET': 'USD',
            'FUNDING PARAMETERS': 'USD-FUNDING-PARAMETERS',
            'SOLVER': 'BRENT',
        })
        self.assertEqual(bm.type, 'YIELD_CURVE_COMMON')
        self.assertEqual(bm.target, 'USD')
        self.assertEqual(bm['FUNDING PARAMETERS'], 'USD-FUNDING-PARAMETERS')
        self.assertEqual(bm['SOLVER'], 'BRENT')

    def test_missing_target_raises(self):
        with self.assertRaises(AssertionError):
            qfCreateBuildMethod('YIELD_CURVE_INDEX', {'OVERNIGHT INDEX SWAP': 'USD-SOFR-OIS'})

    def test_invalid_key_raises(self):
        with self.assertRaises(Exception):
            qfCreateBuildMethod('YIELD_CURVE_INDEX', {'TARGET': 'SOFR-1B', 'INVALID KEY': 'X'})


class TestQfDisplayModelBuildMethod(unittest.TestCase):

    def _assert_display(self, bm, expected_kv):
        df = qfDisplayModelBuildMethod(bm)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(list(df.columns), ['Name', 'Value'])
        for name, value in expected_kv.items():
            self.assertEqual(df.loc[df['Name'] == name, 'Value'].iloc[0], value)

    def test_yield_curve_index(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_INDEX', {
            'TARGET': 'SOFR-1B',
            'OVERNIGHT INDEX SWAP': 'USD-SOFR-OIS',
        })
        self._assert_display(bm, {
            'TARGET': 'SOFR-1B',
            'OVERNIGHT INDEX SWAP': 'USD-SOFR-OIS',
        })

    def test_yield_curve_fx(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_FX', {
            'TARGET': 'EUR-USD',
            'FX SPOT RATE': 'EUR-USD',
        })
        self._assert_display(bm, {'TARGET': 'EUR-USD', 'FX SPOT RATE': 'EUR-USD'})

    def test_yield_curve_funding(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_FUNDING', {
            'TARGET': 'USD',
            'SPREAD ZERO RATE': 'USD-SPREAD-ZR',
        })
        self._assert_display(bm, {'TARGET': 'USD', 'SPREAD ZERO RATE': 'USD-SPREAD-ZR'})

    def test_yield_curve_common(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_COMMON', {
            'TARGET': 'USD',
            'FUNDING PARAMETERS': 'USD-FUNDING-PARAMETERS',
        })
        self._assert_display(bm, {
            'TARGET': 'USD',
            'FUNDING PARAMETERS': 'USD-FUNDING-PARAMETERS',
        })


class TestQfWriteReadBuildMethod(unittest.TestCase):

    def setUp(self):
        fd, self.tmp = tempfile.mkstemp(suffix='.pickle')
        os.close(fd)
        os.unlink(self.tmp)

    def tearDown(self):
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def _assert_round_trip(self, bm, keys):
        result = qfWriteBuildMethodToFile(bm, self.tmp)
        self.assertEqual(result, 'DONE')
        self.assertTrue(os.path.exists(self.tmp))
        bm_back = qfReadBuildMethodFromFile(self.tmp)
        self.assertEqual(bm_back.type, bm.type)
        self.assertEqual(bm_back.target, bm.target)
        for k in keys:
            self.assertEqual(bm_back[k], bm[k])

    def test_yield_curve_index(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_INDEX', {
            'TARGET': 'SOFR-1B',
            'OVERNIGHT INDEX SWAP': 'USD-SOFR-OIS',
            'INSTANTANEOUS FORWARD RATE': 'USD-SOFR-IFR',
        })
        self._assert_round_trip(bm, [
            'OVERNIGHT INDEX SWAP',
            'INSTANTANEOUS FORWARD RATE',
            'INTERPOLATION METHOD',
            'EXTRAPOLATION METHOD',
        ])

    def test_yield_curve_fx(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_FX', {
            'TARGET': 'EUR-USD',
            'FX SPOT RATE': 'EUR-USD',
        })
        self._assert_round_trip(bm, [
            'FX SPOT RATE',
            'INTERPOLATION METHOD',
            'EXTRAPOLATION METHOD',
        ])

    def test_yield_curve_funding(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_FUNDING', {
            'TARGET': 'USD',
            'SPREAD ZERO RATE': 'USD-SPREAD-ZR',
            'REFERENCE INDEX': 'SOFR-1B',
        })
        self._assert_round_trip(bm, [
            'SPREAD ZERO RATE',
            'REFERENCE INDEX',
            'INTERPOLATION METHOD',
            'EXTRAPOLATION METHOD',
        ])

    def test_yield_curve_common(self):
        bm = qfCreateBuildMethod('YIELD_CURVE_COMMON', {
            'TARGET': 'USD',
            'FUNDING PARAMETERS': 'USD-FUNDING-PARAMETERS',
            'SOLVER': 'BRENT',
        })
        self._assert_round_trip(bm, ['FUNDING PARAMETERS', 'SOLVER'])


class TestQfBuildMethodCollection(unittest.TestCase):

    def setUp(self):
        self.bm_idx = qfCreateBuildMethod('YIELD_CURVE_INDEX', {
            'TARGET': 'SOFR-1B',
            'OVERNIGHT INDEX SWAP': 'USD-SOFR-OIS',
            'INSTANTANEOUS FORWARD RATE': 'USD-SOFR-IFR',
        })
        self.bm_fx = qfCreateBuildMethod('YIELD_CURVE_FX', {
            'TARGET': 'EUR-USD',
            'FX SPOT RATE': 'EUR-USD',
        })
        self.bm_fnd = qfCreateBuildMethod('YIELD_CURVE_FUNDING', {
            'TARGET': 'USD',
            'SPREAD ZERO RATE': 'USD-SPREAD-ZR',
            'REFERENCE INDEX': 'SOFR-1B',
        })
        self.bm_com = qfCreateBuildMethod('YIELD_CURVE_COMMON', {
            'TARGET': 'USD',
            'FUNDING PARAMETERS': 'USD-FUNDING-PARAMETERS',
        })
        self.bm_col = qfCreateModelBuildMethodCollection(
            [self.bm_idx, self.bm_fx, self.bm_fnd, self.bm_com]
        )
        fd, self.tmp = tempfile.mkstemp(suffix='.pickle')
        os.close(fd)
        os.unlink(self.tmp)

    def tearDown(self):
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_create_size(self):
        self.assertEqual(self.bm_col.num_build_methods, 4)

    def test_create_retrieve_index(self):
        bm = self.bm_col.get_build_method_from_build_method_collection('SOFR-1B', 'YIELD_CURVE_INDEX')
        self.assertEqual(bm.type, 'YIELD_CURVE_INDEX')
        self.assertEqual(bm.target, 'SOFR-1B')

    def test_create_retrieve_fx(self):
        bm = self.bm_col.get_build_method_from_build_method_collection('EUR-USD', 'YIELD_CURVE_FX')
        self.assertEqual(bm.type, 'YIELD_CURVE_FX')
        self.assertEqual(bm.target, 'EUR-USD')

    def test_create_retrieve_funding(self):
        bm = self.bm_col.get_build_method_from_build_method_collection('USD', 'YIELD_CURVE_FUNDING')
        self.assertEqual(bm.type, 'YIELD_CURVE_FUNDING')
        self.assertEqual(bm.target, 'USD')

    def test_create_retrieve_common(self):
        bm = self.bm_col.get_build_method_from_build_method_collection('USD', 'YIELD_CURVE_COMMON')
        self.assertEqual(bm.type, 'YIELD_CURVE_COMMON')
        self.assertEqual(bm.target, 'USD')

    def test_write_read_round_trip(self):
        result = qfWriteBuildMethodCollectionToFile(self.bm_col, self.tmp)
        self.assertEqual(result, 'DONE')
        self.assertTrue(os.path.exists(self.tmp))

        col_back = qfReadBuildMethodCollectionFromFile(self.tmp)
        self.assertEqual(col_back.num_build_methods, self.bm_col.num_build_methods)

        idx_back = col_back.get_build_method_from_build_method_collection('SOFR-1B', 'YIELD_CURVE_INDEX')
        self.assertEqual(idx_back.type, 'YIELD_CURVE_INDEX')
        self.assertEqual(idx_back['OVERNIGHT INDEX SWAP'], 'USD-SOFR-OIS')

        fx_back = col_back.get_build_method_from_build_method_collection('EUR-USD', 'YIELD_CURVE_FX')
        self.assertEqual(fx_back.type, 'YIELD_CURVE_FX')
        self.assertEqual(fx_back['FX SPOT RATE'], 'EUR-USD')

        fnd_back = col_back.get_build_method_from_build_method_collection('USD', 'YIELD_CURVE_FUNDING')
        self.assertEqual(fnd_back.type, 'YIELD_CURVE_FUNDING')
        self.assertEqual(fnd_back['SPREAD ZERO RATE'], 'USD-SPREAD-ZR')

        com_back = col_back.get_build_method_from_build_method_collection('USD', 'YIELD_CURVE_COMMON')
        self.assertEqual(com_back.type, 'YIELD_CURVE_COMMON')
        self.assertEqual(com_back['FUNDING PARAMETERS'], 'USD-FUNDING-PARAMETERS')

    def test_display_collection(self):
        df = qfDisplayModelBuildMethodCollection(self.bm_col)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(list(df.columns), ['Name', 'Value'])
        self.assertIn('YIELD_CURVE_INDEX', df['Name'].values)
        self.assertIn('YIELD_CURVE_FX', df['Name'].values)
        self.assertIn('YIELD_CURVE_FUNDING', df['Name'].values)
        self.assertIn('YIELD_CURVE_COMMON', df['Name'].values)
        self.assertIn('SOFR-1B', df['Value'].values)
        self.assertIn('EUR-USD', df['Value'].values)


if __name__ == '__main__':
    unittest.main()

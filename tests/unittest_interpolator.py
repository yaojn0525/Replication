import sys
import os
import unittest

import numpy as np
import torch

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath('..'))

from fixedincomelib import qfCreate1DInterpolator, qfCreate2DInterpolator


def to_np(t):
    if isinstance(t, torch.Tensor):
        return t.detach().numpy()
    return np.asarray(t)


def bump_reval_1d_interpolate(x, axis1, values, interp_method, extrap_method, bump_size=1e-4):
    base = qfCreate1DInterpolator(axis1, values, interp_method, extrap_method)
    b_value = to_np(base.interpolate(x))
    grad = []
    for i in range(len(values)):
        values[i] += bump_size
        bumped = to_np(
            qfCreate1DInterpolator(axis1, values, interp_method, extrap_method).interpolate(x)
        )
        grad.append(np.sum((bumped - b_value) / bump_size))
        values[i] -= bump_size
    return np.array(grad)


def bump_reval_1d_integrate(x_s, x_e, axis1, values, interp_method, extrap_method, bump_size=1e-4):
    base = qfCreate1DInterpolator(axis1, values, interp_method, extrap_method)
    b_value = to_np(base.integrate(x_s, x_e))
    grad = []
    for i in range(len(values)):
        values[i] += bump_size
        bumped = to_np(
            qfCreate1DInterpolator(axis1, values, interp_method, extrap_method).integrate(x_s, x_e)
        )
        grad.append(np.sum((bumped - b_value) / bump_size))
        values[i] -= bump_size
    return np.array(grad)


def bump_reval_2d_interpolate(x, y, axis1, axis2, values, interp_method, extrap_method, bump_size=1e-4):
    base = qfCreate2DInterpolator(axis1, axis2, values, interp_method, extrap_method)
    b_value = base.interpolate(x, y)
    grad = []
    for i in range(len(values)):
        for j in range(len(values[0])):
            values[i][j] += bump_size
            bumped = qfCreate2DInterpolator(
                axis1, axis2, values, interp_method, extrap_method
            ).interpolate(x, y)
            grad.append((bumped - b_value) / bump_size)
            values[i][j] -= bump_size
    return np.array(grad)


def analytic_grad_wrt_ordinate_1d(x, axis1, values, interp_method, extrap_method):
    """grad of sum_i interp(x_i) wrt values, via backward() called outside interpolate()."""
    interp = qfCreate1DInterpolator(axis1, values, interp_method, extrap_method)
    out = interp.interpolate(x, calc_grad=True)
    out_sum = out if out.dim() == 0 else out.sum()
    out_sum.backward()
    return interp.values_.grad.detach().numpy()


def analytic_grad_of_integrated_value_wrt_ordinate_1d(x_s, x_e, axis1, values, interp_method, extrap_method):
    """grad of sum_i integrate(x_s_i, x_e_i) wrt values, via backward() called outside integrate()."""
    interp = qfCreate1DInterpolator(axis1, values, interp_method, extrap_method)
    out = interp.integrate(x_s, x_e, calc_grad=True)
    out_sum = out if out.dim() == 0 else out.sum()
    out_sum.backward()
    return interp.values_.grad.detach().numpy()


class TestInterpolator1D(unittest.TestCase):

    def setUp(self):
        self.axis1 = [1, 3, 5, 7]
        self.values = [3, 4, 5, 6]
        self.interp_method = 'PIECEWISE_CONSTANT_LEFT_CONTINUOUS'
        self.extrap_method = 'FLAT'
        self.interp = qfCreate1DInterpolator(
            self.axis1, self.values, self.interp_method, self.extrap_method
        )

    # ---- interpolate ----

    def test_interpolate_regular_and_corner_cases(self):
        # (x, expected, description)
        cases = [
            (1,    4, 'left knot [1,3)'),
            (1.5,  4, 'interior [1,3)'),
            (3,    5, 'middle knot [3,5)'),
            (5,    6, 'knot [5,7)'),
            (5.5,  6, 'interior [5,7)'),
            (7,    6, 'right boundary (flat extrap)'),
            (0.5,  3, 'left extrapolation'),
            (-99,  3, 'far left extrapolation'),
            (6.5,  6, 'interior [5,7)'),
            (100,  6, 'far right extrapolation'),
        ]
        for x, expected, desc in cases:
            with self.subTest(desc=desc):
                self.assertAlmostEqual(float(self.interp.interpolate(x)), expected, places=10)

    def test_interpolate_scalar_input_no_array_wrapping(self):
        out = self.interp.interpolate(2.5)
        self.assertIsInstance(out, torch.Tensor)
        self.assertEqual(out.dim(), 0)

    def test_interpolate_array_matches_scalar(self):
        cases = {
            'single-element array': np.array([1.5]),
            'all left extrap': np.array([-100.0, -1, 0.5, 0.99]),
            'all right extrap': np.array([7.0, 8, 100, 999]),
            'all at knots': np.array([1.0, 3, 5, 7]),
            'mixed interior+extrap': np.array([-5.0, 1, 1.5, 3, 4, 5.5, 7, 20]),
            'duplicate x values': np.array([3.0, 3, 3, 3]),
        }
        for desc, x_arr in cases.items():
            with self.subTest(desc=desc):
                res = to_np(self.interp.interpolate(x_arr))
                exp = np.array([to_np(self.interp.interpolate(float(xi))) for xi in x_arr])
                np.testing.assert_allclose(res, exp, atol=1e-12)

    # ---- integrate ----

    def test_integrate_regular_and_corner_cases(self):
        # (x_s, x_e, expected, description)
        cases = [
            (0.5,  0.9,   1.2, 'both in left wing'),
            (0.5,  1.2,   2.3, 'left wing to first bucket'),
            (0.5,  3.2,  10.5, 'left wing to middle'),
            (1.5,  5.2,  17.2, 'interior span'),
            (3.5,  7.2,  20.7, 'middle to right wing'),
            (6,    7.2,   7.2, 'last bucket to right wing'),
            (8,   10,    12.0, 'both in right wing'),
            (0.1, 10,    50.7, 'full span'),
            (2,    2,     0.0, 'zero-width interval'),
            (1,    3,     8.0, 'knot-to-knot [1,3)'),
            (1,    7,    30.0, 'full interior [1,7)'),
            (-5,  15,    96.0, 'far left to far right'),
        ]
        for x_s, x_e, expected, desc in cases:
            with self.subTest(desc=desc):
                self.assertAlmostEqual(float(self.interp.integrate(x_s, x_e)), expected, places=8)

    def test_integrate_array_matches_scalar(self):
        cases = {
            'single pair': (np.array([1.5]), np.array([4.5])),
            'all zero-width': (np.array([1.0, 3, 5]), np.array([1.0, 3, 5])),
            'all left extrap': (np.array([-5.0, -3]), np.array([-2.0, -1])),
            'all right extrap': (np.array([8.0, 10]), np.array([9.0, 12])),
            'reversed s > e -> 0': (np.array([3.0, 5]), np.array([1.0, 2])),
            'mixed spans': (np.array([-5.0, 1, 3]), np.array([1.0, 5, 15])),
            'same start, diff end': (np.array([1.0, 1, 1]), np.array([3.0, 5, 7])),
            'same end, diff start': (np.array([1.0, 3, 5]), np.array([7.0, 7, 7])),
        }
        for desc, (s_arr, e_arr) in cases.items():
            with self.subTest(desc=desc):
                res = to_np(self.interp.integrate(s_arr, e_arr))
                exp = np.array([
                    to_np(self.interp.integrate(float(s), float(e))) for s, e in zip(s_arr, e_arr)
                ])
                np.testing.assert_allclose(res, exp, atol=1e-12)

    # ---- gradient wrt ordinate (via interpolate + external backward) ----

    def test_gradient_wrt_ordinate_scalar_matches_bump_reval(self):
        cases = [
            (1,    'left knot'),
            (1.5,  'interior [1,3)'),
            (3,    'middle knot'),
            (5,    'knot [5,7)'),
            (7,    'right boundary'),
            (0.5,  'left extrapolation'),
            (-99,  'far left extrapolation'),
            (6.5,  'interior [5,7)'),
            (100,  'far right extrapolation'),
        ]
        for x, desc in cases:
            with self.subTest(desc=desc):
                grad_analytic = analytic_grad_wrt_ordinate_1d(
                    x, self.axis1, self.values, self.interp_method, self.extrap_method
                )
                grad_br = bump_reval_1d_interpolate(
                    x, self.axis1, self.values, self.interp_method, self.extrap_method
                )
                np.testing.assert_allclose(grad_analytic, grad_br, atol=1e-6)

    def test_gradient_wrt_ordinate_array_sums_per_point_grads(self):
        cases = {
            'single element': np.array([1.5]),
            'all same point': np.array([3.0, 3.0, 3.0]),
            'all left extrap': np.array([-5.0, -1, 0.5]),
            'all right extrap': np.array([7.5, 10.0, 100]),
            'knot points only': np.array([1.0, 3, 5, 7]),
            'mixed all regions': np.array([-1.0, 1, 2, 3, 4, 5, 6, 7, 8]),
        }
        for desc, x_arr in cases.items():
            with self.subTest(desc=desc):
                g_vec = analytic_grad_wrt_ordinate_1d(
                    x_arr, self.axis1, self.values, self.interp_method, self.extrap_method
                )
                g_exp = sum(
                    analytic_grad_wrt_ordinate_1d(
                        float(xi), self.axis1, self.values, self.interp_method, self.extrap_method
                    )
                    for xi in x_arr
                )
                np.testing.assert_allclose(g_vec, g_exp, atol=1e-10)

    # ---- gradient of integrated value wrt ordinate (via integrate + external backward) ----

    def test_gradient_of_integrated_value_scalar_matches_bump_reval(self):
        cases = [
            ((0.5, 0.9),  'both in left wing'),
            ((0.5, 1.2),  'left wing to first bucket'),
            ((0.5, 3.2),  'left wing to middle'),
            ((1.5, 5.2),  'interior span'),
            ((3.5, 7.2),  'middle to right wing'),
            ((6,   7.2),  'last bucket to right wing'),
            ((8,  10),    'both in right wing'),
            ((0.1, 10),   'full span'),
            ((2,   2),    'zero-width interval'),
            ((1,   3),    'knot-to-knot [1,3)'),
            ((1,   7),    'full interior [1,7)'),
        ]
        for (x_s, x_e), desc in cases:
            with self.subTest(desc=desc):
                grad_analytic = analytic_grad_of_integrated_value_wrt_ordinate_1d(
                    x_s, x_e, self.axis1, self.values, self.interp_method, self.extrap_method
                )
                grad_br = bump_reval_1d_integrate(
                    x_s, x_e, self.axis1, self.values, self.interp_method, self.extrap_method
                )
                np.testing.assert_allclose(grad_analytic, grad_br, atol=1e-6)

    def test_gradient_of_integrated_value_array_sums_per_pair_grads(self):
        cases = {
            'single pair': (np.array([1.5]), np.array([4.5])),
            'all zero-width': (np.array([1.0, 3, 5]), np.array([1.0, 3, 5])),
            'all same interval': (np.array([1.0, 1, 1]), np.array([3.0, 3, 3])),
            'mixed spans': (np.array([-5.0, 1, 3]), np.array([1.0, 5, 15])),
            'extrap intervals': (np.array([-10.0, 8]), np.array([-5.0, 12])),
        }
        for desc, (s_arr, e_arr) in cases.items():
            with self.subTest(desc=desc):
                g_vec = analytic_grad_of_integrated_value_wrt_ordinate_1d(
                    s_arr, e_arr, self.axis1, self.values, self.interp_method, self.extrap_method
                )
                g_exp = sum(
                    analytic_grad_of_integrated_value_wrt_ordinate_1d(
                        float(s), float(e), self.axis1, self.values, self.interp_method, self.extrap_method
                    )
                    for s, e in zip(s_arr, e_arr)
                )
                np.testing.assert_allclose(g_vec, g_exp, atol=1e-10)


class TestInterpolator2D(unittest.TestCase):

    def setUp(self):
        self.axis1 = [1, 3, 5, 7]
        self.axis2 = [10, 20, 30]
        self.values = [[11, 12, 13],
                        [21, 22, 23],
                        [31, 32, 33],
                        [41, 42, 43]]
        self.interp_method = 'LINEAR'
        self.extrap_method = 'FLAT'
        self.interp = qfCreate2DInterpolator(
            self.axis1, self.axis2, self.values, self.interp_method, self.extrap_method
        )

    # ---- interpolate ----

    def test_interpolate_regular_and_corner_cases(self):
        # (x, y, expected, description)
        cases = [
            (1,    10,  11.0, 'grid corner (1,10)'),
            (1.5,  15,  14.0, 'interior point'),
            (3,    20,  22.0, 'grid point (3,20)'),
            (7,    30,  43.0, 'grid corner (7,30)'),
            (7,    10,  41.0, 'right x boundary, low y'),
            (1,    30,  13.0, 'left x, high y boundary'),
            (0.5,  15,  11.5, 'left x extrapolation'),
            (6.5,  15,  39.0, 'right x extrapolation'),
            (3,     5,  21.0, 'low y extrapolation'),
            (3,    35,  23.0, 'high y extrapolation'),
            (-10,  -5,  11.0, 'far left/low extrapolation'),
            (100, 100,  43.0, 'far right/high extrapolation'),
        ]
        for x, y, expected, desc in cases:
            with self.subTest(desc=desc):
                self.assertAlmostEqual(self.interp.interpolate(x, y), expected, places=8)

    def test_interpolate_array_matches_scalar(self):
        cases = {
            'single pair': (np.array([1.5]), np.array([15.0])),
            'all grid corners': (np.array([1, 1, 7, 7.0]), np.array([10, 30, 10, 30.0])),
            'all left-x extrap': (np.array([-5, -5, -5.0]), np.array([10, 20, 30.0])),
            'all high-y extrap': (np.array([2, 4, 6.0]), np.array([50, 50, 50.0])),
            'both axes extrap': (np.array([-10, 100.0]), np.array([-5, 100.0])),
            'same x, varying y': (np.array([3, 3, 3.0]), np.array([10, 20, 30.0])),
            'varying x, same y': (np.array([1, 3, 5, 7.0]), np.array([20, 20, 20, 20.0])),
            'mixed interior+extrap': (np.array([0.5, 2, 4, 7.5]), np.array([5, 15, 25, 35.0])),
        }
        for desc, (x_arr, y_arr) in cases.items():
            with self.subTest(desc=desc):
                res = self.interp.interpolate(x_arr, y_arr)
                exp = np.array([
                    self.interp.interpolate(float(x), float(y)) for x, y in zip(x_arr, y_arr)
                ])
                np.testing.assert_allclose(res, exp, atol=1e-12)

    # ---- gradient wrt ordinate ----

    def test_gradient_wrt_ordinate_scalar_matches_bump_reval(self):
        cases = [
            ((1,   10),  'grid corner (1,10)'),
            ((1.5, 15),  'interior point'),
            ((3,   20),  'grid point (3,20)'),
            ((7,   30),  'grid corner (7,30)'),
            ((7,   10),  'right x boundary, low y'),
            ((1,   30),  'left x, high y boundary'),
            ((0.5, 15),  'left x extrapolation'),
            ((6.5, 15),  'right x extrapolation'),
            ((3,    5),  'low y extrapolation'),
            ((3,   35),  'high y extrapolation'),
            ((-10, -5),  'far left/low extrapolation'),
            ((100, 100), 'far right/high extrapolation'),
        ]
        for (x, y), desc in cases:
            with self.subTest(desc=desc):
                grad_analytic = self.interp.gradient_wrt_ordinate(
                    x, y, convert_to_numpy=True
                ).flatten()
                grad_br = bump_reval_2d_interpolate(
                    x, y, self.axis1, self.axis2, self.values, self.interp_method, self.extrap_method
                )
                np.testing.assert_allclose(grad_analytic, grad_br, atol=1e-6)

    def test_gradient_wrt_ordinate_array_sums_per_point_grads(self):
        cases = {
            'single pair': (np.array([1.5]), np.array([15.0])),
            'all grid corners': (np.array([1, 1, 7, 7.0]), np.array([10, 30, 10, 30.0])),
            'all left-x extrap': (np.array([-5, -5, -5.0]), np.array([10, 20, 30.0])),
            'all high-y extrap': (np.array([2, 4, 6.0]), np.array([50, 50, 50.0])),
            'both axes extrap': (np.array([-10, 100.0]), np.array([-5, 100.0])),
            'same x, varying y': (np.array([3, 3, 3.0]), np.array([10, 20, 30.0])),
            'varying x, same y': (np.array([1, 3, 5, 7.0]), np.array([20, 20, 20, 20.0])),
            'mixed interior+extrap': (np.array([0.5, 2, 4, 7.5]), np.array([5, 15, 25, 35.0])),
        }
        for desc, (x_arr, y_arr) in cases.items():
            with self.subTest(desc=desc):
                g_vec = self.interp.gradient_wrt_ordinate(x_arr, y_arr, convert_to_numpy=True)
                g_exp = sum(
                    self.interp.gradient_wrt_ordinate(float(x), float(y), convert_to_numpy=True)
                    for x, y in zip(x_arr, y_arr)
                )
                np.testing.assert_allclose(g_vec, g_exp, atol=1e-10)


if __name__ == '__main__':
    unittest.main()

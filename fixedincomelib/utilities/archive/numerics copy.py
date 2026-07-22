import copy
import numpy as np
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional
import torch


class InterpMethod(Enum):

    PIECEWISE_CONSTANT_LEFT_CONTINUOUS = "PIECEWISE_CONSTANT_LEFT_CONTINUOUS"
    LINEAR = "LINEAR"

    @classmethod
    def from_string(cls, value: str) -> "InterpMethod":
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.upper())
        except ValueError:
            raise ValueError(f"Invalid token: {value}")

    def to_string(self) -> str:
        return self.value


class ExtrapMethod(Enum):

    FLAT = "FLAT"
    LINEAR = "LINEAR"

    @classmethod
    def from_string(cls, value: str) -> "ExtrapMethod":
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.upper())
        except ValueError:
            raise ValueError(f"Invalid token: {value}")

    def to_string(self) -> str:
        return self.value


class Interpolator1D(ABC):

    def __init__(
        self,
        axis1: np.ndarray,
        values: np.ndarray,
        interpolation_method: InterpMethod,
        extrpolation_method: ExtrapMethod,
    ) -> None:

        self.axis1_ = axis1
        self.values_ = values
        self.interp_method_ = interpolation_method
        self.extrap_method_ = extrpolation_method
        self.length_ = len(self.axis1)
        self._values_tensor = None

    @abstractmethod
    def interpolate(
        self, x: float, calc_grad: bool = False, convert_to_numpy: bool = False
    ) -> float:
        pass

    @abstractmethod
    def integrate(self, start_x: float, end_x: float, convert_to_numpy: bool = False):
        pass

    # @abstractmethod
    def gradient_wrt_ordinate(self, x: float, convert_to_numpy: bool = False):
        result = self.interpolate(x, calc_grad=True)
        result.backward()
        if convert_to_numpy:
            return self._values_tensor.grad.numpy()
        return self._values_tensor.grad

    # @abstractmethod
    def gradient_of_integrated_value_wrt_ordinate(
        self, start_x: float, end_x: float, convert_to_numpy: bool = False
    ) -> np.ndarray:
        result = self.integrate(start_x, end_x, calc_grad=True)
        result.backward()
        if convert_to_numpy:
            return self._values_tensor.grad.numpy()
        return self._values_tensor.grad

    @property
    def axis1(self) -> np.ndarray:
        return self.axis1_

    @property
    def values(self) -> np.ndarray:
        return self.values_

    @property
    def length(self) -> int:
        return self.length_

    @property
    def interp_method(self) -> str:
        return self.interp_method_.to_string()

    @property
    def extrap_method(self) -> str:
        return self.extrap_method_.to_string()


class Interpolator1DPCP(Interpolator1D):

    def __init__(
        self, axis1: np.ndarray, values: np.ndarray, extrpolation_method: ExtrapMethod
    ) -> None:
        super().__init__(axis1, values, InterpMethod.LINEAR, extrpolation_method)
        assert self.extrap_method_ == ExtrapMethod.FLAT

    def interpolate(
        self, x: float, calc_grad: bool = False, convert_to_numpy: bool = False
    ) -> float:

        if calc_grad:
            self._values_tensor = torch.tensor(
                self.values_, dtype=torch.float64, requires_grad=True
            )
            vals = self._values_tensor
        else:
            vals = self.values_

        if x < self.axis1[0]:
            # flat left extrapolation
            result = vals[0]
        elif x >= self.axis1[-1]:
            # flat right extrpolation
            result = vals[-1]
        else:
            result = None
            for i in range(len(self.axis1) - 1):
                if x >= self.axis1[i] and x < self.axis1[i + 1]:
                    result = vals[i + 1]
                    break

        if convert_to_numpy:
            return result.item() if isinstance(result, torch.Tensor) else float(result)
        return result

    def integrate(
        self, start_x: float, end_x: float, calc_grad: bool = False, convert_to_numpy: bool = False
    ):

        if calc_grad:
            self._values_tensor = torch.tensor(
                self.values_, dtype=torch.float64, requires_grad=True
            )
            vals = self._values_tensor
            acc = torch.tensor(0.0, dtype=torch.float64)
        else:
            vals = self.values_
            acc = 0.0

        if self.length == 1:
            result = (end_x - start_x) * vals[0]

            if convert_to_numpy:
                return result.item() if isinstance(result, torch.Tensor) else float(result)
            return result

        start_fixed = False
        # two pointers
        for i in range(self.length + 1):
            interval_s, interval_e, interval_v = None, None, None
            if i == 0:
                interval_s, interval_e = -np.inf, self.axis1[0]
                interval_v = vals[0]
            elif i == self.length:
                interval_s, interval_e = self.axis1[-1], np.inf
                interval_v = vals[-1]
            else:
                interval_s, interval_e = self.axis1[i - 1], self.axis1[i]
                interval_v = vals[i]

            # if both of them are in the same interval
            if interval_s <= start_x < interval_e and interval_s <= end_x < interval_e:
                acc += (end_x - start_x) * interval_v
                break
            # if start hits this interval
            if not start_fixed and start_x >= interval_s and start_x < interval_e:
                acc += (interval_e - start_x) * interval_v
                start_fixed = True
                continue
            # start already fixed, end hits this interval
            if start_fixed:
                if end_x >= interval_s and end_x < interval_e:
                    # if hit, wrap up
                    acc += (end_x - interval_s) * interval_v
                    break
                else:
                    #  otherwise, count in the whole interval
                    acc += (interval_e - interval_s) * interval_v

        if calc_grad:
            return acc
        if convert_to_numpy:
            return acc.item() if isinstance(acc, torch.Tensor) else float(acc)
        return acc

    # def gradient_wrt_ordinate(self, x: float):

    #     grad = np.zeros(self.length, dtype=float)

    #     if x < self.axis1[0]:
    #         # flat left extrapolation
    #         grad[0] = 1.0
    #         return grad
    #     if x >= self.axis1[-1]:
    #         # flat right extrpolation
    #         grad[-1] = 1.0
    #         return grad

    #     for i in range(len(self.axis1) - 1):
    #         if x >= self.axis1[i] and x < self.axis1[i + 1]:
    #             grad[i + 1] = 1
    #     return grad

    # def gradient_of_integrated_value_wrt_ordinate(self, start_x: float, end_x: float):

    #     grad = np.zeros(self.length, dtype=float)

    #     if self.length == 1:
    #         grad[0] = end_x - start_x
    #         return grad

    #     # acc = 0.
    #     start_fixed = False
    #     # two pointers
    #     for i in range(self.length + 1):
    #         interval_s, interval_e, interval_i = None, None, None
    #         if i == 0:
    #             interval_s, interval_e, interval_i = 0, self.axis1[0], 0
    #         elif i == self.length:
    #             interval_s, interval_e, interval_i = self.axis1[-1], np.inf, self.length - 1
    #         else:
    #             interval_s, interval_e, interval_i = self.axis1[i - 1], self.axis1[i], i
    #         # if both of them are in the same interval
    #         if (
    #             start_x >= interval_s
    #             and start_x < interval_e
    #             and end_x >= interval_s
    #             and end_x < interval_e
    #         ):
    #             grad[interval_i] += end_x - start_x
    #             break
    #         # if start hits this interval
    #         if not start_fixed and start_x >= interval_s and start_x < interval_e:
    #             grad[interval_i] += interval_e - start_x
    #             start_fixed = True
    #             continue
    #         # start already fixed, end hits this interval
    #         if start_fixed:
    #             if end_x >= interval_s and end_x < interval_e:
    #                 # if hit, wrap up
    #                 grad[interval_i] += end_x - interval_s
    #                 break
    #             else:
    #                 #  otherwise, count in the whole interval
    #                 grad[interval_i] += interval_e - interval_s

    #     return grad


class InterpolatorFactory:

    @staticmethod
    def create_1d_interpolator(
        axis1: np.ndarray | List,
        values: np.ndarray | List,
        interpolation_method: InterpMethod,
        extrpolation_method: ExtrapMethod,
    ):

        axis1_ = copy.deepcopy(axis1)
        values_ = copy.deepcopy(values)
        if isinstance(axis1_, list):
            axis1_ = np.array(axis1_)
        if isinstance(values_, list):
            values_ = np.array(values_)
        assert len(axis1_.shape) == 1 and len(values_.shape) == 1
        assert len(axis1_) == len(values_)
        assert np.all(np.diff(axis1_) >= 0)

        if interpolation_method == InterpMethod.PIECEWISE_CONSTANT_LEFT_CONTINUOUS:
            return Interpolator1DPCP(axis1_, values_, extrpolation_method)
        else:
            raise Exception("Currently only support PCP interpolation")

    @staticmethod
    def create_2d_interpolator(
        axis1: np.ndarray | List,
        axis2: np.ndarray | List,
        values: np.ndarray | List,
        interpolation_method: InterpMethod,
        extrpolation_method: ExtrapMethod,
    ):

        axis1_ = copy.deepcopy(axis1)
        axis2_ = copy.deepcopy(axis2)
        values_ = copy.deepcopy(values)
        if isinstance(axis1_, list):
            axis1_ = np.array(axis1_)
        if isinstance(axis2_, list):
            axis2_ = np.array(axis2_)
        if isinstance(values_, list):
            values_ = np.array(values_)
        assert len(axis1_.shape) == 1 and len(axis2_.shape) == 1 and len(values_.shape) == 2
        assert len(axis1_) == values_.shape[0] and len(axis2_) == values_.shape[1]
        assert np.all(np.diff(axis1_) >= 0) and np.all(np.diff(axis2_) >= 0)

        if interpolation_method == InterpMethod.LINEAR and extrpolation_method == ExtrapMethod.FLAT:
            return Interpolator2DLinearFlat(
                axis1_, axis2_, values_, interpolation_method, extrpolation_method
            )
        else:
            raise Exception("Currently only support linear interpolation with flat extrapolation")


class Interpolator2D(ABC):

    def __init__(
        self,
        axis1: np.ndarray,
        axis2: np.ndarray,
        values: np.ndarray,
        interpolation_method: InterpMethod,
        extrpolation_method: ExtrapMethod,
    ) -> None:

        self.axis1_ = axis1
        self.axis2_ = axis2
        self.values_ = values
        self.interp_method_ = interpolation_method
        self.extrap_method_ = extrpolation_method
        self.size1_ = len(self.axis1_)
        self.size2_ = len(self.axis2_)
        self._values_tensor = None

    @abstractmethod
    def interpolate(
        self, x: float, y: float, calc_grad: bool = False, convert_to_numpy: bool = False
    ) -> float:
        pass

    def gradient_wrt_ordinate(
        self, x: float, y: float, convert_to_numpy: bool = False
    ) -> np.ndarray:
        result = self.interpolate(x, y, calc_grad=True)
        result.backward()
        if convert_to_numpy:
            return self._values_tensor.grad.numpy()
        return self._values_tensor.grad

    @property
    def axis1(self) -> np.ndarray:
        return self.axis1_

    @property
    def axis2(self) -> np.ndarray:
        return self.axis2_

    @property
    def values(self) -> np.ndarray:
        return self.values_

    @property
    def size1(self) -> int:
        return self.size1_

    @property
    def size2(self) -> int:
        return self.size2_

    @property
    def interp_method(self) -> str:
        return self.interp_method_.to_string()

    @property
    def extrap_method(self) -> str:
        return self.extrap_method_.to_string()


class Interpolator2DLinearFlat(Interpolator2D):

    def __init__(
        self,
        axis1: np.ndarray,
        axis2: np.ndarray,
        values: np.ndarray,
        interpolation_method: InterpMethod,
        extrpolation_method: ExtrapMethod,
    ) -> None:
        super().__init__(axis1, axis2, values, interpolation_method, extrpolation_method)
        assert self.interp_method_ == InterpMethod.LINEAR
        assert self.extrap_method_ == ExtrapMethod.FLAT

    def interpolate(
        self, x: float, y: float, calc_grad: bool = False, convert_to_numpy: bool = False
    ):
        if calc_grad:
            self._values_tensor = torch.tensor(
                self.values_, dtype=torch.float64, requires_grad=True
            )
            vals = self._values_tensor
        else:
            vals = self.values_

        # clamp to bounds for flat extrapolation
        x = max(x, self.axis1[0])
        x = min(x, self.axis1[-1])
        y = max(y, self.axis2[0])
        y = min(y, self.axis2[-1])

        if x == self.axis1[-1]:
            i = self.size1 - 2
        else:
            for k in range(self.size1 - 1):
                if self.axis1[k] <= x < self.axis1[k + 1]:
                    i = k
                    break

        if y == self.axis2[-1]:
            j = self.size2 - 2
        else:
            for k in range(self.size2 - 1):
                if self.axis2[k] <= y < self.axis2[k + 1]:
                    j = k
                    break

        x1, x2 = self.axis1[i], self.axis1[i + 1]
        y1, y2 = self.axis2[j], self.axis2[j + 1]
        Q11 = vals[i][j]
        Q12 = vals[i][j + 1]
        Q21 = vals[i + 1][j]
        Q22 = vals[i + 1][j + 1]
        f1 = Q11 + (Q21 - Q11) * (x - x1) / (x2 - x1)
        f2 = Q12 + (Q22 - Q12) * (x - x1) / (x2 - x1)
        result = f1 + (f2 - f1) * (y - y1) / (y2 - y1)

        if convert_to_numpy:
            return result.item() if isinstance(result, torch.Tensor) else float(result)
        return result



# Abstract 1-D base


# class Interpolator1D(ABC):

#     def __init__(
#         self,
#         axis1: np.ndarray,
#         values: np.ndarray,
#         interpolation_method: InterpMethod,
#         extrpolation_method: ExtrapMethod,
#     ) -> None:
#         self.axis1_ = axis1
#         self.values_ = values
#         self.interp_method_ = interpolation_method
#         self.extrap_method_ = extrpolation_method
#         self.length_ = len(self.axis1_)
#         self._values_tensor: Optional[torch.Tensor] = None

#     @abstractmethod
#     def interpolate(
#         self, x: Numeric, calc_grad: bool = False, convert_to_numpy: bool = False
#     ) -> Numeric:
#         pass

#     @abstractmethod
#     def integrate(
#         self,
#         start_x: Numeric,
#         end_x: Numeric,
#         calc_grad: bool = False,
#         convert_to_numpy: bool = False,
#     ) -> Numeric:
#         pass

#     def gradient_wrt_ordinate(self, x: Numeric, convert_to_numpy: bool = False):
#         result = self.interpolate(x, calc_grad=True)
#         if isinstance(result, torch.Tensor):
#             result.sum().backward()
#         if convert_to_numpy:
#             return self._values_tensor.grad.numpy()
#         return self._values_tensor.grad

#     def gradient_of_integrated_value_wrt_ordinate(
#         self, start_x: Numeric, end_x: Numeric, convert_to_numpy: bool = False
#     ) -> np.ndarray:
#         result = self.integrate(start_x, end_x, calc_grad=True)
#         if isinstance(result, torch.Tensor):
#             result.sum().backward()
#         if convert_to_numpy:
#             return self._values_tensor.grad.numpy()
#         return self._values_tensor.grad

#     # Properties

#     @property
#     def axis1(self) -> np.ndarray:
#         return self.axis1_

#     @property
#     def values(self) -> np.ndarray:
#         return self.values_

#     @property
#     def length(self) -> int:
#         return self.length_

#     @property
#     def interp_method(self) -> str:
#         return self.interp_method_.to_string()

#     @property
#     def extrap_method(self) -> str:
#         return self.extrap_method_.to_string()


# class Interpolator1DPCP(Interpolator1D):
#     """
#     Piecewise-constant, left-continuous (PCP) interpolator.
#     """

#     def __init__(
#         self,
#         axis1: np.ndarray,
#         values: np.ndarray,
#         extrpolation_method: ExtrapMethod,
#     ) -> None:
#         super().__init__(
#             axis1, values, InterpMethod.PIECEWISE_CONSTANT_LEFT_CONTINUOUS, extrpolation_method
#         )
#         assert self.extrap_method_ == ExtrapMethod.FLAT

#     def interpolate(
#         self, x: Numeric, calc_grad: bool = False, convert_to_numpy: bool = False
#     ) -> Numeric:

#         x_np = _to_numpy_scalar_or_array(x)
#         was_scalar = isinstance(x_np, float)
#         x_arr = np.atleast_1d(np.asarray(x_np, dtype=np.float64))

#         idx_raw = np.searchsorted(self.axis1_, x_arr, side="right")

#         idx = np.clip(idx_raw, 0, self.length_ - 1)

#         if calc_grad:
#             self._values_tensor = torch.tensor(
#                 self.values_, dtype=torch.float64, requires_grad=True
#             )
#             result = self._values_tensor[torch.from_numpy(idx).long()]
#         else:
#             result_np = self.values_[idx]
#             result = _squeeze_scalar(result_np, was_scalar)
#             if convert_to_numpy:
#                 return result
#             return result

#         if convert_to_numpy:
#             r = result.detach().numpy()
#             return _squeeze_scalar(r, was_scalar) if not was_scalar else float(r.item())
#         return result.squeeze() if was_scalar else result

#     def integrate(
#         self,
#         start_x: Numeric,
#         end_x: Numeric,
#         calc_grad: bool = False,
#         convert_to_numpy: bool = False,
#     ) -> Numeric:
#         """
#         Vectorised PCP integration.
#         """
#         s_np = _to_numpy_scalar_or_array(start_x)
#         e_np = _to_numpy_scalar_or_array(end_x)

#         was_scalar = isinstance(s_np, float) and isinstance(e_np, float)

#         s = np.atleast_1d(np.asarray(s_np, dtype=np.float64))
#         e = np.atleast_1d(np.asarray(e_np, dtype=np.float64))
#         s, e = np.broadcast_arrays(s, e)  # shape (Q,)

#         # Extended breakpoints: shape (N+2,)
#         bp = np.concatenate([[-np.inf], self.axis1_, [np.inf]])
#         # Interval left / right endpoints: shapes (N+1,)
#         bp_l = bp[:-1]
#         bp_r = bp[1:]
#         # Interval values: v[0] for (-inf, axis[0]), v[i] for [axis[i-1], axis[i]), …
#         # Extended values shape (N+1,): [v[0], v[1], …, v[-1], v[-1]]
#         ext_vals = np.concatenate([self.values_, [self.values_[-1]]])

#         if calc_grad:
#             self._values_tensor = torch.tensor(
#                 self.values_, dtype=torch.float64, requires_grad=True
#             )
#             ext_vals_t = torch.cat([self._values_tensor, self._values_tensor[-1:]])  # (N+1,)

#             s_t = torch.from_numpy(s).unsqueeze(1)  # (Q, 1)
#             e_t = torch.from_numpy(e).unsqueeze(1)  # (Q, 1)
#             bp_l_t = torch.from_numpy(bp_l).unsqueeze(0)  # (1, N+1)
#             bp_r_t = torch.from_numpy(bp_r).unsqueeze(0)  # (1, N+1)
#             ev_t = ext_vals_t.unsqueeze(0)  # (1, N+1)

#             overlap = torch.clamp(
#                 torch.minimum(e_t, bp_r_t) - torch.maximum(s_t, bp_l_t), min=0.0
#             )  # (Q, N+1)
#             result = (overlap * ev_t).sum(dim=1)  # (Q,)

#             if convert_to_numpy:
#                 r = result.detach().numpy()
#                 return float(r.item()) if was_scalar else r
#             return result.squeeze() if was_scalar else result

#         s2 = s[:, None]  # (Q, 1)
#         e2 = e[:, None]  # (Q, 1)
#         bp_l2 = bp_l[None, :]  # (1, N+1)
#         bp_r2 = bp_r[None, :]  # (1, N+1)
#         ev2 = ext_vals[None, :]  # (1, N+1)

#         overlap = np.maximum(0.0, np.minimum(e2, bp_r2) - np.maximum(s2, bp_l2))  # (Q, N+1)
#         result_arr = (overlap * ev2).sum(axis=1)  # (Q,)

#         result = _squeeze_scalar(result_arr, was_scalar)
#         if convert_to_numpy:
#             return result
#         return result
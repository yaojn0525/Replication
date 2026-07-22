import copy
import numpy as np
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Union
import torch

Numeric = Union[float, np.ndarray, torch.Tensor]

# Enums

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


# Helpers


def _to_numpy_scalar_or_array(x: Numeric) -> Union[float, np.ndarray]:
    """Normalize input to numpy scalar (float) or 1-D ndarray."""
    if isinstance(x, torch.Tensor):
        x = x.detach().numpy()
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 0:
        return float(x)  # scalar path
    if x.ndim == 1:
        return x
    raise ValueError("x must be a scalar or 1-D array")


def _squeeze_scalar(arr: np.ndarray, was_scalar: bool):
    """Return a Python float when the original input was scalar."""
    return float(arr.item()) if was_scalar else arr


class Interpolator1D(ABC):

    def __init__(
        self,
        axis1: np.ndarray,
        values: np.ndarray,
        interpolation_method: InterpMethod,
        extrpolation_method: ExtrapMethod,
    ) -> None:
        self.axis1_ = torch.tensor(axis1)
        self.values_ = torch.tensor(values)
        self.interp_method_ = interpolation_method
        self.extrap_method_ = extrpolation_method
        self.length_ = len(self.axis1)

    @abstractmethod
    def interpolate(
        self, x: Numeric
    ) -> Numeric:
        pass

    @abstractmethod
    def integrate(
        self,
        start_x: Numeric,
        end_x: Numeric
    ) -> Numeric:
        pass

    # Properties

    @property
    def axis1(self) -> torch.Tensor:
        return self.axis1_

    @property
    def values(self) -> torch.Tensor:
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
    """
    Piecewise-constant, left-continuous (PCP) interpolator.
    """

    def __init__(
        self,
        axis1: np.ndarray,
        values: np.ndarray,
        extrpolation_method: ExtrapMethod,
    ) -> None:
        super().__init__(
            axis1, values, InterpMethod.PIECEWISE_CONSTANT_LEFT_CONTINUOUS, extrpolation_method
        )
        assert self.extrap_method_ == ExtrapMethod.FLAT

    def interpolate(
        self, x: Numeric, calc_grad: bool = False
    ) -> Numeric:
        self.values_.requires_grad_(calc_grad)
        x_t = torch.as_tensor(x, dtype=torch.float64)
        idx = torch.searchsorted(self.axis1_, x_t, right=True)
        idx = torch.clamp(idx, 0, self.length_ - 1)
        return self.values_[idx]

    def integrate(
        self,
        start_x: Numeric,
        end_x: Numeric,
        calc_grad: bool = False
    ) -> Numeric:
        """
        Vectorised PCP integration.
        """
        self.values_.requires_grad_(calc_grad)

        s_t = torch.as_tensor(start_x, dtype=torch.float64).unsqueeze(-1)  # (..., 1)
        e_t = torch.as_tensor(end_x, dtype=torch.float64).unsqueeze(-1)  # (..., 1)

        # Extended breakpoints: shape (N+2,)
        inf = torch.tensor([float("inf")], dtype=torch.float64)
        bp = torch.cat([-inf, self.axis1_, inf])
        # Interval left / right endpoints: shapes (N+1,)
        bp_l = bp[:-1]
        bp_r = bp[1:]
        # Interval values: v[0] for (-inf, axis[0]), v[i] for [axis[i-1], axis[i]), …
        # Extended values shape (N+1,): [v[0], v[1], …, v[-1], v[-1]]
        ext_vals = torch.cat([self.values_, self.values_[-1:]])

        overlap = torch.clamp(
            torch.minimum(e_t, bp_r) - torch.maximum(s_t, bp_l), min=0.0
        )  # (..., N+1)
        result = (overlap * ext_vals).sum(dim=-1)  # (...,)
        return result


class Interpolator1DLinearFlat(Interpolator1D):
    """
    Piecewise-linear interpolator with flat (clamped) extrapolation.
    """

    def __init__(
        self,
        axis1: np.ndarray,
        values: np.ndarray,
        extrpolation_method: ExtrapMethod,
    ) -> None:
        super().__init__(axis1, values, InterpMethod.LINEAR, extrpolation_method)
        assert self.extrap_method_ == ExtrapMethod.FLAT

    def interpolate(
        self, x: Numeric, calc_grad: bool = False
    ) -> Numeric:
        self.values_.requires_grad_(calc_grad)
        x_t = torch.as_tensor(x, dtype=torch.float64)

        if self.length_ == 1:
            return self.values_[0].expand_as(x_t) if x_t.dim() > 0 else self.values_[0]

        x_c = torch.clamp(x_t, self.axis1_[0], self.axis1_[-1])
        idx_right = torch.clamp(torch.searchsorted(self.axis1_, x_c, right=True), 1, self.length_ - 1)
        idx_left = idx_right - 1

        x_l, x_r = self.axis1_[idx_left], self.axis1_[idx_right]
        v_l, v_r = self.values_[idx_left], self.values_[idx_right]
        weight_r = (x_c - x_l) / (x_r - x_l)
        return v_l + weight_r * (v_r - v_l)

    def integrate(
        self,
        start_x: Numeric,
        end_x: Numeric,
        calc_grad: bool = False
    ) -> Numeric:
        """
        Definite integral of the flat-extrapolated, piecewise-linear function. Not
        exercised by the rate-interpolation use case this class was added for, but
        implemented to honor the Interpolator1D contract.
        """
        self.values_.requires_grad_(calc_grad)
        s_t = torch.as_tensor(start_x, dtype=torch.float64)
        e_t = torch.as_tensor(end_x, dtype=torch.float64)

        inf = torch.tensor(float("inf"), dtype=torch.float64).unsqueeze(0)
        bp = torch.cat([-inf, self.axis1_, inf])

        total = torch.zeros_like(s_t + e_t)
        for i in range(self.length_ + 1):
            lo = torch.maximum(s_t, bp[i])
            hi = torch.minimum(e_t, bp[i + 1])
            width = torch.clamp(hi - lo, min=0.0)
            if i == 0:
                total = total + width * self.values_[0]
            elif i == self.length_:
                total = total + width * self.values_[-1]
            else:
                x0, x1 = bp[i], bp[i + 1]
                v0, v1 = self.values_[i - 1], self.values_[i]
                slope = (v1 - v0) / (x1 - x0)
                v_lo = v0 + slope * (lo - x0)
                v_hi = v0 + slope * (hi - x0)
                total = total + width * (v_lo + v_hi) / 2.0
        return total

# Factory

class InterpolatorFactory:

    @staticmethod
    def create_1d_interpolator(
        axis1: Union[np.ndarray, List],
        values: Union[np.ndarray, List],
        interpolation_method: InterpMethod,
        extrpolation_method: ExtrapMethod,
    ):
        axis1_ = np.array(copy.deepcopy(axis1), dtype=np.float64)
        values_ = np.array(copy.deepcopy(values), dtype=np.float64)
        assert axis1_.ndim == 1 and values_.ndim == 1
        assert len(axis1_) == len(values_)
        assert np.all(np.diff(axis1_) >= 0)

        if interpolation_method == InterpMethod.PIECEWISE_CONSTANT_LEFT_CONTINUOUS:
            return Interpolator1DPCP(axis1_, values_, extrpolation_method)
        if interpolation_method == InterpMethod.LINEAR and extrpolation_method == ExtrapMethod.FLAT:
            return Interpolator1DLinearFlat(axis1_, values_, extrpolation_method)
        raise NotImplementedError(
            "Currently only PCP interpolation, or LINEAR interpolation with FLAT extrapolation, is supported"
        )

    @staticmethod
    def create_2d_interpolator(
        axis1: Union[np.ndarray, List],
        axis2: Union[np.ndarray, List],
        values: Union[np.ndarray, List],
        interpolation_method: InterpMethod,
        extrpolation_method: ExtrapMethod,
    ):
        axis1_ = np.array(copy.deepcopy(axis1), dtype=np.float64)
        axis2_ = np.array(copy.deepcopy(axis2), dtype=np.float64)
        values_ = np.array(copy.deepcopy(values), dtype=np.float64)
        assert axis1_.ndim == 1 and axis2_.ndim == 1 and values_.ndim == 2
        assert len(axis1_) == values_.shape[0] and len(axis2_) == values_.shape[1]
        assert np.all(np.diff(axis1_) >= 0) and np.all(np.diff(axis2_) >= 0)

        if interpolation_method == InterpMethod.LINEAR and extrpolation_method == ExtrapMethod.FLAT:
            return Interpolator2DLinearFlat(
                axis1_, axis2_, values_, interpolation_method, extrpolation_method
            )
        raise NotImplementedError("Currently only linear interp + flat extrap is supported")


# Abstract 2-D base


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
        self.size1_ = len(axis1)
        self.size2_ = len(axis2)
        self._values_tensor: Optional[torch.Tensor] = None

    @abstractmethod
    def interpolate(
        self, x: Numeric, y: Numeric, calc_grad: bool = False, convert_to_numpy: bool = False
    ) -> Numeric:
        pass

    def gradient_wrt_ordinate(
        self, x: Numeric, y: Numeric, convert_to_numpy: bool = False
    ) -> np.ndarray:
        result = self.interpolate(x, y, calc_grad=True)
        if isinstance(result, torch.Tensor):
            result.sum().backward()
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
    """
    Bilinear interpolator on a 2-D grid with flat (clamped) extrapolation.
    """

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
        self, x: Numeric, y: Numeric, calc_grad: bool = False, convert_to_numpy: bool = False
    ) -> Numeric:

        x_np = _to_numpy_scalar_or_array(x)
        y_np = _to_numpy_scalar_or_array(y)

        was_scalar = isinstance(x_np, float) and isinstance(y_np, float)

        x_arr = np.atleast_1d(np.asarray(x_np, dtype=np.float64))
        y_arr = np.atleast_1d(np.asarray(y_np, dtype=np.float64))
        x_arr, y_arr = np.broadcast_arrays(x_arr, y_arr)  # (Q,)

        # Clamp for flat extrapolation
        x_c = np.clip(x_arr, self.axis1_[0], self.axis1_[-1])
        y_c = np.clip(y_arr, self.axis2_[0], self.axis2_[-1])

        # Lower-left grid cell indices via searchsorted
        # 'right' - 1 gives the left index; clamp to [0, N-2].
        i = np.clip(np.searchsorted(self.axis1_, x_c, side="right") - 1, 0, self.size1_ - 2)
        j = np.clip(np.searchsorted(self.axis2_, y_c, side="right") - 1, 0, self.size2_ - 2)

        x1 = self.axis1_[i]
        x2 = self.axis1_[i + 1]
        y1 = self.axis2_[j]
        y2 = self.axis2_[j + 1]

        # Normalised coordinates in [0, 1]
        tx = np.where(x2 != x1, (x_c - x1) / (x2 - x1), 0.0)
        ty = np.where(y2 != y1, (y_c - y1) / (y2 - y1), 0.0)

        if calc_grad:
            self._values_tensor = torch.tensor(
                self.values_, dtype=torch.float64, requires_grad=True
            )
            i_t = torch.from_numpy(i).long()
            j_t = torch.from_numpy(j).long()
            tx_t = torch.from_numpy(tx)
            ty_t = torch.from_numpy(ty)

            Q11 = self._values_tensor[i_t, j_t]
            Q12 = self._values_tensor[i_t, j_t + 1]
            Q21 = self._values_tensor[i_t + 1, j_t]
            Q22 = self._values_tensor[i_t + 1, j_t + 1]

            f1 = Q11 + (Q21 - Q11) * tx_t
            f2 = Q12 + (Q22 - Q12) * tx_t
            result = f1 + (f2 - f1) * ty_t

            if convert_to_numpy:
                r = result.detach().numpy()
                return float(r.item()) if was_scalar else r
            return result.squeeze() if was_scalar else result

        # Pure numpy path
        Q11 = self.values_[i, j]
        Q12 = self.values_[i, j + 1]
        Q21 = self.values_[i + 1, j]
        Q22 = self.values_[i + 1, j + 1]

        f1 = Q11 + (Q21 - Q11) * tx
        f2 = Q12 + (Q22 - Q12) * tx
        result_arr = f1 + (f2 - f1) * ty

        result = _squeeze_scalar(result_arr, was_scalar)
        if convert_to_numpy:
            return result
        return result

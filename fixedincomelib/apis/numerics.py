import numpy as np
from typing import List
# in-house
from fixedincomelib.utilities import *

def qfCreate1DInterpolator(
    axis1 : np.ndarray | List,
    values : np.ndarray | List,
    interp_method : str,
    extrap_method : str):
    
    interp_method_ = InterpMethod.from_string(interp_method)
    extrap_method_ = ExtrapMethod.from_string(extrap_method)

    return InterpolatorFactory.create_1d_interpolator(axis1, values, interp_method_, extrap_method_)

def qfCreate2DInterpolator(
    axis1 : np.ndarray | List,
    axis2 : np.ndarray | List,
    values : np.ndarray | List,
    interp_method : str,
    extrap_method : str):
    
    interp_method_ = InterpMethod.from_string(interp_method)
    extrap_method_ = ExtrapMethod.from_string(extrap_method)

    return InterpolatorFactory.create_2d_interpolator(axis1, axis2, values, interp_method_, extrap_method_)
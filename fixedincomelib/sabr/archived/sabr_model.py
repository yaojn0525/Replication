import math
from re import sub
from typing import Optional, Any, Dict, List, Tuple
from scipy.linalg import block_diag
from matplotlib.dates import SA
import numpy as np
import pandas as pd
import QuantLib as ql
from zmq import has
from fixedincomelib.date import *
from fixedincomelib.market import *
from fixedincomelib.model.model import Model, ModelComponent, ModelDeserializerRegistry, ModelType, BuildMethodCollection
from fixedincomelib.date import Date
from fixedincomelib.sabr.archived.sabr_parameters import SABRParameters
from fixedincomelib.sabr.archived.build_method import SABRBuildMethod
from fixedincomelib.utilities.numerics import InterpolatorFactory
from fixedincomelib.yield_curve import YieldCurve
from fixedincomelib.data import DataCollection, Data2D, Data1D
from fixedincomelib.yield_curve.archived.model_builder import YieldCurveBuilder

class SABRModel(YieldCurve):

    _version = 1
    _model_type = ModelType.IR_SABR

    def __init__(
        self,
        sub_model : YieldCurve,
        data_collection: DataCollection,
        build_method_collection: BuildMethodCollection,
    ) -> None:
        super().__init__(sub_model.value_date, data_collection, build_method_collection)
        self.sub_model_ = sub_model

    def retrieve_model_component(self, target: ql.Index):
        if isinstance(target, str):
            if target in self.components_:
                return self.components_[target]
            raise Exception(f"This model does not contain {target} component.")

        key = target.name()
        if key in self.components_:
            return self.components_[key]

        raise Exception(f"This model does not contain {key} component.")

    def fx_rate(
        self,
        index: ql.Index,
        expiry_date: Date,
        funding_identifier: Optional[FundingIdentifier] = None,
    ):
        return self.sub_model.fx_rate(index, expiry_date, funding_identifier)

    def fx_rate_gradient_wrt_state(
        self,
        index: ql.Index,
        expiry_date: Date,
        gradient_vector: List[np.ndarray],
        funding_identifier: Optional[FundingIdentifier] = None,
        scaler: Optional[float] = 1.0,
        accumulate: Optional[bool] = False,
    ):
        return self.sub_model.fx_rate_gradient_wrt_state(
            index, expiry_date, gradient_vector, funding_identifier, scaler, accumulate
        )
    
    def discount_factor(
        self, index: ql.Index, expiry_date: Date, underlying_funding: Optional[ql.Index] = None
    ):
        return self.sub_model.discount_factor(index, expiry_date, underlying_funding)
    
    def discount_factor_gradient_wrt_state(
        self,
        index: ql.Index,
        expiry_date: Date,
        gradient_vector: List[np.ndarray],
        scaler: Optional[float] = 1.0,
        accumulate: Optional[bool] = False,
    ):
        return self.sub_model.discount_factor_gradient_wrt_state(
            index, expiry_date, gradient_vector, scaler, accumulate
        )
    
    # check serialization below
    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = SABRModel._version
        content["MODEL_TYPE"] = SABRModel._model_type.to_string()
        content["VALUE_DATE"] = self.value_date.ISO()
        content["BUILD_METHOD_COLLECTION"] = self.build_method_collection.serialize()
        content["DATA_COLLECTION"] = self.data_collection.serialize()
        content["SUB_MODEL"] = self.sub_model_.serialize()
        return content

    @classmethod
    def deserialize(cls, input_dict: dict) -> "SABRModel":
        input_dict_ = input_dict.copy()
        assert "VALUE_DATE" in input_dict_
        assert "BUILD_METHOD_COLLECTION" in input_dict_
        assert "DATA_COLLECTION" in input_dict_
        assert "SUB_MODEL" in input_dict_

        bmc = BuildMethodCollection.deserialize(input_dict_["BUILD_METHOD_COLLECTION"])
        dc = DataCollection.deserialize(input_dict_["DATA_COLLECTION"])
        sub_model = ModelDeserializerRegistry().get(input_dict_["SUB_MODEL"]["MODEL_TYPE"]).deserialize(input_dict_["SUB_MODEL"])
        return cls(sub_model, dc, bmc)
    
    def resize_gradient(self, gradient_vector: List[np.ndarray]):
        gradient_vector.clear()

        # first allocate sub-model gradient slots
        if self.sub_model_ is not None:
            self.sub_model_.resize_gradient(gradient_vector)

        # then allocate SABR component gradient slots
        num_sabr_components = len(self.components_)
        ordered_components = [None] * num_sabr_components
        for target_name, sabr_component in self.components_.items():
            component_index = self.component_indices[target_name]
            ordered_components[component_index] = sabr_component

        for sabr_component in ordered_components:
            gradient_vector.append(np.zeros(sabr_component.num_state_data))

    def calculate_model_jacobian(self):
        if self.is_jacobian_calculated_:
            return
        
        # calculate sub-model jacobian first
        jcb_yc = None
        if hasattr(self.sub_model_, "num_components") and self.sub_model_.num_components > 0:
            self.sub_model_.calculate_model_jacobian()
            jcb_yc = self.sub_model_.model_jacobian

        # calculate SABR jacobian block
        # each SABR component is currently a direct state-data component
        jcb_sabr = None
        num_sabr_components = len(self.components_)
        if num_sabr_components > 0:
            jacobian_pre = [None] * num_sabr_components
            for target_name, sabr_component in self.components_.items():
                index = self.component_indices[target_name]
                this_dim = sabr_component.num_state_data
                jacobian_pre[index] = np.diag(np.ones(this_dim))
            jcb_sabr = block_diag(*jacobian_pre)

        if jcb_yc is None and jcb_sabr is None:
            raise ValueError("No component found in both sub-model and SABR model.")
        elif jcb_yc is None:
            self.model_jacobian_ = jcb_sabr
        elif jcb_sabr is None:
            self.model_jacobian_ = jcb_yc
        else:
            self.model_jacobian_ = block_diag(jcb_yc, jcb_sabr)
        
        self.is_jacobian_calculated_ = True
        
    def risk_postprocess(self, grad: np.ndarray):
        grad = np.asarray(grad, dtype=float).reshape(-1)
        processed_blocks = []

        # process sub-model yc first
        yc_dim = 0
        if self.sub_model_ is not None:
            self.sub_model_.calculate_model_jacobian()
            yc_dim = self.sub_model_.model_jacobian.shape[0]

            if yc_dim > 0:
                yc_grad = grad[:yc_dim]
                processed_blocks.append(self.sub_model_.risk_postprocess(yc_grad))

        # then process SABR part
        sabr_grad = grad[yc_dim:]
        num_sabr_components = len(self.components_)

        if num_sabr_components > 0:
            ordered_components = [None] * num_sabr_components
            for target_name, component_obj in self.components_.items():
                component_index = self.component_indices[target_name]
                ordered_components[component_index] = component_obj

            sabr_blocks = []
            offset = 0

            ordered_params = [
                SABRParameters.NV,
                SABRParameters.BETA,
                SABRParameters.NU,
                SABRParameters.RHO,
            ]

            for component_obj in ordered_components:
                axis1 = component_obj.market_data["AXIS1"]
                axis2 = component_obj.market_data["AXIS2"]
                raw_mkt_data = component_obj.market_data["RAW_MKT_DATA"]

                rows = []
                for param_obj in ordered_params:
                    data_type = param_obj.to_string()
                    raw_data_obj = raw_mkt_data[data_type]

                    market_quotes = np.asarray(raw_data_obj.values, dtype=float)
                    n1, n2 = market_quotes.shape

                    # keep schema aligned with RiskReprt:
                    # [DATA_TYPE, DATA_CONVENTION, AXIS1, AXIS2, MARKET_QUOTE, UNIT]
                    unit = 1.0
                    try:
                        if hasattr(raw_data_obj.data_convention, "data_identifier"):
                            unit = raw_data_obj.data_convention.data_identifier.unit()
                        elif hasattr(raw_data_obj.data_convention, "unit"):
                            unit = raw_data_obj.data_convention.unit()
                    except Exception:
                        unit = 1.0

                    for i in range(n1):
                        for j in range(n2):
                            rows.append([
                                data_type,
                                raw_data_obj.data_convention.name,
                                axis1[i],
                                axis2[j],
                                market_quotes[i, j],
                                unit,
                            ])

                this_frame = np.asarray(rows, dtype=object)
                this_dim = this_frame.shape[0]

                this_grad = sabr_grad[offset: offset + this_dim].reshape(this_dim, 1)
                sabr_blocks.append(np.concatenate([this_frame, this_grad], axis=1))
                offset += this_dim

            if len(sabr_blocks) > 0:
                processed_blocks.append(np.concatenate(sabr_blocks, axis=0))

        if len(processed_blocks) == 0:
            raise ValueError("No risk block can be post-processed.")

        if len(processed_blocks) == 1:
            return processed_blocks[0]

        return np.concatenate(processed_blocks, axis=0)

    def get_sabr_parameters(self, target: ql.Index, expiry: float, tenor: float) -> Dict[SABRParameters, float]:
        comp : SABRModelComponent = self.retrieve_model_component(target)
        return comp.get_sabr_parameters(expiry, tenor)
  
    
    def get_sabr_parameter_gradient_wrt_state(
        self,
        index: ql.Index,
        expiry: float,
        tenor : float,
        gradient_vector: List[np.ndarray],
        scalers: Optional[List] = [1.0, 1.0, 1.0, 1.0],
        accumulate: Optional[bool] = False,
    ):
        
        num_components_of_sub_model = self.sub_model_.num_components # sub model has 10 compoents
        this_component: SABRModelComponent = self.retrieve_model_component(index)
        key = index if isinstance(index, str) else index.name()
        component_index = self.component_indices[key] # <= 2 component, 1 componet => swaption
        this_gradient = gradient_vector[num_components_of_sub_model + component_index]
        this_component.get_sabr_parameter_gradient_wrt_state(
            expiry, tenor, this_gradient, scalers, accumulate
        )


class SABRModelComponent(ModelComponent):

    def __init__(
        self,
        value_date: Date,
        component_identifier: ql.Index,
        state_data: Dict[SABRParameters, np.ndarray],
        build_method: SABRBuildMethod,
        market_data: Dict
    ) -> None:

        super().__init__(
            value_date,
            component_identifier,
            state_data,
            build_method,
            [],
            [],
            market_data
        )

        self.state_data_ = {
            param: np.asarray(surface,dtype=float) for param, surface in state_data.items()
        }

        # in theory, the interpolation method/extrapolatio method
        # should be derived from build_method, here, we know the 
        # only possiblity is linear/flat
        interp_method = self.build_method.interpolation_method
        extrap_method = self.build_method.extrapolation_method
        self.biz_conv_ = self.build_method.business_convention
        self.holiday_conv_ = self.build_method.holiday_convention

        self.axis1_ = [None] * len(self.market_data['AXIS1'])
        self.axis2_ = [None] * len(self.market_data['AXIS2'])
        for i, each in enumerate(self.market_data['AXIS1']):
            this_dt = add_period(
                value_date, 
                Period(each), 
                self.biz_conv_,
                self.holiday_conv_)
            self.axis1_[i] = accrued(value_date, this_dt)
        for i, each in enumerate(self.market_data['AXIS2']):
            this_dt = add_period(
                value_date, 
                Period(each), 
                self.biz_conv_,
                self.holiday_conv_)
            self.axis2_[i] = accrued(value_date, this_dt)

        self.interpolator_ = dict()
        all_parameters = [
            SABRParameters.NV, 
            SABRParameters.BETA, 
            SABRParameters.NU, 
            SABRParameters.RHO]
        for param in all_parameters:
            self.interpolator_[param] = InterpolatorFactory.create_2d_interpolator(
                self.axis1_,
                self.axis2_,
                self.state_data[param],
                interp_method,
                extrap_method
            )
    
    def perturb_model_parameter(
            self, parameter_id: int, perturb_size: float, override_parameter: Optional[bool] = False
            ):
        all_parameters = [
            SABRParameters.NV, 
            SABRParameters.BETA, 
            SABRParameters.NU, 
            SABRParameters.RHO]
        remaining = parameter_id
        for param in all_parameters:
            surface = self.state_data[param]
            this_dim = surface.size
            if remaining < this_dim:
                flat_surface = surface.reshape(-1)
                if override_parameter:
                    flat_surface[remaining] = perturb_size
                else:
                    flat_surface[remaining] += perturb_size
                self.state_data[param] = flat_surface.reshape(surface.shape)
                break
            else:
                remaining -= this_dim
        else:
            raise IndexError(f"parameter_id {parameter_id} is out of range.")
        interp_method = self.build_method.interpolation_method
        extrap_method = self.build_method.extrapolation_method
        self.interpolator_ = {}
        for param in all_parameters:
            self.interpolator_[param] = InterpolatorFactory.create_2d_interpolator(
                self.axis1_,
                self.axis2_,
                self.state_data[param],
                interp_method,
                extrap_method
            )

    @property
    def num_state_data(self) -> int:
        total = 0
        for surface in self.state_data.values():
            total += surface.size
        return total

    def get_sabr_parameters(self, expiry: float, tenor: float) -> Dict[SABRParameters, float]:
        return {
            param: self.interpolator_[param].interpolate(expiry, tenor) for param in self.state_data.keys()
        }
    
    def get_sabr_parameter_gradient_wrt_state(
        self,
        expiry: float,
        tenor : float,
        gradient_vector: np.ndarray,
        scalers: Optional[List] = [1.0, 1.0, 1.0, 1.0],
        accumulate: Optional[bool] = False,
    ):
        # parameters risk w.r.t state variables
        grads = []
        for i, param in enumerate(self.state_data.keys()):
            v : np.ndarray = self.interpolator_[param].gradient_wrt_ordinate(expiry, tenor) # expiry : 5, tenor 6, => 30 dim
            grads.append(v * scalers[i])
        grad = np.concatenate(grads) # 4 * 5 * 6 => 120

        # finalize
        if accumulate:
            assert len(gradient_vector) == len(grad)
            for i in range(len(gradient_vector)):
                gradient_vector[i] += grad[i]
        else:
            gradient_vector[:] = grad
            
            



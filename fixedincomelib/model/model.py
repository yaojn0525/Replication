import numpy as np
import QuantLib as ql
from enum import Enum
from typing import Any, Dict, Optional
from abc import ABCMeta, abstractmethod

# in-house
from fixedincomelib.date import *
from fixedincomelib.data import *
from fixedincomelib.market import *
from fixedincomelib.product import *
from fixedincomelib.model.build_method import *


### registry for deserialization
class ModelDeserializerRegistry(Registry):

    def __new__(cls) -> Self:
        return super().__new__(cls, "", cls.__name__)

    def register(self, key: Any, value: Any) -> None:
        super().register(key, value)
        self._map[key] = value


### registry for model builder
class ModelBuilderRegistry(Registry):

    def __new__(cls) -> Self:
        return super().__new__(cls, "", cls.__name__)

    def register(self, key: Any, value: Any) -> None:
        super().register(key, value)
        self._map[key] = value


### restrict admissible model sets
class ModelType(Enum):

    YIELD_CURVE = "YIELD_CURVE"
    IR_SABR = "IR_SABR"

    @classmethod
    def from_string(cls, value: str) -> "ModelType":
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.upper())
        except ValueError:
            raise ValueError(f"Invalid token: {value}")

    def to_string(self) -> str:
        return self.value


### one model consist of multiple components
class ModelComponent:

    def __init__(
        self,
        value_date: Date,
        component_identifier: ql.Index,  # target for this model component, e.g., SOFR-1B
        state_data: Any,  # model parameters X^{I, k}
        build_method: BuildMethod,  # local recipe
        calibration_products: List[
            Product
        ],  # P is a vector of calibration products, e.g., swap of different tenors
        calibration_funding: List[str],  # Funding info ??? not sure
        market_data: List,
    ) -> None:  # X^{M, k}

        self.value_date_ = value_date
        self.component_identifier_ = component_identifier
        self.calibration_products_ = calibration_products
        self.calibration_funding_ = calibration_funding  # ???
        self.build_method_ = build_method
        self.state_data_ = state_data
        self.market_data_ = market_data
        self.num_state_data_ = -1
        ###
        # Prod :        [P_1,        P_2,        ..., P_m]
        # Market Data : [X^{M, k]_1, X^{M, k}_2, ..., X^{M, k}_m] < market data
        # axis1 :       [tenor 1,    tenor 2.,   ..., tenor_m]
        # values :      [X^{I, k}_1, X^{I, k}_2, ..., X^{I, k}_m] < state
        ###

    @property
    def value_date(self) -> Date:
        return self.value_date_

    @property
    def component_identifier(self) -> Index:
        return self.component_identifier_

    @property
    def calibration_products(self) -> List[Product]:
        return self.calibration_products_

    @property
    def build_method(self) -> BuildMethod:
        return self.build_method_

    @property
    def state_data(self) -> Any:
        return self.state_data_

    @property
    def num_state_data(self) -> int:
        return self.num_state_data_

    @property
    def market_data(self) -> Any:
        return self.market_data_

    @property  # ??? we will come back on this when doing calibration
    def calibration_funding(self) -> List[str]:
        return self.calibration_funding_

    # we will come back to this when doing calibration
    def perturb_model_parameter(
        self, parameter_id: int, perturb_size: float, override_parameter: Optional[bool] = False
    ):
        if override_parameter:
            self.state_data[1][parameter_id] = perturb_size
        else:
            self.state_data[1][parameter_id] += perturb_size


### What is model gradient ?
### Basically, any financial quantities queried from model MUST have a gradient vector w.r.t all model state variables
### Suppose model has N components, we structure the model gradient as a list of N numpy array
###
### | ----------------- |---------------------|------ ... --------|----------------------|--------------------|
###    component 1            component 2             ...               component N-1        component N
### | ----------------- |---------------------|------ ... --------|----------------------|--------------------|
### | \nabla_{X^I_1} Q  |   \nabla_{X^I_2} Q  |       ...         | \nabla_{X^I_{N-1}} Q | \nabla_{X^I_N} Q   |
###
### Suppose we quried a financial quantity Q from component 1, which has a dependency on component 2, then we expect
### only the first two block have non-zero values, and the rest are zero.
###
### NOTICE, the model gradient MUST have the same size as model internal parameters !!!
###
### WE WILL NEED TO SEE WHETHER WE NEED A DEDICATED CLASS FOR GRADIENT VECTOR


### model interface
class Model(metaclass=ABCMeta):

    def __init__(
        self,
        value_date: Date,  # model value date
        model_type: ModelType,  # model type, e.g., YIELD_CURVE, SABR, etc.
        data_collection: DataCollection,  # data collection for this model to retrieve market data
        build_method_collection: BuildMethodCollection,  # model build method collection, which contains the build method for each model component
    ) -> None:

        self.value_date_ = value_date
        self.model_type_ = model_type
        self.data_collection_ = data_collection
        self.build_method_collection_ = build_method_collection
        self.components_: Dict[str, ModelComponent] = {}
        self.component_indices_: Dict[str, int] = {}
        self.sub_model_ = None
        self.n_state_ = -1
        # risk
        self.is_jacobian_calculated_ = False
        self.num_components_ = 0
        self.num_sub_components_ = []  # for each component, how mnay state variables
        self.model_jacobian_: np.ndarray = np.asarray([])

    @property
    def value_date(self) -> Date:
        return self.value_date_

    @property
    def model_type(self) -> str:
        return self.model_type_.to_string()

    @property
    def data_collection(self) -> DataCollection:
        return self.data_collection_

    @property
    def n_state(self) -> int:
        if self.n_state_ < 0:
            self.n_state_ += 1
            for i in range(self.num_components_):
                self.n_state_ += self.num_sub_components_[i]
        return self.n_state_

    @property
    def build_method_collection(self) -> BuildMethodCollection:
        return self.build_method_collection_

    @property
    def num_components(self) -> int:
        return self.num_components_

    @property
    def component_indices(self) -> Dict:
        return self.component_indices_

    @property
    def num_sub_components(self) -> int:
        return self.num_sub_components_

    @property
    def model_jacobian(self) -> np.ndarray:
        return self.model_jacobian_

    @property
    def sub_model(self) -> "Model":
        return self.sub_model_

    @property
    def is_jacobian_calculated(self) -> bool:
        return self.is_jacobian_calculated_

    def resize_gradient(self, gradient: List[np.ndarray]):
        if len(gradient) != self.num_components:
            gradient[:] = [np.array([]) for _ in range(self.num_components)]

        for i in range(self.num_components):
            if len(gradient[i]) != self.num_sub_components[i]:
                gradient[i] = np.zeros(self.num_sub_components[i])

    def set_sub_model(self, model: "Model") -> None:
        self.sub_model_ = model

    def set_model_component(self, target: str, model_component: ModelComponent) -> None:
        self.component_indices_[target] = self.num_components_
        self.components_[target] = model_component
        self.num_sub_components_.append(model_component.num_state_data)
        # increment by 1
        self.num_components_ += 1

    # get key name for model component, which is either a string or a FundingIdentifier or a QuantLib Index
    @staticmethod
    def resolve_component_key(target: Index | str) -> str:
        # Jay: not sure why we need a str ???
        if type(target) is str:
            return target.upper()
        return target.index_name()

    def retrieve_model_component(self, target: Index) -> ModelComponent:
        key = self.resolve_component_key(target)
        if key in self.components_:
            return self.components_[key]
        raise Exception(f"This model does not contain {key} component.")

    ### we will come back to this when doing calibration
    def perturb_model_parameter(
        self,
        target: Index,
        parameter_id: int,
        perturb_size: float,
        override_parameter: Optional[bool] = False,
    ):
        component = self.retrieve_model_component(target)
        component.perturb_model_parameter(parameter_id, perturb_size, override_parameter)

    ### we will come back to this when doing calibration
    @abstractmethod
    def calculate_model_jacobian(self):
        if self.is_jacobian_calculated:
            return

    @abstractmethod
    def get_gradient(self, reset: bool = False):
        pass

    ### we will come back to this when doing calibration
    @abstractmethod
    def risk_postprocess(self, grad: np.ndarray):
        pass

import torch
import numpy as np
from typing import List, Dict
# from scipy.linalg import block_diag
# from scipy.differentiate import jacobian
# in-house
from fixedincomelib.date import *
from fixedincomelib.data import *
from fixedincomelib.market import *
from fixedincomelib.model import *
from fixedincomelib.product import *
from fixedincomelib.utilities import *
from fixedincomelib.valuation import *


class YieldCurve(Model):

    _version = 1
    _model_type = ModelType.YIELD_CURVE

    def __init__(
        self,
        value_date: Date,
        data_collection: DataCollection,
        build_method_collection: BuildMethodCollection,
    ) -> None:
        super().__init__(value_date, self._model_type, data_collection, build_method_collection)
        self.component_dependency_ = {}
        self.component_order_ = []
        self.gradient_lengths_ = []

    def set_component_dependency(self, dependency_map: Dict):
        self.component_dependency_ = dependency_map
        self.component_order_ = self._gradient_component_order()

    ### topological order: a component's reference (if any) always comes before the component itself,
    ### so that gradients can be concatenated in dependency order regardless of build-method insertion order.
    def _gradient_component_order(self) -> List[str]:
        reference_of = {}
        for target_obj, reference_obj in self.component_dependency_.items():
            target_key = self.resolve_component_key(target_obj)
            reference_of[target_key] = (
                self.resolve_component_key(reference_obj) if reference_obj is not None else None
            )

        order = []
        visited = set()

        def visit(key):
            if key in visited or key not in self.components_:
                return
            visited.add(key)
            ref_key = reference_of.get(key)
            if ref_key is not None:
                visit(ref_key)
            order.append(key)

        for key in self.components_:
            visit(key)
        return order

    ### gradients are populated by torch autograd (e.g. via discount_factor(..., calc_grad=True) and a
    ### subsequent .backward() done by the caller / valuation engine). This method only harvests them,
    ### in dependency order (references before their targets), and concatenates them into a single vector.
    ### reset=True clears the harvested .grad on every component so the next valuation starts clean,
    ### i.e. gradients from different products are never silently accumulated by torch.

    def get_gradient(self, reset: bool = False) -> np.ndarray:
        gradient_lengths = []
        gradients = []
        
        for key in self.component_order_:
            component: YieldCurveModelComponent = self.components_[key]
            values_tensor = component.state_data_interpolator.values_
            gradient_lengths.append(component.num_state_data)
            if values_tensor.grad is None:
                gradients.append(np.zeros(component.num_state_data))
            else:
                gradients.append(values_tensor.grad.detach().numpy().copy())
                if reset:
                    values_tensor.grad = None

        self.gradient_lengths_ = gradient_lengths
        return np.concatenate(gradients) if gradients else np.array([])

    ### old world: df : component => exp(-\int_0^t r(s) ds)
    ### new world : df (sofr-1b-flat-over sofr-1b) => exp(-\int_0^t s(u)du) * df(index)

    def discount_factor(
        self,
        target_index: ql.Index,
        expiry_date: Date,
        funding_currency: Optional[FundingIdentifier] = None,
        calc_grad: bool = False,
    ):
        df = 1.0
        
        this_component: YieldCurveModelComponent = self.retrieve_model_component(target_index)
        reference = self.component_dependency_.get(this_component.component_identifier, None) #?
        if reference is not None:
            df = self.discount_factor(
                reference, expiry_date, funding_currency=funding_currency, calc_grad=calc_grad
            )  # recursive
        df = df * this_component.discount_factor(expiry_date, calc_grad=calc_grad)

        ### different currency
        # df(index, collateral=c) = df(index) * df(c's own funding curve) / df(index currency's own funding curve)

        # only happens between funding idntifiers
        if (
            funding_currency is not None
            and type(target_index) == FundingIdentifier
            and funding_currency.currency() != target_index.currency()
        ):
            native_currency_identifier = FundingIdentifierRegistry().get(
                target_index.currency().code()
            )
            df = (
                df
                * self.discount_factor(funding_currency, expiry_date, calc_grad=calc_grad)
                / self.discount_factor(native_currency_identifier, expiry_date, calc_grad=calc_grad)
            )

        return df

    def fx_rate(self, index: ql.Index):
        this_component: YCFXComponent = self.retrieve_model_component(index)
        return this_component.fx_spot()

    def serialize(self) -> dict:
        content = {}
        content["VERSION"] = YieldCurve._version
        content["MODEL_TYPE"] = YieldCurve._model_type.to_string()
        content["VALUE_DATE"] = self.value_date.ISO()
        content["BUILD_METHOD_COLLECTION"] = self.build_method_collection.serialize()
        content["DATA_COLLECTION"] = self.data_collection.serialize()
        return content

    @classmethod
    def deserialize(cls, input_dict: dict) -> "YieldCurve":
        input_dict_ = input_dict.copy()
        assert "VERSION" in input_dict_
        version = input_dict_["VERSION"]
        assert "MODEL_TYPE" in input_dict_
        model_type = input_dict_["MODEL_TYPE"]
        assert "VALUE_DATE" in input_dict_
        value_date = Date(input_dict_["VALUE_DATE"])
        bmc = BuildMethodCollection.deserialize(input_dict_["BUILD_METHOD_COLLECTION"])
        dc = DataCollection.deserialize(input_dict_["DATA_COLLECTION"])
        # find modelbuilder
        func = ModelBuilderRegistry().get(model_type)
        return func(value_date, dc, bmc)

    def calculate_model_jacobian(self):
        pass
        # if self.is_jacobian_calculated_:
        #     return
        # # WARNING: WE DO NOT ALLOW A MIXTURE OF CALIBRATION INSTRUMENTS AND STATE DATA FOR NOW
        # only_state_data = False
        # jacobian_pre = [None] * self.num_components
        # for target_name, yc_component in self.components_.items():
        #     index = self.component_indices[target_name]
        #     calib_prod = yc_component.calibration_product
        #     calib_funding = yc_component.calibration_funding
        #     if len(calib_prod) == 0:
        #         # no calibration, just using state data
        #         # jacobian is identity
        #         jacobian_pre[index] = np.diag(np.ones(yc_component.num_state_data))
        #         only_state_data = True
        #         continue
        #     # calculate calibration instrument gradient
        #     grads = []
        #     for _, (prod, funding) in enumerate(zip(calib_prod, calib_funding)):
        #         if isinstance(funding, dict):
        #             fi_vp = FundingIndexParameter(funding)
        #         else:
        #             fi_vp = FundingIndexParameter({"Funding Index": funding})
        #         vpc = ValuationParametersCollection([fi_vp])
        #         engine = ValuationEngineProductRegistry.new_valuation_engine(
        #             self, prod, vpc, ValuationRequest.PV_DETAILED
        #         )
        #         engine.calculate_value()
        #         grads.append(np.concatenate(engine.grad_at_par()))
        #     jacobian_pre[index] = grads  # np.concatenate(grads, axis=0)

        # self.model_jacobian_ = (
        #     block_diag(*jacobian_pre) if only_state_data else np.concatenate(jacobian_pre, axis=0)
        # )
        # self.is_jacobian_calculated_ = True

    def risk_postprocess(self, grad: np.ndarray):
        # frame = [None] * self.num_components
        # for target_name, yc_component in self.components_.items():
        #     index = self.component_indices[target_name]
        #     frame[index] = yc_component.market_data
        # frame = np.concatenate(frame, axis=0)
        # return np.concatenate([frame, grad.reshape(len(frame), 1)], axis=1)
        pass


### YieldCurveModelComponent is a common interface for all yield curve components, including funding, ibor, on, and fx rate.
### It provides common methods such as those inquirying financial quantities, e.g., discount factor.
### Each specific component can then extend this class and implement its own logic if needed.
### For example, fx component will implement fx_rate method.


class YieldCurveModelComponent(ModelComponent):

    def __init__(
        self,
        value_date: Date,
        component_identifier: ql.Index,  # ibor / on / funding
        state_data: np.ndarray,  # for yield curve, it is always (abscissas x, ordinates y)
        build_method: BuildMethod,  # the local recipe to build this very component
        calibration_product: Optional[
            List[Product]
        ] = [],  # the calibration product for this component, e.g., 1m swap, 3m swap, etc. for libor component
        calibration_funding: Optional[
            List[str]
        ] = [],  # the funding for each calibration product, e.g., sofr disc for sofr swap
        market_data: Optional[
            List
        ] = [],  # the market quotes for each calibration product, e.g., swap rate for each swap
    ) -> None:

        super().__init__(
            value_date,
            component_identifier,
            state_data,
            build_method,
            calibration_product,
            calibration_funding,
            market_data,
        )
        self.intialise()

    def intialise(self):
        assert len(self.state_data) == 2
        self.num_state_data_ = len(self.state_data[0])
        self.interpolator_ = InterpolatorFactory.create_1d_interpolator(
            self.state_data[0],
            self.state_data[1],
            self.build_method.interpolation_method,
            self.build_method.extrapolation_method,
        )

    ### getters
    @property
    def state_data_interpolator(self) -> Interpolator1D:
        return self.interpolator_

    @property
    def num_state_data(self) -> int:
        return self.num_state_data_

    ### all components except FX RATE needs to provide discount factor
    def discount_factor(self, expiry_date: Date, calc_grad: bool = False):
        tte = accrued(self.value_date, expiry_date)
        exponent = self.state_data_interpolator.integrate(0.0, tte, calc_grad=calc_grad)
        dfs = torch.exp(-exponent)
        return dfs

    ### JAY: let's leave it for now
    def perturb_model_parameter(
        self, parameter_id: int, perturb_size: float, override_parameter: Optional[bool] = False
    ):
        super().perturb_model_parameter(parameter_id, perturb_size, override_parameter)
        self.interpolator_ = InterpolatorFactory.create_1d_interpolator(
            self.state_data[0],
            self.state_data[1],
            self.build_method.interpolation_method,
            self.build_method.extrapolation_method,
        )


class YCFundingComponent(YieldCurveModelComponent):
    pass


class YCIBORComponent(YieldCurveModelComponent):
    pass


class YCONIndexComponent(YieldCurveModelComponent):
    pass


class YCFXComponent(YieldCurveModelComponent):

    def intialise(self):
        pass

    def fx_spot(self):
        return torch.tensor(self.state_data_[0][0], requires_grad=True)


### registry
ModelDeserializerRegistry().register(YieldCurve._model_type.to_string(), YieldCurve.deserialize)

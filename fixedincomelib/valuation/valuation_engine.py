from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np
import torch

# in-house
from fixedincomelib.model import Model
from fixedincomelib.product import Product
from fixedincomelib.valuation.report import *
from fixedincomelib.valuation.utilities import *
from fixedincomelib.valuation.valuation_parameters import ValuationParametersCollection
from fixedincomelib.market.anchored_index import *


### requests (probably will move to somewhere else)
class ValuationRequest(Enum):

    PV = "pv"
    CASH = "cash"
    PV_DETAILED = "pvdetailed"
    FIRST_ORDER_RISK = "firstorderrisk"
    CASHFLOWS_REPORT = "cashflowsreport"
    PAR_RATE_OR_SPREAD = "parrateorspread"
    PV01 = "pv01"

    @classmethod
    def from_string(cls, value: str) -> "ValuationRequest":
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid token: {value}")

    def to_string(self) -> str:
        return self.value


### Analyitc Val Engine
class ValuationEngineAnalytics(ABC):

    def __init__(
        self, model: Model, valuation_parameters_collection: ValuationParametersCollection
    ) -> None:
        self.model_ = model
        self.valuation_parameters_collection_ = valuation_parameters_collection
        self.value_date_ = model.value_date

    @abstractmethod
    def calculate_value(self) -> None:
        pass

    @abstractmethod
    def calculate_risk(
        self,
        gradient: List[np.ndarray],
        scaler: Optional[float] = 1.0,
        accumulate: Optional[bool] = False,
    ) -> None:
        pass

    def value(self) -> float:
        pass


class ValuationEngineAnalyticsAnchoredIndex(ValuationEngineAnalytics):

    def __init__(
        self,
        model: Model,
        anchored_index: AnchoredIndex,
        valuation_parameters_collection: ValuationParametersCollection,
    ) -> None:

        super().__init__(model, valuation_parameters_collection)
        self.anchored_index_ = anchored_index

    @abstractmethod
    def calculate_value(self) -> None:
        pass

    @abstractmethod
    def calculate_risk(
        self,
        gradient: List[np.ndarray],
        scaler: Optional[float] = 1.0,
        accumulate: Optional[bool] = False,
    ) -> None:
        pass

    def value(self) -> float:
        pass


### Proper Product
class ValuationEngineProduct(ABC):

    def __init__(
        self,
        model: Model,
        valuation_parameters_collection: ValuationParametersCollection,
        product: Product,
        request: ValuationRequest,
    ) -> None:

        self.model_ = model
        self.product_ = product
        self.valuation_parameters_collection_ = valuation_parameters_collection
        self.request_ = request
        self.value_date_ = self.model_.value_date
        self.value_ = 0.0
        self.cash_ = 0.0

    @property
    def model(self) -> Model:
        return self.model_

    @property
    def value_date(self):
        return self.value_date_

    @property
    def value(self) -> float:
        return self.value_

    @property
    def cash(self) -> float:
        return self.cash_

    @abstractmethod
    def calculate_value(self):
        return

    def get_risk(self, gradient, scaler=None) -> None:

        if isinstance(self.value_, torch.Tensor) and self.value_.requires_grad:
            self.value_.backward(retain_graph=True)

        gradient[:] = self.model_.get_gradient(reset=True)
        gradient *= scaler if scaler is not None else 1.0

    @abstractmethod
    def create_cash_flows_report(self) -> CashflowsReport:
        pass

    @abstractmethod
    def get_value_and_cash(self) -> PVCashReport:
        pass

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    # optional
    def par_rate_or_spread(self) -> float:
        raise Exception("This product does not support par rate or spread calculation.")

    # optional
    def pv01(self) -> float:
        raise Exception("This product does not support pv01 calculation.")

    # optional
    def grad_at_par(self) -> np.ndarray:

        ### V(X^I, s) = 0, we have solved s already, by implicit function theorem,
        ### dV/dX^I + dV/ds * ds/dX^I = 0, ds/dX^I = - (dV/ds)^-1 * dV/dX^I = - dV/dX^I / PV01

        grad = np.zeros(self.model_.n_state)
        self.get_risk(gradient=grad, scaler=-1 / self.pv01())
        return grad

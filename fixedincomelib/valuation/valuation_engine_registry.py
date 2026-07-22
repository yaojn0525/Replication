from typing import Self, Any
# in-house
from fixedincomelib.utilities import *
from fixedincomelib.date import *
from fixedincomelib.product import *
from fixedincomelib.market import *
from fixedincomelib.model import *
from fixedincomelib.valuation.report import *
from fixedincomelib.valuation.utilities import *
from fixedincomelib.valuation.valuation_engine import *
from fixedincomelib.valuation.valuation_parameters import *


class ValuationEngineProductRegistry(Registry):

    def __new__(cls) -> Self:
        return super().__new__(cls, '', cls.__name__)

    def get(self, key: Any, **args) -> Any:
        try:
            return self._map[key]
        except:
            raise KeyError(f'no entry for key : {key}.')

    def exists(self, key: Any) -> bool:
        return key in self._map

    def register(self, key : Any, value : Any) -> None:
        super().register(key, value)
        self._map[key] = value

    @classmethod
    def new_valuation_engine(cls,
                             model : Model,
                             product : Product,
                             valuation_parameters_collection : ValuationParametersCollection,
                             valuation_request: ValuationRequest) -> ValuationEngineProduct:
        
        vp = AnalyticValParam._vp_type
        if not valuation_parameters_collection.has_vp_type(AnalyticValParam._vp_type):
            # TODO: if it is MC, then vp = MCParameter ...
            vp = ''

        key = (model.model_type, product.product_type, vp)
        engine_cls = ValuationEngineProductRegistry().get(key)
        if engine_cls is None:
            raise KeyError(f'No engine registered for key {key}')
        
        return engine_cls(model, valuation_parameters_collection, product, valuation_request)


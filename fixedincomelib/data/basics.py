import pandas as pd
from typing import Any, Self
from abc import ABC, abstractmethod 
# in-house
from fixedincomelib.utilities import Registry
from fixedincomelib.market import *


class DataObjectDeserializerRegistry(Registry):
    
    def __new__(cls) -> Self:
        return super().__new__(cls, '', cls.__name__)

    def register(self, key : Any, value : Any) -> None:
        super().register(key, value)
        self._map[key] = value

class DataObject(ABC):

    _version = -1
    _data_shape = ''

    def __init__(
            self, 
            data_type: str, 
            data_convention: DataConvention):

        self.data_type_ = data_type
        self.data_convention_ = data_convention
        self.data_identifier_ = None
        if data_convention:
            func = DataIdentifierRegistry().get(self.data_type_)
            self.data_identifier_ = func(self.data_convention_)

    @property
    def unique_identifier(self) -> str:
        if self.data_identifier:
            return self.data_identifier.to_string()

    @property
    def data_shape(self) -> str:
        return self._data_shape
         
    @property
    def data_identifier(self) -> DataIdentifier|None:
        return self.data_identifier_
    
    @property
    def data_type(self) -> str:
        return self.data_type_

    @property
    def data_convention(self) -> DataConvention|None:
        return self.data_convention_

    @abstractmethod
    def display(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def serialize(self) -> dict:
        pass

    @abstractmethod
    def deserialize(cls, input_dict : Dict) -> "DataObject":
        pass




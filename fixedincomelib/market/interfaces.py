from abc import ABC, abstractmethod
import pandas as pd
from typing import Self, Dict, Any, Tuple
# in-house
from fixedincomelib.date import *
from fixedincomelib.utilities import *
from fixedincomelib.market.basics import *


### Index
class Index(ABC):

    _type = ''

    def __init__(self, unique_name : str, content : Dict[str, str]):
        self.index_name_ = unique_name.upper()
        self.content_ = content
        assert len(self.content_) != 0
    
    def index_name(self):
        return self.index_name_
    
    def type(self):
        return self._type
    
    def display(self):
        to_print = [["Index Name", self.index_name_], ["Type", self.type()]]
        to_print += [[k.upper().strip("_"), v] for k, v in self.content_.items()]
        return pd.DataFrame(to_print, columns=['Name', 'Value'])

class IndexRegFunction(Registry):

    def __new__(cls) -> Self:
        return super().__new__(cls, "", cls.__name__)

    def register(self, key: str, value: Any) -> None:
        super().register(key, value)
        self._map[key] = value

### interface
class AnchoredIndex(ABC):

    def __init__(
            self,
            start_date : Date,
            term_or_termination_date : Date | Period,
            index : Index,
            accrual_basis : Optional[ql.DayCounter]=ql.SimpleDayCounter()):

        super().__init__()
        self.start_date_ = start_date
        self.term_or_termination_date_ = term_or_termination_date
        self.index_ = index
        self.accrual_basis_ = accrual_basis

    @property
    def start_date(self) -> Date:
        return self.start_date_

    @property
    def term_or_termination_date(self) -> Date | Period:
        return self.term_or_termination_date_

    @property
    def index(self) -> Index:
        return self.index_

    @property
    def accrual_basis(self) -> ql.DayCounter:
        return self.accrual_basis_

### Data Convention
class DataConvention(ABC):

    _type = ""

    def __init__(self, unique_name: str, content: dict):
        super().__init__()
        self.conv_name_ = unique_name.upper()
        self.content_ = content
        assert len(self.content_) != 0

    @property
    def name(self):
        return self.conv_name_

    @classmethod
    def type(cls):
        return cls._type

    def display(self):
        to_print = [[k, v] for k, v in self.content_.items()]
        return pd.DataFrame(to_print, columns=["Name", "Value"])

class DataConventionRegFunction(Registry):

    def __new__(cls) -> Self:
        return super().__new__(cls, "", cls.__name__)

    def register(self, key: str, value: Any) -> None:
        super().register(key, value)
        self._map[key] = value

### Data Identifier
class DataIdentifier(ABC):

    _data_type = ""

    def __init__(self, data_convention : DataConvention) -> None:
        self.data_convention_ = data_convention
        self.data_identifier_ = (self._data_type, data_convention.name)
    
    @property
    def data_type(self) -> str:
        return self._data_type
    
    @property
    def data_convention(self) -> DataConvention:
        return self.data_convention_
    
    @property
    def data_identifier(self) -> Tuple[str, str]:
        return self.data_identifier_

    def to_string(self):
        return f"{self.data_type}:{self.data_convention.name}"
    
    @abstractmethod
    def unit(self):
        pass

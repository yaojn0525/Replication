from typing import List, Self, Any
from abc import ABC, abstractmethod
import pandas as pd
# in-house
from fixedincomelib.utilities import *
from fixedincomelib.market import *


class BuildMethodBuilderRegistry(Registry):
    
    def __new__(cls) -> Self:
        return super().__new__(cls, '', cls.__name__)

    def register(self, key : Any, value : Any) -> None:
        super().register(key, value)
        self._map[key] = value

class BuildMethod(ABC):

    _version = 1
    _build_method_type = ""

    def __init__(self, target : str, content : Dict[str, Any]) -> None:

        self.target_ = target
        # make everything upper case
        self.content_ : Dict[str, Any] = dict()
        for key in content.keys():
            v = content[key]
            self.content_[key.upper()] = v.upper() if isinstance(v, str) else v
        ##  build method in the making
        # target and reference (optional)
        self.build_method_ : Dict[str, Any] = dict()
        self.build_method_["TARGET"] = content["TARGET"]
        if self.has_reference():
            self.build_method_["REFERENCE"] = ""
            if self.content_.get("REFERENCE"):
                self.build_method_["REFERENCE"] = self.content_["REFERENCE"]
        # process calibration instruments
        for each in self.calibration_instruments():
            self.build_method_[each.upper()] = ""
            if each.upper() in self.content_:
                self.build_method_[each.upper()] = self.content_[each.upper()]
        # process other defaultable entries
        for each in self.defaultable_entries:
            k = each[0].upper()
            default_v = each[1].upper() if isinstance(each[1], str) else each[1]
            self.build_method_[k] = default_v
            if k in self.content_:
                self.build_method_[k] = self.content_[k]

    def has_reference(self) -> bool:
        return True

    @abstractmethod
    def calibration_instruments(self) -> List[str]:
        pass

    @property
    def defaultable_entries(self) -> List:
        return []
    
    def __getitem__(self, key : str):
        return self.build_method_[key.upper()]
    
    @property
    def target(self):
        return self.target_
        
    @property
    def type(self):
        return self._build_method_type

    @property
    def build_mehtod(self):
        return self.build_method_

    def display(self) -> pd.DataFrame:
        return pd.DataFrame(self.build_method_.items(), columns=['Name', 'Value'])

    def serialize(self) -> dict:
        content : Dict[str, Any] = {}
        content['VERSION'] = self._version
        content['TYPE'] = self._build_method_type
        content.update(self.build_mehtod)
        return content

    @classmethod
    def deserialize(cls, input_dict : Dict[str, Any]) -> 'BuildMethod':
        assert "TYPE" in input_dict
        assert "VERSION" in input_dict
        assert "TARGET" in input_dict
        version = input_dict["VERSION"]
        target = input_dict["TARGET"]

        input_dict_ = dict()
        for key in input_dict.keys():
            if key.upper() in ["VERSION", "TYPE"]:
                continue
            input_dict_[key.upper()] = input_dict[key]
        return cls(target, input_dict_)

class BuildMethodCollection:

    _version = 1

    def __init__(self, bm_list : List[BuildMethod]) -> None:
        self.bm_col = {}
        for each in bm_list:
            key = f'{each.type.upper()}:{each.target.upper()}'
            self.bm_col[key] = each
        self.num_bms = len(self.bm_col)

    @property
    def num_build_methods(self):
        return self.num_bms
    
    @property
    def items(self):
        return self.bm_col.items()

    def get_build_method_from_build_method_collection(
            self, 
            target : str, 
            type : str) -> BuildMethod:

        key = f'{type.upper()}:{target.upper()}'
        if key not in self.bm_col:
            raise Exception(f'Cannot find {key}.')
        return self.bm_col[key]
    
    def display(self):
        content = []
        for k, _ in self.bm_col.items():
            tokenized = k.split(':')
            content.append(tokenized)
        return pd.DataFrame(content, columns=['Name', 'Value'])
    
    def serialize(self):
        content = {}
        content['VERSION'] = self._version
        content['TYPE'] = 'BUILDMETHODCOLLECTION'
        count = 0
        for _, v in self.bm_col.items():
            content[f'BUILD_MEHTOD_{count}'] = v.serialize()
            count += 1
        return content
    
    @classmethod
    def deserialize(cls, input_dict : dict):
        input_dict_ = input_dict.copy()
        assert 'VERSION' in input_dict_
        version = input_dict_['VERSION']
        input_dict_.pop('VERSION')
        assert 'TYPE' in input_dict_
        type = input_dict_['TYPE']
        input_dict_.pop('TYPE')
        bm_list = []
        for _, v in input_dict_.items():
            func : BuildMethod = BuildMethodBuilderRegistry().get(v['TYPE'])
            bm = func.deserialize(v)
            bm_list.append(bm)
        return cls(bm_list)
 
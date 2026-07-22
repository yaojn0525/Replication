import os, json, yaml
from typing import Optional, Self, Dict, Any
from abc import ABC, abstractmethod

### miscs
def noramlize_surrogated_str(input_str : str):
    return input_str.encode('utf-8', 'surrogateescape').decode('latin-1')

### default config path
def get_config():
    path = os.path.join(os.path.pardir, 'static_files')
    file = os.path.join(path, f'config.yaml')
    if not os.path.exists(file):
        raise Exception('Cannot find config to initialize the library.')
    with open(file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

### template for registry
class Registry(ABC):

    _instance = None
    _registry_type = None

    def __new__(cls, file_name : str, registry_type : str, file_type : Optional[str]='json', **kwargs) -> Self:
        
        if cls._instance is None:
            # init
            obj = super().__new__(cls)
            obj._map = dict()
            # read files
            path = os.path.join(os.path.pardir, 'static_files')
            file = os.path.join(path, f'{file_name}.{file_type}')
            if file_name != '' and os.path.exists(file):
                # resolve content
                if file_type == 'json':
                    with open(file, 'r', encoding='utf-8') as f:
                        for k, v in json.load(f).items():
                            obj.register(k, v)
                elif file_type == 'yaml':
                    with open(file, 'r') as file:
                        data : Dict = yaml.safe_load(file)
                        for k, v in data.items():
                            try:
                                obj.register(k, v)
                            except:
                                raise Exception(f"Cannot register {k}.")
                else:
                    raise Exception('Currently only supports json raw file.')
            # finalize
            cls._instance = obj
            cls._registry_type = registry_type
        return cls._instance
    
    @abstractmethod
    def register(self, key : str, value : Any) -> None:
        if self.exists(key):
            pass 
            # raise ValueError(f'duplicate key : {key}')
            
    def get(self, key: str, **args) -> Any:
        try: 
            return self._map[key.upper()]
        except:
            raise KeyError(f'no entry for key : {key}.')

    def clear(self) -> None:
        self._map.clear()

    def erase(self, key : str) -> None:
        if not self.exists(key.upper()):
            raise KeyError(f'Cannot find this key {key}.')
        self._map.pop(key.upper())
    
    def exists(self, key : str) -> None:
        return key.upper() in self._map

    def display_registry(self) -> None:
        for k, v in self._map.items():
            print(f'Key : {k}, Value : {v}.')

    @classmethod
    def reset_registry(cls) -> None:
        cls._instance = None

    @property
    def registry_name(self):
        return self._registry_type
    
    @property
    def get_keys(self):
        return list(self._map.keys())
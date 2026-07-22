# in-house
from fixedincomelib.market.indices import *


### Funding Identifier
class FundingIdentifier(Index):

    _type = 'FUNDING IDENTIFIER'

    def __init__(self, unique_name: str, currency: str, base_index: Optional[str] = ""):
        super().__init__(unique_name, {"currency" : currency, "base index" : base_index}) 
        self.currency_ = Currency(currency)
        self.base_index_ = None
        if base_index:
            if IndexRegistry().exists(base_index):
                self.base_index_ = IndexRegistry().get(base_index)
            else:
                raise Exception(f"Cannot find reference index {base_index}.")

    def currency(self) -> Currency:
        return self.currency_
    
    @property
    def base_index(self) -> IBORIndex|OvernightIndex:
        return self.base_index_

class FundingIdentifierRegistry(Registry):

    def __new__(cls) -> Self:
        return super().__new__(cls, "fundingidentifiers", "FundingIdentifier", "yaml")

    def register(self, key: str, value: Any) -> None:
        super().register(key, value)
        assert "currency" in value
        base_index = value.get("base index", "")
        self._map[key.upper()] = FundingIdentifier(
            key.upper(), 
            value["currency"], 
            base_index)

    def get(self, key: str, **args) -> FundingIdentifier:
        if key.upper() not in self._map:
            raise Exception(f"Cannot find {key} in funding identifier registry.")
        return self._map[key.upper()]

    def display_all_indices(self) -> pd.DataFrame:
        to_print = []
        for k, _ in self._map.items():
            fi: FundingIdentifier = self.get(k)
            to_print.append([fi.index_name()])
        return pd.DataFrame(to_print, columns=["FundingIdentifier"])

def cast_to_index(input_str: str):
    if IndexRegistry().exists(input_str):
        return IndexRegistry().get(input_str)
    elif FundingIdentifierRegistry().exists(input_str):
        return FundingIdentifierRegistry().get(input_str)
    else:
        return None

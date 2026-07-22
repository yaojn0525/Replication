# in-house
from fixedincomelib.market.interfaces import *
from fixedincomelib.market.data_conventions import *


class DataIdentifierCashDeposite(DataIdentifier):
    
    _data_type = "Cash Deposit"

    def __init__(self, data_convention: DataConventionCashDeposit) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierFRAOrFixing(DataIdentifier):
    
    _data_type = "FRA Or Fixing"

    def __init__(self, data_convention: DataConventionFRAOrFixing) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierOvernightIndexFuture(DataIdentifier):

    _data_type = "Overnight Index Future"

    def __init__(self, data_convention: DataConventionOvernightIndexFuture) -> None:
        super().__init__(data_convention)

    def unit(self):
        return -0.01

class DataIdentifierOvernightIndexSwap(DataIdentifier):

    _data_type = "Overnight Index Swap"

    def __init__(self, data_convention: DataConventionOvernightIndexSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierOvernightIndexBasisSwap(DataIdentifier):

    _data_type = "Overnight Index Basis Swap"

    def __init__(self, data_convention: DataConventionOvernightIndexBasisSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierOISBasisSwap(DataIdentifier):

    _data_type = "OIS BASIS SWAP"

    def __init__(self, data_convention: DataConventionOISBasisSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierOvernightIndexCurrencyBasisSwap(DataIdentifier):

    _data_type = "Overnight Index Currency Basis Swap"

    def __init__(self, data_convention: DataConventionOvernightIndexCurrencyBasisSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierOISIBORCurrencyBasisSwap(DataIdentifier):

    _data_type = "Overnight IBOR Currency Basis Swap"

    def __init__(self, data_convention: DataConventionOISIBORCurrencyBasisSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierGenericForward(DataIdentifier):

    _data_type = "Generic Forward"

    def __init__(self, data_convention: DataConventionGenericForward) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierGenericForwardSpread(DataIdentifier):

    _data_type = "Generic Forward Spread"

    def __init__(self, data_convention: DataConventionGenericForwardSpread) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierZeroSpread(DataIdentifier):

    _data_type = "IBOR Spread Zero Rate"

    def __init__(self, data_convention: DataConventionIborSpreadZeroRate) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierGenericSpread(DataIdentifier):

    _data_type = "Generic Spread"

    def __init__(self, data_convention: DataConventionGenericSpread) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierFRN(DataIdentifier):

    _data_type = "Floating Rate Note"

    def __init__(self, data_convention: DataConventionFRN) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierSwapSpreadBasisSwap(DataIdentifier):

    _data_type = "Swap Spread Basis Swap"

    def __init__(self, data_convention: DataConventionSwapSpreadBasisSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierIBORFuture(DataIdentifier):

    _data_type = "IBOR Future"

    def __init__(self, data_convention: DataConventionIBORFuture) -> None:
        super().__init__(data_convention)

    def unit(self):
        return -0.01

class DataIdentifierSwap(DataIdentifier):

    _data_type = "Swap"

    def __init__(self, data_convention: DataConventionSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierBasisSwap(DataIdentifier):

    _data_type = "Basis Swap"

    def __init__(self, data_convention: DataConventionBasisSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierCurrencyBasisSwap(DataIdentifier):

    _data_type = "Currency Basis Swap"

    def __init__(self, data_convention: DataConventionCurrencyBasisSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierOvernightIndexFRASpread(DataIdentifier):

    _data_type = "Overnight Index FRA Spread"

    def __init__(self, data_convention: DataConventionOvernightIndexFRASpread) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierCompoundSwap(DataIdentifier):

    _type = "Compound Swap"

    def __init__(self, data_convention: DataConventionCompoundSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierCompoundBasisSwap(DataIdentifier):

    _type = "Compound Basis Swap"

    def __init__(self, data_convention: DataConventionCompoundBasisSwap) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierInstantaneousForwardRate(DataIdentifier):

    _data_type = 'Instantaneous Forward Rate'

    def __init__(self, data_convention: DataConventionInstantaneousForwardRate) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierFXRateIndex(DataIdentifier):

    _data_type = 'FX Rate Index'

    def __init__(self, data_convention: DataConventionFXRateIndex) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 1.

class DataIdentifierJump(DataIdentifier):

    _data_type = 'Jump'

    def __init__(self, data_convention: DataConventionJump) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierSwaptionNormalVolatility(DataIdentifier):

    _data_type = 'Swaption Normal Volatility'

    def __init__(self, data_convention: DataConventionSwaption) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierSwaptionSABRBeta(DataIdentifier):

    _data_type = 'Swaption SABR Beta'

    def __init__(self, data_convention: DataConventionSwaption) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.01
    
class DataIdentifierSwaptionSABRNu(DataIdentifier):

    _data_type = 'Swaption SABR Nu'

    def __init__(self, data_convention: DataConventionSwaption) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.01

class DataIdentifierSwaptionSABRRho(DataIdentifier):

    _data_type = 'Swaption SABR Rho'

    def __init__(self, data_convention: DataConventionSwaption) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.01

class DataIdentifierCapfloorNormalVolatility(DataIdentifier):

    _data_type = 'Capfloor Normal Volatility'

    def __init__(self, data_convention: DataConventionCapFloor) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.0001

class DataIdentifierCapfloorSABRBeta(DataIdentifier):

    _data_type = 'Capfloor SABR Beta'

    def __init__(self, data_convention: DataConventionCapFloor) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.01
    
class DataIdentifierCapfloorSABRNu(DataIdentifier):

    _data_type = 'Capfloor SABR Nu'

    def __init__(self, data_convention: DataConventionCapFloor) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.01

class DataIdentifierCapfloorSABRRho(DataIdentifier):

    _data_type = 'Capfloor SABR Rho'

    def __init__(self, data_convention: DataConventionCapFloor) -> None:
        super().__init__(data_convention)

    def unit(self):
        return 0.01

### Registry
class DataIdentifierRegistry(Registry):

    def __new__(cls) -> Self:
        return super().__new__(cls, "", cls.__name__)

    def register(self, key: Any, value: Any) -> None:
        super().register(key, value)
        self._map[key] = value

### registration
DataIdentifierRegistry().register(DataIdentifierCashDeposite._data_type.upper(), DataIdentifierCashDeposite)
DataIdentifierRegistry().register(DataIdentifierFRAOrFixing._data_type.upper(), DataIdentifierFRAOrFixing)
DataIdentifierRegistry().register(DataIdentifierOvernightIndexFuture._data_type.upper(), DataIdentifierOvernightIndexFuture)
DataIdentifierRegistry().register(DataIdentifierOvernightIndexSwap._data_type.upper(), DataIdentifierOvernightIndexSwap)
DataIdentifierRegistry().register(DataIdentifierOvernightIndexBasisSwap._data_type.upper(), DataIdentifierOvernightIndexBasisSwap)
DataIdentifierRegistry().register(DataIdentifierOISBasisSwap._data_type.upper(), DataIdentifierOISBasisSwap)
DataIdentifierRegistry().register(DataIdentifierOvernightIndexCurrencyBasisSwap._data_type.upper(), DataIdentifierOvernightIndexCurrencyBasisSwap)
DataIdentifierRegistry().register(DataIdentifierOISIBORCurrencyBasisSwap._data_type.upper(), DataIdentifierOISIBORCurrencyBasisSwap)
DataIdentifierRegistry().register(DataIdentifierGenericForward._data_type.upper(), DataIdentifierGenericForward)
DataIdentifierRegistry().register(DataIdentifierGenericForwardSpread._data_type.upper(), DataIdentifierGenericForwardSpread)
DataIdentifierRegistry().register(DataIdentifierZeroSpread._data_type.upper(), DataIdentifierZeroSpread)
DataIdentifierRegistry().register(DataIdentifierGenericSpread._data_type.upper(), DataIdentifierGenericSpread)
DataIdentifierRegistry().register(DataIdentifierFRN._data_type.upper(), DataIdentifierFRN)
DataIdentifierRegistry().register(DataIdentifierSwapSpreadBasisSwap._data_type.upper(), DataIdentifierSwapSpreadBasisSwap)
DataIdentifierRegistry().register(DataIdentifierIBORFuture._data_type.upper(), DataIdentifierIBORFuture)
DataIdentifierRegistry().register(DataIdentifierSwap._data_type.upper(), DataIdentifierSwap)
DataIdentifierRegistry().register(DataIdentifierBasisSwap._data_type.upper(), DataIdentifierBasisSwap)
DataIdentifierRegistry().register(DataIdentifierCurrencyBasisSwap._data_type.upper(), DataIdentifierCurrencyBasisSwap)
DataIdentifierRegistry().register(DataIdentifierOvernightIndexFRASpread._data_type.upper(), DataIdentifierOvernightIndexFRASpread)
DataIdentifierRegistry().register(DataIdentifierCompoundSwap._data_type.upper(), DataIdentifierCompoundSwap)
DataIdentifierRegistry().register(DataIdentifierCompoundBasisSwap._data_type.upper(), DataIdentifierCompoundBasisSwap)
DataIdentifierRegistry().register(DataIdentifierInstantaneousForwardRate._data_type.upper(), DataIdentifierInstantaneousForwardRate)
DataIdentifierRegistry().register(DataIdentifierFXRateIndex._data_type.upper(), DataIdentifierFXRateIndex)
DataIdentifierRegistry().register(DataIdentifierSwaptionNormalVolatility._data_type.upper(), DataIdentifierSwaptionNormalVolatility)
DataIdentifierRegistry().register(DataIdentifierSwaptionSABRBeta._data_type.upper(), DataIdentifierSwaptionSABRBeta)
DataIdentifierRegistry().register(DataIdentifierSwaptionSABRNu._data_type.upper(), DataIdentifierSwaptionSABRNu)
DataIdentifierRegistry().register(DataIdentifierSwaptionSABRRho._data_type.upper(), DataIdentifierSwaptionSABRRho)
DataIdentifierRegistry().register(DataIdentifierCapfloorNormalVolatility._data_type.upper(), DataIdentifierCapfloorNormalVolatility)
DataIdentifierRegistry().register(DataIdentifierCapfloorSABRBeta._data_type.upper(), DataIdentifierCapfloorSABRBeta)
DataIdentifierRegistry().register(DataIdentifierCapfloorSABRNu._data_type.upper(), DataIdentifierCapfloorSABRNu)
DataIdentifierRegistry().register(DataIdentifierCapfloorSABRRho._data_type.upper(), DataIdentifierCapfloorSABRRho)
DataIdentifierRegistry().register(DataIdentifierJump._data_type.upper(), DataIdentifierJump)

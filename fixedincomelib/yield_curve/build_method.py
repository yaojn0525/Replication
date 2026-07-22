from typing import Union, List
# in-house
from fixedincomelib.utilities import *
from fixedincomelib.market import *
from fixedincomelib.model import *

### YC FUNDING METHOD
class YieldCurveFundingBuildMethod(BuildMethod):

    _version = 1
    _build_method_type = "YC_FUNDING_ELEMENT"

    def __init__(self, target: str, content: Dict[str, Any]):
        super().__init__(target, content)
        self.target_index_ : FundingIdentifier = FundingIdentifierRegistry().get(self.target)

    @property
    def defaultable_entries(self) -> List:
        return [
            ["INTERPOLATION METHOD" , "PIECEWISE_CONSTANT_LEFT_CONTINUOUS"],
            ["EXTRAPOLATION METHOD" , "FLAT"] 
        ] 
    
    def calibration_instruments(self) -> List[str]:
        return [
            "INSTANTANEOUS FORWARD RATE",  # tick
            "IBOR SPREAD ZERO RATE",  # tick
            "CASH DEPOSIT",
            "FRA",
            "GENERIC FORWARD",
            "GENERIC FORWARD SPREAD",
            "GENERIC SPREAD",
            "LIBOR FUTURE",
            "SWAP",
            "FLOATING RATE NOTE",
            "CURRENCY BASIS SWAP",
            "OVERNIGHT INDEX CURRENCY SWAP",
            "OVERNIGHT INDEX BASIS CURRENCY SWAP"]
            ### to be added
            # "BOND",
            # "REPO"

    def additional_entries(self) -> set:
        return {"REFERENCE", "INTERPOLATION METHOD", "EXTRAPOLATION METHOD"}

    @property
    def target_index(self) -> FundingIdentifier:
        return self.target_index_

    @property
    def reference_index(self) -> Index:
        if not self.build_mehtod.get("REFERENCE"):
            return None
        return cast_to_index(self.build_mehtod["REFERENCE"])

    @property
    def instantaneous_forward_rate(self) -> DataConventionInstantaneousForwardRate:
        if self["INSTANTANEOUS FORWARD RATE"] == "":
            return None
        return DataConventionRegistry().get(self["INSTANTANEOUS FORWARD RATE"])

    @property
    def ibor_spread_zero_rate(self) -> DataConventionIborSpreadZeroRate:
        if not self["IBOR SPREAD ZERO RATE"]:
            return None
        return DataConventionRegistry().get(self["IBOR SPREAD ZERO RATE"])

    @property
    def cash_deposite(self) -> DataConventionCashDeposit:
        if not self["CASH DEPOSIT"]:
            return None
        return DataConventionRegistry().get(self["CASH DEPOSIT"])
    
    @property
    def fra_or_fixing(self) -> DataConventionFRAOrFixing:
        if not self["FRA OR FIXING"]:
            return None
        return DataConventionRegistry().get(self["FRA OR FIXING"])
    
    @property
    def generic_forward(self) -> DataConventionGenericForward:
        if not self["GENERIC FORWARD"]:
            return None
        return DataConventionRegistry().get(self["GENERIC FORWARD"])
    
    @property
    def generic_forward_spread(self) -> DataConventionGenericForwardSpread:
        if not self["GENERIC FORWARD SPREAD"]:
            return None
        return DataConventionRegistry().get(self["GENERIC FORWARD SPREAD"])
    
    @property
    def generic_spread(self) -> DataConventionGenericSpread:
        if not self["GENERIC SPREAD"]:
            return None
        return DataConventionRegistry().get(self["GENERIC SPREAD"])
    
    @property
    def ibor_future(self) -> DataConventionIBORFuture:
        if not self["IBOR FUTURE"]:
            return None
        return DataConventionRegistry().get(self["IBOR FUTURE"])
    
    @property
    def swap(self) -> DataConventionSwap:
        if not self["SWAP"]:
            return None
        return DataConventionRegistry().get(self["SWAP"])
    
    @property
    def floating_rate_note(self) -> DataConventionFRN:
        if not self["FLOATING RATE NOTE"]:
            return None
        return DataConventionRegistry().get(self["FLOATING RATE NOTE"])
    
    @property
    def currency_basis_swap(self) -> DataConventionCurrencyBasisSwap:
        if not self["CURRENCY BASIS SWAP"]:
            return None
        return DataConventionRegistry().get(self["CURRENCY BASIS SWAP"])

    @property
    def overnight_index_basis_swap(self) -> DataConventionOvernightIndexBasisSwap:
        if self["OVERNIGHT INDEX BASIS SWAP"] == "":
            return None
        return DataConventionRegistry().get(self["OVERNIGHT INDEX BASIS SWAP"])

    @property
    def overnight_index_currency_basis_swap(self) -> DataConventionOvernightIndexCurrencyBasisSwap:
        if self["OVERNIGHT INDEX CURRENCY BASIS SWAP"] == "":
            return None
        return DataConventionRegistry().get(self["OVERNIGHT INDEX CURRENCY BASIS SWAP"])

    @property
    def interpolation_method(self) -> InterpMethod:
        return InterpMethod.from_string(self["INTERPOLATION METHOD"])

    @property
    def extrapolation_method(self) -> ExtrapMethod:
        return ExtrapMethod.from_string(self["EXTRAPOLATION METHOD"])

### YC IBOR METHOD
class YieldCurveIBORBuildMethod(BuildMethod):

    _version = 1
    _build_method_type = "YC_IBOR_ELEMENT"

    def __init__(self, target: str, content: Dict[str, Any]):
        super().__init__(target, content)
        self.target_index_ : IBORIndex = IndexRegistry().get(self.target)

    @property
    def defaultable_entries(self) -> List:
        return [
            ["INTERPOLATION METHOD" , "PIECEWISE_CONSTANT_LEFT_CONTINUOUS"],
            ["EXTRAPOLATION METHOD" , "FLAT"] 
        ]
    
    def calibration_instruments(self) -> List[str]:
        return [
            "INSTANTANEOUS FORWARD RATE",
            "IBOR SPREAD ZERO RATE",
            "FRA OR FIXING",
            "GENERIC FORWARD",
            "GENERIC FORWARD SPREAD",
            "GENERIC SPREAD",
            "IBOR FUTURE",
            "SWAP",
            "COMPOUND SWAP",
            "FLOATING RATE NOTE",
            "COMPOUND BASIS SWAP",
            "CURRENCY BASIS SWAP",
            "OVERNIGHT INDEX CURRENCY SWAP",
            "OVERNIGHT INDEX BASIS SWAP"]

    @property
    def target_index(self) -> IBORIndex:
        return self.target_index_

    @property
    def reference_index(self) -> Index:
        if not self.build_mehtod.get("REFERENCE"):
            return None
        return cast_to_index(self.build_mehtod["REFERENCE"])

    @property
    def instantaneous_forward_rate(self) -> DataConventionInstantaneousForwardRate:
        if self["INSTANTANEOUS FORWARD RATE"] == "":
            return None
        return DataConventionRegistry().get(self["INSTANTANEOUS FORWARD RATE"])

    @property
    def ibor_spread_zero_rate(self) -> DataConventionIborSpreadZeroRate:
        if not self["IBOR SPREAD ZERO RATE"]:
            return None
        return DataConventionRegistry().get(self["IBOR SPREAD ZERO RATE"])
    
    @property
    def fra_or_fixing(self) -> DataConventionFRAOrFixing:
        if not self["FRA OR FIXING"]:
            return None
        return DataConventionRegistry().get(self["FRA OR FIXING"])
    
    @property
    def generic_forward(self) -> DataConventionGenericForward:
        if not self["GENERIC FORWARD"]:
            return None
        return DataConventionRegistry().get(self["GENERIC FORWARD"])
    
    @property
    def generic_forward_spread(self) -> DataConventionGenericForwardSpread:
        if not self["GENERIC FORWARD SPREAD"]:
            return None
        return DataConventionRegistry().get(self["GENERIC FORWARD SPREAD"])
    
    @property
    def generic_spread(self) -> DataConventionGenericSpread:
        if not self["GENERIC SPREAD"]:
            return None
        return DataConventionRegistry().get(self["GENERIC SPREAD"])
    
    @property
    def ibor_future(self) -> DataConventionIBORFuture:
        if not self["IBOR FUTURE"]:
            return None
        return DataConventionRegistry().get(self["IBOR FUTURE"])
    
    @property
    def swap(self) -> DataConventionSwap:
        if not self["SWAP"]:
            return None
        return DataConventionRegistry().get(self["SWAP"])
    
    @property
    def compound_swap(self) -> DataConventionCompoundSwap:
        if not self["COMPOUND SWAP"]:
            return None
        return DataConventionRegistry().get(self["COMPOUND SWAP"])
    
    @property
    def floating_rate_note(self) -> DataConventionFRN:
        if not self["FLOATING RATE NOTE"]:
            return None
        return DataConventionRegistry().get(self["FLOATING RATE NOTE"])
    
    @property
    def compound_basis_swap(self) -> DataConventionCompoundBasisSwap:
        if not self["COMPOUND BASIS SWAP"]:
            return None
        return DataConventionRegistry().get(self["COMPOUND BASIS SWAP"])

    @property
    def currency_basis_swap(self) -> DataConventionCurrencyBasisSwap:
        if not self["CURRENCY BASIS SWAP"]:
            return None
        return DataConventionRegistry().get(self["CURRENCY BASIS SWAP"])

    @property
    def overnight_index_currency_basis_swap(self) -> DataConventionOvernightIndexCurrencyBasisSwap:
        if self["OVERNIGHT INDEX CURRENCY BASIS SWAP"] == "":
            return None
        return DataConventionRegistry().get(self["OVERNIGHT INDEX CURRENCY BASIS SWAP"])

    @property
    def overnight_index_basis_swap(self) -> DataConventionOvernightIndexBasisSwap:
        if self["OVERNIGHT INDEX BASIS SWAP"] == "":
            return None
        return DataConventionRegistry().get(self["OVERNIGHT INDEX BASIS SWAP"])

    @property
    def interpolation_method(self) -> InterpMethod:
        return InterpMethod.from_string(self["INTERPOLATION METHOD"])

    @property
    def extrapolation_method(self) -> ExtrapMethod:
        return ExtrapMethod.from_string(self["EXTRAPOLATION METHOD"])

### YC OVERNIGHT INDEX METHOD
class YieldCurveONIndexBuildMethod(BuildMethod):

    _version = 1
    _build_method_type = "YC_OVERNIGHT_INDEX_ELEMENT"

    def __init__(self, target: str, content: Dict[str, Any]):

        super().__init__(target, content)
        self.target_index_ : OvernightIndex = IndexRegistry().get(self.target)

    @property
    def defaultable_entries(self) -> List:
        return [
            ["INTERPOLATION METHOD" , "PIECEWISE_CONSTANT_LEFT_CONTINUOUS"],
            ["EXTRAPOLATION METHOD" , "FLAT"]
        ]

    def calibration_instruments(self) -> List[str]:
        return [
            "INSTANTANEOUS FORWARD RATE",
            "IBOR SPREAD ZERO RATE",
            "FIXING",
            "FRA",
            "GENERIC FORWARD",
            "GENERIC FORWARD SPREAD",
            "GENERIC SPREAD",
            "LIBOR FUTURE",
            "SWAP",
            "OVERNIGHT INDEX FUTURE",
            "OVERNIGHT INDEX SWAP",
            "OVERNIGHT INDEX FRA SPREAD",
            "OVERNIGHT INDEX BASIS SWAP",
            "OIS BASIS SWAP"]

    @property
    def target_index(self) -> OvernightIndex:
        return self.target_index_

    @property
    def reference_index(self) -> Index:
        if not self.build_mehtod.get("REFERENCE"):
            return None
        return cast_to_index(self.build_mehtod["REFERENCE"])

    @property
    def instantaneous_forward_rate(self) -> DataConventionInstantaneousForwardRate:
        if self["INSTANTANEOUS FORWARD RATE"] == "":
            return None
        return DataConventionRegistry().get(self["INSTANTANEOUS FORWARD RATE"])

    @property
    def ibor_spread_zero_rate(self) -> DataConventionIborSpreadZeroRate:
        if not self["IBOR SPREAD ZERO RATE"]:
            return None
        return DataConventionRegistry().get(self["IBOR SPREAD ZERO RATE"])
    
    @property
    def fra_or_fixing(self) -> DataConventionFRAOrFixing:
        if not self["FRA OR FIXING"]:
            return None
        return DataConventionRegistry().get(self["FRA OR FIXING"])
    
    @property
    def generic_forward(self) -> DataConventionGenericForward:
        if not self["GENERIC FORWARD"]:
            return None
        return DataConventionRegistry().get(self["GENERIC FORWARD"])
    
    @property
    def generic_forward_spread(self) -> DataConventionGenericForwardSpread:
        if not self["GENERIC FORWARD SPREAD"]:
            return None
        return DataConventionRegistry().get(self["GENERIC FORWARD SPREAD"])
    
    @property
    def generic_spread(self) -> DataConventionGenericSpread:
        if not self["GENERIC SPREAD"]:
            return None
        return DataConventionRegistry().get(self["GENERIC SPREAD"])
    
    @property
    def ibor_future(self) -> DataConventionIBORFuture:
        if not self["IBOR FUTURE"]:
            return None
        return DataConventionRegistry().get(self["IBOR FUTURE"])
    
    @property
    def swap(self) -> DataConventionSwap:
        if not self["SWAP"]:
            return None
        return DataConventionRegistry().get(self["SWAP"])
    
    @property
    def overnight_index_future(self) -> DataConventionOvernightIndexFuture:
        if not self["OVERNIGHT INDEX FUTURE"]:
            return None
        return DataConventionRegistry().get(self["OVERNIGHT INDEX FUTURE"])
    
    @property
    def overnight_index_swap(self) -> DataConventionOvernightIndexSwap:
        if not self["OVERNIGHT INDEX SWAP"]:
            return None
        return DataConventionRegistry().get(self["OVERNIGHT INDEX SWAP"])

    @property
    def overnight_index_fra_sprad(self) -> DataConventionOvernightIndexFRASpread:
        if not self["OVERNIGHT INDEX FRA SPREAD"]:
            return None
        return DataConventionRegistry().get(self["OVERNIGHT INDEX FRA SPREAD"])

    @property
    def overnight_index_basis_swap(self) -> DataConventionOvernightIndexBasisSwap:
        if not self["OVERNIGHT INDEX BASIS SWAP"]:
            return None
        return DataConventionRegistry().get(self["OVERNIGHT INDEX BASIS SWAP"])
    
    @property
    def ois_basis_swap(self) -> DataConventionOISBasisSwap:
        if not self["OIS BASIS SWAP"]:
            return None
        return DataConventionRegistry().get(self["OIS BASIS SWAP"])

    @property
    def interpolation_method(self) -> InterpMethod:
        return InterpMethod.from_string(self["INTERPOLATION METHOD"])

    @property
    def extrapolation_method(self) -> ExtrapMethod:
        return ExtrapMethod.from_string(self["EXTRAPOLATION METHOD"])

### YC FX RATE METHOD
class YieldCurveFXBuildMethod(BuildMethod):

    _version = 1
    _build_method_type = "YC_FX_RATE"

    def __init__(self, target: str, content: Union[List, dict]):
        super().__init__(target, content)
        self.target_index_ : FXIndex = IndexRegistry().get(self.target)

    def has_reference(self) -> bool:
        return False

    @property
    def defaultable_entries(self) -> List:
        return [["BUILD CURRENCY CHAIN" , True]]

    def calibration_instruments(self) -> List[str]:
        return ["FX RATE INDEX"]

    @property
    def target_index(self) -> FXIndex:
        return self.target_index_

    @property
    def fx_rate_index(self) -> DataConventionFXRateIndex:
        if self["FX RATE INDEX"] == "":
            return None
        return DataConventionRegistry().get(self["FX RATE INDEX"])

    @property
    def build_currency_chain(self) -> bool:
        return self["BUILD CURRENCY CHAIN"]

### YC COMMON METHOD
class YieldCurveBuildMethodCommon(BuildMethod):

    _version = 1
    _build_method_type = "YC_COMMON"

    def __init__(self, currency: str, content: Union[List, dict]):
        super().__init__(currency, content)
        assert "FUNDING PARAMETERS" in self.build_mehtod
        self.target_currency_ = Currency(self.target)

    def has_reference(self) -> bool:
        return False

    @property
    def defaultable_entries(self) -> List:
        return [["SOLVER METHOD" , "ND_ITERATIVE_SOLVER"]]

    def calibration_instruments(self) -> List[str]:
        return ["FUNDING PARAMETERS"]

    @property
    def target_currency(self) -> Currency:
        return self.target_currency_

    @property
    def funding_parameter(self) -> str:
        return self["FUNDING PARAMETERS"]

    @property
    def solver(self) -> str:
        return self["SOLVER METHOD"]

### register
BuildMethodBuilderRegistry().register(YieldCurveFundingBuildMethod._build_method_type, YieldCurveFundingBuildMethod)
BuildMethodBuilderRegistry().register(YieldCurveIBORBuildMethod._build_method_type, YieldCurveIBORBuildMethod)
BuildMethodBuilderRegistry().register(YieldCurveONIndexBuildMethod._build_method_type, YieldCurveONIndexBuildMethod)
BuildMethodBuilderRegistry().register(YieldCurveFXBuildMethod._build_method_type, YieldCurveFXBuildMethod)
BuildMethodBuilderRegistry().register(YieldCurveBuildMethodCommon._build_method_type, YieldCurveBuildMethodCommon)
BuildMethodBuilderRegistry().register(f"{YieldCurveFundingBuildMethod._build_method_type}_DES", YieldCurveFundingBuildMethod.deserialize)
BuildMethodBuilderRegistry().register(f"{YieldCurveIBORBuildMethod._build_method_type}_DES", YieldCurveIBORBuildMethod.deserialize)
BuildMethodBuilderRegistry().register(f"{YieldCurveONIndexBuildMethod._build_method_type}_DES", YieldCurveONIndexBuildMethod.deserialize,)
BuildMethodBuilderRegistry().register(f"{YieldCurveFXBuildMethod._build_method_type}_DES", YieldCurveFXBuildMethod.deserialize)
BuildMethodBuilderRegistry().register(f"{YieldCurveBuildMethodCommon._build_method_type}_DES", YieldCurveBuildMethodCommon.deserialize)

from enum import Enum

class SABRParameters(Enum):

    # parameters
    NV = "SWAPTION NORMAL VOLATILITY"
    BETA = "SWAPTION SABR BETA"
    NU = "SWAPTION SABR NU"
    RHO = "SWAPTION SABR RHO"

    @classmethod
    def from_string(cls, value: str) -> "SABRParameters":
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.upper())
        except ValueError:
            raise ValueError(f"Invalid token: {value}")

    def to_string(self) -> str:
        return self.value
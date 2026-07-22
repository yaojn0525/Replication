from typing import Union, List
import QuantLib as ql
from fixedincomelib.sabr.archived.sabr_parameters import SABRParameters
from fixedincomelib.date import Period
from fixedincomelib.market.basics import BusinessDayConvention, Currency, HolidayConvention
from fixedincomelib.market.data_conventions import (
    DataConventionRFRSwaption, DataConventionRFRCapFloor)
from fixedincomelib.market.indices import (
    Index, DataConventionRegistry, FundingIdentifier, FundingIdentifierRegistry, IndexRegistry, SABRIndex)
from fixedincomelib.model import (BuildMethod, BuildMethodBuilderRregistry)
from fixedincomelib.utilities.numerics import (ExtrapMethod, InterpMethod)

class SABRBuildMethod(BuildMethod):

    _version = 1
    _build_method_type = 'IR_SABR'

    def __init__(self, 
                 target : str,
                 content : Union[List, dict]):

        super().__init__(target, 'IR_SABR', content)
        if self.bm_dict['VOL INTERPOLATION DOMAIN'] == '':
            self.bm_dict['VOL INTERPOLATION DOMAIN'] = 'VOLATILITY'
        if self.bm_dict['INTERPOLATION METHOD'] == '':
            self.bm_dict['INTERPOLATION METHOD'] = 'LINEAR'
        if self.bm_dict['EXTRAPOLATION METHOD'] == '':
            self.bm_dict['EXTRAPOLATION METHOD'] = 'FLAT'
        if self.bm_dict['BUSINESSDAY CONVENTION'] == '':
            self.bm_dict['BUSINESSDAY CONVENTION'] = 'F'
        if self.bm_dict['HOLIDAY CONVENTION'] == '':
            self.bm_dict['HOLIDAY CONVENTION'] = 'USGS'
        if self.bm_dict['SHIFT'] == '':
            self.bm_dict['SHIFT'] = 0
        v = self.target.split('|')
        v : SABRIndex = IndexRegistry().get(self.target)
        self.target_index_ = v.index # e.g., SOFR-1B
        self.is_swpt_ = not v.iscapfloor

    def calibration_instruments(self) -> set:
        return {
            SABRParameters.NV.to_string(),
            SABRParameters.BETA.to_string(),
            SABRParameters.NU.to_string(),
            SABRParameters.RHO.to_string()}

    def additional_entries(self) -> set:
        return {
            'VOL INTERPOLATION DOMAIN',
            'INTERPOLATION METHOD', 
            'EXTRAPOLATION METHOD',
            'BUSINESSDAY CONVENTION', 
            'HOLIDAY CONVENTION',
            'SHIFT'}

    @property
    def is_swpt(self):
        return self.is_swpt_

    @property
    def normal_vol(self) -> DataConventionRFRSwaption:
        assert self[SABRParameters.NV] != ''
        return DataConventionRegistry().get(self[SABRParameters.NV])

    @property
    def beta(self) -> DataConventionRFRSwaption:
        assert self[SABRParameters.BETA] != ''
        return DataConventionRegistry().get(self[SABRParameters.BETA])
    
    @property
    def nu(self) -> DataConventionRFRSwaption:
        assert self[SABRParameters.NU] != ''
        return DataConventionRegistry().get(self[SABRParameters.NU])

    @property
    def rho(self) -> DataConventionRFRSwaption:
        assert self[SABRParameters.RHO] != ''
        return DataConventionRegistry().get(self[SABRParameters.RHO])

    @property
    def target_index(self) -> ql.Index:
        return self.target_index_

    @property
    def interpolation_domain(self) -> str:
        return self.bm_dict['VOL INTERPOLATION DOMAIN']

    @property
    def interpolation_method(self) -> InterpMethod:
        return InterpMethod.from_string(self['INTERPOLATION METHOD'])

    @property
    def extrapolation_method(self) -> ExtrapMethod:
        return ExtrapMethod.from_string(self['EXTRAPOLATION METHOD'])

    @property
    def business_convention(self) -> BusinessDayConvention:
        return BusinessDayConvention(self['BUSINESSDAY CONVENTION'])

    @property
    def holiday_convention(self) -> HolidayConvention:
        return HolidayConvention(self['HOLIDAY CONVENTION'])

    @property
    def shift(self) -> float:
        return self['SHIFT']

### register
BuildMethodBuilderRregistry().register(SABRBuildMethod._build_method_type, SABRBuildMethod)
BuildMethodBuilderRregistry().register(f'{SABRBuildMethod._build_method_type}_DES', SABRBuildMethod.deserialize)

from enum import Enum
import numpy as np
from typing import Dict, Optional
import QuantLib as ql
from fixedincomelib.sabr.archived.sabr_model import SABRModel, SABRModelComponent
from fixedincomelib.sabr.archived.build_method import SABRBuildMethod
from fixedincomelib.analytics.archived.sabr import SABRAnalytics, SabrMetrics
from fixedincomelib.valuation.valuation_parameters import ValuationParametersCollection
from fixedincomelib.analytics.archived.european_options import CallOrPut, SimpleMetrics
from fixedincomelib.sabr.archived.sabr_parameters import SABRParameters


class SABRPriceAndRiskCalculator:

    def __init__(self, 
                model : SABRModel,
                valuation_parameters_collection : ValuationParametersCollection,
                index : ql.Index,
                forward : float,
                strike : float,
                time_to_expiry : float,
                tenor : float,
                call_or_put : CallOrPut,
                apply_transform : Optional[bool]=False, # don't need this for now
                calc_risk : Optional[bool]=False):

            # initialization
            self.model_ = model
            self.vpc_ = valuation_parameters_collection # potential usage
            self.index_ = index
            self.forward_ = forward
            self.strike_ = strike
            self.expiry_ = time_to_expiry
            self.tenor_ = tenor
            self.call_or_put_ = call_or_put
            self.is_overnight_index_ = isinstance(index, ql.OvernightIndex)
            self.calc_risk_ = calc_risk
            # self.apply_transform_ = apply_transform

            self.value_ = None
            self.risk_ = {}
            self.result_ = {}
    
            # resolve negative treatment
            this_component : SABRModelComponent = self.model_.retrieve_model_component(self.index_)
            this_bm : SABRBuildMethod = this_component.build_method
            self.shift_ = this_bm.shift # shift !!!
            self.forward_shifted_ = self.forward_ + self.shift_
            self.strike_shifted_ = self.strike_ + self.shift_

            # get sabr parameters,
            sabr_info : Dict[SABRParameters, float] = self.model_.get_sabr_parameters(self.index_, self.expiry_, self.tenor_)
            self.nv_ = sabr_info[SABRParameters.NV]
            self.beta_ = sabr_info[SABRParameters.BETA]
            self.nu_ = sabr_info[SABRParameters.NU]
            self.rho_ = sabr_info[SABRParameters.RHO]

            self.alpha_transform_info_ : Dict[SabrMetrics, float] = \
                SABRAnalytics.alpha_from_atm_normal_sigma(
                self.forward_, 
                self.expiry_,
                self.nv_,
                self.beta_, 
                self.rho_,
                self.nu_, 
                self.shift_,
                self.calc_risk_
            )
            self.alpha_ = self.alpha_transform_info_[SabrMetrics.ALPHA]
    
    def calculate_value(self):
        # sabr analytics lacks one function
        res = SABRAnalytics.european_option_alpha(
            self.forward_,
            self.strike_, 
            self.expiry_,
            self.call_or_put_,
            self.alpha_,
            self.beta_,
            self.rho_,
            self.nu_,
            self.shift_,
            self.calc_risk_)
        
        res[SABRParameters.NV] = self.nv_
        res[SABRParameters.BETA] = self.beta_
        res[SABRParameters.NU] = self.nu_
        res[SABRParameters.RHO] = self.rho_
        res[SabrMetrics.ALPHA] = self.alpha_
        for k, v in self.alpha_transform_info_.items():
            if k not in res:
                res[k] = v

        self.result_ = res
        self.value_ = res[SimpleMetrics.PV]

        if self.calc_risk_:
             self.risk_ = {
                key: value
                for key, value in self.result_.items()
                if key != SimpleMetrics.PV
            }
        else:
             self.risk_ = {}

        return res
    
    def calculate_risk(self,
        gradient_vector: np.ndarray,
        scaler : float
    ):
        
        if not self.result_:
              self.calculate_value()
         
        self.risk_ = {
            key: value * scaler
            for key, value in self.result_.items()
            if key != SimpleMetrics.PV
        }

        # forward process: grid => interpolate sigma => sabr formula
        # backward process: dsabr/dparam => interpolator_grad => grid

        # risk from european_option_alpha is in alpha-parameterization
        dV_dalpha = self.risk_[SabrMetrics.DALPHA]
        # chain rule: 
        # dV/dNV   = dV/dALPHA * dALPHA/dNV
        dV_dnv = dV_dalpha * self.alpha_transform_info_[SabrMetrics.D_ALPHA_D_NORMAL_SIGMA_ATM]
        # dV/dBETA = direct dV/dBETA + dV/dALPHA * dALPHA/dBETA
        dV_dbeta = (self.risk_[SabrMetrics.DBETA] + dV_dalpha * self.alpha_transform_info_[SabrMetrics.D_ALPHA_D_BETA])
        dV_dnu = (self.risk_[SabrMetrics.DNU] + dV_dalpha * self.alpha_transform_info_[SabrMetrics.D_ALPHA_D_NU])
        dV_drho = (self.risk_[SabrMetrics.DRHO] + dV_dalpha * self.alpha_transform_info_[SabrMetrics.D_ALPHA_D_RHO])

        local_risk = [dV_dnv, dV_dbeta, dV_dnu, dV_drho]

        # what did i do here ?
        # i project all local risk back to the internal state of SABR
        self.model_.get_sabr_parameter_gradient_wrt_state(
            self.index_, 
            self.expiry_, 
            self.tenor_,
            gradient_vector, # give me gradient vector
            local_risk,
            True
        )

        return self.risk_ # <= this must contain forward risk
    
    @property
    def value(self):
        if self.value_ is None:
            self.calculate_value()
        return self.value_
    
    @property
    def risk(self):
        if self.calc_risk_ and len(self.risk_) == 0:
             self.calculate_value() # only local risk
        return self.risk_
    
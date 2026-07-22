from enum import Enum
import numpy as np
from typing import Optional, Dict, Any, Tuple, List
from scipy.stats import norm
from fixedincomelib.analytics.archived.european_options import (
    CallOrPut,
    SimpleMetrics,
    EuropeanOptionAnalytics,
)


class SabrMetrics(Enum):

    # parameters
    ALPHA = "alpha"
    BETA = "beta"
    NU = "nu"
    RHO = "rho"

    # risk
    DALPHA = "dalpha"
    DLNSIGMA = "dlnsigma"
    DNORMALSIGMA = "dnormalsigma"
    DBETA = "dbeta"
    DRHO = "drho"
    DNU = "dnu"
    DFORWARD = "dforward"
    DSTRIKE = "dstrike"
    DTTE = "dtte"
    DSTRIKESTRIKE = "dstrikestrike"

    # (alpha, beta, nu, rho, forward, strike, tte) => \sigma_k
    D_LN_SIGMA_D_FORWARD = "d_ln_sigma_d_forward"
    D_LN_SIGMA_D_STRIKE = "d_ln_sigma_d_strike"
    D_LN_SIGMA_D_TTE = "d_ln_sigma_d_tte"
    D_LN_SIGMA_D_ALPHA = "d_ln_sigma_d_alpha"
    D_LN_SIGMA_D_BETA = "d_ln_sigma_d_beta"
    D_LN_SIGMA_D_NU = "d_ln_sigma_d_nu"
    D_LN_SIGMA_D_RHO = "d_ln_sigma_d_rho"
    D_LN_SIGMA_D_STRIKESTRIKE = "d_ln_sigma_d_strike_strike"

    # (\sigma_ln_atm, f, tte, beta, nu, rho) => alpha
    D_ALPHA_D_LN_SIGMA_ATM = "d_alpha_d_ln_sigma_atm"
    D_ALPHA_D_FORWARD = "d_alpha_d_forward"
    D_ALPHA_D_TTE = "d_alpha_d_tte"
    D_ALPHA_D_BETA = "d_alpha_d_beta"
    D_ALPHA_D_NU = "d_alpha_d_nu"
    D_ALPHA_D_RHO = "d_alpha_d_rho"

    # (alpha, beta, nu, rho, f, tte) => \sigma_n_atm
    D_NORMAL_SIGMA_D_ALPHA = "d_normal_sigma_d_alpha"
    D_NORMAL_SIGMA_D_BETA = "d_normal_sigma_d_beta"
    D_NORMAL_SIGMA_D_NU = "d_normal_sigma_d_nu"
    D_NORMAL_SIGMA_D_RHO = "d_normal_sigma_d_rho"
    D_NORMAL_SIGMA_D_FORWARD = "d_normal_sigma_d_forward"
    D_NORMAL_SIGMA_D_TTE = "d_normal_sigma_d_tte"
    D_ALPHA_D_NORMAL_SIGMA_ATM = "d_alpha_d_normal_sigma_atm"

    @classmethod
    def from_string(cls, value: str) -> "SabrMetrics":
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        try:
            return cls(value.lower())
        except ValueError as e:
            raise ValueError(f"Invalid token: {value}") from e

    def to_string(self) -> str:
        return self.value


class SABRAnalytics:

    EPSILON = 1e-6

    ### parameters conversion

    @staticmethod
    def lognormal_vol_from_alpha(
        forward: float,
        strike: float,
        time_to_expiry: float,
        alpha: float,
        beta: float,
        rho: float,
        nu: float,
        shift: Optional[float] = 0.0,
        calc_risk: Optional[bool] = False,
    ) -> Dict[SabrMetrics | SimpleMetrics, float]:

        res: Dict[Any, float] = {}

        ln_sigma, risks = SABRAnalytics._vol_and_risk(
            forward + shift, strike + shift, time_to_expiry, alpha, beta, rho, nu, calc_risk
        )
        res[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL] = ln_sigma

        if len(risks) == 0:
            return res

        res.update(risks)
        return res

    @staticmethod
    def alpha_from_atm_lognormal_sigma(
        forward: float,
        time_to_expiry: float,
        sigma_atm_lognormal: float,
        beta: float,
        rho: float,
        nu: float,
        shift: Optional[float] = 0.0,
        calc_risk: Optional[bool] = False,
        max_iter: Optional[int] = 50,
        tol: Optional[float] = 1e-12,
    ) -> Dict[SabrMetrics, float]:

        if forward + shift <= 0.0:
            raise ValueError("forward must be > 0")
        if time_to_expiry < 0.0:
            raise ValueError("time_to_expiry must be >= 0")
        if sigma_atm_lognormal <= 0.0:
            raise ValueError("sigma_atm_lognormal must be > 0")
        if abs(rho) >= 1.0:
            raise ValueError("rho must be in (-1,1)")
        if nu < 0.0:
            raise ValueError("nu must be >= 0")
        if not (0.0 <= beta <= 1.0):
            raise ValueError("beta should be in [0,1] for standard SABR usage")

        # newton + bisec fallback
        # root finding
        # f = F(alpha, theta) - ln_sigma = 0
        # where F is lognormal_vol_from_alpha
        # alpha^* = alpha(ln_sigma, theta)

        this_res = None
        alpha = sigma_atm_lognormal * (forward + shift) ** (1.0 - beta)
        for _ in range(max_iter):

            this_res = SABRAnalytics.lognormal_vol_from_alpha(
                forward, forward, time_to_expiry, alpha, beta, rho, nu, shift, True
            )

            fval = this_res[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL] - sigma_atm_lognormal
            dval = this_res[SabrMetrics.D_LN_SIGMA_D_ALPHA]  # df/dAlpha

            if abs(fval) < tol:
                break

            if dval == 0.0 or not np.isfinite(dval):
                alpha = max(1e-16, alpha * 0.9)
                continue

            alpha_new = alpha - fval / dval

            if (alpha_new <= 0.0) or (not np.isfinite(alpha_new)):
                alpha_new = alpha * 0.5
            if alpha_new > 10.0 * alpha:
                alpha_new = 0.5 * (alpha_new + alpha)

            alpha = alpha_new

        else:
            raise RuntimeError("alpha_from_atm_lognormal_sigma: Newton did not converge")

        res: Dict[SabrMetrics, float] = {SabrMetrics.ALPHA: alpha}

        if not calc_risk:
            return res

        # dalphad...
        # alpha^* = alpha(ln_sigma, theta, target_ln_sigma)
        # F(alpha(ln_sigma, theta), theta) = target_ln_sigma
        # using implicit function theorem
        # df/dalpha * dalpha/dln_sigma = 1 =>             dalpha / dln_sigma = 1 / df/dalpha
        # df/dalpha * dalpha/dtheta  + df/dtheta = 0 =>  dalpha / dtheta = - df/dtheta / df/dalpha

        res[SabrMetrics.D_ALPHA_D_LN_SIGMA_ATM] = 1.0 / this_res[SabrMetrics.D_LN_SIGMA_D_ALPHA]
        res[SabrMetrics.D_ALPHA_D_BETA] = (
            -this_res[SabrMetrics.D_LN_SIGMA_D_BETA] / this_res[SabrMetrics.D_LN_SIGMA_D_ALPHA]
        )
        res[SabrMetrics.D_ALPHA_D_NU] = (
            -this_res[SabrMetrics.D_LN_SIGMA_D_NU] / this_res[SabrMetrics.D_LN_SIGMA_D_ALPHA]
        )
        res[SabrMetrics.D_ALPHA_D_RHO] = (
            -this_res[SabrMetrics.D_LN_SIGMA_D_RHO] / this_res[SabrMetrics.D_LN_SIGMA_D_ALPHA]
        )
        res[SabrMetrics.D_ALPHA_D_FORWARD] = (
            -(
                this_res[SabrMetrics.D_LN_SIGMA_D_FORWARD]
                + this_res[SabrMetrics.D_LN_SIGMA_D_STRIKE]
            )
            / this_res[SabrMetrics.D_LN_SIGMA_D_ALPHA]
        )
        res[SabrMetrics.D_ALPHA_D_TTE] = (
            -this_res[SabrMetrics.D_LN_SIGMA_D_TTE] / this_res[SabrMetrics.D_LN_SIGMA_D_ALPHA]
        )

        return res

    @staticmethod
    def alpha_from_atm_normal_sigma(
        forward: float,
        time_to_expiry: float,
        sigma_atm_normal: float,
        beta: float,
        rho: float,
        nu: float,
        shift: Optional[float] = 0.0,
        calc_risk: bool = False,
        max_iter: int = 50,
        tol: float = 1e-8,
    ) -> Dict[SabrMetrics, float]:

        # at atm, from nv vol to ln vol
        this_res = EuropeanOptionAnalytics.normal_vol_to_lognormal_vol(
            forward, forward, time_to_expiry, sigma_atm_normal, calc_risk, shift, tol
        )

        # compute implied log normal vol
        that_res = SABRAnalytics.alpha_from_atm_lognormal_sigma(
            forward,
            time_to_expiry,
            this_res[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL],
            beta,
            rho,
            nu,
            shift,
            calc_risk,
            max_iter,
            tol,
        )

        # risk aggregation
        final_res = {SabrMetrics.ALPHA: that_res[SabrMetrics.ALPHA]}
        if calc_risk:
            # dalpha / dsigma
            final_res[SabrMetrics.D_ALPHA_D_NORMAL_SIGMA_ATM] = (
                that_res[SabrMetrics.D_ALPHA_D_LN_SIGMA_ATM]
                * this_res[SimpleMetrics.D_LN_VOL_D_N_VOL]
            )
            # dalpha / dbeta/nu/rho just copy over
            final_res[SabrMetrics.D_ALPHA_D_BETA] = that_res[SabrMetrics.D_ALPHA_D_BETA]
            final_res[SabrMetrics.D_ALPHA_D_RHO] = that_res[SabrMetrics.D_ALPHA_D_RHO]
            final_res[SabrMetrics.D_ALPHA_D_NU] = that_res[SabrMetrics.D_ALPHA_D_NU]
            # dalpha / dtte
            final_res[SabrMetrics.D_ALPHA_D_TTE] = (
                that_res[SabrMetrics.D_ALPHA_D_TTE]
                + that_res[SabrMetrics.D_ALPHA_D_LN_SIGMA_ATM]
                * this_res[SimpleMetrics.D_LN_VOL_D_TTE]
            )
            # dalpha / dforward
            final_res[SabrMetrics.D_ALPHA_D_FORWARD] = that_res[
                SabrMetrics.D_ALPHA_D_FORWARD
            ] + that_res[SabrMetrics.D_ALPHA_D_LN_SIGMA_ATM] * (
                this_res[SimpleMetrics.D_LN_VOL_D_FORWARD]
                + this_res[SimpleMetrics.D_LN_VOL_D_STRIKE]
            )

        return final_res

    @staticmethod
    def atm_normal_sigma_from_alpha(
        forward: float,
        time_to_expiry: float,
        alpha: float,
        beta: float,
        rho: float,
        nu: float,
        shift: Optional[float] = 0.0,
        calc_risk: Optional[bool] = False,
        tol: Optional[float] = 1e-8,
    ):

        # at atm, from alpha to log normal vol
        this_res = SABRAnalytics.lognormal_vol_from_alpha(
            forward, forward, time_to_expiry, alpha, beta, rho, nu, shift, calc_risk
        )

        # compute normal vol
        that_res = EuropeanOptionAnalytics.lognormal_vol_to_normal_vol(
            forward,
            forward,
            time_to_expiry,
            this_res[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL],
            calc_risk,
            shift,
            tol,
        )

        # calc risk
        # risk aggregation
        final_res = {SimpleMetrics.IMPLIED_NORMAL_VOL: that_res[SimpleMetrics.IMPLIED_NORMAL_VOL]}
        if calc_risk:
            # dnvol / dalpha|beta|nu|rho
            final_res[SabrMetrics.D_NORMAL_SIGMA_D_ALPHA] = (
                that_res[SimpleMetrics.D_N_VOL_D_LN_VOL] * this_res[SabrMetrics.D_LN_SIGMA_D_ALPHA]
            )
            final_res[SabrMetrics.D_NORMAL_SIGMA_D_BETA] = (
                that_res[SimpleMetrics.D_N_VOL_D_LN_VOL] * this_res[SabrMetrics.D_LN_SIGMA_D_BETA]
            )
            final_res[SabrMetrics.D_NORMAL_SIGMA_D_RHO] = (
                that_res[SimpleMetrics.D_N_VOL_D_LN_VOL] * this_res[SabrMetrics.D_LN_SIGMA_D_RHO]
            )
            final_res[SabrMetrics.D_NORMAL_SIGMA_D_NU] = (
                that_res[SimpleMetrics.D_N_VOL_D_LN_VOL] * this_res[SabrMetrics.D_LN_SIGMA_D_NU]
            )
            # dnvol / dforward
            final_res[SabrMetrics.D_NORMAL_SIGMA_D_FORWARD] = (
                that_res[SimpleMetrics.D_N_VOL_D_LN_VOL]
                * (
                    this_res[SabrMetrics.D_LN_SIGMA_D_FORWARD]
                    + this_res[SabrMetrics.D_LN_SIGMA_D_STRIKE]
                )
                + that_res[SimpleMetrics.D_N_VOL_D_FORWARD]
                + that_res[SimpleMetrics.D_N_VOL_D_STRIKE]
            )
            # dnvol / dtte
            final_res[SabrMetrics.D_NORMAL_SIGMA_D_TTE] = (
                that_res[SimpleMetrics.D_N_VOL_D_LN_VOL] * this_res[SabrMetrics.D_LN_SIGMA_D_TTE]
                + that_res[SimpleMetrics.D_N_VOL_D_TTE]
            )

        return final_res

    ### option pricing

    @staticmethod
    def european_option_alpha(
        forward: float,
        strike: float,
        time_to_expiry: float,
        opt_type: CallOrPut,
        alpha: float,
        beta: float,
        rho: float,
        nu: float,
        shift: Optional[float] = 0.0,
        calc_risk: Optional[bool] = False,
    ):

        ### pv
        ln_sigma_and_sensitivities = SABRAnalytics.lognormal_vol_from_alpha(
            forward, strike, time_to_expiry, alpha, beta, rho, nu, shift, calc_risk
        )
        ln_iv = ln_sigma_and_sensitivities[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL]
        value_and_sensitivities = EuropeanOptionAnalytics.european_option_log_normal(
            forward + shift, strike + shift, time_to_expiry, ln_iv, opt_type, calc_risk
        )

        ### risk(analytic)
        if calc_risk:
            ## first order risks
            dvdsigma = value_and_sensitivities[SimpleMetrics.VEGA]
            value_and_sensitivities.pop(SimpleMetrics.VEGA)
            # delta
            value_and_sensitivities[SimpleMetrics.DELTA] += (
                dvdsigma * ln_sigma_and_sensitivities[SabrMetrics.D_LN_SIGMA_D_FORWARD]
            )
            # theta
            value_and_sensitivities[SimpleMetrics.THETA] -= (
                dvdsigma * ln_sigma_and_sensitivities[SabrMetrics.D_LN_SIGMA_D_TTE]
            )
            # sabr alpha/beta/nu/rho
            for key, risk in [
                (SabrMetrics.DALPHA, SabrMetrics.D_LN_SIGMA_D_ALPHA),
                (SabrMetrics.DBETA, SabrMetrics.D_LN_SIGMA_D_BETA),
                (SabrMetrics.DRHO, SabrMetrics.D_LN_SIGMA_D_RHO),
                (SabrMetrics.DNU, SabrMetrics.D_LN_SIGMA_D_NU),
            ]:
                value_and_sensitivities[key] = dvdsigma * ln_sigma_and_sensitivities[risk]
            # strike
            value_and_sensitivities[SimpleMetrics.STRIKE_RISK] += (
                dvdsigma * ln_sigma_and_sensitivities[SabrMetrics.D_LN_SIGMA_D_STRIKE]
            )

            ## second order risk (bump reval)
            v_base = value_and_sensitivities[SimpleMetrics.PV]
            # strike
            res_up = SABRAnalytics.lognormal_vol_from_alpha(
                forward, strike + SABRAnalytics.EPSILON, time_to_expiry, alpha, beta, rho, nu, shift
            )
            vol_up = res_up[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL]
            v_up = EuropeanOptionAnalytics.european_option_log_normal(
                forward + shift,
                strike + shift + SABRAnalytics.EPSILON,
                time_to_expiry,
                vol_up,
                opt_type,
            )[SimpleMetrics.PV]

            res_dn = SABRAnalytics.lognormal_vol_from_alpha(
                forward, strike - SABRAnalytics.EPSILON, time_to_expiry, alpha, beta, rho, nu, shift
            )
            vol_dn = res_dn[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL]
            v_dn = EuropeanOptionAnalytics.european_option_log_normal(
                forward + shift,
                strike + shift - SABRAnalytics.EPSILON,
                time_to_expiry,
                vol_dn,
                opt_type,
            )[SimpleMetrics.PV]
            value_and_sensitivities[SimpleMetrics.STRIKE_RISK_2] = (v_up - 2 * v_base + v_dn) / (
                SABRAnalytics.EPSILON**2
            )

            # gamma
            res_up = SABRAnalytics.lognormal_vol_from_alpha(
                forward + SABRAnalytics.EPSILON, strike, time_to_expiry, alpha, beta, rho, nu, shift
            )
            vol_up = res_up[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL]
            v_up = EuropeanOptionAnalytics.european_option_log_normal(
                forward + shift + SABRAnalytics.EPSILON,
                strike + shift,
                time_to_expiry,
                vol_up,
                opt_type,
            )[SimpleMetrics.PV]
            res_dn = SABRAnalytics.lognormal_vol_from_alpha(
                forward - SABRAnalytics.EPSILON, strike, time_to_expiry, alpha, beta, rho, nu, shift
            )
            vol_dn = res_dn[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL]
            v_dn = EuropeanOptionAnalytics.european_option_log_normal(
                forward + shift - SABRAnalytics.EPSILON,
                strike + shift,
                time_to_expiry,
                vol_dn,
                opt_type,
            )[SimpleMetrics.PV]
            value_and_sensitivities[SimpleMetrics.GAMMA] = (v_up - 2 * v_base + v_dn) / (
                SABRAnalytics.EPSILON**2
            )

        return value_and_sensitivities

    @staticmethod
    def european_option_ln_sigma(
        forward: float,
        strike: float,
        time_to_expiry: float,
        opt_type: CallOrPut,
        ln_sigma_atm: float,
        beta: float,
        rho: float,
        nu: float,
        shift: Optional[float] = 0.0,
        calc_risk: Optional[bool] = False,
    ):

        ### pv
        alpha_and_sensitivities = SABRAnalytics.alpha_from_atm_lognormal_sigma(
            forward, time_to_expiry, ln_sigma_atm, beta, rho, nu, shift, calc_risk
        )
        alpha = alpha_and_sensitivities[SabrMetrics.ALPHA]
        value_and_sensitivities = SABRAnalytics.european_option_alpha(
            forward, strike, time_to_expiry, opt_type, alpha, beta, rho, nu, shift, calc_risk
        )

        ### risk
        if calc_risk:
            ## first order risks
            dvdalpha = value_and_sensitivities[SabrMetrics.DALPHA]
            value_and_sensitivities.pop(SabrMetrics.DALPHA)

            # delta
            value_and_sensitivities[SimpleMetrics.DELTA] += (
                dvdalpha * alpha_and_sensitivities[SabrMetrics.D_ALPHA_D_FORWARD]
            )
            # theta
            value_and_sensitivities[SimpleMetrics.THETA] -= (
                dvdalpha * alpha_and_sensitivities[SabrMetrics.D_ALPHA_D_TTE]
            )
            # ln_sigma
            value_and_sensitivities[SabrMetrics.DLNSIGMA] = (
                dvdalpha * alpha_and_sensitivities[SabrMetrics.D_ALPHA_D_LN_SIGMA_ATM]
            )
            # sabr beta/rho/nu
            for key, risk in [
                (SabrMetrics.DBETA, SabrMetrics.D_ALPHA_D_BETA),
                (SabrMetrics.DRHO, SabrMetrics.D_ALPHA_D_RHO),
                (SabrMetrics.DNU, SabrMetrics.D_ALPHA_D_NU),
            ]:
                value_and_sensitivities[key] += dvdalpha * alpha_and_sensitivities[risk]

            ## second order risk (bump reval)
            v_base = value_and_sensitivities[SimpleMetrics.PV]

            # gamma
            res_up = SABRAnalytics.alpha_from_atm_lognormal_sigma(
                forward + SABRAnalytics.EPSILON, time_to_expiry, ln_sigma_atm, beta, rho, nu, shift
            )
            alpha_up = res_up[SabrMetrics.ALPHA]
            v_up = SABRAnalytics.european_option_alpha(
                forward + SABRAnalytics.EPSILON,
                strike,
                time_to_expiry,
                opt_type,
                alpha_up,
                beta,
                rho,
                nu,
                shift,
            )[SimpleMetrics.PV]
            res_dn = SABRAnalytics.alpha_from_atm_lognormal_sigma(
                forward - SABRAnalytics.EPSILON, time_to_expiry, ln_sigma_atm, beta, rho, nu, shift
            )
            alpha_dn = res_dn[SabrMetrics.ALPHA]
            v_dn = SABRAnalytics.european_option_alpha(
                forward - SABRAnalytics.EPSILON,
                strike,
                time_to_expiry,
                opt_type,
                alpha_dn,
                beta,
                rho,
                nu,
                shift,
            )[SimpleMetrics.PV]
            value_and_sensitivities[SimpleMetrics.GAMMA] = (v_up - 2 * v_base + v_dn) / (
                SABRAnalytics.EPSILON**2
            )

        return value_and_sensitivities

    @staticmethod
    def european_option_normal_sigma(
        forward: float,
        strike: float,
        time_to_expiry: float,
        opt_type: CallOrPut,
        normal_sigma_atm: float,
        beta: float,
        rho: float,
        nu: float,
        shift: Optional[float] = 0.0,
        calc_risk: Optional[bool] = False,
    ):

        ### pv
        alpha_and_sensitivities = SABRAnalytics.alpha_from_atm_normal_sigma(
            forward, time_to_expiry, normal_sigma_atm, beta, rho, nu, shift, calc_risk
        )
        alpha = alpha_and_sensitivities[SabrMetrics.ALPHA]
        value_and_sensitivities = SABRAnalytics.european_option_alpha(
            forward, strike, time_to_expiry, opt_type, alpha, beta, rho, nu, shift, calc_risk
        )

        ### risk
        if calc_risk:
            ## first order risks
            dvdalpha = value_and_sensitivities[SabrMetrics.DALPHA]
            value_and_sensitivities.pop(SabrMetrics.DALPHA)
            # delta
            value_and_sensitivities[SimpleMetrics.DELTA] += (
                dvdalpha * alpha_and_sensitivities[SabrMetrics.D_ALPHA_D_FORWARD]
            )
            # theta
            value_and_sensitivities[SimpleMetrics.THETA] -= (
                dvdalpha * alpha_and_sensitivities[SabrMetrics.D_ALPHA_D_TTE]
            )
            # normal_sigma
            value_and_sensitivities[SabrMetrics.DNORMALSIGMA] = (
                dvdalpha * alpha_and_sensitivities[SabrMetrics.D_ALPHA_D_NORMAL_SIGMA_ATM]
            )
            # sabr beta/rho/nu
            for key, risk in [
                (SabrMetrics.DBETA, SabrMetrics.D_ALPHA_D_BETA),
                (SabrMetrics.DRHO, SabrMetrics.D_ALPHA_D_RHO),
                (SabrMetrics.DNU, SabrMetrics.D_ALPHA_D_NU),
            ]:
                value_and_sensitivities[key] += dvdalpha * alpha_and_sensitivities[risk]

            # second order risk (bump reval)
            v_base = value_and_sensitivities[SimpleMetrics.PV]

            # gamma
            res_up = SABRAnalytics.alpha_from_atm_normal_sigma(
                forward + SABRAnalytics.EPSILON,
                time_to_expiry,
                normal_sigma_atm,
                beta,
                rho,
                nu,
                shift,
            )
            alpha_up = res_up[SabrMetrics.ALPHA]
            v_up = SABRAnalytics.european_option_alpha(
                forward + SABRAnalytics.EPSILON,
                strike,
                time_to_expiry,
                opt_type,
                alpha_up,
                beta,
                rho,
                nu,
                shift,
            )[SimpleMetrics.PV]
            res_dn = SABRAnalytics.alpha_from_atm_normal_sigma(
                forward - SABRAnalytics.EPSILON,
                time_to_expiry,
                normal_sigma_atm,
                beta,
                rho,
                nu,
                shift,
            )
            alpha_dn = res_dn[SabrMetrics.ALPHA]
            v_dn = SABRAnalytics.european_option_alpha(
                forward - SABRAnalytics.EPSILON,
                strike,
                time_to_expiry,
                opt_type,
                alpha_dn,
                beta,
                rho,
                nu,
                shift,
            )[SimpleMetrics.PV]
            value_and_sensitivities[SimpleMetrics.GAMMA] = (v_up - 2 * v_base + v_dn) / (
                SABRAnalytics.EPSILON**2
            )

        return value_and_sensitivities

    ### pdf and cdf
    @staticmethod
    def pdf_and_cdf(
        forward: float,
        time_to_expiry: float,
        alpha: float,
        beta: float,
        rho: float,
        nu: float,
        grids: List | np.ndarray,
        shift: Optional[float] = 0,
    ):

        ks, ks_shifted, cdf, pdf = [], [], [], []

        T = time_to_expiry
        F = forward

        for k in grids:
            F_s = F + shift
            K_s = k + shift
            ln_res = SABRAnalytics.lognormal_vol_from_alpha(
                forward, k, time_to_expiry, alpha, beta, rho, nu, shift, calc_risk=True
            )
            sigma_LN = ln_res[SimpleMetrics.IMPLIED_LOG_NORMAL_VOL]
            dsigmaLN_dK = ln_res[SabrMetrics.D_LN_SIGMA_D_STRIKE]
            dsigmaLN2_dk2 = ln_res[SabrMetrics.D_LN_SIGMA_D_STRIKESTRIKE]

            sqrtT = np.sqrt(T)

            d2 = (np.log(F_s / K_s) - 1.0 / 2.0 * sigma_LN**2 * T) / sigma_LN / sqrtT
            d1 = d2 + sigma_LN * sqrtT

            c_k = norm.cdf(-d2) + K_s * norm.pdf(d2) * sqrtT * dsigmaLN_dK

            p_k = norm.pdf(d2) * (
                1.0 / (K_s * sigma_LN * sqrtT)
                + 2.0 * d1 / sigma_LN * dsigmaLN_dK
                + K_s * sqrtT * dsigmaLN2_dk2
                + K_s * sqrtT * (d1 * d2 / sigma_LN) * (dsigmaLN_dK**2)
            )

            ks.append(k)
            ks_shifted.append(k + shift)
            cdf.append(c_k)
            pdf.append(p_k)

        return ks, ks_shifted, cdf, pdf

    ### helpers

    @staticmethod
    def w2_risk(F, K, T, a, b, r, n) -> Dict:

        risk = {}

        risk[SabrMetrics.DALPHA] = (1 - b) ** 2 / 12 * a / (F * K) ** (1 - b) + b * r * n / (
            4 * (F * K) ** ((1 - b) / 2)
        )
        risk[SabrMetrics.DBETA] = (
            1 / 12 * (b - 1) * a**2 * (F * K) ** (b - 1)
            + 1 / 24 * (b - 1) ** 2 * a**2 * (F * K) ** (b - 1) * np.log(F * K)
            + 1 / 4 * a * r * n * (F * K) ** ((b - 1) / 2)
            + 1 / 8 * a * b * r * n * (F * K) ** ((b - 1) / 2) * np.log(F * K)
        )
        risk[SabrMetrics.DRHO] = 1 / 4 * a * b * n * (F * K) ** ((b - 1) / 2) - 1 / 4 * n**2 * r
        risk[SabrMetrics.DNU] = (
            1 / 4 * a * b * r * (F * K) ** ((b - 1) / 2) + 1 / 6 * n - 1 / 4 * r**2 * n
        )
        risk[SabrMetrics.DFORWARD] = (b - 1) ** 3 / 24 * a**2 * (F * K) ** (
            b - 2
        ) * K + a * r * n * b * (b - 1) / 8 * K ** ((b - 1) / 2) * F ** ((b - 3) / 2)

        risk[SabrMetrics.DSTRIKE] = (b - 1) ** 3 / 24 * a**2 * F ** (b - 1) * K ** (
            b - 2
        ) + a * b * r * n * (b - 1) / 8 * F ** ((b - 1) / 2) * K ** ((b - 3) / 2)

        risk[SabrMetrics.DSTRIKESTRIKE] = (b - 1) ** 3 / 24 * a**2 * (b - 2) * F ** (
            b - 1
        ) * K ** (b - 3) + a * b * r * n / 16 * (b - 1) * (b - 3) * F ** ((b - 1) / 2) * K ** (
            (b - 5) / 2
        )

        return risk

    @staticmethod
    def w1_risk(F, K, T, a, b, r, n) -> Dict:

        log_FK = np.log(F / K)

        risk = {}
        risk[SabrMetrics.DALPHA] = 0.0
        risk[SabrMetrics.DBETA] = (b - 1) / 12.0 * log_FK**2 + (b - 1) ** 3 / 480 * log_FK**4
        risk[SabrMetrics.DRHO] = 0.0
        risk[SabrMetrics.DNU] = 0.0
        risk[SabrMetrics.DFORWARD] = (b - 1) ** 2 / 12 * log_FK / F + (
            b - 1
        ) ** 4 / 480 / F * log_FK**3
        risk[SabrMetrics.DSTRIKE] = (
            -((b - 1) ** 2) / 12 * log_FK / K - (b - 1) ** 4 / 480 / K * log_FK**3
        )
        risk[SabrMetrics.DSTRIKESTRIKE] = (
            (b - 1) ** 2 / 12 / K**2
            + (b - 1) ** 2 / 12 * log_FK / K**2
            + (b - 1) ** 4 / 160 * log_FK**2 / K**2
            + (b - 1) ** 4 / 480 * log_FK**3 / K**2
        )

        return risk

    @staticmethod
    def z_risk(F, K, T, a, b, r, n) -> Dict:

        log_FK = np.log(F / K)
        fk = (F * K) ** ((1 - b) / 2)
        # z = n / a * log_FK * fk

        risk = {}
        risk[SabrMetrics.DALPHA] = -n / a * log_FK * fk / a
        risk[SabrMetrics.DBETA] = -1.0 / 2 * n / a * log_FK * fk * np.log(F * K)
        risk[SabrMetrics.DRHO] = 0.0
        risk[SabrMetrics.DNU] = 1.0 / a * log_FK * fk
        risk[SabrMetrics.DFORWARD] = (
            n * (1 - b) * K / 2 / a * (F * K) ** ((-b - 1) / 2) * log_FK + n / a * fk / F
        )
        risk[SabrMetrics.DSTRIKE] = (
            n * F * (1 - b) / 2 / a * log_FK * (F * K) ** ((-b - 1) / 2) - n / a * fk / K
        )
        risk[SabrMetrics.DSTRIKESTRIKE] = (
            n / a * F ** ((1 - b) / 2) * K ** ((-b - 3) / 2) * (log_FK * (b**2 - 1) / 4 + b)
        )

        return risk

    @staticmethod
    def x_risk(F, K, T, a, b, r, n) -> Dict:

        logFK = np.log(F / K)
        fk = (F * K) ** ((1 - b) / 2)
        z = n / a * fk * logFK
        dx_dz = 1 / np.sqrt(1 - 2 * r * z + z**2)

        risk = {}
        risk_z = SABRAnalytics.z_risk(F, K, T, a, b, r, n)

        risk[SabrMetrics.DALPHA] = dx_dz * risk_z[SabrMetrics.DALPHA]
        risk[SabrMetrics.DBETA] = dx_dz * risk_z[SabrMetrics.DBETA]
        risk[SabrMetrics.DRHO] = 1 / (1 - r) + (-z * dx_dz - 1) / (1 / dx_dz + z - r)
        risk[SabrMetrics.DNU] = dx_dz * risk_z[SabrMetrics.DNU]
        risk[SabrMetrics.DFORWARD] = dx_dz * risk_z[SabrMetrics.DFORWARD]
        risk[SabrMetrics.DSTRIKE] = dx_dz * risk_z[SabrMetrics.DSTRIKE]

        risk[SabrMetrics.DSTRIKESTRIKE] = (r - z) * dx_dz**3 * (
            risk_z[SabrMetrics.DSTRIKE] ** 2
        ) + dx_dz * risk_z[SabrMetrics.DSTRIKESTRIKE]

        return risk

    @staticmethod
    def C_risk(F, K, T, a, b, r, n) -> Dict:

        log_FK = np.log(F / K)
        fk = (F * K) ** ((1 - b) / 2)

        z = n / a * log_FK * fk
        risk = {}

        C0 = 1.0
        C1 = -r / 2.0
        C2 = -(r**2) / 4.0 + 1.0 / 6.0
        C3 = -(1.0 / 4.0 * r**2 - 5.0 / 24.0) * r
        C4 = -5.0 / 16.0 * r**4 + 1.0 / 3.0 * r**2 - 17.0 / 360.0
        C5 = -(7.0 / 16.0 * r**4 - 55.0 / 96.0 * r**2 + 37.0 / 240.0) * r

        dC_dz = C1 + 2 * C2 * z + 3 * C3 * z**2 + 4 * C4 * z**3 + 5 * C5 * z**4
        dC2_dz2 = 2 * C2 + 6 * C3 * z + 12 * C4 * z**2 + 20 * C5 * z**3

        risk[SabrMetrics.DRHO] = (
            -1.0 / 2 * z
            + 5.0 / 24 * z**3
            - 37.0 / 240 * z**5
            - 1.0 / 2 * z**2 * r
            + 2.0 / 3 * z**4 * r
            - 3.0 / 4 * z**3 * r**2
            + 55.0 / 32 * z**5 * r**2
            - 5.0 / 4 * z**4 * r**3
            - 35.0 / 16 * z**5 * r**4
        )
        risk_z = SABRAnalytics.z_risk(F, K, T, a, b, r, n)

        risk[SabrMetrics.DALPHA] = dC_dz * risk_z[SabrMetrics.DALPHA]
        risk[SabrMetrics.DBETA] = dC_dz * risk_z[SabrMetrics.DBETA]
        risk[SabrMetrics.DNU] = dC_dz * risk_z[SabrMetrics.DNU]
        risk[SabrMetrics.DFORWARD] = dC_dz * risk_z[SabrMetrics.DFORWARD]
        risk[SabrMetrics.DSTRIKE] = dC_dz * risk_z[SabrMetrics.DSTRIKE]
        risk[SabrMetrics.DSTRIKESTRIKE] = (
            dC_dz * risk_z[SabrMetrics.DSTRIKESTRIKE] + dC2_dz2 * risk_z[SabrMetrics.DSTRIKE] ** 2
        )
        return risk

    @staticmethod
    def _vol_and_risk(
        F, K, T, a, b, r, n, calc_risk=False, z_cut=1e-2
    ) -> Tuple[float, Dict[SabrMetrics, float]]:
        """
        Get analytical solution Lognormal Vol and Greeks
        """

        log_FK = np.log(F / K)
        fk = (F * K) ** ((1 - b) / 2)
        greeks: Dict[SabrMetrics, float] = {}

        z = n / a * log_FK * fk

        w1 = 1 + ((1 - b) ** 2) / 24 * (log_FK**2) + (1 - b) ** 4 / 1920 * (log_FK**4)
        w2 = (
            (1 - b) ** 2 / 24 * a**2 / fk**2
            + 1 / 4 * a * b * r * n / fk
            + (2 - 3 * r**2) / 24 * n**2
        )

        if abs(z) < z_cut:
            # FIC
            C0 = 1.0
            C1 = -r / 2.0
            C2 = -(r**2) / 4.0 + 1.0 / 6.0
            C3 = -(1.0 / 4.0 * r**2 - 5.0 / 24.0) * r
            C4 = -5.0 / 16.0 * r**4 + 1.0 / 3.0 * r**2 - 17.0 / 360.0
            C5 = -(7.0 / 16.0 * r**4 - 55.0 / 96.0 * r**2 + 37.0 / 240.0) * r

            C = C0 + C1 * z + C2 * z**2 + C3 * z**3 + C4 * z**4 + C5 * z**5

            sigma = a / fk / w1 * C * (1 + w2 * T)

            if calc_risk:

                risk_w1 = SABRAnalytics.w1_risk(F, K, T, a, b, r, n)
                risk_w2 = SABRAnalytics.w2_risk(F, K, T, a, b, r, n)

                risk_C = SABRAnalytics.C_risk(F, K, T, a, b, r, n)

                greeks[SabrMetrics.D_LN_SIGMA_D_ALPHA] = (
                    sigma / a
                    + sigma / C * risk_C[SabrMetrics.DALPHA]
                    + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DALPHA]
                )
                greeks[SabrMetrics.D_LN_SIGMA_D_BETA] = (
                    sigma * 1 / 2 * np.log(F * K)
                    - sigma / w1 * risk_w1[SabrMetrics.DBETA]
                    + sigma / C * risk_C[SabrMetrics.DBETA]
                    + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DBETA]
                )
                greeks[SabrMetrics.D_LN_SIGMA_D_RHO] = (
                    +sigma / C * risk_C[SabrMetrics.DRHO]
                    + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DRHO]
                )
                greeks[SabrMetrics.D_LN_SIGMA_D_NU] = (
                    sigma / C * risk_C[SabrMetrics.DNU]
                    + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DNU]
                )
                greeks[SabrMetrics.D_LN_SIGMA_D_FORWARD] = (
                    sigma * (b - 1) / 2 / F
                    + sigma / C * risk_C[SabrMetrics.DFORWARD]
                    - sigma / w1 * risk_w1[SabrMetrics.DFORWARD]
                    + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DFORWARD]
                )
                greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE] = (
                    sigma * (b - 1) / 2 / K
                    + sigma / C * risk_C[SabrMetrics.DSTRIKE]
                    - sigma / w1 * risk_w1[SabrMetrics.DSTRIKE]
                    + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DSTRIKE]
                )
                greeks[SabrMetrics.D_LN_SIGMA_D_TTE] = sigma / (1 + w2 * T) * w2

                greeks[SabrMetrics.D_LN_SIGMA_D_STRIKESTRIKE] = (
                    (b - 1) / 2 / K * greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE]
                    - (b - 1) / 2 / K**2 * sigma
                    + 1 / C * greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE] * risk_C[SabrMetrics.DSTRIKE]
                    - sigma / C**2 * (risk_C[SabrMetrics.DSTRIKE] ** 2)
                    + sigma / C * (risk_C[SabrMetrics.DSTRIKESTRIKE])
                    + T
                    / (1 + w2 * T)
                    * greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE]
                    * risk_w2[SabrMetrics.DSTRIKE]
                    - sigma * T**2 / (1 + w2 * T) ** 2 * (risk_w2[SabrMetrics.DSTRIKE] ** 2)
                    + sigma * T / (1 + w2 * T) * risk_w2[SabrMetrics.DSTRIKESTRIKE]
                    - 1
                    / w1
                    * greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE]
                    * risk_w1[SabrMetrics.DSTRIKE]
                    + sigma / w1**2 * risk_w1[SabrMetrics.DSTRIKE] ** 2
                    - sigma / w1 * risk_w1[SabrMetrics.DSTRIKESTRIKE]
                )

            return sigma, greeks

        # raw SABR
        x = np.log((np.sqrt(1 - 2 * r * z + z**2) + z - r) / (1 - r))
        sigma = a / fk / w1 * z / x * (1 + w2 * T)

        if calc_risk:
            risk_z = SABRAnalytics.z_risk(F, K, T, a, b, r, n)
            risk_w1 = SABRAnalytics.w1_risk(F, K, T, a, b, r, n)
            risk_w2 = SABRAnalytics.w2_risk(F, K, T, a, b, r, n)
            risk_x = SABRAnalytics.x_risk(F, K, T, a, b, r, n)

            greeks[SabrMetrics.D_LN_SIGMA_D_ALPHA] = (
                sigma / a
                + sigma / z * risk_z[SabrMetrics.DALPHA]
                - sigma / x * risk_x[SabrMetrics.DALPHA]
                + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DALPHA]
            )
            greeks[SabrMetrics.D_LN_SIGMA_D_BETA] = (
                sigma * 1 / 2 * np.log(F * K)
                - sigma / w1 * risk_w1[SabrMetrics.DBETA]
                + sigma / z * risk_z[SabrMetrics.DBETA]
                - sigma / x * risk_x[SabrMetrics.DBETA]
                + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DBETA]
            )
            greeks[SabrMetrics.D_LN_SIGMA_D_RHO] = (
                -sigma / x * risk_x[SabrMetrics.DRHO]
                + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DRHO]
            )
            greeks[SabrMetrics.D_LN_SIGMA_D_NU] = (
                sigma / z * risk_z[SabrMetrics.DNU]
                - sigma / x * risk_x[SabrMetrics.DNU]
                + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DNU]
            )
            greeks[SabrMetrics.D_LN_SIGMA_D_FORWARD] = (
                sigma * (b - 1) / 2 / F
                + sigma / z * risk_z[SabrMetrics.DFORWARD]
                - sigma / w1 * risk_w1[SabrMetrics.DFORWARD]
                - sigma / x * risk_x[SabrMetrics.DFORWARD]
                + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DFORWARD]
            )
            greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE] = (
                sigma * (b - 1) / 2 / K
                + sigma / z * risk_z[SabrMetrics.DSTRIKE]
                - sigma / w1 * risk_w1[SabrMetrics.DSTRIKE]
                - sigma / x * risk_x[SabrMetrics.DSTRIKE]
                + sigma / (1 + w2 * T) * T * risk_w2[SabrMetrics.DSTRIKE]
            )
            greeks[SabrMetrics.D_LN_SIGMA_D_TTE] = sigma / (1 + w2 * T) * w2
            greeks[SabrMetrics.D_LN_SIGMA_D_STRIKESTRIKE] = (
                (b - 1) / 2 / K * greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE]
                - (b - 1) / 2 / K**2 * sigma
                + 1 / z * greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE] * risk_z[SabrMetrics.DSTRIKE]
                - sigma / z**2 * (risk_z[SabrMetrics.DSTRIKE] ** 2)
                + sigma / z * (risk_z[SabrMetrics.DSTRIKESTRIKE])
                - 1 / x * greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE] * risk_x[SabrMetrics.DSTRIKE]
                + sigma / x**2 * (risk_x[SabrMetrics.DSTRIKE] ** 2)
                - sigma / x * (risk_x[SabrMetrics.DSTRIKESTRIKE])
                + T
                / (1 + w2 * T)
                * greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE]
                * risk_w2[SabrMetrics.DSTRIKE]
                - sigma * T**2 / (1 + w2 * T) ** 2 * (risk_w2[SabrMetrics.DSTRIKE] ** 2)
                + sigma * T / (1 + w2 * T) * risk_w2[SabrMetrics.DSTRIKESTRIKE]
                - 1 / w1 * greeks[SabrMetrics.D_LN_SIGMA_D_STRIKE] * risk_w1[SabrMetrics.DSTRIKE]
                + sigma / w1**2 * risk_w1[SabrMetrics.DSTRIKE] ** 2
                - sigma / w1 * risk_w1[SabrMetrics.DSTRIKESTRIKE]
            )
        return sigma, greeks

from typing import List

import numpy as np

# in-house imports
from fixedincomelib.date import *
from fixedincomelib.market import *
from fixedincomelib.product import *
from fixedincomelib.valuation import *


class ValuationEngineProductPortfolio(ValuationEngineProduct):

    def __init__(
        self,
        model: Model,
        valuation_parameters_collection: ValuationParametersCollection,
        product: ProductPortfolio,
        request: ValuationRequest,
    ):
        super().__init__(model, valuation_parameters_collection, product, request)

        self.engines_: List[ValuationEngineProduct] = []
        self.weights = []
        self.currencies = []
        for prod, weight in product.elements_:
            self.weights.append(weight)
            self.currencies.append(prod.currency)
            self.engines_.append(
                ValuationEngineProductRegistry().new_valuation_engine(
                    model, prod, valuation_parameters_collection, request
                )
            )

    @classmethod
    def val_engine_type(cls) -> str:
        return cls.__name__

    def calculate_value(self):

        self.value_ = 0.0
        self.cash_ = 0.0

        self.aggregated_value_ = {}
        self.aggregated_cash_ = {}
        for i, engine in enumerate(self.engines_):
            engine.calculate_value()
            this_ccy: Currency = self.currencies[i]
            if this_ccy in self.aggregated_value_:
                self.aggregated_value_[this_ccy] += self.weights[i] * engine.value
                self.aggregated_cash_[this_ccy] += self.weights[i] * engine.cash
            else:
                self.aggregated_value_[this_ccy] = self.weights[i] * engine.value
                self.aggregated_cash_[this_ccy] = self.weights[i] * engine.cash

    def get_risk(self, gradient=None) -> None:

        local_grad = np.zeros_like(self.model_.get_gradient(reset=False))

        # risk is always computed separately per product first, then aggregated to the portfolio level
        self.product_risk_: List[np.ndarray] = []
        for i, engine in enumerate(self.engines_):
            leg_grad = np.zeros_like(local_grad)
            engine.get_risk(gradient=leg_grad)
            weighted_grad = self.weights[i] * leg_grad
            self.product_risk_.append(weighted_grad)
            local_grad += weighted_grad

        if gradient is None:
            return

        gradient[:] = local_grad

    @property
    def product_risk(self) -> List[np.ndarray]:
        return self.product_risk_

    # return vp to control risk report
    def _risk_level(self) -> str:
        vpc = self.valuation_parameters_collection_
        if vpc.has_vp_type(RiskValParam._vp_type):
            return vpc.get_vp_from_build_method_collection(RiskValParam._vp_type).level
        return "PORTFOLIO"

    def get_risk_report(self):
        # vpc-driven view on top of get_risk(): "PORTFOLIO" (default) returns the aggregated
        # gradient array; "PRODUCT" returns the per-product breakdown instead.
        local_grad = np.zeros_like(self.model_.get_gradient(reset=False))
        self.get_risk(gradient=local_grad)
        if self._risk_level() == "PRODUCT":
            return self.product_risk_
        return local_grad

    def get_value_and_cash(self) -> PVCashReport:
        report = PVCashReport(self.currencies)
        for ccy, value in self.aggregated_value_.items():
            report.set_pv(ccy, value)
            report.set_cash(ccy, self.aggregated_cash_[ccy])
        return report

    def create_cash_flows_report(self) -> CashflowsReport:

        portfolio_cf = CashflowsReport()
        for i, engine in enumerate(self.engines_):
            leg_cf = engine.create_cash_flows_report()
            for row in leg_cf.content:
                row_dict = dict(zip(leg_cf.schema, row))
                portfolio_cf.add_row(
                    i,  # leg_id: the element's own position within the portfolio
                    row_dict[CFReportColumns.PRODUCT_TYPE.to_string()],
                    row_dict[CFReportColumns.VALUATION_ENGINE_TYPE.to_string()],
                    row_dict[CFReportColumns.NOTIONAL.to_string()],
                    row_dict[CFReportColumns.PAY_OR_RECEIVE.to_string()],
                    row_dict[CFReportColumns.PAY_DATE.to_string()],
                    row_dict[CFReportColumns.FORECASTED_AMOUNT.to_string()],
                    row_dict[CFReportColumns.PV.to_string()],
                    row_dict[CFReportColumns.DF.to_string()],
                    fixing_date=row_dict.get(CFReportColumns.FIXING_DATE.to_string()),
                    start_date=row_dict.get(CFReportColumns.START_DATE.to_string()),
                    end_date=row_dict.get(CFReportColumns.END_DATE.to_string()),
                    accrued=row_dict.get(CFReportColumns.ACCRUED.to_string()),
                    index_or_fixed=row_dict.get(CFReportColumns.INDEX_OR_FIXED.to_string()),
                    index_value=row_dict.get(CFReportColumns.INDEX_VALUE.to_string()),
                )

        return portfolio_cf


ValuationEngineProductRegistry().register(
    (
        ModelType.YIELD_CURVE.value,
        ProductPortfolio._product_type,
        AnalyticValParam._vp_type,
    ),
    ValuationEngineProductPortfolio,
)

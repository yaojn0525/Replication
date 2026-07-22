from re import sub
import numpy as np
from typing import Optional, Any, Dict, List
from fixedincomelib.date import *
from fixedincomelib.data import *
from fixedincomelib.market import *
from fixedincomelib.model import *
from fixedincomelib.product import *
from fixedincomelib.sabr.archived.sabr_model import SABRModel
from fixedincomelib.utilities import *
from fixedincomelib.valuation.archived import *
from fixedincomelib.valuation.valuation_engine import ValuationRequest
from fixedincomelib.sabr.archived.build_method import SABRBuildMethod
from fixedincomelib.sabr.archived.sabr_parameters import SABRParameters
# import sabr component
from fixedincomelib.sabr.archived.sabr_model import SABRModelComponent
from fixedincomelib.utilities.numerics import InterpolatorFactory
from fixedincomelib.yield_curve import *


class SABRModelBuilder:

    @staticmethod
    def create_sabr_model_without_yield_curve(
        value_date: Date,
        data_collection: DataCollection,
        build_method_collection: BuildMethodCollection,
    ):
        yc_bm_list = []
        for _, bm in build_method_collection.items:
            if isinstance(bm, SABRBuildMethod):
                continue
            yc_bm_list.append(bm)
        yc_bm_collection = BuildMethodCollection(yc_bm_list)
        sub_model = YieldCurveBuilder.create_model_yield_curve(value_date, data_collection, yc_bm_collection)

        return SABRModelBuilder.create_sabr_model(sub_model, data_collection, build_method_collection)


    @staticmethod
    def create_sabr_model(
        sub_model : YieldCurve,
        data_collection: DataCollection,
        build_method_collection: BuildMethodCollection,
    ):

        sabr_model_skeleton = SABRModel(sub_model, data_collection, build_method_collection)

        for _, bm in build_method_collection.items:
            if not isinstance(bm, SABRBuildMethod):
                continue
            raw_mkt_data = {}
            mkt_data_list = []
            for data_type in bm.calibration_instruments():
                data_conv = bm[data_type]
                if data_conv == '': continue
                mkt_data = data_collection.get_data_from_data_collection(data_type, data_conv)
                raw_mkt_data[data_type] = mkt_data
                this_axis1 = mkt_data.axis1
                this_axis2 = mkt_data.axis2
                this_values = mkt_data.values
                param = SABRParameters(data_type)
                mkt_data_list.append((param, this_axis1, this_axis2, this_values))
            axis1 = mkt_data_list[0][1]
            axis2 = mkt_data_list[0][2]
            state_data = {param: values for param, _, _, values in mkt_data_list}
            market_data = {
                'AXIS1': axis1,
                'AXIS2': axis2,
                'RAW_MKT_DATA': raw_mkt_data
            }

            sabr_comp = SABRModelComponent(
                value_date = sub_model.value_date,
                component_identifier=bm.target_index,
                state_data=state_data,
                build_method=bm,
                market_data=market_data
            )
            sabr_model_skeleton.set_model_component(bm.target, sabr_comp)

        return sabr_model_skeleton
import numpy as np
from typing import List, Dict
# in-house
from fixedincomelib.date import *
from fixedincomelib.data import *
from fixedincomelib.market import *
from fixedincomelib.model import *
from fixedincomelib.utilities import *
from fixedincomelib.yield_curve.build_method import *
from fixedincomelib.yield_curve.yield_curve_model import *


class YieldCurveBuilder:

    @staticmethod
    def create_model_yield_curve(
        value_date: Date,
        data_collection: DataCollection,
        build_method_collection: BuildMethodCollection
    ):
        ### this is the entry for all types of model creation
        ### for now, let us only deal with building from state data

        ### intialize model yield curve shell
        model_yield_curve = YieldCurve(
            value_date, data_collection, build_method_collection)

        ### if all build methods "calibrate" to IFR, we route to create from state data api
        dependency_map = dict()

        # parse build methods to see if all of them calibrate to IFR
        build_from_state_data = YieldCurveBuilder._parse_state_build_method(
            build_method_collection, dependency_map)

        if build_from_state_data:
            model_yield_curve = YieldCurveBuilder.create_yield_curve_from_state_data(
                value_date, data_collection, build_method_collection, model_yield_curve)
            # set_component_dependency must run after components are added (not before)
            model_yield_curve.set_component_dependency(dependency_map)
            return model_yield_curve

        # TODO: implement calibration to market data when build methods don't all calibrate to IFR
        raise NotImplementedError("Only support build from state data.")

    @staticmethod
    def create_yield_curve_from_state_data(
        value_date: Date,
        data_collection: DataCollection,
        build_method_collection: BuildMethodCollection,
        model_yield_curve: YieldCurve,
    ):

        # components does not require calibration
        for _, bm in build_method_collection.items:
            this_bm: BuildMethod = bm
            if type(this_bm) != YieldCurveBuildMethodCommon:
                data_conv_ifr = getattr(this_bm, "instantaneous_forward_rate", None)
                state_data = data_collection.get_data_from_data_collection(
                    "INSTANTANEOUS FORWARD RATE", data_conv_ifr.name
                )
                component = YieldCurveBuilder.calibrate_single_component_from_state_data(
                    value_date, data_conv_ifr, state_data, this_bm
                )
                model_yield_curve.set_model_component(this_bm.target.upper(), component)
        return model_yield_curve

    @staticmethod
    def calibrate_single_component_from_state_data(
        value_date: Date,
        data_conv: DataConventionInstantaneousForwardRate,
        state_data: Data1D,
        build_method: BuildMethod,
    ):

        calendar_index = build_method.target_index
        if isinstance(calendar_index, FundingIdentifier):
            calendar_index = calendar_index.base_index
        business_day_convention = calendar_index.payment_business_day_conv
        holiday_convention = calendar_index.payment_holiday_conv

        time_to_anchored_dates = []
        values = []
        market_data = []
        for i in range(len(state_data.axis1)):
            this_x = state_data.axis1[i]
            if TermOrDate(this_x).is_term():
                # if it is term
                moved_date = add_period(value_date, Period(this_x), business_day_convention, holiday_convention)
                time = accrued(value_date, moved_date)
            else:
                # if it is date
                time = accrued(value_date, Date(this_x))
            time_to_anchored_dates.append(time)
            values.append(state_data.values[i])
            market_data.append(
                [
                    "INSTANTANEOUS FORWARD RATE",
                    data_conv.name,
                    this_x,
                    "",
                    state_data.values[i],
                    state_data.data_identifier.unit(),
                ]
            )

        # check if time instances are sorted
        assert np.all(np.diff(time_to_anchored_dates) >= 0)
        combined_data = np.asarray([time_to_anchored_dates, values])

        return YieldCurveModelComponent(
            value_date,
            build_method.target_index,
            combined_data,
            build_method,
            market_data=market_data,
        )

    ### utils
    @staticmethod
    def _parse_state_build_method(
        build_method_collection: BuildMethodCollection, dependency_map: Dict
    ) -> bool:

        has_ifr = True
        for _, bm in build_method_collection.items:
            this_bm: BuildMethod = bm
            if (
                type(this_bm) != YieldCurveBuildMethodCommon
                and type(this_bm) != YieldCurveFXBuildMethod
            ):
                target_index: Index = this_bm.target_index
                this_reference: Index = this_bm.reference_index
                # insert into dependency map
                if this_reference:
                    dependency_map[target_index] = this_reference
                this_ifr = this_bm.instantaneous_forward_rate
                has_ifr &= bool(this_ifr)

        return has_ifr

### registry
ModelBuilderRegistry().register(YieldCurve._model_type.to_string(), YieldCurveBuilder.create_model_yield_curve)

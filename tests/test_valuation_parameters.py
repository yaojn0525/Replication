"""
Level 5 (valuation engine) unit tests for `RiskValParam`
(fixedincomelib/valuation/valuation_parameters.py), the new `ValuationParameters` subclass that
drives `ValuationEngineProductPortfolio.get_risk_report()`'s PORTFOLIO/PRODUCT level switch.

Follows the plain pytest-discoverable `.py` convention used for the atomic/mechanical layer of
this level (see .claude/skills/test_valuation_engine.md and
tests/test_valuation_engine_anchored_index.py) -- construction/validation/serialization
correctness against the documented contract in `ValuationParameters`/`ValuationParametersCollection`
is deterministic and needs no narrative walkthrough. There is no pre-existing dedicated test file
for `AnalyticValParam`/`FundingIndexParameter` to extend (they're only exercised inline as fixture
setup inside the product-layer notebooks) -- this file establishes that coverage for `RiskValParam`
directly off the class's own documented contract, and cross-checks the same
serialize/deserialize/collection round trip against the two existing sibling classes for
consistency.
"""

import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(".."))

import pytest

from fixedincomelib.valuation.valuation_parameters import (
    ValuationParametersBuilderRegistry,
    ValuationParametersCollection,
    AnalyticValParam,
    FundingIndexParameter,
    RiskValParam,
)


class TestRiskValParamConstruction:

    def test_default_level_is_portfolio_when_omitted(self):
        vp = RiskValParam({})
        assert vp.level == "PORTFOLIO"

    def test_explicit_portfolio_dict(self):
        vp = RiskValParam({"LEVEL": "PORTFOLIO"})
        assert vp.level == "PORTFOLIO"

    def test_explicit_product_dict(self):
        vp = RiskValParam({"LEVEL": "PRODUCT"})
        assert vp.level == "PRODUCT"

    def test_case_insensitive_input_lowercase(self):
        vp = RiskValParam({"LEVEL": "product"})
        assert vp.level == "PRODUCT"

    def test_case_insensitive_input_mixed_case_key_and_value(self):
        vp = RiskValParam({"level": "Portfolio"})
        assert vp.level == "PORTFOLIO"

    def test_list_content_form(self):
        # ValuationParameters.__init__ also accepts a list of [key, value] pairs, same as
        # AnalyticValParam/FundingIndexParameter are constructed with elsewhere.
        vp = RiskValParam([["LEVEL", "product"]])
        assert vp.level == "PRODUCT"

    def test_invalid_level_raises(self):
        with pytest.raises(Exception):
            RiskValParam({"LEVEL": "BOGUS"})

    def test_unknown_key_raises(self):
        with pytest.raises(Exception):
            RiskValParam({"NOT_A_VALID_KEY": "PORTFOLIO"})

    def test_get_valid_keys(self):
        vp = RiskValParam({})
        assert vp.get_valid_keys() == {"LEVEL"}

    def test_vp_type(self):
        vp = RiskValParam({})
        assert vp.vp_type == "RISK PARAMETER"
        assert RiskValParam._vp_type == "RISK PARAMETER"


class TestRiskValParamRegistry:

    def test_registered_under_vp_type(self):
        cls = ValuationParametersBuilderRegistry().get(RiskValParam._vp_type)
        assert cls is RiskValParam

    def test_registered_deserialize_under_des_suffix(self):
        func = ValuationParametersBuilderRegistry().get(f"{RiskValParam._vp_type}_DES")
        assert func == RiskValParam.deserialize


class TestRiskValParamSerializeRoundTrip:

    @pytest.mark.parametrize("level", ["PORTFOLIO", "PRODUCT"])
    def test_serialize_deserialize_round_trip(self, level):
        vp = RiskValParam({"LEVEL": level})
        content = vp.serialize()
        assert content["TYPE"] == "RISK PARAMETER"
        assert content["VERSION"] == RiskValParam._version
        assert content["LEVEL"] == level

        vp2 = RiskValParam.deserialize(content)
        assert vp2.level == level
        assert vp2.vp_type == vp.vp_type

    def test_registry_dispatch_deserialize(self):
        # mirrors how ValuationParametersCollection.deserialize looks the deserializer up --
        # via the registry keyed off the serialized dict's own "TYPE" entry, not by importing
        # RiskValParam.deserialize directly.
        vp = RiskValParam({"LEVEL": "PRODUCT"})
        content = vp.serialize()
        func = ValuationParametersBuilderRegistry().get(content["TYPE"])
        vp2 = func.deserialize(content)
        assert vp2.level == "PRODUCT"


class TestValuationParametersCollectionRoundTrip:

    def _build_collection(self, level="PRODUCT"):
        return ValuationParametersCollection(
            [
                RiskValParam({"LEVEL": level}),
                AnalyticValParam({"ANALYTIC": ""}),
                FundingIndexParameter(
                    {
                        "FUNDING INDEX": "",
                        "CURRENCIES": "",
                        "FUNDING INDICES": "",
                        "UNDERLYING FUNDING INDEX": "",
                    }
                ),
            ]
        )

    def test_has_vp_type_true_when_present(self):
        vpc = self._build_collection("PRODUCT")
        assert vpc.has_vp_type(RiskValParam._vp_type)
        assert vpc.has_vp_type("risk parameter")  # case-insensitive lookup

    def test_has_vp_type_false_when_absent(self):
        # this is exactly the branch ValuationEngineProductPortfolio._risk_level() relies on to
        # default to "PORTFOLIO" for any vpc that never had a RiskValParam added.
        vpc = ValuationParametersCollection([AnalyticValParam({"ANALYTIC": ""})])
        assert not vpc.has_vp_type(RiskValParam._vp_type)

    def test_get_vp_from_build_method_collection(self):
        vpc = self._build_collection("PRODUCT")
        vp = vpc.get_vp_from_build_method_collection(RiskValParam._vp_type)
        assert isinstance(vp, RiskValParam)
        assert vp.level == "PRODUCT"

    @pytest.mark.parametrize("level", ["PORTFOLIO", "PRODUCT"])
    def test_collection_serialize_deserialize_round_trip(self, level):
        vpc = self._build_collection(level)
        serialized = vpc.serialize()
        vpc2 = ValuationParametersCollection.deserialize(serialized)

        assert vpc2.has_vp_type(RiskValParam._vp_type)
        assert (
            vpc2.get_vp_from_build_method_collection(RiskValParam._vp_type).level == level
        )
        # sibling classes still round-trip correctly alongside the new one
        assert vpc2.has_vp_type(AnalyticValParam._vp_type)
        assert vpc2.has_vp_type(FundingIndexParameter._vp_type)

    def test_collection_without_risk_val_param_serialize_deserialize(self):
        vpc = ValuationParametersCollection([AnalyticValParam({"ANALYTIC": ""})])
        serialized = vpc.serialize()
        vpc2 = ValuationParametersCollection.deserialize(serialized)
        assert not vpc2.has_vp_type(RiskValParam._vp_type)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

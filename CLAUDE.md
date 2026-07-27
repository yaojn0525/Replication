# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Workflow

At the end of any session that produced a non-trivial architectural change, a bug fix, a new
convention, or a correction to this file, **update this file before ending the session**. One
paragraph or bullet list per topic — log decisions and traps, not diffs. The `## Bug Log` section
at the bottom is append-only and grouped by subsystem; everything above it is living reference
documentation and should be edited in place as the codebase evolves (stale entries corrected, not
left to rot alongside new ones).

## Commands

```bash
pip install -e ".[dev]"     # install, editable + dev deps
pytest                      # run the pytest-discoverable suite (test_*.py / *_test.py under tests/)
pytest tests/unittest_interpolator.py -q   # unittest-style suite, not auto-discovered — run explicitly
ruff check . && black . && mypy fixedincomelib
```

`tests/test_linear_product.py` currently fails to collect (`ImportError: cannot import name
'ProductZeroSpread'` — that class doesn't exist anywhere in the active codebase). Pre-existing,
unrelated to yield-curve/valuation work.

Tests must `os.chdir` into `tests/` before importing `fixedincomelib`, since `Registry` resolves
static files relative to the current working directory (see below).

## Architecture

### Import surface: what's actually live

`fixedincomelib/__init__.py` wildcard-imports only `market`, `date`, `data`, `model`, `yield_curve`,
`apis`. **`product`, `analytics`, `sabr`, and `valuation` are not re-exported at the top level** —
`product`/`analytics`/`sabr` are commented out entirely; `valuation` must be reached via explicit
submodule imports (`from fixedincomelib.valuation.valuation_parameters import
ValuationParametersCollection`). Same for `fixedincomelib.yield_curve.valuation_engine_analytics` —
it exists but isn't pulled into `yield_curve/__init__.py`, so callers import it directly.

`ValuationEngineProductRegistry` (`fixedincomelib/valuation/valuation_engine_registry.py`) — dispatch
by `(model.model_type, product.product_type, vp_type)` to a `ValuationEngineProduct` subclass, via
`ValuationEngineProductRegistry().new_valuation_engine(model, product, vpc, request)` — **is now
live**, not commented out (corrected from an earlier version of this note; re-verify against the
file before trusting either state, since this has flipped once already). Every `ValuationEngineProduct*`
class in `fixedincomelib/yield_curve/valuation_engine.py` registers itself at module load time (see
the `### Registry` block at the bottom of that file) and `ValuationEngineProductPortfolio`
(`fixedincomelib/valuation/valuation_engine_portfolio.py`) dispatches to its children through this
registry. Only product types with both a `ProductBuilderRegistry` entry (`product/product_factory.py`)
and a `ValuationEngineProductRegistry` entry are reachable generically — e.g. `DataConventionSwap`
(`"SWAP"`) has no registered `ProductBuilderRegistry` builder today, so `ProductFactory.
create_product_from_data_convention` raises `KeyError` for it despite `DataConventionSwap` itself
existing; check both registries before assuming a given data-convention/product type is usable via
generic dispatch. `ValuationEngineAnalyticIndexRegistry`, by contrast, genuinely **is** still
commented out (`yield_curve/valuation_engine_analytics.py`) — the pattern for that lower
(anchored-index) layer really is still "construct the concrete `ValuationEngineAnalytics*` subclass
directly" (e.g. `ValuationEngineAnalyticsCompoundIborIndex(model, anchored_index, vpc)`). Don't
conflate the two registries — one is live, the other isn't.

### Registry pattern (singleton)

Domain objects load once from `static_files/*` into singleton registries, keyed off `Registry`
(`fixedincomelib/utilities/utils.py`), which resolves files relative to `../static_files` from the
current working directory — hence the `os.chdir` requirement in tests.

| Registry | File | Format | Contents |
|---|---|---|---|
| `IndexRegistry` | `indices.yaml` | yaml | index objects (SOFR, SONIA, EUR-USD, …) |
| `FundingIdentifierRegistry` | `fundingidentifiers.yaml` | yaml | funding curve identifiers |
| `DataConventionRegistry` | `data_conventions.yaml` | yaml | instrument conventions (futures, swaps, IFR, xccy) |
| `IndexFixingsManager` | `config.yaml: fixing source` dir + CSVs | yaml/CSV | historical fixings per index |
| `BondSpecsRegistry` | `bond_specs.json` | json | bond specifications |

Everything migrated from `.json` to `.yaml` except `bond_specs.json` — don't assume `.json` from
older references. `Registry.__new__` defaults to `file_type='json'`; yaml registries pass
`file_type='yaml'` explicitly at construction.

`static_files/config.yaml`'s `fixing source` path is machine-local — point it at the repo's own
`fixings/` directory (or your own fixture set) rather than committing another developer's path.

`DataConventionRegistry().register(name, content)` expects the on-disk schema:
`{type: ..., convention: {...fields...}}` — the actual instrument fields must be nested under
`convention`, even when registering ad hoc conventions at runtime (e.g. in a notebook).

### Naming convention: uppercase keys everywhere

Every registry, `BuildMethod` content dict, and `Index.index_name()` normalizes keys to uppercase.
Two places this bites: (1) `Model.resolve_component_key` uppercases `Index.index_name()` lookups
but historically did *not* uppercase plain-string lookups — component storage and lookup must
agree on case, or mixed-case target names (`USD-Federal Funds-H.15-1B`) silently fail to resolve
while all-caps ones (`SOFR-1B`) work by accident. (2) `BuildMethod.build_method_["TARGET"]` must be
stored uppercase for the same reason.

### BuildMethod pattern

`BuildMethod` (`fixedincomelib/model/build_method.py`) is the abstract base for describing how to
construct a model component. `__init__` populates `build_method_` from three sources, in order:
`TARGET` (required) → `REFERENCE` (optional, present only if `has_reference()`) → per-subclass
`calibration_instruments()` keys → per-subclass `defaultable_entries` (key, default) pairs, each
seeded with its default and overridden only if the caller's content actually supplies it. All keys
are uppercase strings. `BuildMethodBuilderRegistry` dispatches construction by a string type
identifier.

Concrete types in `fixedincomelib/yield_curve/build_method.py`:

| Class | Type string | Target |
|---|---|---|
| `YieldCurveONIndexBuildMethod` | `YC_OVERNIGHT_INDEX_ELEMENT` | overnight index (SOFR, SONIA, …) |
| `YieldCurveIBORBuildMethod` | `YC_IBOR_ELEMENT` | IBOR/term index (LIBOR, term SOFR, …) |
| `YieldCurveFundingBuildMethod` | `YC_FUNDING_ELEMENT` | funding/CSA curve |
| `YieldCurveFXBuildMethod` | `YC_FX_RATE` | FX index |
| `YieldCurveBuildMethodCommon` | `YC_COMMON` | shared per-currency parameters (funding, solver) |

Every non-common/FX subclass exposes `target_index` and `reference_index` properties — both are
read unconditionally by `YieldCurveBuilder._parse_state_build_method`, so a class missing either
one breaks curve construction for that instrument type. `reference_index` resolves off the single
`"REFERENCE"` build-method key (there is no separate `"REFERENCE INDEX"` key).

### Model → YieldCurve build pipeline (state-data path)

`qfCreateModel(value_date, 'YIELD_CURVE', data_collection, build_method_collection)` →
`YieldCurveBuilder.create_model_yield_curve` (`fixedincomelib/yield_curve/model_factory.py`):

1. `_parse_state_build_method` walks the build-method collection, reading `target_index` /
   `reference_index` off each method to build a `dependency_map`, and checks every method
   calibrates off `INSTANTANEOUS FORWARD RATE`.
2. `create_yield_curve_from_state_data` calibrates each component and calls
   `set_model_component(target.upper(), component)`.
3. `set_component_dependency(dependency_map)` runs **after** step 2, never before — it populates
   `component_dependency_` / `component_order_` / `gradient_lengths_` on `YieldCurve`, and
   `_gradient_component_order()` (a DFS topological sort) iterates `self.components_`, which must
   already be populated. Both `discount_factor` (valuation path) and `get_gradient()` (risk path)
   depend on this being done once at build time, not lazily recomputed.

Calibrating a single component (`calibrate_single_component_from_state_data`) needs a business-day
convention and calendar to place tenor points on the timeline. Get these from
`build_method.target_index.payment_business_day_conv` / `.payment_holiday_conv` — **not**
`.businessDayConvention()` / `.fixingCalendar()`. See the C++-binding gotcha below.

### Anchored-index valuation analytics

`AnchoredIndex` (`fixedincomelib/market/interfaces.py`) is the base for a single accrual period
anchored to an index: `start_date`, `term_or_termination_date` (a `Date` *or* a `Period` — resolved
by the caller, not the constructor), `index`, `accrual_basis`. Concrete subclasses
(`fixedincomelib/market/anchored_index.py`):

| Class | Index | Shape |
|---|---|---|
| `AnchoredIborIndex` | IBOR/term index | single period, may be a stub/extension of the native tenor |
| `AnchoredOvernightIndex` | overnight index | single period, daily-fixed and compounded/averaged internally |
| `AnchoredCompoundIborIndex` | IBOR/term index | *n* > 1 full native-tenor periods, compounded across periods (`SPREAD_EXCLUSIVE_COMPOUND` or `FLAT_COMPOUND`) |

Each has a matching `ValuationEngineAnalytics*` (`fixedincomelib/yield_curve/valuation_engine_analytics.py`,
base class `ValuationEngineAnalyticsAnchoredIndex` in `fixedincomelib/valuation/valuation_engine.py`).
All three split `.value` into `.value_h` (realized, off historical fixings via `IndexFixingsManager`)
and `.value_f` (forward, curve-implied via `model.discount_factor(..., calc_grad=True)`), combined as
`((1 + tau_h*value_h)(1 + tau_f*value_f) - 1) / tau`. `.value` carries a live torch autograd graph
end to end when any leg is forward-looking — call `.backward()` then `model.get_gradient()`.

Construct engines directly (no registry dispatch — see above): `ValuationEngineAnalyticsIborIndex(model,
anchored_index, valuation_parameters_collection)`, etc. Each constructor asserts the anchored
index's exact type, so don't pass e.g. an `AnchoredOvernightIndex` to the IBOR engine.

### Convention factories are `.new(...)`, not constructors

`BusinessDayConvention`, `HolidayConvention`, `AccrualBasis` (`fixedincomelib/market/basics.py`) are
plain classes with a `.new(str) -> ql object` classmethod and no `__init__` accepting a string —
`BusinessDayConvention("F")` raises `TypeError: ... takes no arguments`. Always call
`BusinessDayConvention.new("F")`. This is deliberate (raised and confirmed in review) — don't add
`__new__`/`__call__` sugar to make the bare constructor work; keep the factory-method convention
explicit. `AccrualBasis.new(...)` keys are long-form (`"ACTUAL/ACTUAL (ISMA)"`, `"ACTUAL/360"`) —
there is no `"ACT/ACT"` short alias, and none should be added.

### Custom index wrappers don't back a real QuantLib object

`IBORIndex` / `OvernightIndex` (`fixedincomelib/market/indices.py`) subclass `ql.IborIndex` /
`ql.OvernightIndex` for typing, but their `__init__` only ever calls `Index.__init__` (the
plain-Python mixin) — **never** the QuantLib base constructor. Any inherited native QuantLib method
that needs real C++ state (`.businessDayConvention()`, `.fixingCalendar()`, `.tenor()`, …) raises a
SWIG `TypeError` if called. Use the Python-level equivalents these classes actually define instead:

| Instead of | Use |
|---|---|
| `.businessDayConvention()` | `.payment_business_day_conv` |
| `.fixingCalendar()` | `.payment_holiday_conv` |
| `.tenor()` | `.term` |

For a `FundingIdentifier` (which wraps an underlying index rather than being one), go through
`.base_index` first.

### Public API (`qf`-prefixed functions)

User-facing functions live in `fixedincomelib/apis/` and are re-exported from
`fixedincomelib/__init__.py`. Key entry points: `qfCreateBuildMethod`, `qfCreateModelBuildMethodCollection`,
`qfCreateModel`, `qfDiscountFactor`, `qfCreateData1D` / `qfCreateDataCollection`,
`qfWriteBuildMethodToFile` / `qfReadBuildMethodFromFile` (pickle round-trip), date utilities in
`apis/date.py`, index/convention queries in `apis/index_and_conventions.py`.

### Archived vs. active code

`*/archived/` subdirectories hold legacy implementations (products, valuation engines, SABR models,
yield curve solvers). The active codebase is whatever a module's `__init__.py` actually imports —
per the import-surface note above, that's a strictly smaller set than "everything not in
`archived/`". When extending the library, add to the active layer and register new types in the
relevant registry.

### Interpolator (torch autograd)

`Interpolator1D` / `Interpolator2D` (`fixedincomelib/utilities/numerics.py`) use PyTorch autograd
instead of hand-coded gradient loops. `interpolate` / `integrate` take `calc_grad: bool = False`; when
`True`, values are wrapped in a `torch.tensor(..., requires_grad=True)` (`self._values_tensor`) and
the method returns a differentiable torch scalar. Concrete gradient methods call the forward pass
with `calc_grad=True`, invoke `.backward()`, and read `self._values_tensor.grad`.

```python
v = interp.interpolate(x)                                    # float
t = interp.interpolate(x, calc_grad=True)                     # torch.Tensor, differentiable
g = interp.gradient_wrt_ordinate(x, convert_to_numpy=True)    # np.ndarray
```

### DataConvention index return types

`IndexRegistry().get(...)` returns the common `Index` base; both overnight and IBOR indices inherit
from it. Type convention properties as `Index` unless the caller genuinely needs a subtype — e.g.
`DataConventionOvernightIndexBasisSwap.index_1`/`index_2` are both typed `Index` even though one is
an overnight index and the other IBOR.

### `ValuationEngineProduct` on top of the torch-autograd anchored-index engines

`ValuationEngineProductOvernightIndexFuture` (`fixedincomelib/yield_curve/valuation_engine.py`) is
the first live (non-archived, non-stub) `ValuationEngineProduct` built directly on the torch-based
anchored-index engines rather than the old numpy `calculate_risk`/`resize_gradient` path — a
pattern worth reusing for the next product engine. It was later rewritten to wrap
`ValuationEngineProductOvernightIndexCompositeCashflow` instead of building its own
`AnchoredOvernightIndex`/`ValuationEngineAnalyticsCompositeIndex` pair by hand — this works because
`ProductOvernightIndexFuture` *is itself* a `ProductOvernightIndexCompositeCashflow` (`pay_or_rec
=RECEIVE`, `spread=0.`, `leverage=1.`, see its constructor in `product/linear_products.py`), so the
future's own `product` object can be passed straight through as the composite-cashflow engine's
`product` argument. Only `forward_rate_` off the wrapped engine is used — the future's `.value_`
(`notional * (F - K)`, undiscounted, since a margined instrument isn't present-valued) and `.cash_`
(daily variation margin) are computed independently on top, same as before. Two consequences of the
reuse worth flagging: (1) it pulls the compounding business-day-convention/calendar from
`on_composite_index.business_day_conv`/`.payment_holiday_conv` (the *index's* own convention) rather
than the product's `payment_business_day_convention`/`payment_holiday_convention` the hand-rolled
version used — a deliberate behavior change, and arguably more correct (one source of truth for
compounding conventions, matching how a swap's floating leg already does it), but worth knowing if a
future's price shifts slightly after this rewrite; (2) constructing
`ValuationEngineProductOvernightIndexCompositeCashflow` unconditionally asserts a
`FundingIndexParameter` is present in the vpc (even though the future never uses its discounted
value) — futures now require a funding parameter for their currency that they didn't strictly need
before. The original from-scratch pattern below is still accurate at the
`ValuationEngineAnalytics*` layer (that's exactly what the composite-cashflow engine builds
internally) — just no longer duplicated at the product-engine layer for the future specifically:

- Build one `AnchoredOvernightIndex`/`AnchoredIborIndex`/`AnchoredCompoundIborIndex` (whichever
  fits) plus its matching `ValuationEngineAnalytics*` once in `__init__`, off the product's own
  dates/conventions/index. `calculate_value` just calls `.calculate_value()` on it and reads
  `.value` — a plain float once matured, a live torch tensor (with `requires_grad=True`) whenever
  any part of the accrual period is still forward-looking.
- **First-order risk is `value_.backward(scaler_tensor, retain_graph=True)` then
  `model_.get_gradient(reset=True)`** — not `model_.resize_gradient(...)` /
  `index_engine_.calculate_risk(...)` (that numpy-list path belongs to the archived engines only;
  the modern anchored-index engines' own `calculate_risk` is a literal `pass`). `retain_graph=True`
  is required on every internal `.backward()`/`torch.autograd.grad(...)` call in a product engine
  if more than one of `calculate_first_order_risk` / `grad_at_par` / `pv01` might read the same
  underlying graph later — the first `.backward()` without it frees the graph and the second raises
  `RuntimeError: Trying to backward through the graph a second time`.
- A par-rate instrument's `grad_at_par` should differentiate the *par rate itself* (e.g.
  `forward_rate_`), not the product's PV — no need to re-derive the old price-space `-100.0` scaler
  from the archived engines, since the new convention keeps par quantities in rate space throughout.
- For a PV that's an exact affine function of one underlying rate (`PV = notional * (F - K)`),
  `pv01()` can still go through `torch.autograd.grad(value_, forward_rate_, retain_graph=True)`
  rather than hardcoding `notional * 1e-4` — cheap, and stays correct automatically if the PV
  formula changes — but must fall back to the closed form once `forward_rate_` has no live graph
  (fully matured trade, nothing left to differentiate).
- Mark-to-market cash (for a margined instrument like a future, cash realized daily as
  `notional * (today's price - yesterday's)` up to and including the payment date): the anchored
  index engines take their `value_date_` from `model.value_date` only once, at construction
  (`ValuationEngineAnalytics.__init__`), and never re-read it from the model afterwards — so
  "yesterday's" market-implied rate can be obtained by building a second engine instance against
  the *same* model/curve and directly overwriting its `.value_date_` attribute to one business day
  earlier, without needing a second curve build. This only reprices the known-vs-forward fixing
  cutoff a day earlier on today's curve, not a true historical curve snapshot — the best available
  proxy given the codebase keeps no time series of prior curve builds. Since the rewrite, this
  attribute lives one layer deeper than it looks: build a second
  `ValuationEngineProductOvernightIndexCompositeCashflow` and overwrite *its*
  `index_engine_.value_date_` (the nested `ValuationEngineAnalyticsCompositeIndex`'s own
  attribute) — overwriting the outer product-engine's `.value_date_` instead is a no-op for this
  purpose, since that outer attribute only gates its own (here-unused, since the future never reads
  the wrapped engine's `.value_`/`.cash_`) discounting branch.

`ValuationEngineProductFRAOrFixing` follows the same base pattern but is a discounted single
cashflow rather than a margined instrument, which changes a few things:
- It's *the* first engine in this file that needs `FundingIndexParameter` from the vpc (the future
  skips discounting entirely — MTM instruments don't need it). Discounting uses
  `model_.discount_factor(funding_index, payment_date_, calc_grad=True)`, so curve risk flows
  through both the projection leg (`forward_rate_`) and the discounting leg in one `value_.backward()`
  — no need to handle them separately.
- `ProductFRAOrFixing` covers two distinct payoff shapes off one `payment_date_ vs
  termination_date_` comparison, driven entirely by what `pay_date_or_offset` the caller passed in
  (there's no separate boolean field): if `payment_date_ < termination_date_` it's a *true* FRA,
  settling early with the standard ISDA `1 / (1 + F*tau)` early-settlement discount factor (`F` =
  the floating rate); if they're equal (the default — `pay_date_or_offset` defaults to
  `TermOrDate("0D")`, which resolves to `termination_date_`), it's a plain fixing/coupon cashflow
  with no such adjustment. **Only ISDA discounting is implemented** — `__init__` asserts
  `product.fra_discounting_style.upper() == "ISDA"` (AFMA, which discounts at the fixed coupon
  instead of the floating rate, isn't needed yet; `qfCreateProductFRA` already only ever produces
  ISDA FRAs, so this doesn't constrain any live call path). Don't re-add an AFMA branch without
  being asked — if it's needed later, the discount factor is `1 / (1 + coupon_*tau)` instead of
  `1 / (1 + forward_rate_*tau)`.
- Picks `AnchoredOvernightIndex` + `ValuationEngineAnalyticsCompositeIndex` by hand for the ON
  branch (`product.is_on` — `ProductCashflow` already derives this from
  `isinstance(index_, OvernightIndex)`), since `ProductFRAOrFixing.index` can be either an
  `OvernightIndex` or an `IBORIndex`. For the IBOR branch, though,
  `ProductFRAOrFixing` *is* a `ProductIBORIndexCashflow` (its base class), so its own `product`
  object is handed straight to `ValuationEngineProductIBORIndexCashflow` instead of re-deriving an
  `AnchoredIborIndex`/`ValuationEngineAnalyticsIborIndex` pair by hand — same reuse pattern as
  `ValuationEngineProductOvernightIndexFuture` wrapping
  `ValuationEngineProductOvernightIndexCompositeCashflow`. Only the wrapped engine's
  `forward_rate_` is read; its own discounted `.value_`/`.cash_` are ignored in favor of the FRA's
  early-settlement-adjusted discounting above. Unlike the future's rewrite, this introduces **no**
  behavior change: `ProductFRAOrFixing.__init__` already sets
  `payment_business_day_convention`/`payment_holiday_convention` straight from
  `index.payment_business_day_conv`/`index.payment_holiday_conv`, the same source
  `ValuationEngineProductIBORIndexCashflow` itself reads — so there was no product-level-vs-
  index-level convention mismatch to worry about here (unlike the OI future, where the two sources
  actually differ). The ON branch has no equivalent natural reuse target: `ProductFRAOrFixing`
  only carries a raw `OvernightIndex` there, not an `OvernightCompositeIndex`, so there's no
  product-level composite-cashflow object to delegate to without first constructing a synthetic one
  — judged not worth the indirection, so that branch is left building
  `AnchoredOvernightIndex`/`ValuationEngineAnalyticsCompositeIndex` by hand.
- `ValuationEngineProductCashDeposit` has no index at all (see further below) and nothing
  analogous to reuse from either the future or FRA rewrites — reviewed, no change needed there.
- `pv01()`/`grad_at_par()` fall back to `0.0`/`get_gradient(reset=False)` (not a nonzero closed
  form) once `forward_rate_` has no live graph, unlike the future — here PV is *not* affine in `F`
  once the FRA early-settlement adjustment is in play, and a fully-realized (historical-fixing) FRA
  has no live rate to be sensitive to in the first place.

`ValuationEngineProductCashDeposit` has no index at all (`ProductCashDeposit` is a pure fixed
cashflow), so it's the simplest of the three and structurally different: no anchored-index engine,
its only curve dependency is the funding/discount curve. It's the classic money-market
two-leg par condition, not a single settlement like the future/FRA: `PV = sign * (notional * (1 +
coupon*tau) * DF(payment_date) - notional * DF(effective_date))`. The funding (principal) leg only
enters PV while `value_date_ < effective_date_` (forward-starting deposit) — once the deposit has
actually started, that principal exchange is sunk and drops out of a forward PV. `par_rate_or_spread`
is the curve-implied simple rate that zeros this two-leg PV, `(DF(effective)/DF(payment) -
1)/tau` — not read off an anchored-index engine's `.value` like the other two, since there isn't
one. `pv01()` is a closed form (`sign * notional * tau * DF(payment) * 1e-4`), not an autograd
call, because `coupon_` is a plain Python float that's never wrapped in a tensor here — there's no
graph node to differentiate through at all, unlike the future/FRA where the differentiated
quantity (`forward_rate_`) is itself curve-implied and lives in the graph.

`ValuationEngineProductOvernightIndexCompositeCashflow` prices a single
`ProductOvernightIndexCompositeCashflow` leg (the building block a floating leg of an
overnight-index swap is made of) — structurally the overnight-index analogue of
`ValuationEngineProductFRAOrFixing`'s plain-cashflow branch: one `AnchoredOvernightIndex` +
`ValuationEngineAnalyticsCompositeIndex`, discounted once off `FundingIndexParameter` at
`payment_date_`, payoff `sign * notional * tau * (forward_rate_ + spread)`. `par_rate_or_spread()`
returns `forward_rate_` (the raw compounded rate, not a rate net of `spread`) and `pv01()`/
`grad_at_par()` are exact closed forms off `forward_rate_`'s graph, same pattern as the FRA.

`ValuationEngineProductOvernightIndexSwap` (`fixedincomelib/yield_curve/valuation_engine.py`) is the
first engine to wrap two whole legs (`ProductInterestRateStream`) rather than one atomic cashflow —
the pattern reused for `ValuationEngineProductOvernightIndexBasisSwap` and
`ValuationEngineProductOISBasisSwap` right below it (see further down), all three living in the same
file in that order:
- `ProductOvernightIndexSwap.fixed_leg`/`.floating_leg` already carry opposite `pay_or_rec` (the
  floating leg is built with `PayOrReceive.reverse(pay_or_rec)` — see the product constructor), and
  each underlying per-period cashflow engine's own `sign_` is derived from its leg's `pay_or_rec`.
  That means the two leg engines' `.value_`/`.cash_` are **already sign-consistent** and can just be
  added (`fixed_leg_engine_.value_ + floating_leg_engine_.value_`) — no separate
  `fixed_leg_sign_`/`floating_leg_sign_` multiplication on top, unlike the archived numpy-risk
  `ValuationEngineProductRfrSwap` (`yield_curve/archived/valuation_engine.py`), which needed that
  extra sign layer because its leg engine wasn't leg-direction-aware on its own.
- Each leg is built as a `ValuationEngineProductInterestRateStream` directly (constructed in
  `__init__` off `product.fixed_leg`/`product.floating_leg`), not via
  `ValuationEngineProductRegistry().new_valuation_engine(...)` — `ProductOvernightIndexSwap` itself
  isn't a `ProductPortfolio` (no `.elements_`), so it can't inherit `ValuationEngineProductPortfolio`
  the way `ValuationEngineProductInterestRateStream` does; it's a plain `ValuationEngineProduct`
  holding two named sub-engines instead of a list.
- **Risk**: `get_risk` is overridden (not left to the base class's single-tensor autograd default)
  because `value_` is a Python-float/tensor sum whose two addends' graphs are independently owned by
  each leg engine — accumulate via `leg_engine.get_risk(gradient=leg_grad)` into a shared
  `np.zeros_like(...)` array per leg, same idiom `ValuationEngineProductPortfolio.get_risk` already
  uses for N children, just unrolled for 2 named legs instead of a loop over `self.engines_`.
- **Par rate**: since the floating leg carries no dependency on the fixed rate (`spread=0` on the
  floating leg, coupon lives only on the fixed leg), swap PV is exactly affine in `fixed_rate`:
  `PV(fixed_rate) = floating_leg.value_ + fixed_rate * fixed_leg_engine_.annuity_` (the fixed leg's
  own `annuity_`, as already computed by `ValuationEngineProductInterestRateStream.calculate_value`,
  is precisely `d(PV_fixed_leg)/d(fixed_rate)`). Solving `PV(par) = 0` gives
  `par_rate_or_spread() = fixed_rate_ - value_ / fixed_leg_engine_.annuity_` — same
  `rate - value/annuity` identity `ValuationEngineProductInterestRateStream.par_rate_or_spread` uses
  for a single leg, just applied against the swap's total (both-legs) PV. `pv01()` is
  `fixed_leg_engine_.annuity_ * 1e-4`, again reusing the fixed leg's own annuity rather than
  re-deriving one at the swap level. Verified end to end against a synthetic flat SOFR curve: PV at
  the computed `par_rate_or_spread()` is ~1e-11 (zero to floating-point precision). No
  `grad_at_par()` — not needed for a swap used as a valuation target rather than a calibration
  instrument.

`ValuationEngineProductOvernightIndexBasisSwap` is the float-vs-float sibling, immediately below the
fixed-vs-float engine in the same file — `ProductOvernightIndexBasisSwap.on_composite_index_leg`
(ON composite, carries the quoted `spread`) vs. `.ibor_index_leg` (IBOR, `fixed_rate_or_spread=0.`,
`leverage=1.`, see the product constructor). Structurally identical wrap-two-
`ValuationEngineProductInterestRateStream`-legs pattern, with one substitution: there's no "fixed
leg" here, so the **on-composite leg stands in for it** in the par/pv01 math, because it's the only
leg whose payoff depends on the quantity being solved for (the spread). This works because
`ValuationEngineProductOvernightIndexCompositeCashflow`'s payoff,
`sign * notional * tau * (leverage * forward_rate + spread)`, has `spread` entering with exactly the
same coefficient shape (`sign * notional * tau`, then `* df`) that `ValuationEngineProductFixedAccrued`
gives `coupon` — so `ValuationEngineProductInterestRateStream.annuity_` (generic across whichever
atomic engine type populates `self.engines_`) is `d(PV_on_leg)/d(spread)` on the on-composite leg
exactly as it was `d(PV_fixed_leg)/d(fixed_rate)` on the fixed leg. `par_rate_or_spread()` and
`pv01()` are therefore the same two formulas as the fixed-vs-float engine, verbatim, with
`fixed_rate_`/`fixed_leg_engine_` swapped for `spread_`/`on_leg_engine_`. `get_risk` and
`create_cash_flows_report` follow the identical two-leg-accumulation shape. Verified end to end
against a synthetic SOFR + flat-LIBOR-3M curve (quarterly accrual, 2Y, 8 periods/leg): PV at the
computed `par_rate_or_spread()` is exactly `0.`, and `get_risk` produces nonzero gradient entries
across all three curve components (SOFR-1B, SOFR-1B-FLAT, LIBOR-3M).

`ValuationEngineProductOISBasisSwap` is float-vs-float again, but both legs are overnight composite
indices this time — `ProductOISBasisSwap.basis_leg` (carries the quoted `spread`) vs.
`.reference_leg` (`fixed_rate_or_spread=0.`). Identical to
`ValuationEngineProductOvernightIndexBasisSwap` in every respect except naming
(`basis_leg`/`reference_leg` in place of `on_composite_index_leg`/`ibor_index_leg`,
`basis_leg_engine_`/`reference_leg_engine_` in place of `on_leg_engine_`/`ibor_leg_engine_`) — the
basis leg stands in for the "fixed leg" in the `par_rate_or_spread()`/`pv01()` formulas for the same
reason (it's the only leg whose payoff depends on `spread`), since both legs are
`ValuationEngineProductOvernightIndexCompositeCashflow`-backed and the annuity/coefficient argument
doesn't care which atomic engine type populates `self.engines_`. Verified end to end against a
synthetic SOFR + flat-Fed-Funds curve (quarterly, 2Y, 8 periods/leg, basis leg = SOFR compound pay,
reference leg = Fed Funds compound receive): PV at the computed `par_rate_or_spread()` is ~1e-11
(zero to floating-point precision), `get_risk` produces nonzero gradients across all three curve
components (SOFR-1B, SOFR-1B-FLAT, USD-FEDERAL FUNDS-H.15-1B).

`ValuationEngineProductGenericSpread` prices `ProductGenericSpread` — a spread between a "target"/basis
instrument T (`product.basis_data_convention`) and a "reference" instrument R
(`product.reference_data_convention`), where T and R can be *any* two data-convention-driven
instrument types (a swap vs. a deposit, a FRA vs. an OIS, ...), not just two legs of one known
product shape. This is architecturally different from every engine above it in the file: those all
combine legs that are already the *same* atomic-cashflow-engine family (so their PVs can just be
summed on one shared torch graph); a generic spread's T and R may go through entirely unrelated
`ValuationEngineProduct` subclasses with no common graph to sum. It follows the Felix model doc's
"generic spread" construction (RBC internal model doc §6.4.9, provided by the user as reference,
not checked into the repo): T is assumed coupon 0, R is assumed coupon `-spread`, T and R pay
opposite sides (`ProductFactory.create_generic_spread` already encodes basis=target/T,
reference=R), R's notional stands for 1 unit of the trade (scaled by `product.notional`), and T's
notional is implicitly DV01-matched to R via `PV01_r/PV01_t`.
1. Builds T (coupon `0.`) and R (coupon `-product.spread`) as real `Product` instances via
   `ProductFactory.create_product_from_data_convention`, over the trade's own
   `effective_date`/`termination_date` expressed as an explicit `"YYYY-MM-DD x YYYY-MM-DD"` axis1
   string — this bypasses each data convention's own settlement-offset resolution (see
   `_tokenize_axis1`'s cross-axis branch), so the trade's actual schedule gets priced rather than a
   re-derived tenor. Neither build passes a `pay_or_rec` kwarg, so both build under whichever side
   that data convention's factory method defaults to (every one checked in this file defaults to
   `"receive"`) — T and R therefore land on the *same* side; the opposite-sides relationship from doc
   assumption 3 is instead encoded as a minus sign in the PV formula, not a build-time difference.
2. Dispatches both through `ValuationEngineProductRegistry().new_valuation_engine(...)` — meaning a
   generic spread can only be built from data conventions whose product type has both a
   `ProductBuilderRegistry` entry and a `ValuationEngineProductRegistry` entry (see the import-surface
   note above for a concrete gap: plain `DataConventionSwap` has neither wired up as of this writing).
3. Reads each engine's **raw `.value`/`.pv01()` directly** — deliberately *not* each engine's
   `par_rate_or_spread()` — and combines them as
   `value_ = sign * scale * Fx * (R.value - ratio * T.value)`, where `scale = notional /
   reference_built_notional` (projects R's own natural build notional onto "R notional = 1 unit of
   this trade"), `ratio = R.pv01() / T.pv01()` (a plain float ratio of the two engines' own reported
   PV01s — this *is* the `PV01_r/PV01_t` DV01-matching ratio; it needs no separate per-unit
   normalization since both PV01s already come from the same `.pv01()` contract), and `Fx` converts
   R's currency into `product.currency`. `sign` comes from `product.pay_or_rec`. This works because
   PV(coupon) is affine in an engine's own coupon for every linear-rate engine in this file, so T's
   DV01-matched contribution reduces to exactly `ratio * T.value` with no need to ever recover `p_t`
   separately — and since R is already built at the real coupon `-spread`, `p_r` and `spread` never
   need to be extracted either; `spread` only enters via the coupon R was built at. The minus sign in
   front of `ratio * T.value` is what encodes T and R being on opposite sides (see point 1). A single
   `Fx = fx(reference_ccy -> product.currency)` factor covers *both* legs' currency conversion — but
   only because `__init__` now asserts `target_currency_.code() == reference_currency_.code()`
   (`self.target_currency_ = target_product.currency`, captured but otherwise unused besides this
   check). Without that assertion this is **not** a general FX triangulation: `ratio = R.pv01() /
   T.pv01()` is a bare division of two PV01s with no FX adjustment between T's and R's own
   currencies, so if they ever differed, `ratio * T.value` would carry an un-corrected T-ccy/R-ccy
   quantity that the single R-ccy-based `Fx` factor would not fix. Asserting same-currency (rather
   than adding a real T-ccy -> R-ccy conversion into `ratio` itself) was the chosen fix, raised and
   confirmed in review, since nothing in this codebase currently needs a genuinely
   cross-currency generic spread — fail loudly instead of silently mispricing one. Old version of
   this engine computed `p_t`, `p_r` via `par_rate_or_spread()` and
   combined them with `spread` explicitly instead; this formulation is mathematically identical
   (cross-checked to agree to float precision on the same fixture, see below) but reads more directly
   off what every `ValuationEngineProduct` already reports (`.value`/`.pv01()`), rather than trusting
   each engine's own possibly-bespoke `par_rate_or_spread()` implementation.
- **This makes `value_` a plain Python float, not a live torch tensor** — `.value`/`.pv01()` are read
  and combined via plain-float `ratio`/`scale`/`Fx` multipliers, which detaches the result even
  though `.value` itself is a live tensor on each sub-engine. There is therefore no autograd graph to
  chain through T's and R's own curve sensitivity. `get_risk()` is deliberately left at the
  `ValuationEngineProduct` default rather than overridden with a fake implementation — since
  `value_` isn't a tensor, that default skips `.backward()` and returns whatever's already on the
  model's gradient accumulator. **Curve risk for a generic spread is not currently supported**, only
  PV/par-rate/pv01 reporting; a real implementation would need a `grad_at_par()`-style live-graph par
  rate (or a live-graph `.value`/`.pv01()` combination) on every engine T/R might resolve to, which
  nothing in this codebase provides yet (the one sketch of it, on
  `ValuationEngineProductInterestRateStream`, is itself commented out).
- `par_rate_or_spread()`/`pv01()` on the generic-spread engine itself follow the same `rate -
  value/sensitivity` idiom as the other spread/basis engines in this file
  (`spread_ - value_/spread_pv01_unit_`, `spread_pv01_unit_*1e-4`), with `spread_pv01_unit_ =
  -sign_*scale_*fx_*reference_pv01_raw/1e-4` derived from `d(value_)/d(spread_)` (only R's build
  coupon depends on `spread_`) — named `spread_pv01_unit_` rather than `annuity_` (the name every
  sibling engine uses for this same slot) because it isn't a discounted-cashflow-sum annuity the
  way e.g. `ValuationEngineProductInterestRateStream.annuity_` is; it's R's own `pv01()` rescaled
  onto the spread axis by `sign_`/`scale_`/`fx_`. Renamed from an initial `annuity_` at the user's
  request once this distinction was raised.
- Verified end to end against a synthetic SOFR-1B / USD-Federal-Funds-H.15-1B curve, spreading
  `USD-SOFR-OIS` (target) against `USD-OIS` (reference, Fed Funds) over 5Y: `target_engine_.
  par_rate_or_spread()` matched a standalone `ValuationEngineProductOvernightIndexSwap` built off the
  same convention/dates exactly; PV at the computed `par_rate_or_spread()` was exactly `0.`; the two
  `create_cash_flows_report()` rows summed to `value_` exactly; and this PV/PV01-based formulation's
  `value_`/`pv01()`/`par_rate_or_spread()` matched the earlier par-rate-based formulation to float
  precision on the same fixture.

`ValuationEngineProductGenericForward` prices `ProductGenericForward` — an implied-forward instrument:
`PV = sign * notional * (F - K) * tau * DF_funding(payment_date)`, where `F` is the curve-implied
forward rate of `product.index` over `[effective_date, termination_date]`, read directly off the
ratio of that index's own discount factors at the two dates rather than through an
`AnchoredIborIndex`/`AnchoredOvernightIndex` + `ValuationEngineAnalytics*` pair the way every other
forward-rate-driven engine in this file is — a "generic forward" isn't anchored to any particular
index's own native accrual/compounding convention, it just reads whatever `product.index` resolves
to on the model (IBOR, overnight, or a `FundingIdentifier` all work, since `discount_factor()`
dispatches on the component itself, not on the caller's assumptions about its type):
- `simple`:     `F = (DF(effective)/DF(termination) - 1) / tau`
- `continuous`: `F = ln(DF(effective)/DF(termination)) / tau`, via `torch.log` on the graph-connected
  discount-factor ratio (both `discount_factor(...)` calls use `calc_grad=True`, per the shared-state
  footgun below).
`K = product.coupon`, `tau = accrued(effective_date, termination_date, product.accrual_basis,
product.business_day_convention, product.holiday_convention)` — `ProductGenericForward` has no stored
`.accrued` property (unlike `ProductFixedAccrued`/`ProductCashDeposit`), so the engine computes it once
in `__init__`. `payment_date_` (`product.pay_date`) defaults to `termination_date_`
(`pay_date_or_offset` defaults to `TermOrDate("0D")`), matching the `PV = (F-K)*tau*N*P(0,T_e)`
shorthand where `T_e` is the forward's own termination date — discounting is off the funding curve
(`FundingIndexParameter`) at `payment_date_`, not `product.index` itself, consistent with every other
atomic cashflow engine in this file (the funding curve and the projection index are independent
curve components in this multi-curve setup). Because the funding discount factor doesn't depend on
`F` (unlike the FRA's early-settlement discount factor, which is itself a function of the forward
rate being discounted), PV is exactly affine in `F`, so `pv01()` is a closed form
(`sign*notional*tau*df*1e-4`), no `torch.autograd.grad` needed — simpler than
`ValuationEngineProductFRAOrFixing.pv01()`, which does need autograd for that reason.
- Verified end to end against the same synthetic SOFR-1B curve fixture used elsewhere in this file:
  for both `SIMPLE` and `CONTINUOUS` compounding, the engine's `forward_rate_` and `value_` matched an
  independent closed-form computation (discount factors read with `calc_grad=False`, forward rate
  derived the same way, `PV = notional*(F-K)*tau*DF_funding(pay_date)`) to float precision; `pv01()`
  was identical across both compounding methods on the same trade (expected, since it doesn't depend
  on how `F` was derived, only on `d(value_)/dF`).
- **Found, not fixed, while building this fixture** (status since re-verified — `ProductGenericForward`
  has since been fixed; the other two have not, so don't assume all three still share this bug):
  `ProductGenericForward.__init__` originally set `self.termination_date_ = None` and only overwrote
  it `if self.term_or_termination_date_.is_term(): ...`, with no `else` branch to set it from
  `self.term_or_termination_date_.get_date()` when the caller passes an explicit `Date` instead of a
  `Period`/tenor string — this has since been fixed (an `else` branch was added). `ProductGenericSpread.__init__`
  and `ProductGenericForwardSpread.__init__` (`fixedincomelib/product/linear_products.py`) still have
  the original bug, unfixed as of this writing. Constructing either of those two with an explicit
  termination date (e.g. `TermOrDate(some_date)`) silently leaves `termination_date_`/`pay_date_`/
  `last_date_` as `None`, then fails downstream with a confusing SWIG `TypeError` out of
  `Calendar.advance(None, ...)` the first time something tries to `add_period` off it — not a
  `None`-specific error message, so it's easy to misdiagnose as something else. Both remaining product
  classes work fine when `term_or_termination_date` is a term/tenor (the common case, and the only form
  exercised by either engine's own smoke test); flagged here rather than fixed since it's a
  product-layer bug, not part of the valuation-engine work that surfaced it.

`ValuationEngineProductGenericForwardSpread` prices `ProductGenericForwardSpread` — a spread between
two *implied forward rates* (`product.basis_index` vs `product.reference_index`) over the same
`[effective_date, termination_date]` period, rather than between two arbitrary data-convention
products. It subclasses `ValuationEngineProductGenericSpread` and reuses that class's
`calculate_value`/`par_rate_or_spread`/`pv01`/`get_value_and_cash`/`_fx_rate` **unchanged** — only
`__init__` and `create_cash_flows_report` are overridden. The reuse works because both classes reduce
to the identical shape (`self.target_engine_`/`self.reference_engine_`, each exposing `.value`/
`.pv01()`/`.cash`, combined via `sign_*scale_*fx_*(reference - ratio*target)`); what differs is only
how the two leg engines get built:
- `__init__` calls `ValuationEngineProduct.__init__(...)` directly (skipping
  `ValuationEngineProductGenericSpread.__init__`, which expects `product.basis_data_convention`/
  `.reference_data_convention` — attributes `ProductGenericForwardSpread` doesn't have), then builds
  the basis leg (target) and reference leg as two `ProductGenericForward` instances directly — basis
  leg at coupon `0.` off `basis_index`, reference leg at coupon `-spread` off `reference_index`, same
  target/reference role assignment as the data-convention `ValuationEngineProductGenericSpread`. Both
  legs share `product.effective_date`/`product.termination_date` (passed as an explicit
  `TermOrDate(product.termination_date)`, not re-derived from a tenor — `ProductGenericForward` now
  handles this correctly per the fixed bug above), `product.notional`, and every settlement/payment
  convention off the parent `ProductGenericForwardSpread`, and are both built `pay_or_rec=RECEIVE`
  (the opposite-sides relationship is encoded in the combination formula's sign, not the build side —
  same convention as the data-convention case). Each leg gets its own accrual basis: the basis leg
  uses `product.accrual_basis`, the reference leg uses `product.reference_leg_accrual_basis` if given,
  else falls back to `product.accrual_basis` too.
- Because both legs are built on the *same* notional (`product.notional`, not a separately-derived
  data-convention notional), `reference_notional_ == notional_` always, so `scale_` is always `1.`.
  Currency, though, is **not** forced to `product.currency` on either leg — each is built with its own
  index's native currency (`currency=product.basis_index.currency` / `product.reference_index.currency`,
  both `@property`), mirroring how `ValuationEngineProductGenericSpread`'s target/reference each carry
  whatever currency their own data convention produces, rather than the trade's currency. `fx_` is
  therefore `1.` only when `basis_index`/`reference_index` share a currency (the common case — e.g.
  SOFR vs Fed Funds, both USD), not unconditionally; the same `target_currency_ ==
  reference_currency_` assertion added to `ValuationEngineProductGenericSpread.__init__` (see above) is
  duplicated here rather than inherited, since this subclass builds its legs in its own `__init__`
  without calling the parent's. `ratio_` (`reference.pv01()/target.pv01()`) is not always `1.` either —
  it only collapses to `1.` when both legs share the same accrual basis and discounting, since
  `reference_leg_accrual_basis` can differ from `accrual_basis` and each leg's own `tau_` (hence its
  `pv01()`) is computed independently even though notional/pay_date/discounting are shared.
- `create_cash_flows_report()` is overridden on this subclass directly (the same "contribution" idiom
  originally written for `ValuationEngineProductGenericSpread` — see the fix described earlier in this
  file for that class's `create_cash_flows_report`), pulling `PRODUCT_TYPE`/`VALUATION_ENGINE_TYPE`
  from each leg's own `target_engine_.product_`/`reference_engine_.product_`, not the wrapper's own
  type, and using `self.product_.pay_date` (not `.termination_date`) as the reported pay date, since a
  `ProductGenericForwardSpread` can have a `pay_date_or_offset` distinct from its termination date.
- Verified end to end against the same synthetic SOFR-1B / USD-Federal-Funds-H.15-1B curve fixture
  used elsewhere in this file, spreading SOFR (basis) against Fed Funds (reference) over 2Y,
  `CONTINUOUS` compounding, `spread=0.0010`: `engine.value` matched an independent closed-form
  `sign*notional*tau_ref*df*((F_ref+spread) - ratio*F_basis)` computation to float precision (with
  `ratio_ == 1.` on this fixture, since both legs shared the default accrual basis and discounting);
  the two `create_cash_flows_report()` rows summed to `value_` exactly.

`ValuationEngineProductZeroSpread` prices `ProductIBORZeroSpread` — a bilateral outright struck at a
continuously-compounded zero-rate spread between two curve components, `basis_index` (the curve the
spread is quoted against, e.g. an IBOR curve) and `reference_index` (the base/discounting curve,
e.g. that currency's OIS curve): `PV = sign * notional * (DF_reference(T)/DF_basis(T) -
exp(-spread*T))`, `T = accrued(value_date, termination_date)` (default ACT/ACT (ISDA), no
accrual-basis field on the product). This is a straight port of the archived
`ValuationEngineProductZeroSpread` (`yield_curve/archived/valuation_engine.py`, keyed to the
no-longer-existing `ProductZeroSpread`, whose fields were `basis_index_str`/`reference_index_str`
per `tests/test_linear_product.py`'s still-failing-to-collect fixture — see the Commands section)
onto its live replacement product, `ProductIBORZeroSpread` (`product/linear_products.py`), with one
architectural change: the archived engine pulled its "funding" (denominator-role) leg out of the
vpc's `FundingIndexParameter` by currency rather than from a product field; `ProductIBORZeroSpread`
carries `reference_index` explicitly as a stored `Index`/`FundingIdentifier`, so the new engine reads
`product.basis_index`/`product.reference_index` directly and needs no `FundingIndexParameter` at
all — same simplification pattern as `ValuationEngineProductGenericForward` reading `product.index`
directly instead of going through the vpc. `sign_` comes from `product.pay_or_rec`
(`PayOrReceive`), not `long_or_short` (the archived product had no `pay_or_rec`). Both discount
factors are read with `calc_grad=True` and multiplied/divided directly (no anchored-index engine
involved — this is a raw two-discount-factor ratio, not an accrual-period cashflow), so `value_`
stays a live torch tensor and the base `ValuationEngineProduct.get_risk()` default (`.backward()`
then `model_.get_gradient(reset=True)`) works unmodified, unlike the archived engine's own
`calculate_first_order_risk`/`grad_at_par`, which used the numpy `resize_gradient`/
`discount_factor_gradient_wrt_state` path — not reused here, per the modern-engine convention
elsewhere in this file. `par_rate_or_spread()` is `-1/T * ln(DF_reference/DF_basis)` (solves
`PV=0`, the direct analogue of the archived `grad_at_par`'s inline derivation, but returning the
par spread itself rather than a gradient vector); `pv01()` is the closed-form
`sign*notional*T*exp(-spread*T)*1e-4` (`spread` is a plain float, never wrapped in a tensor, so
there's no graph to differentiate through, same reasoning as `ValuationEngineProductCashDeposit`).
`create_cash_flows_report()` raises, same as the archived version — an outright zero-rate spread
isn't a cashflow series. Verified end to end against a synthetic SOFR-1B (10-tenor) + SOFR-1B-FLAT
(2-tenor: 5Y/10Y spread curve) fixture: PV at the computed `par_rate_or_spread()` was exactly `0.`;
registry dispatch (`ValuationEngineProductRegistry().new_valuation_engine(...)`, newly registered
under `ProductIBORZeroSpread._product_type`) matched direct construction exactly; `get_risk()`
produced nonzero gradient entries on both curve components (dominant sensitivity on
`SOFR-1B-FLAT`, the reference/spread leg, with float-noise-level entries on `SOFR-1B` itself).

### Portfolio-level risk: per-product breakdown vs. aggregated (`RiskValParam`)

`ValuationEngineProductPortfolio.get_risk` (`fixedincomelib/valuation/valuation_engine_portfolio.py`)
always computes risk separately per element first and only then sums it — this was already true in
shape (a `leg_grad`/`local_grad` accumulation loop), but the per-element breakdown used to be
discarded once summed. It's now retained on `self.product_risk_` (exposed via a `product_risk`
property — a list of `np.ndarray`, one per `product.elements_` entry, each already scaled by that
element's portfolio weight, in the same order as `self.engines_`/`self.weights`/`self.currencies`).
`get_risk`'s own signature/contract is unchanged (`gradient[:] = local_grad`, the aggregated array) —
this matters because other engines call `child_engine.get_risk(gradient=some_flat_array)` recursively
(nested portfolios, and the two-leg swap engines' own `get_risk` overrides) and all of them expect
exactly one flat `np.ndarray` back, not a sometimes-list.

Whether an external caller gets the aggregated array or the per-product breakdown is controlled by a
new `ValuationParameters` type, `RiskValParam` (`fixedincomelib/valuation/valuation_parameters.py`,
vp_type `"RISK PARAMETER"`, single key `LEVEL` ∈ `{"PORTFOLIO", "PRODUCT"}`, case-insensitive on
input/stored uppercase, defaults to `"PORTFOLIO"` when omitted) — same
`ValuationParameters.get_valid_keys()`/defaults pattern as `AnalyticValParam`/`FundingIndexParameter`,
registered in `ValuationParametersBuilderRegistry` the same way. `ValuationEngineProductPortfolio.
get_risk_report()` is the new entry point that reads it: internally calls `get_risk()`, then checks
`valuation_parameters_collection_.has_vp_type(RiskValParam._vp_type)` — if the vpc has no
`RiskValParam` at all (the common case today, since nothing constructs one yet outside tests), it
silently defaults to `"PORTFOLIO"` and returns the same aggregated array `get_risk()` always produced,
so existing callers are unaffected; only a caller that explicitly adds `RiskValParam({"LEVEL":
"PRODUCT"})` to its vpc gets `product_risk_` back instead. Verified in
`tests/test_valuation_engine_fixed_ibor_stream.ipynb` (§5e) against the notebook's existing
4-cashflow `fixed_leg` portfolio fixture: `sum(product_risk)` reproduces `get_risk()`'s aggregated
array exactly, and each element of `product_risk` was checked — not just for internal
self-consistency, but against independently-built per-cashflow `ValuationEngineProductFixedAccrued`
engines constructed directly off `fixed_leg.elements_[i]` — and matched exactly, confirming ordering
as well as values. `RiskValParam` itself (defaults, validation, serialize/deserialize, registry
round-trip) has unit coverage in `tests/test_valuation_parameters.py`.

## Day-count-basis footguns worth knowing about

- **`AnchoredIborIndex`/`AnchoredOvernightIndex`/`AnchoredCompoundIborIndex` no longer hardcode
  `accrual_basis=ACTUAL/ACTUAL (ISMA)`** — each now accepts an optional `accrual_basis` param and
  defaults to the underlying index's own native day count (`index.accrual_basis`, e.g. `ACT/360`
  for SOFR/LIBOR) when not given. This matters because a product-level engine that scales a
  `ValuationEngineAnalytics*` engine's `.value` by its *own* `tau` (e.g. `product.accrued`, which
  is computed off the index's native basis) needs that `tau` to use the **same** day-count basis
  the engine used internally to derive the rate in the first place — `rate * tau` only reproduces
  the underlying discount-factor-implied growth (`DF_first/DF_last - 1`) when both `rate` and `tau`
  came from the same basis; mixing bases silently rescales the payoff by the wrong day-count
  fraction. Before this fix, only instruments that never multiply by `tau` (the future, which
  folds the day-count into `notional` via `contractual_notional * basis_point/1e4` instead) were
  safe from this; anything that does (the FRA's overnight branch, and the new composite-cashflow
  engine) was silently exposed.
- **`model.discount_factor(index, date)` mutates shared state even in read-only usage.**
  `calc_grad` defaults to `False`, and `Interpolator1D.integrate`/`.interpolate` call
  `self.values_.requires_grad_(calc_grad)` **in place** on the curve component's state-data
  tensor — the same tensor object every other call against that model shares. A plain
  (non-`calc_grad`) discount-factor lookup used purely for display/comparison purposes (e.g. an
  independent closed-form check in a test notebook) run *after* a product engine has already built
  its differentiable `.value_` graph on the same model will flip that graph's leaf tensor back to
  `requires_grad=False` — a later `.backward()`/`get_gradient()` call then silently returns an
  all-zero gradient (no error). Always pass `calc_grad=True` for any `discount_factor` call against
  a model that risk will be computed on afterwards, even for a "just print this number" lookup.
- **Finite-difference risk checks against a `REFERENCE`d + solved (`BRENT`) discounting curve must
  bump one component's calibration target at a time, and compare only against that component's own
  gradient block** — not the full concatenated gradient vector. Rebuilding the whole model from a
  bumped *target* input (`qfCreateModel` with e.g. `USD-SOFR-OIS-1B-IFR` shifted) re-solves any
  `YC_FUNDING_ELEMENT` referencing it back to its own unchanged target, so that component's own
  state data barely moves and its analytic gradient block (a genuine, nonzero partial derivative
  at the frozen, already-built model) has no counterpart in that particular finite difference.
  Comparing the full rebuild-based FD against the sum of *all* gradient blocks combined will show a
  large, confusing mismatch that looks like a broken gradient but isn't — bump each component's
  target independently and compare against that component's block alone.

## Bug Log

Grouped by subsystem, most-recent work first. Terse by design — the fix is usually a one-liner; the
"why" is what's worth preserving.

**`qfCreateModel` state-data build path** (`model/build_method.py`, `yield_curve/build_method.py`,
`yield_curve/model_factory.py`, `model/model.py`) — six bugs, all only surfacing once you actually
drive a build-method collection through end to end (not caught by import or unit tests, since there's
no test coverage of `model_factory.py`):
- `BuildMethod.__init__` indexed `content["REFERENCE"]` unconditionally → `KeyError` when a root
  build method omitted the key entirely. Now `self.content_.get("REFERENCE")`.
- The "defaultable entries" loop had its branch inverted: wrote the default when the key *was*
  present, `""` when it *wasn't*. Broke `INTERPOLATION METHOD`/`EXTRAPOLATION METHOD`/`SOLVER METHOD`
  for any caller not explicitly repeating the default.
- `YieldCurveONIndexBuildMethod` was missing `target_index` (its siblings both have it) →
  `AttributeError` in `_parse_state_build_method` for any overnight-index element.
- Three `reference_index` properties read `"REFERENCE INDEX"`, but only `"REFERENCE"` is ever
  populated → dependency map silently never populated.
- `calibrate_single_component_from_state_data`: `add_period(...)` called with 2 of 4 required args;
  `data_conv.conv_name` (should be `.name`); business-day-convention/calendar pulled via the unbound
  native methods (see index-wrapper gotcha above) instead of `.payment_business_day_conv`/`.payment_holiday_conv`.
- Component storage/lookup case mismatch — see uppercase-keys convention above.
- `YieldCurveBuilder.create_model_yield_curve` had stopped calling `set_component_dependency(...)`
  at all — `component_dependency_`/`component_order_`/`gradient_lengths_` stuck at `__init__`
  defaults, breaking `get_gradient()` and `discount_factor` reference lookups. Fixed by calling it
  once, after components are populated (see build-pipeline section above for why ordering matters).

**Anchored-index valuation path** (`market/anchored_index.py`, `market/interfaces.py`,
`yield_curve/valuation_engine_analytics.py`, `valuation/valuation_engine.py`, `date/utilities.py`) —
this area was mid-refactor with uncommitted WIP; getting it to run end to end surfaced:
- Convention-factory constructor misuse and missing `"ACT/ACT"` alias — see conventions section above.
- `AnchoredIndex` base class exposed `.end_date`/typo'd `arrcual_basis`; every caller expected
  `.term_or_termination_date`/`accrual_basis`. Renamed the base class to match its callers.
- `AnchoredOvernightIndex` didn't exist as a class (only `AnchoredOvernightCompositeIndex`), despite
  every caller — including the engine's own assert message — using that name. Renamed.
- `.tenor()` calls on the unbound index wrappers — see gotcha above; use `.term`.
- `IndexRegistry.look_up_index_name(index)` doesn't exist; use `index.index_name()`.
- `subtract_period` (date minus a period, for rate-cutoff/look-back math; originally added under the
  name `reduce_period`, later renamed) didn't exist in `date/utilities.py` despite being used
  throughout the valuation analytics — added it, built on the already-present-but-unused
  `Period.negate_period(...)`.
- `AnchoredIborIndex`/`AnchoredOvernightIndex`/`AnchoredCompoundIborIndex` each hardcoded
  `accrual_basis=AccrualBasis.new("ACTUAL/ACTUAL (ISMA)")` regardless of the index's real native
  day count (e.g. `ACT/360` for SOFR/LIBOR) — harmless for engines that never multiply `.value` by
  an externally-computed `tau` (the future), but silently mis-scaled the payoff for any engine that
  does (see the day-count-basis footgun note above). Fixed by adding an optional `accrual_basis`
  param to each, defaulting to `index.accrual_basis` when not supplied.
- `ValuationEngineAnalyticsCompoundIborIndex.calculate_value`'s `FLAT_COMPOUND` branch referenced
  `casted_yc` (for the forward-leg discount-factor lookups) without ever assigning it in that
  branch — `casted_yc: YieldCurve = self.model_` was only assigned in the sibling
  `SPREAD_EXCLUSIVE_COMPOUND` branch, so any forward-looking (`tau_f > 0`) `FLAT_COMPOUND` period
  raised `NameError: cannot access free variable 'casted_yc'`. Fixed by assigning `casted_yc` at
  the top of the `FLAT_COMPOUND` branch too. Only surfaced when converting
  `tests/test_valuation_engine_anchored_index.ipynb` to a pytest `.py` file (Test 8c) — the
  notebook itself had passed earlier in the same session, before this branch regressed.
- `ValuationEngineAnalyticsIborIndex.calculate_value`'s historical-fixing-date computation was
  improved to branch on `index.from_ql`: a `from_ql` index (e.g. `USD-LIBOR-BBA-3M`, backed by a
  real QuantLib index name) now looks up its fixing date via `index.fixingDate(start_date)` (the
  index's own native settlement-lag convention, e.g. real T-2 for LIBOR) instead of always
  `subtract_period(start_date, idx.look_back_window, bdc, hol)` — the latter is only correct for
  non-`from_ql` (explicit-convention) indices. A test seeding a historical fixing must compute
  the lookup date the same way (check `index.from_ql` first) or the fixing silently won't be
  found at the date the engine actually asks for.

**Products** (`product/product_interfaces.py`, `product/linear_products.py`):
- `ProductCashflow.__init__`: the indexed-cashflow branch set `self.spread_ = None` and then, one
  line later, checked `if self.spread_ is None: self.spread_ = 0.` — since `self.spread_` had *just*
  been set to `None` unconditionally, that check was always true, so the caller's own
  `fixed_rate_or_spread` argument (the actual spread, e.g. from `ProductOvernightIndexCompositeCashflow`
  or `ProductIBORIndexCashflow`) was silently discarded and `.spread` always read back `0.0`. Fixed
  to `self.spread_ = fixed_rate_or_spread if fixed_rate_or_spread is not None else 0.`. Only surfaced
  once a valuation engine actually needed to read a nonzero `product.spread`.
- `ProductOvernightIndexBasisSwap.__init__` set `self.accrual_basis` (missing trailing underscore)
  in its explicit-`accrual_basis` branch → `AttributeError` on every read. Fixed to `self.accrual_basis_`.
- `ProductOvernightIndexBasisSwap`/`ProductOISBasisSwap` `.deserialize` double-wrapped
  `rate_cut_off_days_offset` in `Period(...)` before handing it to a constructor that wraps it again.
  Fixed to pass the raw string.
- `ProductOvernightIndexFuture.__init__`: `self.sign_ = long_or_short == 1. if LongOrShort.LONG else
  -1.` — Python parses the ternary as `(long_or_short == 1.) if LongOrShort.LONG else -1.`, and
  `LongOrShort.LONG` (the bare enum member, not a comparison) is always truthy, so this *always*
  evaluated to `long_or_short == 1.` — an enum compared to a float, always `False` — making
  `sign_` (and therefore `notional_`, which multiplies by it) silently `0.0` for every future,
  long or short. Fixed to `1.0 if long_or_short == LongOrShort.LONG else -1.0`. Only surfaced by
  actually instantiating the product end to end; nothing type-checks a boolean-as-float multiplier.
- `ProductFRAOrFixing.__init__` passed `payment_holiday_convention=index.payment_holiday_conv()` —
  `payment_holiday_conv` is a `@property` (see index-wrapper gotcha above), not a method, and its
  return value is a `ql.Calendar`, which isn't callable either → `TypeError: '...Calendar' object is
  not callable` on every construction. Fixed to drop the `()`. Also never instantiated end to end
  before this.

**Registry** (`utilities/utils.py`, `valuation/valuation_engine_registry.py`):
- `ValuationEngineProductRegistry` is keyed on 3-tuples (`(model_type, product_type, vp_type)`, see
  `new_valuation_engine`) and already overrode `get()` to skip the base `Registry`'s
  string-only `key.upper()` lookup — but not `register()`, which calls the base class's abstract
  `register(key, value)` that unconditionally does `self.exists(key)`, and the base `exists()` also
  does `key.upper()`. Any module-load-time `ValuationEngineProductRegistry().register((...), ...)`
  call with a tuple key raised `AttributeError: 'tuple' object has no attribute 'upper'` before the
  importing module could even finish loading. Fixed by overriding `exists()` on
  `ValuationEngineProductRegistry` the same way `get()` already was (plain `key in self._map`, no
  `.upper()`). If another tuple/non-string-keyed registry subclass shows up, it needs the same
  `exists()` override, not just `get()`.

**Interpolator** (`utilities/numerics.py`):
- `Interpolator1DPCP.integrate` read `self.values[i]` inside its two-pointer loop even under
  `calc_grad=True`, so accumulation never entered the autograd graph. Fixed to use the local tensor
  reference (`vals[i]`) in every branch.

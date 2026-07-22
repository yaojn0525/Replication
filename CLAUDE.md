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

Registry-based valuation-engine dispatch (`ValuationEngineProductRegistry`,
`ValuationEngineAnalyticIndexRegistry` in `fixedincomelib/valuation/valuation_engine_registry.py`)
is **entirely commented out** — scaffolding for a dispatch-by-`(model_type, product_type, vp_type)`
design that isn't wired up. The pattern that actually works today: callers construct the concrete
`ValuationEngineAnalytics*` subclass directly (e.g.
`ValuationEngineAnalyticsCompoundIborIndex(model, anchored_index, vpc)`). Don't assume the registry
dispatch path is live without checking whether it's still commented out.

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
pattern worth reusing for the next product engine:

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
  proxy given the codebase keeps no time series of prior curve builds.

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
  settling early with the standard `1 / (1 + d*tau)` early-settlement discount factor (`d` = the
  floating rate under `"ISDA"`, the fixed coupon under `"AFMA"`); if they're equal (the default —
  `pay_date_or_offset` defaults to `TermOrDate("0D")`, which resolves to `termination_date_`), it's
  a plain fixing/coupon cashflow with no such adjustment.
- Picks `AnchoredIborIndex` + `ValuationEngineAnalyticsIborIndex` or `AnchoredOvernightIndex` +
  `ValuationEngineAnalyticsCompositeIndex` off `product.is_on` (`ProductCashflow` already derives
  this from `isinstance(index_, OvernightIndex)`), since `ProductFRAOrFixing.index` can be either.
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

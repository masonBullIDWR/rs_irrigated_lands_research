#%%
"""BULC (Bayesian Updating of Land Cover) for Google Earth Engine.

Faithful implementation of Cardille & Fortin (2016), "Bayesian updating of
land-cover estimates in a data-rich environment" (Remote Sensing of Environment).
Unlike the lightweight recursive filter in `gist_bulc_smoothing.py`, this builds
BULC's self-calibrating "leveling" matrix each step -- the part that makes BULC
actually BULC.

Algorithm, per time step t (one classification "event" E_t):

  1. Harden the running estimate S_{t-1} to its most-likely class (per-pixel
     argmax).
  2. Overlay that hardened estimate against the new event E_t over the study
     region and tabulate a contingency matrix T[h][e]  (rows = hardened/"truth"
     classes, columns = event classes).
  3. Column-normalize T -> conditional matrix  M[h][e] = P(class h | event = e),
     tempered by a minimum so no entry is exactly 0. This is the "leveling":
     when an event agrees well with the accumulated estimate its classes map
     confidently; when it disagrees the mass gets spread out, so a noisy year is
     automatically down-weighted.
  4. Per pixel, the event class selects a column of M -> an n-class likelihood
     vector image.
  5. Bayesian update:  S_t = normalize( S_{t-1} * likelihood ).

Inputs are CLASSIFICATIONS, not probabilities -- this is the canonical
categorical-event BULC. If you have per-year P(irrigated) from one model,
threshold it first (see `classes_from_prob`). For an n=2 irrigation legend the
contingency is 2x2; the code is written for arbitrary n_classes.

    import ee, gist_bulc as bulc
    ee.Initialize(project="your-project")

    # events: {year: ee.Image} single-band int in [0, n_classes-1], wall-to-wall
    #         over `region` (gap-filled; BULC assumes complete event maps).
    states = bulc.bulc(events, n_classes=2, region=aoi, scale=30)

    p_irr   = bulc.probability(states, k=1)   # {year: P(class 1)} if irr == 1
    classes = bulc.mode_class(states)          # {year: argmax class image}

Cost note: this runs one `reduceRegion` per step to build the leveling matrix,
so it is heavier than the per-pixel smoothing filter. That region reduction is
inherent to BULC.
"""

from __future__ import annotations

import ee
ee.Initialize(project = 'idwr-450722')
ee.Authenticate()

ee.data.setWorkloadTag('bulc_processing')
# --- Defaults (override per call) -------------------------------------------
MIN_PROB = 0.05  # floor on each conditional-matrix entry, then renormalized;
# keeps the leveling from collapsing a class to exactly 0.
INIT_CONF = 0.85  # confidence assigned to the first event's class at t0 (the
# first event has nothing to be compared against).
LEAK = 0.0  # optional per-step decay of the accumulated state back toward the
# class BASE RATE (not uniform), applied after each Bayesian update. 0.0 =
# canonical BULC: purely multiplicative, so confidence can lock in permanently
# and later events stop being able to flip a saturated pixel. Larger -> less
# temporal stickiness (saturated pixels relax toward the population composition
# each step, so sustained later change can still move them). Try ~0.05-0.2 for a
# long, multi-decade series that looks over-smoothed in its later years.
# The leak target defaults to each event's own class marginals (the observed
# base rate that year); pass `prior=` to pin a fixed one. It is deliberately
# NOT uniform -- on a landscape dominated by one class, leaking toward 0.5 would
# bias every stable majority-class pixel toward the minority class.
MAX_PIXELS = 1e13


def _state_bands(n: int):
    return [f"p{k}" for k in range(n)]


def _prior_image(prior, n: int) -> ee.Image:
    """Fixed leak target from a length-n sequence of class weights (renormalized
    to sum to 1). Bands p0..p{n-1}."""
    if len(prior) != n:
        raise ValueError(f"prior must have {n} entries, got {len(prior)}")
    s = float(sum(prior))
    if s <= 0:
        raise ValueError("prior must sum to a positive number")
    return ee.Image.constant([float(w) / s for w in prior]).rename(_state_bands(n))


def _event_base_rate(T, n: int) -> ee.Image:
    """Leak target derived from the event's class marginals: p(class j) =
    (sum_h T[h][j]) / total, i.e. the fraction of the region the new event map
    labels class j. Free -- it reuses the contingency already tabulated this
    step. Bands p0..p{n-1}, summing to 1."""
    cols, total = [], ee.Number(0)
    for j in range(n):
        s = ee.Number(0)
        for h in range(n):
            s = s.add(T[h][j])
        cols.append(s)
        total = total.add(s)
    total = total.max(1)  # guard: empty region
    bands = [ee.Image.constant(cols[j].divide(total)).rename(f"p{j}") for j in range(n)]
    return ee.Image.cat(bands)


def _leak(state: ee.Image, target: ee.Image, n: int, leak: float) -> ee.Image:
    """Pull the accumulated state a fraction `leak` toward `target` so confidence
    can't lock in permanently. Both operands sum to 1, so the result does too."""
    return state.multiply(1.0 - leak).add(target.select(_state_bands(n)).multiply(leak))


def _from_event(event: ee.Image, n: int, conf: float) -> ee.Image:
    """Initial estimate from the first event: observed class gets `conf`, the
    rest share (1 - conf) equally. Bands p0..p{n-1}, summing to 1."""
    rest = (1.0 - conf) / (n - 1)
    bands = [
        event.eq(h).multiply(conf - rest).add(rest).rename(f"p{h}") for h in range(n)
    ]
    return ee.Image.cat(bands)


def _harden(state: ee.Image, n: int) -> ee.Image:
    """Per-pixel argmax class index of the n-band probability state."""
    arr = state.select(_state_bands(n)).toArray()  # 1-D array, band order
    return arr.arrayArgmax().arrayGet([0]).toInt().rename("hard")


def _contingency(
    hard: ee.Image,
    event: ee.Image,
    n: int,
    region,
    scale: int,
    tile_scale: int,
    max_pixels: float,
):
    """T[h][e] = pixel count where hardened class == h and event class == e.
    One reduceRegion builds the whole n x n matrix (as server-side numbers)."""
    cells = ee.Image.cat(
        [
            hard.eq(h).And(event.eq(e)).rename(f"c_{h}_{e}")
            for h in range(n)
            for e in range(n)
        ]
    )
    d = cells.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=region,
        scale=scale,
        maxPixels=max_pixels,
        tileScale=tile_scale,
    )
    return [[ee.Number(d.get(f"c_{h}_{e}")) for e in range(n)] for h in range(n)]


def _conditional(T, n: int, min_prob: float):
    """Column-normalize the contingency to M[h][e] = P(class h | event e),
    temper by `min_prob`, and renormalize each column to sum to 1."""
    cond = [[None] * n for _ in range(n)]
    for e in range(n):
        col_sum = ee.Number(0)
        for h in range(n):
            col_sum = col_sum.add(T[h][e])
        col_sum = col_sum.max(1)  # guard: event class absent over the region
        tempered = [ee.Number(T[h][e]).divide(col_sum).max(min_prob) for h in range(n)]
        renorm = ee.Number(0)
        for v in tempered:
            renorm = renorm.add(v)
        for h in range(n):
            cond[h][e] = tempered[h].divide(renorm)
    return cond


def _likelihood(event: ee.Image, cond, n: int) -> ee.Image:
    """Per-pixel n-band likelihood: band h = M[h][event]. The event class
    selects a column of the conditional matrix."""
    bands = []
    for h in range(n):
        band = ee.Image.constant(0)
        for e in range(n):
            band = band.add(event.eq(e).multiply(ee.Image.constant(cond[h][e])))
        bands.append(band.rename(f"p{h}"))
    return ee.Image.cat(bands)


def _update(state: ee.Image, likelihood: ee.Image, n: int) -> ee.Image:
    """Bayes update: S_t = normalize(S_{t-1} * likelihood), across the n bands."""
    prod = state.select(_state_bands(n)).multiply(likelihood.select(_state_bands(n)))
    total = prod.reduce(ee.Reducer.sum())
    return prod.divide(total).rename(_state_bands(n))


def bulc(
    events: dict,
    n_classes: int = 2,
    region: "ee.Geometry" = None,
    scale: int = 30,
    min_prob: float = MIN_PROB,
    init_conf: float = INIT_CONF,
    leak: float = LEAK,
    prior=None,
    tile_scale: int = 4,
    max_pixels: float = MAX_PIXELS,
) -> dict:
    """Run BULC over a time series of categorical event images.

    events    : {int year: ee.Image} single-band int class in [0, n_classes-1],
                wall-to-wall over `region`.
    region    : geometry over which the leveling contingency is tabulated (req'd).
    leak      : optional per-step decay toward the class base rate (0.0 = off =
                canonical BULC). See LEAK. Larger -> less temporal stickiness.
    prior     : leak target when leak > 0. None -> each event's own class
                marginals (base rate that year). A length-`n_classes` sequence
                (e.g. [0.85, 0.15]) pins a fixed base rate instead. Ignored when
                leak == 0.
    Returns     {int year: ee.Image} with bands p0..p{n_classes-1} = P(class k).
    """
    if region is None:
        raise ValueError(
            "region is required: BULC tabulates the leveling "
            "contingency over it each step."
        )
    if not 0.0 <= leak <= 1.0:
        raise ValueError(f"leak must be a fraction in [0, 1]; got {leak}")
    if not 0.0 <= min_prob < 1.0 / n_classes:
        raise ValueError(
            f"min_prob must be in [0, 1/n_classes) = [0, {1.0 / n_classes:.3g}); "
            f"got {min_prob}. At or above 1/n the floor alone flattens every "
            "conditional column to uniform, so the leveling carries no signal."
        )
    years = sorted(events)
    state = _from_event(ee.Image(events[years[0]]).toInt(), n_classes, init_conf)
    out = {years[0]: state}
    fixed_target = _prior_image(prior, n_classes) if prior is not None else None
    for y in years[1:]:
        event = events[y].toInt()
        hard = _harden(state, n_classes)
        T = _contingency(hard, event, n_classes, region, scale, tile_scale, max_pixels)
        cond = _conditional(T, n_classes, min_prob)
        L = _likelihood(event, cond, n_classes)
        state = _update(state, L, n_classes)
        if leak > 0.0:
            target = fixed_target if fixed_target is not None else _event_base_rate(T, n_classes)
            state = _leak(state, target, n_classes, leak)
        out[y] = state
    return out


# --- Convenience -------------------------------------------------------------


def probability(states: dict, k: int) -> dict:
    """Pull P(class k) per year -> {year: single-band ee.Image}."""
    return {y: s.select(f"p{k}").rename(f"p{k}") for y, s in states.items()}


def mode_class(states: dict, n_classes: int = 2) -> dict:
    """Per-year most-likely class -> {year: single-band int ee.Image}."""
    return {y: _harden(s, n_classes).rename("class") for y, s in states.items()}


def classes_from_prob(
    prob_by_year: dict, cutoff: float = 0.5, irr_class: int = 1
) -> dict:
    """Threshold a P(irrigated) series into BULC events (int class images).

    irr_class is the class index assigned where P >= cutoff; the other class is
    1 - irr_class. Use this if your events come from a probability classifier.
    """
    other = 1 - irr_class
    return {
        y: p.gte(cutoff).multiply(irr_class - other).add(other).toInt().rename("event")
        for y, p in prob_by_year.items()
    }


#run---------------------
import geemap
import geopandas as gpd

method = 'im' #either 'rf' for IDWR RF classifications or 'im' for IrrMapper
if method == 'rf':
    col = ee.ImageCollection('projects/idwr-450722/assets/TreasureValley/tv-irr-lands').toList(6)
    events = {1987: ee.Image(col.get(0)),
              1997: ee.Image(col.get(1)),
              2000: ee.Image(col.get(2)),
              2004: ee.Image(col.get(3)),
              2015: ee.Image(col.get(4)),
              2023: ee.Image(col.get(5))}
elif method == 'im':
    col = ee.ImageCollection("UMT/Climate/IrrMapper_RF/v1_2").filter(ee.Filter.stringContains('system:index', 'ID'))
    events = {}
    years = list(range(1985, 2026))
    for y in years:
        img = col.filterDate(f'{str(y)}-01-01', f'{str(y+1)}-01-01').first()
        events.update({y:img})

shp = gpd.read_file(r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\TV_and_MH_outline_union.shp")
aoi = geemap.gdf_to_ee(shp)
states = bulc(events, n_classes=2, region=aoi, scale=30)
p_irr   = probability(states, k=1)   # {year: P(class 1)} if irr == 1
classes = mode_class(states)          # {year: argmax class image}

leak_str = str(LEAK).split('.')
leak_val = f'{leak_str[0]}-{leak_str[1]}'
min_prob_str = str(MIN_PROB).split('.')
min_prob_val = f'{min_prob_str[0]}-{min_prob_str[1]}'
for i in states.keys():
    year = str(i)
    img = states[i]
    prob = p_irr[i]
    class_img = classes[i]
    ee.batch.Export.image.toDrive(
        image=img,
        #name indicates {region}_bulc_{irrmapper or idwrrf}_{image type}_{year}_{leak value}_{min prob value}
        fileNamePrefix=f'tv_bulc_{method}_state_{year}_l{leak_val}_mp{min_prob_val}',
        description=f'tv_bulc_{method}_state_{year}_l{leak_val}_mp{min_prob_val}_export',
        folder='BULC_tv',
        region=aoi.geometry(),
        scale=30,
        crs='EPSG:8826',
        formatOptions={'cloudOptimized': True}
    ).start()
    print(f'state for {method} {year} exported')

    ee.batch.Export.image.toDrive(
        image=prob,
        fileNamePrefix=f'tv_bulc_{method}_prob_{year}_l{leak_val}_mp{min_prob_val}',
        description=f'tv_bulc_{method}_prob_{year}_l{leak_val}_mp{min_prob_val}_export',
        folder='BULC_tv',
        region=aoi.geometry(),
        scale=30,
        crs='EPSG:8826',
        formatOptions={'cloudOptimized': True}
    ).start()
    print(f'probabilty for {method} {year} exported')

    ee.batch.Export.image.toDrive(
        image=class_img,
        fileNamePrefix=f'tv_bulc_{method}_class_{year}_l{leak_val}_mp{min_prob_val}',
        description=f'tv_bulc_{method}_class_{year}_l{leak_val}_mp{min_prob_val}_export',
        folder='BULC_tv',
        region=aoi.geometry(),
        scale=30,
        crs='EPSG:8826',
        formatOptions={'cloudOptimized': True}
    ).start()
    print(f'class for {method} {year} exported\n')

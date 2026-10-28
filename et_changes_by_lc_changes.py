#%%
import numpy as np
import pandas as pd
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from pathlib import Path

# ----------------------------------------------------------------- config
PARENT_DIR = Path(r'D:\Geoprocessing\Data\TV\et_trends\imagery')
nlcd_path = lambda y: PARENT_DIR / f"wspa_nlcd_{y}.tif"
et_path = lambda y: PARENT_DIR / f"et_ensemble_2_0_{y}.tif"      # seasonal (Apr-Oct) sum

YEARS = list(range(1986, 2025))
URBAN = (22, 23, 24)                             # 21 (open space) is not urban, as in your script
CLASSES = [11, 12, 21, 31, 41, 42, 43, 52, 71, 81, 82, 90, 95]

# ---------------------------------------------------------------- readers
def read_nlcd(year):
    with rasterio.open(nlcd_path(year)) as src:
        return src.read(1), src.profile

def read_et_on_grid(year, ref_profile):
    """Read an ET raster resampled onto the NLCD reference grid, NaN for nodata."""
    with rasterio.open(et_path(year)) as src:
        with WarpedVRT(src,
                       crs=ref_profile["crs"],
                       transform=ref_profile["transform"],
                       width=ref_profile["width"],
                       height=ref_profile["height"],
                       resampling=Resampling.nearest) as vrt:
            arr = vrt.read(1, masked=True)
    return arr.astype("float32").filled(np.nan)

# ------------------------------------------- part 1: new-urban ET change
def new_urban_et_change(y1, y2):
    """ET change on pixels that were non-urban in y1 and urban in y2,
    summarized by the y1 landcover class."""
    lc1, prof = read_nlcd(y1)
    lc2, _ = read_nlcd(y2)
    et1 = read_et_on_grid(y1, prof)
    et2 = read_et_on_grid(y2, prof)

    new_urban = ~np.isin(lc1, URBAN) & np.isin(lc2, URBAN)

    # later minus earlier (your GEE script was first - second; flip the sign if you want that)
    diff = et2 - et1
    valid = new_urban & np.isfinite(diff)

    rows = []
    for lc in CLASSES:
        vals = diff[valid & (lc1 == lc)]
        rows.append({
            "year1": y1, "year2": y2, "lc_prior": lc,
            "count": vals.size,
            "mean": vals.mean() if vals.size else np.nan,
            "std": vals.std() if vals.size else np.nan,   # population std, like ee.Reducer.stdDev
        })
    return rows

def run_all_pairs(years=YEARS):
    out = []
    for y1, y2 in zip(years[:-1], years[1:]):
        try:
            out += new_urban_et_change(y1, y2)
        except (rasterio.errors.RasterioIOError, FileNotFoundError) as e:
            print(f"skipping {y1}->{y2}: {e}")
    return pd.DataFrame(out)

# ------------------------------------ part 2: multi-step trajectories
# Collapse NLCD into coarse groups so trajectories are readable
GROUPS = {1: "water", 2: "urban", 3: "ag", 4: "natural", 5: "open_space"}
_lut = np.zeros(256, dtype="uint8")             # 0 = other/unknown
for c in (11, 12):                        _lut[c] = 1
for c in URBAN:                           _lut[c] = 2
for c in (81, 82):                        _lut[c] = 3
for c in (31, 41, 42, 43, 52, 71, 90, 95): _lut[c] = 4
_lut[21] = 5

def build_group_stack(years=YEARS):
    """(T, H, W) uint8 stack of coarse landcover groups. Returns stack and ref profile."""
    layers, prof = [], None
    for y in years:
        lc, p = read_nlcd(y)
        prof = prof or p
        layers.append(_lut[lc])
    return np.stack(layers), prof

def collapse(seq, min_run=2):
    """Collapse a yearly sequence into its ordered states, ignoring runs shorter
    than min_run years (annual NLCD flickers, so this suppresses noise)."""
    runs = []
    for s in seq:
        if runs and runs[-1][0] == s:
            runs[-1][1] += 1
        else:
            runs.append([s, 1])
    kept = [s for s, n in runs if n >= min_run]
    out = []
    for s in kept:                              # re-collapse after dropping short runs
        if not out or out[-1] != s:
            out.append(s)
    return tuple(out)

def find_trajectory(stack, pattern, min_run=2):
    """Boolean (H, W) mask of pixels whose collapsed history equals `pattern`,
    e.g. pattern=(3, 2, 3) for ag -> urban -> ag."""
    T, H, W = stack.shape
    flat = stack.reshape(T, -1).T                # (npix, T)
    changed = (flat != flat[:, [0]]).any(axis=1) # only pixels that ever change
    idx = np.flatnonzero(changed)

    uniq, inv = np.unique(flat[idx], axis=0, return_inverse=True)
    match_uniq = np.array([collapse(u, min_run) == tuple(pattern) for u in uniq])

    mask = np.zeros(flat.shape[0], dtype=bool)
    mask[idx] = match_uniq[inv.ravel()]
    return mask.reshape(H, W)

def et_by_state_for_mask(stack, mask, prof, years=YEARS):
    """For the pixels in `mask`, mean ET each year, split by what group
    each pixel was in that year."""
    rows = []
    for t, y in enumerate(years):
        et = read_et_on_grid(y, prof)
        for g, name in GROUPS.items():
            m = mask & (stack[t] == g) & np.isfinite(et)
            if m.any():
                rows.append({"year": y, "state": name,
                             "n_px": int(m.sum()), "mean_et": float(et[m].mean())})
    return pd.DataFrame(rows)

# --------------------------------------------------------------- usage
if __name__ == "__main__":
    # Part 1: ET change on new urban pixels, every consecutive pair
    df = run_all_pairs()
    df.to_csv("new_urban_et_change_by_lc.csv", index=False)

    # Part 2: ag -> urban -> ag
    stack, prof = build_group_stack()
    mask = find_trajectory(stack, pattern=(3, 2, 3), min_run=2)
    print("matching pixels:", mask.sum())
    et_ts = et_by_state_for_mask(stack, mask, prof)
    et_ts.to_csv("ag_urban_ag_et.csv", index=False)

#%%
import seaborn as sns
import matplotlib.pyplot as plt
import json
with open(r"D:\Geoprocessing\Data\nlcd_lookup.json") as dat:
    nlcd_lookup = json.load(dat)
palette = {}
replacement = {}
df2 = df
for i in nlcd_lookup.keys():
    palette.update({nlcd_lookup[i]['name']: nlcd_lookup[i]['color']})
    replacement.update({i: nlcd_lookup[i]['name']})
df['lc_prior'] = df['lc_prior'].astype('str').map(replacement).fillna(df['lc_prior'])
df['area'] = df['count']*9e-4
from matplotlib.lines import Line2D

fig, ax = plt.subplots()

dot_min, dot_max = (10, 200)
sns.scatterplot(data=df, x='year1', y='mean', hue='lc_prior', palette=palette,
                size='area', sizes=(dot_min, dot_max), legend=False, ax=ax)
sns.lineplot(data=df, x='year1', y='mean', hue='lc_prior', palette=palette,
             errorbar=None, legend=False, ax=ax)
ax.set_ylim(-300, 300)
ax.grid(color = "#14121215", alpha = 0.15)
ax.set_ylabel('Mean ET Change (mm)')
ax.set_xlabel('Starting Year')

# one handle per landcover type actually present in the data
present = [lc for lc in palette if lc in df['lc_prior'].unique()]
handles = [Line2D([0], [0], color=palette[lc], marker='o', markersize=7,
                  linewidth=1.5, label=lc) for lc in present]

ax.legend(handles=handles, title='Prior landcover',
          loc='upper center', bbox_to_anchor=(0.5, -0.15), ncols=3, frameon=False)

leg1 = ax.legend(handles=handles, title='Prior landcover',
                 loc='upper center', bbox_to_anchor=(0.35, -0.15), ncols=2, frameon=False)
ax.add_artist(leg1)

ref = np.percentile(df['area'].dropna(), [93, 95, 99, 100]).round(-1)
# match seaborn's size scaling: linear map of count -> area between 10 and 500
cmin, cmax = df['area'].min(), df['area'].max()
area = lambda c: 10 + (c - cmin) / (cmax - cmin) * (dot_max - dot_min)
size_handles = [ax.scatter([], [], s=area(c), color='gray', label=f'{int(c):,}') for c in ref]
ax.legend(handles=size_handles, title='LC area (km²)',
          loc='upper center', bbox_to_anchor=(0.8, -0.15), frameon=False)
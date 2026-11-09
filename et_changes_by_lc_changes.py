#%%
import numpy as np
import pandas as pd
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from pathlib import Path
from math import ceil
from math import floor
import re

# ----------------------------------------------------------------- config
PARENT_DIR = Path(r'D:\Geoprocessing\Data\TV\et_trends\imagery')
nlcd_path = lambda y: PARENT_DIR / f"wspa_nlcd_{y}.tif"
et_path = lambda y: PARENT_DIR / f"et_ensemble_2_0_{y}.tif"      # seasonal (Apr-Oct) sum
eto_path = lambda y: PARENT_DIR / f"wspa_eto_v1_sum_{y}.tif"

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

def read_eto_on_grid(year, ref_profile):
    """Read an ET raster resampled onto the NLCD reference grid, NaN for nodata."""
    with rasterio.open(eto_path(year)) as src:
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
    eto1 = read_eto_on_grid(y1, prof)
    eto2 = read_eto_on_grid(y2, prof)
    etof1 = np.where(eto1 != 0, et1 / eto1, np.nan)
    etof2 = np.where(eto2 != 0, et2 / eto2, np.nan)

    new_urban = ~np.isin(lc1, URBAN) & np.isin(lc2, URBAN)
    stable = np.where(lc1 == lc2, True, False)
    # later minus earlier (your GEE script was first - second; flip the sign if you want that)
    diff = et2 - et1
    diff_eto = eto2 - eto1
    diff_etof = etof2 - etof1

    valid = new_urban & np.isfinite(diff)
    stable_valid = stable & np.isfinite(diff)

    rows = []
    for lc in CLASSES:
        vals = diff[valid & (lc1 == lc)]
        vals_eto = diff_eto[valid & (lc1 == lc)]
        vals_etof = diff_etof[valid & (lc1 == lc)]
        stable_vals = diff[stable_valid & (lc1 == lc)]
        stable_vals_eto = diff_eto[stable_valid & (lc1 == lc)]
        stable_vals_etof = diff_etof[stable_valid & (lc1 == lc)]

        rows.append({
            "year1": y1, "year2": y2, "lc_prior": lc,
            "count": vals.size,
            "mean": vals.mean() if vals.size else np.nan,
            "std": vals.std() if vals.size else np.nan,   # population std, like ee.Reducer.stdDev
            "eto_mean": vals_eto.mean() if vals.size else np.nan,
            "eto_std": vals_eto.std() if vals.size else np.nan,
            "etof_mean": vals_etof.mean() if vals.size else np.nan,
            "etof_std": vals_etof.std() if vals.size else np.nan,
            "stable_count": stable_vals.size,
            "stable_mean": stable_vals.mean() if vals.size else np.nan,
            "stable_std": stable_vals.std() if vals.size else np.nan,
            "stable_eto_mean": stable_vals_eto.mean() if stable_vals.size else np.nan,
            "stable_eto_std": stable_vals_eto.std() if stable_vals.size else np.nan,
            "stable_etof_mean": stable_vals_etof.mean() if stable_vals.size else np.nan,
            "stable_etof_std": stable_vals_etof.std() if stable_vals.size else np.nan,
        })
    return rows

def run_all_pairs(years=YEARS):
    out = []
    for y1, y2 in zip(years[:-1], years[1:]):
        try:
            print(f'{y1} to {y2}')
            out += new_urban_et_change(y1, y2)
            print('done\n')
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

#%%
# --------------------------------------------------------------- usage
if __name__ == "__main__":
    # Part 1: ET change on new urban pixels, every consecutive pair
    print(f'Getting ET changes for:\n')
    df = run_all_pairs()
    df.to_csv("outputs/documents/new_urban_et_change_by_lc.csv", index=False)
    print('Wrote csv for ET stats to "outputs/documents/new_urban_et_change_by_lc.csv"')

    # Part 2: ag -> urban -> ag
    print('\nFinding pixel trjectories and changes\n')
    stack, prof = build_group_stack()
    print('Done\n')
    mask = find_trajectory(stack, pattern=(3, 2, 3), min_run=2)
    print("matching pixels:", mask.sum())
    et_ts = et_by_state_for_mask(stack, mask, prof)
    et_ts.to_csv("outputs/documents/ag_urban_ag_et.csv", index=False)
#%%
import seaborn as sns
import matplotlib.pyplot as plt
import json

try:
    df = df
except:
    df = pd.read_csv("outputs/documents/new_urban_et_change_by_lc.csv")

with open(r"D:\Geoprocessing\Data\nlcd_lookup.json") as dat:
    nlcd_lookup = json.load(dat)
palette = {}
replacement = {}

for i in nlcd_lookup.keys():
    palette.update({nlcd_lookup[i]['name']: nlcd_lookup[i]['color']})
    replacement.update({i: nlcd_lookup[i]['name']})
if type(df['lc_prior'][0]) != str:
    df['lc_prior'] = df['lc_prior'].dropna().astype('int').astype('str').map(replacement).fillna(df['lc_prior'])

#unlss otherwise specified, measurements are in metric (depth mm, area km2)
#area calculations
df['acres'] = df['count']*900/4046.86
df['sqkm'] = df['count']*9e-4

#depth calculations
df['mean_feet'] = df['mean']/304.8
df['stable_feet'] = df['stable_mean']/304.8
df['etof_feet'] = df['etof_mean'] /304.8
df['stable_etof_feet'] = df['stable_etof_mean'] /304.8

#volume
df['acre_feet'] = df['mean_feet']*df['acres']
df['stable_acre_feet'] = df['stable_feet']*df['acres']
df['volume'] = df['mean'] * df['area']
df['stable_volume'] = df['stable_mean'] * df['area']

#difference of differences
df['change_minus_stable_mean'] = df['mean'] - df['stable_mean']
df['change_minus_stable_volume'] = df['volume'] - df['stable_volume']
df['etof_change_minus_stable_mean'] = df['etof_mean'] - df['stable_etof_mean']

df['change_minus_stable_mean_feet'] = df['mean_feet'] - df['stable_feet']
df['change_minus_stable_acre_feet'] = df['acre_feet'] - df['stable_acre_feet']
df['etof_change_minus_stable_mean_feet'] = df['etof_feet'] - df['stable_etof_feet']

df['year1'] = df['year1'].astype(int)
df2 = df.copy()
df2[df2['area'] < 0.5] = np.nan
from matplotlib.lines import Line2D

fig, ax = plt.subplots()

dot_min, dot_max = (10, 200)
sns.scatterplot(data=df2, x='year1', y='mean', hue='lc_prior', palette=palette,
                size='area', sizes=(dot_min, dot_max), legend=False, ax=ax)
sns.lineplot(data=df2, x='year1', y='mean', hue='lc_prior', palette=palette,
             errorbar=None, legend=False, ax=ax)
ax.set_ylim(-300, 300)
ax.grid(color = "#14121215", alpha = 0.15)
ax.set_ylabel('Mean ET Change (mm)')
ax.set_xlabel('Starting Year')

# one handle per landcover type actually present in the data
present = [lc for lc in palette if lc in df2['lc_prior'].unique()]
handles = [Line2D([0], [0], color=palette[lc], marker='o', markersize=7,
                  linewidth=1.5, label=lc) for lc in present]

ax.legend(handles=handles, title='Prior landcover',
          loc='upper center', bbox_to_anchor=(0.5, -0.1), ncols=3, frameon=False)

leg1 = ax.legend(handles=handles, title='Prior landcover',
                 loc='upper center', bbox_to_anchor=(0.35, -0.1), ncols=2, frameon=False)
ax.add_artist(leg1)

ref = np.percentile(df2['area'].dropna(), [93, 95, 99, 100]).round(-1)
# match seaborn's size scaling: linear map of count -> area between 10 and 500
cmin, cmax = df2['area'].min(), df2['area'].max()
area = lambda c: 10 + (c - cmin) / (cmax - cmin) * (dot_max - dot_min)
size_handles = [ax.scatter([], [], s=area(c), color='gray', label=f'{int(c):,}') for c in ref]
ax.legend(handles=size_handles, title='LC area (km²)',
          loc='upper center', bbox_to_anchor=(0.95, -0.25), frameon=False)

#%%

fig1, ax1 = plt.subplots()
sns.scatterplot(data=df2, x='year1', y='stable_volume', hue='lc_prior', palette=palette, legend=True, ax=ax1)
ax1.set_title('Stable Landcover ET Changes')
ax1.set_xlabel('Year')
ax1.set_ylabel('ET Change (km²mm)')
sns.scatterplot(data=df2, x='year1', y='volume', hue='lc_prior', palette=palette, legend=False, ax=ax1, marker = 'X')
ax1.set_ylim(-500, 300)
ax1.set_xlim(2007, 2014)
plt.grid(color = 'black', alpha = 0.15)
fig1.show()
#%%
#trying to account for normal changes in ET without changes in landcover, take a difference of the two
fig1, ax1 = plt.subplots()
sns.scatterplot(data=df2, x='year1', y='change_minus_stable_mean', hue='lc_prior', palette=palette, legend=True, ax=ax1)
ax1.set_title('Change minus Stable Landcover ET Changes')
ax1.set_xlabel('Year')
ax1.set_ylabel('ET Change (mm)')
plt.grid(color = 'black', alpha = 0.15)
fig1.show()
#%%same as above but for etof
fig1, ax1 = plt.subplots()
sns.scatterplot(data=df2, x='year1', y='etof_change_minus_stable_mean', hue='lc_prior', palette=palette, legend=True, ax=ax1)
ax1.set_title('Change minus Stable Landcover EToF Changes')
ax1.set_xlabel('Year')
ax1.set_ylabel('EToF Change')
#ax1.set_xlim(2007, 2014)
plt.grid(color = 'black', alpha = 0.15)
fig1.show()
#%%
#trying out individual plots for each landcover class
df['first_formatted'] = df['year1'] + 0.5
first_year =list(df['year1'])[0]
last_year = list(df['year1'])[-1] + 1

def individual_lc_plots(metric_column, area_column, area_unit, y_lower_lim = -250, y_upper_lim = 250, min_area = 1):
    y_lab = ' '.join([w.capitalize() for w in metric_column.split('_')])
    highest_y = max(df[metric_column]) 
    lowest_y = min(df[metric_column])

    for l in set(df['lc_prior']):
        dat = df[df['lc_prior'] == l]
        if max(dat[area_column]) < min_area:
            continue
        highest_area = max(dat[area_column])
        area_ranges = np.linspace(0, highest_area, 5)
        alpha_dict  = {area_ranges[1]: 0.25,
                   area_ranges[2]: 0.50,
                   area_ranges[3]: 0.75,
                   area_ranges[4]: 1.0,}

        lc_max = max(dat[metric_column])
        lc_min = min(dat[metric_column])
        
        fig, ax = plt.subplots()
        sns.barplot(data = dat, x = 'first_formatted', y = metric_column, hue = 'lc_prior', palette= palette, native_scale = True, width = 1)
        for bar, area in zip(ax.patches, dat[area_column]):
            closest = min(list(alpha_dict.keys()), key = lambda x: abs(x - area))
            bar.set_alpha(alpha_dict[closest])
        x_label_list = list(dat['year1'])
        x_label_list.append(2024)
        ax.set_xticks(ticks = np.arange(first_year, last_year+1, step = 1), labels= x_label_list, rotation = 90, ha = 'center', va = 'center_baseline')
        leg = ax.legend(frameon =False, loc = 'lower center', bbox_to_anchor = (0.5,-0.25), title = None)
        ax.set_xlabel('Year')
        ax.set_ylabel(f'{y_lab} ET Difference')
        ax.set_xlim(first_year, last_year)
        ax.set_ylim(y_lower_lim, y_upper_lim)
        if lc_min <= y_lower_lim:
            ax.set_ylim(lc_min, y_upper_lim)
        if lc_max >= y_upper_lim:
            ax.set_ylim(y_lower_lim, lc_max)
        ax.add_artist(leg)
        plt.vlines(x = [first_year, last_year],ymin=lowest_y + 50, ymax = highest_y + 50, color = 'black', alpha = 0.1)
        plt.grid(color = 'black', alpha = 0.15)

        area = lambda c: int(area_ranges[np.where(area_ranges== c)[0][0] - 1])
        alpha_handles = [ax.scatter([], [], marker = 's', color=palette[l], alpha = alpha_dict[c], label=f'{area(c)} - {int(c)}') for c in area_ranges[1:]]
        ax.legend(handles=alpha_handles, title=f'LC area ({area_unit})', #km², acres
              loc='upper center', bbox_to_anchor=(0.5, -0.2), frameon=False, ncols = 4)
        
        file_string = '_'.join([i for i in re.findall(r'(\w*)', l) if len(i)>0])
        fig.savefig(f'outputs/plots/{metric_column}_{file_string}.pdf')
        fig.show()

individual_lc_plots(metric_column= 'change_minus_stable_acre_feet', area_column='acres', area_unit='acres', min_area = 20)
#individual_lc_plots('change_minus_stable_volume', 'sqkm', 'km²')
#individual_lc_plots('etof_change_minus_stable_mean', 'acres', 'acres', -0.5, 0.5)
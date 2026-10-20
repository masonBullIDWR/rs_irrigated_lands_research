'''Script that plots the calculations of ET and NDVI trends in Dry Creek.
Does not do any of the calculation, just the plotting. If data need adjusted then see the
poorly named "calculate_et_of_grass_and_ag.py" and "calculate_ndvi_and_irrigated_area.py'''

#%%
import rasterio as rio
from rasterio.features import rasterize
from rasterio.features import shapes
from rasterio.mask import mask
from shapely.geometry import shape
import geopandas as gpd
import numpy as np
import numpy.ma as ma
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import json

import ee, geemap
ee.Authenticate()
ee.Initialize(project= 'idwr-450722')
ee.data.setWorkloadTag('dry-creek-et')

et_version = 'v2_1'

et = ee.ImageCollection(f"projects/openet/assets/ensemble/conus/gridmet/monthly/{et_version}")
eto = ee.ImageCollection(f"projects/openet/assets/reference_et/conus/gridmet/daily/v1")
cdl = ee.ImageCollection("USDA/NASS/CDL")

dc_center = ee.Geometry.Point([-116.290277075344,43.73373080477343])

aoi_path = r"D:\Geoprocessing\Data\TV\dryCreek\DryCreek_AOI.gpkg"
aoi = gpd.read_file(aoi_path, layer = 'POU Merge', columns=['geometry']).to_crs('EPSG:8826')

output_dict = {}

with open(r"D:\Geoprocessing\Data\cdl_lookup.json") as src:
    cdl_lookup = json.load(src)    

plotting_data = pd.read_csv(fr"D:\Geoprocessing\Data\TV\dryCreek\segmentation\dry_creek_et_gee_dict_{et_version}.csv")

plotting_data = pd.concat([plotting_data.drop(['crop_types'], axis = 1), plotting_data['crop_types'].apply(pd.Series)], axis=1)
plotting_data['et_sum'] = plotting_data['grass_et'] + plotting_data['crops_et']

plotting_data['area_sum'] = plotting_data['grass_acres'] + plotting_data['crop_acres']

plotting_data['grass_eto']=plotting_data['grass_eto']/304.8
plotting_data['crop_eto']=plotting_data['crop_eto']/304.8

plotting_data['grass_et_depth'] = (plotting_data['grass_et']/plotting_data['grass_acres']).replace(np.nan, 0)
plotting_data['crops_et_depth'] = plotting_data['crops_et']/plotting_data['crop_acres']

grass = plotting_data['grass_et_depth'].replace(np.nan, 0)*plotting_data['grass_acres']
crop = plotting_data['crops_et_depth']*plotting_data['crop_acres']

plotting_data['average_et_rate'] = (grass+crop)/plotting_data['area_sum']

plotting_data['grass_etof'] = plotting_data['grass_et_depth']/plotting_data['grass_eto']
plotting_data['crops_etof'] = plotting_data['crops_et_depth']/plotting_data['crop_eto']

grass_etof = plotting_data['grass_etof'].replace(np.nan, 0)*plotting_data['grass_acres']
crop_etof = plotting_data['crops_etof']*plotting_data['crop_acres']

plotting_data['average_etof'] = (grass_etof+crop_etof)/plotting_data['area_sum']

plotting_data = plotting_data.drop('Unnamed: 0', axis = 1).rename(columns={0: 'crops'})
l = []
for v in cdl_lookup:
    i = cdl_lookup[v]['crop']
    l.append(i)
crops = set(l)

columns = list(plotting_data.columns)
res = [i for i in columns if any(n in i for n in crops)]

plotting_data['year'] = plotting_data['year'].astype(str)

import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style='whitegrid')  # closest equivalent to theme_bw()

SUBTITLE = 'Note: data pre-2016 are V2.0'
VLINE_COLOR = '#BF131370'

# NOTE: plotnine's xintercept=3.5 only makes sense if 'year' is categorical
# (positions 1, 2, 3, ...), i.e. a line between the 3rd and 4th year.
# Matplotlib/seaborn categorical axes are 0-indexed, so the same spot is 2.5.
# If 'year' is numeric in your data, set DEV_X to the actual x value instead.
DEV_X = 2.5
TEXT_X = DEV_X + 0.1

# ---------------------------------------------------------------- reshape
et_volume = plotting_data.melt(id_vars='year',
                               value_vars=['grass_et', 'crops_et', 'et_sum'],
                               var_name='et_cover', value_name='et_acre-feet')

area = plotting_data.melt(id_vars=['year'],
                          value_vars=['area_sum', 'grass_acres', 'crop_acres'],
                          var_name='area', value_name='acre')

rate = plotting_data.melt(id_vars=['year'],
                          value_vars=['grass_et_depth', 'crops_et_depth', 'average_et_rate'],
                          var_name='et_depth', value_name='depth')

etof = plotting_data.melt(id_vars=['year'],
                          value_vars=['grass_etof', 'crops_etof', 'average_etof'],
                          var_name='etof', value_name='etof_val')

# Replace raw column names with legend labels, and make y numeric
# (float64 instead of float16 to avoid precision loss).
et_volume['et_cover'] = et_volume['et_cover'].map(
    {'crops_et': 'Crops', 'et_sum': 'Sum', 'grass_et': 'Grass'})
area['area'] = area['area'].map(
    {'area_sum': 'Summed Acres', 'crop_acres': 'Crops Acres', 'grass_acres': 'Grass Acres'})
rate['et_depth'] = rate['et_depth'].map(
    {'average_et_rate': 'Weighted Avg', 'crops_et_depth': 'Crops ET Rate', 'grass_et_depth': 'Grass ET Rate'})
etof['etof'] = etof['etof'].map(
    {'average_etof': 'Average EToF', 'crops_etof': 'Crops EToF', 'grass_etof': 'Grass EToF'})

et_volume['et_acre-feet'] = et_volume['et_acre-feet'].astype(float)
area['acre'] = area['acre'].astype(float)
rate['depth'] = rate['depth'].astype(float)
etof['etof_val'] = etof['etof_val'].astype(float)


# ---------------------------------------------------------------- helper
def line_plot(data, y, title, ylabel, text_y, hue=None, palette=None,
              color=None, linestyle='-', subtitle=None, ylim=None):
    fig, ax = plt.subplots(figsize=(9, 5))

    if hue:
        sns.lineplot(data=data, x='year', y=y, hue=hue,
                     hue_order=list(palette), palette=palette,
                     linestyle=linestyle, ax=ax)
        # ggplot-style legend: outside right, no title
        sns.move_legend(ax, 'center left', bbox_to_anchor=(1.01, 0.5), title=None)
    else:
        sns.lineplot(data=data, x='year', y=y, color=color,
                     linestyle=linestyle, ax=ax)

    # "Development starts" marker
    ax.axvline(DEV_X, color=VLINE_COLOR, linestyle=':')
    ax.text(TEXT_X, text_y, 'Development starts', rotation=270,
            va='center', ha='left')

    # Title + optional subtitle (left-aligned, like ggplot)
    ax.set_title(title, loc='left', pad=22 if subtitle else 6, fontweight='bold')
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color='gray')

    ax.set_xlabel('year')
    ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)

    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------- plots
# Palette dict order = legend order (matches plotnine's alphabetical order)
et_vol_fig, _ = line_plot(
    et_volume, y='et_acre-feet', hue='et_cover',
    palette={'Crops': 'red', 'Sum': '#F5A11D', 'Grass': 'green'},
    title=f'Acre feet of ET by landcover from Ensemble vers {et_version}',
    ylabel='Acre feet', subtitle=SUBTITLE, text_y=225)

area_fig, _ = line_plot(
    area, y='acre', hue='area',
    palette={'Summed Acres': '#F5A11D', 'Crops Acres': 'red', 'Grass Acres': 'green'},
    title='Irrigated Area', ylabel='Acres', subtitle=SUBTITLE,
    linestyle='--', text_y=150)

et_rate_fig, _ = line_plot(
    rate, y='depth', hue='et_depth',
    palette={'Weighted Avg': '#F5A11D', 'Crops ET Rate': 'red', 'Grass ET Rate': 'green'},
    title=f'ET Rate from Ensemble vers {et_version}', ylabel='Feet',
    subtitle=SUBTITLE, text_y=0.5)

plotting_data['grass_eto'] = plotting_data['grass_eto'].astype(float)
eto_fig, _ = line_plot(
    plotting_data, y='grass_eto', color='blue',
    title='ETo', ylabel='Feet', text_y=2, ylim=(0, 4))

etof_fig, _ = line_plot(
    etof, y='etof_val', hue='etof',
    palette={'Average EToF': '#F5A11D', 'Crops EToF': 'red', 'Grass EToF': 'green'},
    title=f'EToF from Ensemble vers {et_version}', ylabel='EToF',
    subtitle=SUBTITLE, text_y=0.6)

plt.show()

shp = gpd.read_file(r"P:\AMoody\_Mason\DryCreek_AOI.gpkg", layer='POU Merge')
neighborhood = gpd.read_file(r'C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\dryCreek\neighborhood_2023.shp')
naip_2017= r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\naip_dry_creek_2017_clipped.tif"
naip_2023= r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\naip_dry_creek_2023.tif"

with rio.open(naip_2017) as src:
    dat_2017, _ = mask(src, shp.geometry, crop = True, nodata = 900)
    red_2017 = dat_2017[2]
    nir_2017 = dat_2017[3]
    meta_2017 = src.meta
    ndvi_2017 = (nir_2017 - red_2017)/(nir_2017 + red_2017)
    

with rio.open(naip_2023) as src:
    dat_2023, _ = mask(src, shp.geometry, crop = True, nodata = 0)
    meta_2023 = src.meta
    red_2023 = dat_2023[2].astype('float32')
    red_2023 = np.where(red_2023==0, 900, red_2023)
    nir_2023 = dat_2023[3].astype('float32')
    nir_2023 = np.where(nir_2023==0, 900, nir_2023)
    ndvi_2023 = (nir_2023 - red_2023)/(nir_2023 + red_2023)


irr_area_2017 = r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\dryCreek\dry_creek_2017_irrigation_masked.tif"
irr_area_2023 = r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\dryCreek\dry_creek_2023_irrigation_masked_clip.tif"

with rio.open(irr_area_2017) as src:
    area, _ = mask(src, shp.geometry, nodata=3, crop = True)
    neighborhood_area, _ = mask(src, neighborhood.geometry, nodata=3, crop = True)
    area_2017 = np.where(area[0]==3, 0, area[0])
    neighborhood_area_2017 = np.where(neighborhood_area[0]==3, 0, neighborhood_area[0])
    meta_2017 = src.meta
    count = np.count_nonzero(area_2017)
    yards_count = np.count_nonzero(neighborhood_area_2017)
    irr_area_km_2017 = count*0.36/1e6
    irr_area_acre_2017 = count*0.36/4047
    neigh_irr_area_km_2017 = yards_count*0.36/1e6
    neigh_irr_area_acre_2017 = yards_count*0.36/4047

    irr_area_2017_shape = ((shape(s), v) for s, v in shapes(area_2017, transform = src.transform))
    irr_area_2017_gdf = gpd.GeoDataFrame(dict(zip(['geometry', 'class'], zip(*irr_area_2017_shape))), crs = src.crs)


with rio.open(irr_area_2023) as src:
    area, _ = mask(src, shp.geometry, nodata=3, crop = True)
    neighborhood_area, _ = mask(src, neighborhood.geometry, nodata=3, crop = True)
    area_2023 = np.where(area[0]==3, 0, area[0])
    neighborhood_area_2023 = np.where(neighborhood_area[0]==3, 0, neighborhood_area[0])
    meta_2023 = src.meta
    count = np.count_nonzero(area_2023)
    yards_count = np.count_nonzero(neighborhood_area_2023)
    irr_area_km_2023 = count*0.36/1e6
    irr_area_acre_2023 = count*0.36/4047
    neigh_irr_area_km_2023 = yards_count*0.36/1e6
    neigh_irr_area_acre_2023 = yards_count*0.36/4047

    irr_area_2023_shape = ((shape(s), v) for s, v in shapes(area_2023, transform = src.transform))
    irr_area_2023_gdf = gpd.GeoDataFrame(dict(zip(['geometry', 'class'], zip(*irr_area_2023_shape))), crs = src.crs)

irr_area_dict = {'2017': {'gdf': irr_area_2017_gdf, 
                          'area': irr_area_acre_2017},
                 '2023': {'gdf': irr_area_2023_gdf,
                          'area': irr_area_acre_2023}}
irr_area_ndvi_2017 = np.pad(area_2017, pad_width=((1,0), (0,0)), mode='constant',constant_values=(0,0)) * ndvi_2017
irr_area_ndvi_2023 = np.pad(area_2023, pad_width=((1,0), (0,0)), mode='constant',constant_values=(0,0)) * ndvi_2023

sns.set_theme(style = 'white') #remove the gridlines created in earlier steps

plt.imshow(ndvi_2017, cmap = 'RdYlGn', vmin = -1, vmax = 1)
plt.title('2017 NDVI')
plt.colorbar()
plt.show()

plt.imshow(ndvi_2023, cmap = 'RdYlGn', vmin = -1, vmax = 1)
plt.title('2023 NDVI')
plt.colorbar()
plt.show()

plt.imshow(irr_area_ndvi_2017, cmap = 'RdYlGn', vmin = -1, vmax = 1)
plt.title('2017 NDVI of Irrigated Area')
plt.colorbar()
plt.show()

plt.imshow(irr_area_ndvi_2023, cmap = 'RdYlGn', vmin = -1, vmax = 1)
plt.title('2023 NDVI of Irrigated Area')
plt.colorbar()
plt.show()


print(f'Mean ndvi of the whole area 2017: {ndvi_2017.mean()}')
print(f'Mean ndvi of the whole area 2023: {ndvi_2023.mean()}')

print(f'\nMean ndvi of the irrigated area 2017: {irr_area_ndvi_2017.mean()}')
print(f'Mean ndvi of the irrigated area 2023: {irr_area_ndvi_2023.mean()}')

print(f'\nIrrigated Area acres 2017: {irr_area_acre_2017}')
print(f'Irrigated Area sqkm 2017: {irr_area_km_2017}')

print(f'\nIrrigated Area acres 2023: {irr_area_acre_2023}')
print(f'Irrigated Area sqkm 2023: {irr_area_km_2023}')

print(f'\nNeighborhood Irrigated Area acres 2017: {neigh_irr_area_acre_2017}')#367.98 acft if we take the mean ET of irrigated area in this polygon
print(f'Neighborhood Irrigated Area sqkm 2017: {neigh_irr_area_km_2017}')

print(f'\nNeighborhood Irrigated Area acres 2023: {neigh_irr_area_acre_2023}')
print(f'Neighborhood Irrigated Area sqkm 2023: {neigh_irr_area_km_2023}') #127.3 acft if mean grass ET is 704.5 mm for the growing season

output_dictionary = {'2017': {'ndvi_array':ndvi_2017, 
                              'irr_area_ndvi_array': irr_area_ndvi_2017, 
                              'irr_area_km': irr_area_km_2017,
                              'neigh_irr_area_km': neigh_irr_area_km_2017,},
                    '2023': {'ndvi_array':ndvi_2023, 
                              'irr_area_ndvi_array': irr_area_ndvi_2023, 
                              'irr_area_km': irr_area_km_2023,
                              'neigh_irr_area_km': neigh_irr_area_km_2023,},
                    'et_vol_plot':et_vol_fig,
                    'area_plot': area_fig,
                    'et_rate_plot': et_rate_fig,
                    'eto_plot': eto_fig,
                    'etof_plot': etof_fig
                    }

def pack():
    return output_dictionary
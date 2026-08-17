'''
A script to calculate ET trends over time via OpenET Ensemble and NLCD data. This is an improvment upon the code entire_tv_et_trends.py
This will do the calculations and create a basic report as a word doc (hopefully)
'''
#%%set up cell, no calculations
import rasterio
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
import re
from numpy import zeros
from matplotlib.ticker import FuncFormatter

ee.Authenticate()
ee.Initialize(project= 'idwr-450722')
ee.data.setWorkloadTag('tv-et-trends')

#cdl data don't start in the TV until 2005
years_of_interest = list(range(2005, 2025))

et_version = 2.0
et_options = {2.0 : ['v2_0', '2.0'],
              2.1 : ['v2_1', '2.1']}

aoi_path = r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\TV_and_MH_outline_union.shp"
aoi = gpd.read_file(aoi_path).to_crs('EPSG:8826')
aoi_ee = geemap.gdf_to_ee(aoi)

et = ee.ImageCollection(f"projects/openet/assets/ensemble/conus/gridmet/monthly/{et_options[et_version][0]}").filterBounds(aoi_ee).select('et_ensemble_mad')
eto = ee.ImageCollection(f"projects/openet/assets/reference_et/conus/gridmet/daily/v1").filterBounds(aoi_ee).select('eto')
cdl = ee.ImageCollection("USDA/NASS/CDL").filterBounds(aoi_ee).select('cropland')

#the mask for cdl is set up in 3 stages, minimal, medial, and agressive
#water is only masking out water, wetlands, and barren,
#forest is masking water, wetlands, barren, and forest 
#Desert is masking all of the above and desert areas
#all is masking everything that is not a crop
water = [0, 81, 83, 87, 88, 92, 111, 112, 190, 195]
forest = [0, 63, 81, 83, 87, 88, 92, 111, 112, 141, 142, 143, 190, 195]
desert = [0, 63, 64, 65, 81, 83, 87, 88, 92, 111, 112, 131, 141, 142, 143, 152, 176, 190, 195]
all = [0, 63, 64, 65, 81, 82, 83, 87, 88, 92, 111, 112, 121, 122, 123, 124, 131, 141, 142, 143, 152, 176, 190, 195]

#these masks filter out pixels across all images to return a masked image. ie., the water mask looks at all images 
#from 2000 to 2025 and masks out pixels that are water in ANY of the images, returning a single mask image
cdl_water_mask = cdl.map(lambda img: ee.Image(img).remap(water, [0]*len(water), 1)).sum().selfMask()

cdl_forest_mask = cdl.map(lambda img: ee.Image(img).remap(forest, [0]*len(forest), 1)).sum().selfMask()

cdl_desert_mask = cdl.map(lambda img: ee.Image(img).remap(desert, [0]*len(desert), 1)).sum().selfMask()

cdl_all_mask = cdl.map(lambda img: ee.Image(img).remap(all, [0]*len(all), 1)).sum().selfMask()

#a dictionary of values and colors for the cdl
cdl_lookup = json.load(open(r'C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\cdl_lookup.txt'))

#%%
#get data for ET and ETo
years_ee = ee.List(years_of_interest)

#function to unpack some dictionaries later
def unpackDict(di):
    keys = ee.Dictionary(di).keys()
    metric = keys.filter(ee.Filter.stringContains('item', 'crop').Not()).get(0)
    crop = ee.Dictionary(di).get('cropland')
    value = ee.Dictionary(di).get(metric)
    return ee.Dictionary([ee.String(crop), value])

#function to get growing season mean ET for each year over the aoi
def calculateET(year):
    year_str = ee.Number(year).format('%04d')
    filter_dates = ee.List([year_str.cat('-04-01'), year_str.cat('-11-01')])
    growing_season_cumm_et = et.filterDate(filter_dates.get(0), filter_dates.get(1)).sum()
    growing_season_cumm_eto = eto.filterDate(filter_dates.get(0), filter_dates.get(1)).sum()

    et_water_masked  = ee.Image(growing_season_cumm_et).updateMask(cdl_water_mask).rename(ee.String('et_water'))
    et_desert_masked = ee.Image(growing_season_cumm_et).updateMask(cdl_desert_mask).rename(ee.String('et_desert'))
    et_all_masked    = ee.Image(growing_season_cumm_et).updateMask(cdl_all_mask).rename(ee.String('et_all'))
    et_img = et_water_masked.addBands([et_desert_masked, et_all_masked])
    et_reductions = et_img.reduceRegion(reducer=ee.Reducer.mean(),
                                        geometry=aoi_ee.geometry(),
                                        scale=30,
                                        crs='EPSG:8826',
                                        maxPixels=3e7)
    
    eto_water_masked  = ee.Image(growing_season_cumm_eto).updateMask(cdl_water_mask).rename(ee.String('eto_water'))
    eto_desert_masked = ee.Image(growing_season_cumm_eto).updateMask(cdl_desert_mask).rename(ee.String('eto_desert'))
    eto_all_masked    = ee.Image(growing_season_cumm_eto).updateMask(cdl_all_mask).rename(ee.String('eto_all'))
    eto_img = eto_water_masked.addBands([eto_desert_masked, eto_all_masked])
    eto_reductions = eto_img.reduceRegion(reducer=ee.Reducer.mean(),
                                        geometry=aoi_ee.geometry(),
                                        scale=30,
                                        crs='EPSG:8826',
                                        maxPixels=3e7)

    #now get landcover area per crop and crop et
    cdl_img = ee.ImageCollection(cdl.filterDate(year_str)).first()

    et_lc_img = ee.Image(growing_season_cumm_et).addBands(cdl_img)

    lc_et_reducer = ee.Reducer.mean().group(groupField= 1, groupName='cropland')
    lc_area_reducer = ee.Reducer.count().group(groupField= 1, groupName='cropland')
    lc_et = ee.Image(et_lc_img).reduceRegion(reducer= lc_et_reducer.combine(
                                                                      lc_area_reducer, 
                                                                      outputPrefix='area', 
                                                                      sharedInputs=True),
                                       geometry=aoi_ee.geometry(),
                                       scale=30,
                                       crs='EPSG:8826',
                                       maxPixels=3e7)
    crop_area = lc_et.get('areagroups')
    crop_et = lc_et.get('groups')
    crop_et_dict = ee.List(crop_et).map(unpackDict)
    crop_area_dict = ee.List(crop_area).map(unpackDict)
        
    return ee.Feature(None, {'year': year, 'crop_area': crop_area_dict, 'crop_et': crop_et_dict,
                             'et_water': et_reductions.get('et_water'), 'et_desert': et_reductions.get('et_desert'), 'et_all': et_reductions.get('et_all'), 
                             'eto_water': eto_reductions.get('eto_water'), 'eto_desert': eto_reductions.get('eto_desert'), 'eto_all': eto_reductions.get('eto_all'),
                             })

entire_aoi_et_values = ee.FeatureCollection(years_ee.map(calculateET))

#there has to be an export here because the reductions are so large
ee.batch.Export.table.toDrive(collection=entire_aoi_et_values,
                              description='tv_et_lc_trends_export',
                              fileNamePrefix='tv_et_lc_trends',
                              )#.start() #this gets commented out as a failsafe to not accidentally export the csv 

#%%
#getting the csv into the format we want before plotting
et_data = pd.read_csv(r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\et_trends\tv_et_lc_trends.csv")
et_data = et_data.drop(columns=['.geo', 'system:index'])

#this gets us a row id to separate lines on instead of a year, incase there is an empty year
et_data = et_data.reset_index(drop = True).rename_axis('row_id').reset_index()

#the expression that is in each string that gets output by the EE export
et_expression = re.compile(r'(\w+)=([\d$.]+)')

#function to find area or et values by crop, organize them, and neatly store them in a dataframe
def parse_metrics(metric):
    column_name = f'crop_{metric}'

    items = [(row_id, int(k), float(v))
             for row_id, s in zip(et_data['row_id'], et_data[column_name])
             for k, v in et_expression.findall(s)]
    return pd.DataFrame(items, columns = ['row_id', 'crop_code', column_name])

et_long = parse_metrics('et')
area_long = parse_metrics('area')

#combine the crop type dfs and add a column for crop name and color code
crop_long = et_long.merge(area_long, on = ['row_id', 'crop_code'], how = 'outer')
crop_long['crop'] = crop_long['crop_code'].map(lambda c: cdl_lookup.get(str(c), {}).get('crop', f'unknown_{c}'))
crop_long['color_code'] = crop_long['crop_code'].map(lambda c: cdl_lookup.get(str(c), {}).get('color', f'unknown_{c}'))

columns_to_pivot = et_data[['row_id', 'year', 'et_all', 'et_water', 'et_desert', 'eto_all', 'eto_water', 'eto_desert']]

#use a single pivot to get the data to a long format without having to stack up melt arguments
filters_long = pd.wide_to_long(columns_to_pivot, stubnames=['et', 'eto'], i='row_id', 
                               j = 'filter', sep='_', suffix=(r'\w+')).reset_index()

#finalize and add new columns we want
df_final = crop_long.merge(filters_long, on='row_id', how='inner')
df_final['et_of'] = df_final['et']/df_final['eto']
df_final['year'] = df_final['year'].astype(int)
df_final['crop_area'] = df_final['crop_area']*9e-4
for i in ['Water', 'Clouds/No Data', 'Grass/Pasture', 'Shrubland', 'Open Water', 'Perennial Ice/Snow',
          'Forest', 'Developed', 'Deciduous Forest', 'Evergreen Forest', 'Woody Wetlands', 'Herbaceous Wetlands'
          'Mixed Forest', 'Wetlands']: #pick lc types to exclude from plotting
    df_final = df_final[df_final.crop != i]

#make a palette for plotting crop types
palette = {}
for k in cdl_lookup:
    palette.update({cdl_lookup[k]['crop']:cdl_lookup[k]['color']})
#%%

#plotting

#plot of ET depth 
fig, ax = plt.subplots()
sns.lineplot(data=df_final, x = 'year', y = 'et', hue='filter')
ax.set_title('Treasure Valley ET')
ax.set_xlim(2005, 2025)
ax.set_ylabel('ET (mm)')
ax.set_xlabel('Year')
ax.legend(title = None, loc = 'center right')
plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x,_: int(x)))
fig.show()

#plot of ETo
fig, ax = plt.subplots()
sns.lineplot(data=df_final, x = 'year', y = 'eto', hue='filter')
ax.set_title('Treasure Valley ETo')
ax.set_xlim(2005, 2025)
ax.set_ylabel('ETo (mm)')
ax.set_xlabel('Year')
ax.legend(title = None, loc = 'lower right')
plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x,_: int(x)))
fig.show()

#plot of EToF
fig, ax = plt.subplots()
sns.lineplot(data=df_final, x = 'year', y = 'et_of', hue='filter')
ax.set_title('Treasure Valley EToF')
ax.set_xlim(2005, 2025)
ax.set_ylabel('EToF')
ax.set_xlabel('Year')
ax.legend(title = None, loc = 'lower right')
plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x,_: int(x)))
fig.show()

#plot of area for each crop 
fig, ax = plt.subplots()
sns.lineplot(data = df_final, x = 'year', y = 'crop_area', palette= palette, hue = 'crop')
ax.set_xlim(2005, 2024)
ax.set_title('Area per crop')
ax.set_ylabel('Area (km²)')
ax.set_xlabel('Year')
ax.legend(title = None)
sns.move_legend(ax, 'upper center', bbox_to_anchor = (0.5,-0.1), ncols = 3)
plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x,_: int(x)))
fig.show()

#plot of ET for each crop 
fig, ax = plt.subplots()
sns.lineplot(data = df_final, x = 'year', y = 'crop_et', palette= palette, hue = 'crop')
ax.set_xlim(2005, 2025)
ax.set_title('ET depth per crop')
ax.set_ylabel('Depth (mm)')
ax.set_xlabel('Year')
ax.legend(title = None)
sns.move_legend(ax, 'upper center', bbox_to_anchor = (0.5,-0.1), ncols = 3)
plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x,_: int(x)))
fig.show()
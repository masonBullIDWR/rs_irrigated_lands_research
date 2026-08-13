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
from numpy import zeros

ee.Authenticate()
ee.Initialize(project= 'idwr-450722')
ee.data.setWorkloadTag('tv-et-trends')

years_of_interest = list(range(2000, 2026))

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
years_ee = ee.List(years_of_interest)
#function to get growing season mean ET for each year over the aoi
def calculateET(year):
    year_str = ee.Number(year).format('%04d')
    filter_dates = ee.List([year_str.cat('-04-01'), year_str.cat('-11-01')])
    growing_season_cumm_et = et.filterDate(filter_dates.get(0), filter_dates.get(1)).sum()
    growing_season_cumm_eto = eto.filterDate(filter_dates.get(0), filter_dates.get(1)).sum()

    et_water_masked  = ee.Image(growing_season_cumm_et).updateMask(cdl_water_mask).rename(ee.String('et_water_').cat(year_str))
    et_desert_masked = ee.Image(growing_season_cumm_et).updateMask(cdl_desert_mask).rename(ee.String('et_desert_').cat(year_str))
    et_all_masked    = ee.Image(growing_season_cumm_et).updateMask(cdl_all_mask).rename(ee.String('et_all_').cat(year_str))
    et_imgs = ee.List([et_water_masked, et_desert_masked, et_all_masked]).map(lambda img: ee.Image(img).reduceRegion(
                                                                                    reducer=ee.Reducer.mean(),
                                                                                    geometry=aoi_ee.geometry(),
                                                                                    scale=30,
                                                                                    crs='EPSG:8826'))

    eto_water_masked  = ee.Image(growing_season_cumm_eto).updateMask(cdl_water_mask).rename(ee.String('eto_water_').cat(year_str))
    eto_desert_masked = ee.Image(growing_season_cumm_eto).updateMask(cdl_desert_mask).rename(ee.String('eto_desert_').cat(year_str))
    eto_all_masked    = ee.Image(growing_season_cumm_eto).updateMask(cdl_all_mask).rename(ee.String('eto_all_').cat(year_str))
    eto_imgs = ee.List([eto_water_masked, eto_desert_masked, eto_all_masked]).map(lambda img: ee.Image(img).reduceRegion(
                                                                                    reducer=ee.Reducer.mean(),
                                                                                    geometry=aoi_ee.geometry(),
                                                                                    scale=30,
                                                                                    crs='EPSG:8826'))
    
    return ee.Feature(None, {'et': [et_imgs, eto_imgs]})

entire_aoi_et_values = ee.FeatureCollection(years_ee.map(calculateET))

ee.batch.Export.table.toDrive(collection=entire_aoi_et_values,
                              description='tv_et_trends_export',
                              fileNamePrefix='tv_et_trends',
                              ).start()
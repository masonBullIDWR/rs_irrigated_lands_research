#%%
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

import ee, geemap
ee.Authenticate()
ee.Initialize(project= 'idwr-450722')
ee.data.setWorkloadTag('dry-creek-et')

et_version = 'v2_1'

et = ee.ImageCollection(f"projects/openet/assets/ensemble/conus/gridmet/monthly/{et_version}")
eto = ee.ImageCollection(f"projects/openet/assets/reference_et/conus/gridmet/daily/v1")

dc_center = ee.Geometry.Point([-116.290277075344,43.73373080477343])

aoi_path = r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\dryCreek\DryCreek_AOI.gpkg"
aoi = gpd.read_file(aoi_path, layer = 'POU Merge', columns=['geometry']).to_crs('EPSG:8826')

output_dict = {}
#%%
if et_version == 'v2_1':
    years = list(range(2015, 2026, 2))
else:
    years = list(range(2013, 2023, 2))
for y in years:
    year = str(y)

    dev_mask_path =     f"C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Data/TV/dryCreek/segmentation/developement_mask_{year}.shp"
    segmentation_path = f"C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Data/TV/dryCreek/segmentation/dry_creek_segmented_merge_{year}.tif"
    irr_mask_path =     f"C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Data/TV/dryCreek/segmentation/irr_mask_{year}.shp"

    #get the irrigation mask onto the classification raster 
    dev_mask = gpd.read_file(dev_mask_path).to_crs('EPSG:8826').clip(aoi)
    irr_mask = gpd.read_file(irr_mask_path).to_crs('EPSG:8826').clip(aoi)
    valid_geom = irr_mask['geometry'].make_valid(method='linework')
    irr_mask['geometry'] = valid_geom

    with rasterio.open(segmentation_path, 'r') as src:
        meta = src.meta
        dat, _ = mask(src, aoi.geometry, crop = False, pad = True, nodata = 3)
        irr_mask_arr = rasterize(shapes = zip(irr_mask['geometry'], irr_mask['class']), out = dat[0],
                             fill = 3, nodata= 3, transform= meta['transform'], dtype= 'uint8',
                             skip_invalid=False, masked=False)


    #get the area of irrigation in urban areas with the developed mask
    urban_mask = rasterio.features.geometry_mask(dev_mask.geometry, out_shape = (meta['height'], meta['width']), 
                                                transform = meta['transform'])

    ag_mask = rasterio.features.geometry_mask(dev_mask.geometry, out_shape = (meta['height'], meta['width']), 
                                                transform = meta['transform'], invert = True)

    developed_area = ma.masked_array(irr_mask_arr, mask=urban_mask)
    ag_area = ma.masked_greater(ma.masked_array(irr_mask_arr, mask=ag_mask, dtype='int16'), 1)

    dev_pixels = developed_area.sum()
    dev_acres = dev_pixels*0.36/4047

    ag_pixels = ag_area.sum()
    ag_acres = ag_pixels*0.36/4047

    ag_shp_generator = ((shape(s), v) for s, v in shapes(ag_area, transform=meta['transform']))
    df = pd.DataFrame(ag_shp_generator, columns = ['geometry', 'class'])
    ag_gdf = gpd.GeoDataFrame(df['class'], geometry=df['geometry'], crs = 'EPSG:8826')


    #calculate ET based on the areas calculated above
    col = et.filterBounds(dc_center).filterDate(f'{year}-04-01', f'{year}-11-01').select('et_ensemble_mad').sum()
    eto_col = eto.filterBounds(dc_center).filterDate(f'{year}-04-01', f'{year}-11-01').select('eto').sum()

    grass_points = ee.Geometry.MultiPoint([[-116.14435810786225,43.54677968549953],
                                     [-116.21768552820251,43.60910023895453],
                                     [-116.27675057273248,43.65463002404425],
                                     [-116.19923565143907,43.65063111241265]])

    ag_fc = geemap.gdf_to_ee(ag_gdf)

    avg_grass_et_reduction = col.reduceRegions(reducer = ee.Reducer.mean(),
                                   collection = grass_points,
                                   crs= 'EPSG:8826',
                                   scale = 30)

    avg_crop_et_reduction = col.reduceRegion(reducer = ee.Reducer.mean(),
                                   geometry = ag_fc,
                                   crs= 'EPSG:8826',
                                   scale = 30)
    
    avg_grass_eto_reduction = eto_col.reduceRegions(reducer = ee.Reducer.mean(),
                                   collection = grass_points,
                                   crs= 'EPSG:8826',
                                   scale = 30)

    avg_crop_eto_reduction = eto_col.reduceRegion(reducer = ee.Reducer.mean(),
                                   geometry = ag_fc,
                                   crs= 'EPSG:8826',
                                   scale = 30)

    grass_et = ee.Number(avg_grass_et_reduction.first().get('mean')).divide(304.8).multiply(dev_acres) #get acre feet of ET over irrigated area
    crop_et = ee.Number(avg_crop_et_reduction.get('et_ensemble_mad')).divide(304.8).multiply(ag_acres)
    grass_eto = ee.Number(avg_grass_eto_reduction.first().get('mean'))
    crop_eto = ee.Number(avg_crop_eto_reduction.get('eto'))

    et_dict = ee.Dictionary({'grass_et': grass_et,
                             'crops_et': crop_et,
                             'grass_eto': grass_eto,
                             'crop_eto': crop_eto}).getInfo()

    output_dict.update({year: {'grass_et': et_dict['grass_et'],
                               'crops_et': et_dict['crops_et'],
                               'grass_eto': et_dict['grass_eto'],
                               'crop_eto': et_dict['crop_eto'],
                               'grass_acres': dev_acres,
                               'crop_acres': ag_acres}})

    print(f'Acres of Grass in {year}: {dev_acres}\nGrass ET for {year}: {et_dict['grass_et']}\n\nAcres of Crops in {year}: {ag_acres}\nCropland ET for {year}: {et_dict['crops_et']}\n\n')

#%%
from plotnine import *

plotting_data = pd.DataFrame(output_dict).transpose().reset_index().rename(columns={'index': 'year'})

plotting_data['et_sum'] = plotting_data['grass_et'] + plotting_data['crops_et']

plotting_data['grass_eto']=plotting_data['grass_eto']/304.8
plotting_data['crop_eto']=plotting_data['crop_eto']/304.8

plotting_data['grass_et_depth'] = plotting_data['grass_et']/plotting_data['grass_acres']
plotting_data['crops_et_depth'] = plotting_data['crops_et']/plotting_data['crop_acres']

plotting_data['grass_etof'] = plotting_data['grass_et_depth']/plotting_data['grass_eto']
plotting_data['crops_etof'] = plotting_data['crops_et_depth']/plotting_data['crop_eto']

et_volume = plotting_data.melt(id_vars=['year', 'et_sum'],
                                       value_vars=['grass_et', 'crops_et'],
                                       var_name='et_cover', value_name='et_acre-feet')

area = plotting_data.melt(id_vars=['year'], 
                                  value_vars=['grass_acres', 'crop_acres'], 
                                  var_name='area', value_name='acre')

rate = plotting_data.melt(id_vars=['year'], 
                                  value_vars=['grass_et_depth', 'crops_et_depth'], 
                                  var_name='et_depth', value_name='depth')

etof = plotting_data.melt(id_vars=['year'], 
                                  value_vars=['grass_etof', 'crops_etof'], 
                                  var_name='etof', value_name='etof_val')

et_vol_plot = (ggplot(et_volume, aes(x = 'year')) + 
      geom_line(aes(y = 'et_acre-feet', group = 'et_cover', color = 'et_cover')) +
      geom_line(aes(y = 'et_sum', group = 1), color = '#0BA11870', linetype = 'dotted') +
      labs(title=f'Acre feet of ET by landcover from Ensemble vers {et_version}', y = 'Acre feet')+
      geom_vline(xintercept = 2.5, color = '#BF131370', linetype = 'dotted') +
      annotate('text', label = 'Development starts', x = 2.6, y = 225, angle = 270) +
      theme_bw())

area_plot = (ggplot(area, aes(x = 'year')) + 
        geom_line(aes(y = 'acre', group = 'area', color = 'area'), linetype = 'dashed') +
        labs(title='Irrigated Area', y = 'Acres')+
      geom_vline(xintercept = 2.5, color = '#BF131370', linetype = 'dotted') +
      annotate('text', label = 'Development starts', x = 2.6, y = 150, angle = 270) +
        theme_bw())

et_rate_plot = (ggplot(rate, aes(x = 'year')) + 
        geom_line(aes(y = 'depth', group = 'et_depth', color = 'et_depth'), linetype = 'solid') +
        labs(title=f'ET Rate from Ensemble vers {et_version}', y = 'Feet')+
      geom_vline(xintercept = 2.5, color = '#BF131370', linetype = 'dotted') +
      annotate('text', label = 'Development starts', x = 2.6, y = .75, angle = 270) +
        theme_bw())

eto_plot = (ggplot(plotting_data, aes(x = 'year')) + 
        geom_line(aes(y = 'grass_eto', group = 1), color = 'blue', linetype = 'solid') +
        labs(title=f'ETo', y = 'Feet')+
      geom_vline(xintercept = 2.5, color = '#BF131370', linetype = 'dotted') +
      annotate('text', label = 'Development starts', x = 2.6, y = 2, angle = 270) +
      scale_y_continuous(limits = (0, 4)) +
        theme_bw())

etof_plot = (ggplot(etof, aes(x = 'year')) + 
        geom_line(aes(y = 'etof_val', group = 'etof', color = 'etof'), linetype = 'solid') +
        labs(title=f'EToF from Ensemble vers {et_version}', y = 'EToF')+
        geom_vline(xintercept = 2.5, color = '#BF131370', linetype = 'dotted') +
        annotate('text', label = 'Development starts', x = 2.6, y = 0.3, angle = 270) +
        theme_bw())

et_vol_plot.show()
area_plot.show()
et_rate_plot.show()
eto_plot.show()
etof_plot.show()

#%%
plotting_data.to_csv(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Data/TV/dryCreek/segmentation/dry_creek_et_data_ensemble_{et_version}.csv')

et_vol_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/et_acre_feet_ensemble_{et_version}.png')
area_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/landcover_area.png')
et_rate_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/et_rate_ensemble_{et_version}.png')
etof_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/etof_ensemble_{et_version}.png')
eto_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/eto_ensemble_{et_version}.png')
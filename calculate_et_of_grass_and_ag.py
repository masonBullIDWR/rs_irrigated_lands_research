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
import seaborn as sns

import ee, geemap
ee.Authenticate()
ee.Initialize(project= 'idwr-450722')
ee.data.setWorkloadTag('dry-creek-et')

et_version = 'v2_1'

et = ee.ImageCollection(f"projects/openet/assets/ensemble/conus/gridmet/monthly/{et_version}")
eto = ee.ImageCollection(f"projects/openet/assets/reference_et/conus/gridmet/daily/v1")
cdl = ee.ImageCollection("USDA/NASS/CDL")

dc_center = ee.Geometry.Point([-116.290277075344,43.73373080477343])

aoi_path = r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\dryCreek\DryCreek_AOI.gpkg"
aoi = gpd.read_file(aoi_path, layer = 'POU Merge', columns=['geometry']).to_crs('EPSG:8826')

output_dict = {}
#%% the cdl lookup table 
cdl_lookup = {
0:  {'color': '#000000', 'crop': 'Background'},
1:  {'color': '#ffd400', 'crop': 'Corn'},
2:  {'color': '#ff2626', 'crop': 'Cotton'},
3:  {'color': '#00a9e6', 'crop': 'Rice'},
4:  {'color': '#ff9e0f', 'crop': 'Sorghum'},
5:  {'color': '#267300', 'crop': 'Soybeans'},
6:  {'color': '#ffff00', 'crop': 'Sunflower'},
10: {'color': '#70a800', 'crop': 'Peanuts'},
11: {'color': '#00af4d', 'crop': 'Tobacco'},
12: {'color': '#e0a60f', 'crop': 'Sweet Corn'},
13: {'color': '#e0a60f', 'crop': 'Pop or Orn Corn'},
14: {'color': '#80d4ff', 'crop': 'Mint'},
21: {'color': '#e2007f', 'crop': 'Barley'},
22: {'color': '#8a6453', 'crop': 'Durum Wheat'},
23: {'color': '#d9b56c', 'crop': 'Spring Wheat'},
24: {'color': '#a87000', 'crop': 'Winter Wheat'},
25: {'color': '#d69dbc', 'crop': 'Other Small Grains'},
26: {'color': '#737300', 'crop': 'Dbl Crop WinWht/Soybeans'},
27: {'color': '#ae017e', 'crop': 'Rye'},
28: {'color': '#a15889', 'crop': 'Oats'},
29: {'color': '#73004c', 'crop': 'Millet'},
30: {'color': '#d69dbc', 'crop': 'Speltz'},
31: {'color': '#d1ff00', 'crop': 'Canola'},
32: {'color': '#8099ff', 'crop': 'Flaxseed'},
33: {'color': '#d6d600', 'crop': 'Safflower'},
34: {'color': '#d1ff00', 'crop': 'Rape Seed'},
35: {'color': '#00af4d', 'crop': 'Mustard'},
36: {'color': '#ffa8e3', 'crop': 'Alfalfa'},
37: {'color': '#a5f58d', 'crop': 'Other Hay/Non Alfalfa'},
38: {'color': '#00af4d', 'crop': 'Camelina'},
39: {'color': '#d69dbc', 'crop': 'Buckwheat'},
41: {'color': '#a900e6', 'crop': 'Sugarbeets'},
42: {'color': '#a80000', 'crop': 'Dry Beans'},
43: {'color': '#732600', 'crop': 'Potatoes'},
44: {'color': '#00af4d', 'crop': 'Other Crops'},
45: {'color': '#b380ff', 'crop': 'Sugarcane'},
46: {'color': '#732600', 'crop': 'Sweet Potatoes'},
47: {'color': '#ff6666', 'crop': 'Misc Vegs & Fruits'},
48: {'color': '#ff6666', 'crop': 'Watermelons'},
49: {'color': '#ffcc66', 'crop': 'Onions'},
50: {'color': '#ff6666', 'crop': 'Cucumbers'},
51: {'color': '#00af4d', 'crop': 'Chick Peas'},
52: {'color': '#00deb0', 'crop': 'Lentils'},
53: {'color': '#55ff00', 'crop': 'Peas'},
54: {'color': '#f5a27a', 'crop': 'Tomatoes'},
55: {'color': '#ff6666', 'crop': 'Caneberries'},
56: {'color': '#00af4d', 'crop': 'Hops'},
57: {'color': '#80d4ff', 'crop': 'Herbs'},
58: {'color': '#e8beff', 'crop': 'Clover/Wildflowers'},
59: {'color': '#b2ffde', 'crop': 'Sod/Grass Seed'},
60: {'color': '#00af4d', 'crop': 'Switchgrass'},
61: {'color': '#bfbf7a', 'crop': 'Fallow/Idle Cropland'},
63: {'color': '#95ce93', 'crop': 'Forest'},
64: {'color': '#c7d79e', 'crop': 'Shrubland'},
65: {'color': '#ccbfa3', 'crop': 'Barren'},
66: {'color': '#ff00ff', 'crop': 'Cherries'},
67: {'color': '#ff91ab', 'crop': 'Peaches'},
68: {'color': '#b90050', 'crop': 'Apples'},
69: {'color': '#704489', 'crop': 'Grapes'},
70: {'color': '#007878', 'crop': 'Christmas Trees'},
71: {'color': '#b39c70', 'crop': 'Other Tree Crops'},
72: {'color': '#ffff80', 'crop': 'Citrus'},
74: {'color': '#b6705c', 'crop': 'Pecans'},
75: {'color': '#00a884', 'crop': 'Almonds'},
76: {'color': '#ebd6b0', 'crop': 'Walnuts'},
77: {'color': '#b39c70', 'crop': 'Pears'},
81: {'color': '#f7f7f7', 'crop': 'Clouds/No Data'},
82: {'color': '#9c9c9c', 'crop': 'Developed'},
83: {'color': '#4d70a3', 'crop': 'Water'},
87: {'color': '#80b3b3', 'crop': 'Wetlands'},
88: {'color': '#e9ffbe', 'crop': 'Nonag/Undefined'},
92: {'color': '#00ffff', 'crop': 'Aquaculture'},
111:{'color': '#4d70a3', 'crop': 'Open Water'},
112:{'color': '#d4e3fc', 'crop': 'Perennial Ice/Snow'},
121:{'color': '#9c9c9c', 'crop': 'Developed/Open Space'},
122:{'color': '#9c9c9c', 'crop': 'Developed/Low Intensity'},
123:{'color': '#9c9c9c', 'crop': 'Developed/Med Intensity'},
124:{'color': '#9c9c9c', 'crop': 'Developed/High Intensity'},
131:{'color': '#ccbfa3', 'crop': 'Barren'},
141:{'color': '#95ce9c', 'crop': 'Deciduous Forest'},
142:{'color': '#95ce9c', 'crop': 'Evergreen Forest'},
143:{'color': '#95ce93', 'crop': 'Mixed Forest'},
152:{'color': '#c7d79e', 'crop': 'Shrubland'},
176:{'color': '#e9ffbe', 'crop': 'Grass/Pasture'},
190:{'color': '#80b3b3', 'crop': 'Woody Wetlands'},
195:{'color': '#80b3b3', 'crop': 'Herbaceous Wetlands'},
204:{'color': '#00ff8c', 'crop': 'Pistachios'},
205:{'color': '#d69dbc', 'crop': 'Triticale'},
206:{'color': '#ff6666', 'crop': 'Carrots'},
207:{'color': '#ff6666', 'crop': 'Asparagus'},
208:{'color': '#ff6666', 'crop': 'Garlic'},
209:{'color': '#ff6666', 'crop': 'Cantaloupes'},
210:{'color': '#ff91ab', 'crop': 'Prunes'},
211:{'color': '#344a34', 'crop': 'Olives'},
212:{'color': '#e67525', 'crop': 'Oranges'},
213:{'color': '#ff6666', 'crop': 'Honeydew Melons'},
214:{'color': '#ff6666', 'crop': 'Broccoli'},
215:{'color': '#66994d', 'crop': 'Avocados'},
216:{'color': '#ff6666', 'crop': 'Peppers'},
217:{'color': '#b39c70', 'crop': 'Pomegranates'},
218:{'color': '#ff91ab', 'crop': 'Nectarines'},
219:{'color': '#ff6666', 'crop': 'Greens'},
220:{'color': '#ff91ab', 'crop': 'Plums'},
221:{'color': '#ff6666', 'crop': 'Strawberries'},
222:{'color': '#ff6666', 'crop': 'Squash'},
223:{'color': '#ff91ab', 'crop': 'Apricots'},
224:{'color': '#00af4d', 'crop': 'Vetch'},
225:{'color': '#ffd400', 'crop': 'Dbl Crop WinWht/Corn'},
226:{'color': '#ffd400', 'crop': 'Dbl Crop Oats/Corn'},
227:{'color': '#ff6666', 'crop': 'Lettuce'},
228:{'color': '#ffd400', 'crop': 'Dbl Crop Triticale/Corn'},
229:{'color': '#ff6666', 'crop': 'Pumpkins'},
230:{'color': '#8a6453', 'crop': 'Dbl Crop Lettuce/Durum Wht'},
231:{'color': '#ff6666', 'crop': 'Dbl Crop Lettuce/Cantaloupe'},
232:{'color': '#ff2626', 'crop': 'Dbl Crop Lettuce/Cotton'},
233:{'color': '#e2007f', 'crop': 'Dbl Crop Lettuce/Barley'},
234:{'color': '#ff9e0f', 'crop': 'Dbl Crop Durum Wht/Sorghum'},
235:{'color': '#ff9e0f', 'crop': 'Dbl Crop Barley/Sorghum'},
236:{'color': '#a87000', 'crop': 'Dbl Crop WinWht/Sorghum'},
237:{'color': '#ffd400', 'crop': 'Dbl Crop Barley/Corn'},
238:{'color': '#a87000', 'crop': 'Dbl Crop WinWht/Cotton'},
239:{'color': '#267300', 'crop': 'Dbl Crop Soybeans/Cotton'},
240:{'color': '#267300', 'crop': 'Dbl Crop Soybeans/Oats'},
241:{'color': '#ffd400', 'crop': 'Dbl Crop Corn/Soybeans'},
242:{'color': '#000099', 'crop': 'Blueberries'},
243:{'color': '#ff6666', 'crop': 'Cabbage'},
244:{'color': '#ff6666', 'crop': 'Cauliflower'},
245:{'color': '#ff6666', 'crop': 'Celery'},
246:{'color': '#ff6666', 'crop': 'Radishes'},
247:{'color': '#ff6666', 'crop': 'Turnips'},
248:{'color': '#ff6666', 'crop': 'Eggplants'},
249:{'color': '#ff6666', 'crop': 'Gourds'},
250:{'color': '#ff6666', 'crop': 'Cranberries'},
254:{'color': '#267300', 'crop': 'Dbl Crop Barley/Soybeans'}}

#%%
#setting up and testing the CDL stuff
years = list(range(2015, 2026, 1))
crop_areas_dict = {}

year = years[-2]
cdl_filt = cdl.filterBounds(dc_center).filterDate(str(year)).select('cropland').first()
non_crop_classes = [0, 81, 82, 83, 87, 88, 92, 111, 112, 121, 122, 123, 124, 131, 141, 142, 143, 152, 176, 190, 195]
values = ee.List.repeat(0, len(non_crop_classes))
non_crop_mask = ee.Image(cdl_filt).remap(non_crop_classes, values, 1).selfMask()
crops_img = ee.Image(cdl_filt).updateMask(non_crop_mask)

region = geemap.gdf_to_ee(aoi)
counts = ee.Dictionary(crops_img.reduceRegion(reducer = ee.Reducer.frequencyHistogram(),
                                geometry= region.geometry(),
                                scale= 30,
                                crs='EPSG:8826').get('cropland')).getInfo()
year_crop_dict = {}
for i in counts:
    crop = cdl_lookup[int(i)]['crop']
    crop_area = counts[i]*(900)/(4046.86)
    year_crop_dict.update({crop: crop_area})
year_crop_dict_filt = {key: value for key, value in year_crop_dict.items() if value > 1}
crop_areas_dict.update({year: year_crop_dict})
#%%
#quick check of ET over the whole study area
avg_aoi_et = {}
avg_aoi_eto = {}
for y in years:
    if int(y) <= 2015:
        et = ee.ImageCollection(f"projects/openet/assets/ensemble/conus/gridmet/monthly/v2_0")
    else:
        et = ee.ImageCollection(f"projects/openet/assets/ensemble/conus/gridmet/monthly/{et_version}")
    eto_col = eto.filterBounds(dc_center).filterDate(f'{y}-04-01', f'{y}-11-01').select('eto').sum()
    dat = et.filterDate(f'{y}-01-01', f'{str(int(y)+1)}-01-01').filterBounds(region).select('et_ensemble_mad').sum()
    avg = ee.Number(ee.Image(dat).reduceRegion(reducer=ee.Reducer.mean(),
                                     geometry=region.geometry(),
                                     scale=30,
                                     crs='EPSG:8826').get('et_ensemble_mad')).divide(304.8).getInfo()
    avg_eto = ee.Number(ee.Image(eto_col).reduceRegion(reducer=ee.Reducer.mean(),
                                     geometry=region.geometry(),
                                     scale=30,
                                     crs='EPSG:8826').get('eto')).divide(304.8).getInfo()
    avg_aoi_et.update({y:avg})
    avg_aoi_eto.update({y:avg_eto})

df = pd.DataFrame.from_dict(avg_aoi_et, orient='index', columns=['et_rate'])
area = aoi.area/4046.86
df['acre_feet'] = df['et_rate']*area[0]
fig, ax = plt.subplots()

sns.lineplot(df, x = df.index, y = 'et_rate')
ax.set_xlabel('Year')
ax.set_ylabel('Avg Growing Season ET (feet)')
ax.set_title(f'Avg ET over AOI from {et_version} (data pre 2016 are V2.0)')
plt.show()

df = pd.DataFrame.from_dict(avg_aoi_eto, orient='index', columns=['eto_rate'])

fig, ax = plt.subplots()

sns.lineplot(df, x = df.index, y = 'eto_rate')
ax.set_xlabel('Year')
ax.set_ylabel('Avg Growing Season ETo (feet)')
ax.set_title(f'Avg ETo over AOI from {et_version} (data pre 2016 are V2.0)')
ax.set_ylim(0,4)
plt.show()


#%%
#if you already have run this, you don't need to run it again, skip down to plotting_Data
if et_version == 'v2_1':
    years = list(range(2013, 2026, 2))
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
    if y <= 2015:
        et = ee.ImageCollection(f"projects/openet/assets/ensemble/conus/gridmet/monthly/v2_0")
    else:
        et = ee.ImageCollection(f"projects/openet/assets/ensemble/conus/gridmet/monthly/{et_version}")
    col = et.filterBounds(dc_center).filterDate(f'{year}-04-01', f'{year}-11-01').select('et_ensemble_mad').sum()
    eto_col = eto.filterBounds(dc_center).filterDate(f'{year}-04-01', f'{year}-11-01').select('eto').sum()

    grass_points = ee.Geometry.MultiPoint([[-116.14435810786225,43.54677968549953],
                                           [-116.21768552820251,43.60910023895453],
                                           [-116.27675057273248,43.65463002404425],
                                           [-116.19923565143907,43.65063111241265],
                                           [-116.4305704567148,43.657203441157634],
                                           [-116.39728482613323,43.6365471144574],
                                           [-116.26453158662328,43.67193033547616],
                                           [-116.30936952222483,43.68923563496508],
                                           [-116.32618685742202,43.50128911971363],
                                           [-116.52107413314606,43.6041573300393],
                                           [-116.53673823379303,43.60230828335806],
                                           [-116.67146693545912,43.63667554114842],
                                           [-116.29387470193619,43.746596119069714],
                                           [-116.55862400142448,43.54628442033048]])

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

    cdl_filt = cdl.filterBounds(dc_center).filterDate(year).select('cropland').first()
    non_crop_classes = [0, 81, 82, 83, 87, 88, 92, 111, 112, 121, 122, 123, 124, 131, 141, 142, 143, 152, 176, 190, 195]
    values = ee.List.repeat(0, len(non_crop_classes))
    non_crop_mask = ee.Image(cdl_filt).remap(non_crop_classes, values, 1).selfMask()
    crops_img = ee.Image(cdl_filt).updateMask(non_crop_mask)
    
    region = geemap.gdf_to_ee(aoi)
    counts = ee.Dictionary(crops_img.reduceRegion(reducer = ee.Reducer.frequencyHistogram(),
                                    geometry= region.geometry(),
                                    scale= 30,
                                    crs='EPSG:8826').get('cropland')).getInfo()
    year_crop_dict = {}
    for i in counts:
        crop = cdl_lookup[int(i)]['crop']
        crop_area = counts[i]*(900)/(4046.86)
        year_crop_dict.update({crop: crop_area})
    year_crop_dict_filt = {key: value for key, value in year_crop_dict.items() if value > 1}

    et_dict = ee.Dictionary({'grass_et': grass_et,
                             'crops_et': crop_et,
                             'grass_eto': grass_eto,
                             'crop_eto': crop_eto}).getInfo()

    output_dict.update({year: {'grass_et': et_dict['grass_et'],
                               'crops_et': et_dict['crops_et'],
                               'grass_eto': et_dict['grass_eto'],
                               'crop_eto': et_dict['crop_eto'],
                               'grass_acres': dev_acres,
                               'crop_acres': ag_acres,
                               'crop_types': year_crop_dict_filt}})

    print(f'Acres of Grass in {year}: {dev_acres}\nGrass ET for {year}: {et_dict['grass_et']}\n\nAcres of Crops in {year}: {ag_acres}\nCropland ET for {year}: {et_dict['crops_et']}\n\n')

pd.DataFrame(output_dict).transpose().reset_index().rename(columns={'index': 'year'}).to_csv(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Data/TV/dryCreek/segmentation/dry_creek_et_gee_dict_{et_version}.csv')
#%% 
plotting_data = pd.read_csv(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Data/TV/dryCreek/segmentation/dry_creek_et_gee_dict_{et_version}.csv')

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
#%%
#the plotting section
from plotnine import *
et_volume = plotting_data.melt(id_vars='year',
                                       value_vars=['grass_et', 'crops_et', 'et_sum'],
                                       var_name='et_cover', value_name='et_acre-feet')

area = plotting_data.melt(id_vars=['year'], 
                                  value_vars=['area_sum','grass_acres', 'crop_acres'], 
                                  var_name='area', value_name='acre')

rate = plotting_data.melt(id_vars=['year'], 
                                  value_vars=['grass_et_depth', 'crops_et_depth', 'average_et_rate'], 
                                  var_name='et_depth', value_name='depth')

etof = plotting_data.melt(id_vars=['year'], 
                                  value_vars=['grass_etof', 'crops_etof', 'average_etof'], 
                                  var_name='etof', value_name='etof_val')

et_vol_plot = (ggplot(et_volume, aes(x = 'year')) + 
      geom_line(aes(y = et_volume['et_acre-feet'].astype('float16'), group = 'et_cover', color = 'et_cover')) +
      labs(title=f'Acre feet of ET by landcover from Ensemble vers {et_version}', y = 'Acre feet', subtitle=('Note: data pre-2016 are V2.0'))+
      geom_vline(xintercept = 3.5, color = '#BF131370', linetype = 'dotted') +
      scale_color_manual(values= ['red', '#0BA11870','blue'], labels= ['Crops', 'Sum', 'Grass'])+
      annotate('text', label = 'Development starts', x = 3.6, y = 225, angle = 270) +
      theme_bw()+ theme(legend_title= element_blank()))

area_plot = (ggplot(area, aes(x = 'year')) + 
        geom_line(aes(y = area['acre'].astype('float16'), group = 'area', color = 'area'), linetype = 'dashed') +
        labs(title='Irrigated Area', y = 'Acres', subtitle=('Note: data pre-2016 are V2.0')) +
      geom_vline(xintercept = 3.5, color = '#BF131370', linetype = 'dotted') +
      annotate('text', label = 'Development starts', x = 3.6, y = 150, angle = 270) +
      scale_color_manual(values= ['#0BA11870','red','blue'], labels= ['Summed Acres', 'Crops Acres', 'Grass Acres'])+
        theme_bw()+ theme(legend_title= element_blank()))

et_rate_plot = (ggplot(rate, aes(x = 'year')) + 
        geom_line(aes(y = rate['depth'].astype('float16'), group = 'et_depth', color = 'et_depth'), linetype = 'solid') +
        labs(title=f'ET Rate from Ensemble vers {et_version}', y = 'Feet', subtitle=('Note: data pre-2016 are V2.0'))+
      geom_vline(xintercept = 3.5, color = '#BF131370', linetype = 'dotted') +
      annotate('text', label = 'Development starts', x = 3.6, y = 0.5, angle = 270) +
      scale_color_manual(values= ['green', 'red','blue'], labels= ['Weighted Avg','Crops ET Rate', 'Grass ET Rate'])+
        theme_bw()+ theme(legend_title= element_blank()))

eto_plot = (ggplot(plotting_data, aes(x = 'year')) + 
        geom_line(aes(y = plotting_data['grass_eto'].astype('float16'), group = 1), color = 'blue', linetype = 'solid') +
        labs(title=f'ETo', y = 'Feet')+
      geom_vline(xintercept = 3.5, color = '#BF131370', linetype = 'dotted') +
      annotate('text', label = 'Development starts', x = 3.6, y = 2, angle = 270) +
      scale_y_continuous(limits = (0, 4)) +
        theme_bw()+ theme(legend_title= element_blank()))

etof_plot = (ggplot(etof, aes(x = 'year')) + 
        geom_line(aes(y = etof['etof_val'].astype('float16'), group = 'etof', color = 'etof'), linetype = 'solid') +
        labs(title=f'EToF from Ensemble vers {et_version}', y = 'EToF', subtitle=('Note: data pre-2016 are V2.0'))+
        geom_vline(xintercept = 3.5, color = '#BF131370', linetype = 'dotted') +
        annotate('text', label = 'Development starts', x = 3.6, y = 0.6, angle = 270) +
              scale_color_manual(values= ['green', 'red','blue'], labels= ['Average EToF', 'Crops EToF', 'Grass EToF'])+
        theme_bw()+ theme(legend_title= element_blank()))

et_vol_plot.show()
area_plot.show()
et_rate_plot.show()
eto_plot.show()
etof_plot.show()

#%%
et_vol_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/et_acre_feet_ensemble_{et_version}.png')
area_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/landcover_area.png')
et_rate_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/et_rate_ensemble_{et_version}.png')
etof_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/etof_ensemble_{et_version}.png')
eto_plot.save(f'C:/Users/mason.bull/OneDrive - State of Idaho/Desktop/Geoprocessing/Plots/TV/eto_ensemble_{et_version}.png')

#%%
import seaborn as sns
#plot of et acre feet and crop
fig, ax = plt.subplots()
crop_type = crop_type[(crop_type['acres'] > 7)]
crop_acres = crop_type.groupby('year')['acres'].sum().reset_index()
distribution = pd.crosstab(crop_type['year'], [crop_type['acres']], normalize='index')
pivot = crop_type.pivot_table(index='year', columns='crop_type', values='acres', aggfunc='sum')

sns.lineplot(et_volume, x = 'year', y = 'et_acre-feet', hue='et_cover', palette=['blue', 'red', 'green'])
ax.set_ylim(bottom = 0)

ax2 = ax.twinx()
pivot.plot(kind = 'bar', stacked=True, colormap='jet', ax = ax2, alpha = 0.5, legend=None)

ax.set_xlabel('Year')
ax.set_ylabel('ET Acre Feet')
ax.set_title(f'ET Acre-Feet from Ensemble vers {et_version} (data pre 2016 are V2.0)')
ax2.set_ylabel('Crop Acreage')
ax2.set_ylim(ax.get_ybound())

ax_handles, ax_labels = ax.get_legend_handles_labels()
ax2_handles, ax2_labels = ax2.get_legend_handles_labels()

ax2_labels[0:0] = ['Grass ET', 'Crop ET', 'ET Sum']
ax2_handles[0:0] = ax_handles 
ax.legend(title=None, bbox_to_anchor=(1.1, 1), loc="upper left", labels = ax2_labels, handles= ax2_handles)
plt.show()

#%%
#plot of et rate and crop
fig, ax = plt.subplots()

sns.lineplot(rate, x = 'year', y = 'depth', hue='et_depth', palette=['blue', 'red', 'green'])
ax.set_ylim(bottom = 0)

ax2 = ax.twinx()
pivot.plot(kind = 'bar', stacked=True, colormap='jet', ax = ax2, alpha = 0.5, legend=None)

ax.set_xlabel('Year')
ax.set_ylabel('ET Rate (feet)')
ax.set_title(f'ET Rate from Ensemble vers {et_version} (data pre 2016 are V2.0)')
ax2.set_ylabel('Crop Acreage')
ax2.set_ylim(0, 700)

ax_handles, ax_labels = ax.get_legend_handles_labels()
ax2_handles, ax2_labels = ax2.get_legend_handles_labels()

ax2_labels[0:0] = ['Grass ET', 'Crop ET', 'Weighted Avg ET']
ax2_handles[0:0] = ax_handles 
ax.legend(title=None, bbox_to_anchor=(1.1, 1), loc="upper left", labels = ax2_labels, handles= ax2_handles)
plt.show()

#%%
#plot of etof and crop
fig, ax = plt.subplots()

sns.lineplot(etof, x = 'year', y = 'etof_val', hue='etof', palette=['blue', 'red', 'green'])
ax.set_ylim(bottom = 0)

ax2 = ax.twinx()
pivot.plot(kind = 'bar', stacked=True, colormap='jet', ax = ax2, alpha = 0.5, legend=None)

ax.set_xlabel('Year')
ax.set_ylabel('EToF')
ax.set_title(f'EToF from Ensemble vers {et_version} (data pre 2016 are V2.0)')
ax2.set_ylabel('Crop Acreage')
ax2.set_ylim(0, 700)

ax_handles, ax_labels = ax.get_legend_handles_labels()
ax2_handles, ax2_labels = ax2.get_legend_handles_labels()

ax2_labels[0:0] = ['Grass ET', 'Crop ET', 'Weighted Avg EToF']
ax2_handles[0:0] = ax_handles 
ax.legend(title=None, bbox_to_anchor=(1.1, 1), loc="upper left", labels = ax2_labels, handles= ax2_handles)
plt.show()


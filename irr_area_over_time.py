#%%count irrmapper area in aoi
import ee
ee.Authenticate()
ee.Initialize(project = 'idwr-450722')

irrmapper = ee.ImageCollection("UMT/Climate/IrrMapper_RF/v1_2")
nlcd_ee = ee.ImageCollection("projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER").select('b1')
aoi = ee.FeatureCollection('projects/idwr-450722/assets/wspa_outline').geometry()
ee_years = ee.List(list(range(1987, 2025, 1)))
def get_area_ee(year):
    year_string = ee.Number(year).format('%4d')
    im = irrmapper.filterDate(year_string).mosaic().remap([0], [1]).rename('classification')
    nl = nlcd_ee.filterDate(year_string).first().rename('classification')
    low = nl.eq(22)
    med = nl.eq(23)
    high = nl.eq(24)
    urban = low.add(med).add(high).unmask()

    im_masked = im.add(urban).eq(1).selfMask()

    im_count = im.reduceRegion(reducer = ee.Reducer.count(),
                                   geometry = aoi,
                                   crs = 'EPSG:8826',
                                   scale = 30).get('classification')
    im_masked_count= im_masked.reduceRegion(reducer = ee.Reducer.count(),
                               geometry = aoi,
                               crs = 'EPSG:8826',
                               scale = 30).get('classification')
    return ee.Feature(None, {'year': year, 'im_count': im_count, 'im_masked_count': im_masked_count})
counts = ee.FeatureCollection(ee_years.map(get_area_ee))
ee.batch.Export.table.toDrive(collection=counts,
                              fileNamePrefix= 'wspa_irrmapper_count',
                              description= 'wspa_irrmapper_count_export')#.start()

#just run this once and then save the csv for use later
#%%
#import setup libraries
import pathlib
import rasterio
import numpy as np
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
from os.path import getmtime
#set the root directory to find the raster files
root = pathlib.Path(r'D:\Geoprocessing\Data\TV')
#root = pathlib.Path(r'C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\bulc_stuff')

#get the list of raster images that are ready to be plotted 
rasters = []#list(root.glob('**/*_postProcessed.tif'))
[rasters.append(i) for i in list(root.glob('**/tv*classification-final-COG.tif'))]
#rasters = list(root.glob('**/tv_bulc_im_class_*_l0-0_mp0-05.tif'))

nlcd_rasters = list(root.glob('**/wspa_nlcd*-final-COG.tif'))
#instead of using this pd.read_csv you can also just getInfo() the collection above, this is just cheaper
irrmapper_counts = pd.read_csv(r"D:\Geoprocessing\Data\TV\wspa_irrmapper_count.csv")
#assign an empty dictionary to be filled later
reg_output_list = []
urb_masked_list = []

def get_irr_area(year, region = 'wspa'):
    if region == 'wspa':
        rf = list(root.glob(f'**/tv-{year}*classification-final-COG.tif'))
    else:
        rf = list(root.glob(f'**/{region}-{year}*-final-COG.tif'))

    if len(rf) > 1:
        lookup = {}
        for i in rf:
            mod_date = getmtime(i)
            lookup.update({mod_date: str(i)})
        times = list(lookup.keys())
        times.sort(reverse=True)
        most_recent = times[0]
        newest = lookup[most_recent]
        rf = [pathlib.Path(newest)]

    rf = rf[0]
    
    nlcd_check = len(list(root.glob(f'**/{region}_nlcd_{year}*-final-COG.tif'))) > 0 #check if nlcd images exist

    with rasterio.open(rf) as src:
        rf_rast = src.read(1)
        rf_meta = src.meta
        irr_pixels = np.count_nonzero(rf_rast == 1)
        pixel_area = abs(round(src.transform[0])*round(src.transform[4]))/1e6 #pixel area in square kilometers

    if nlcd_check:
        nlcd = list(root.glob(f'**/{region}_nlcd_{year}*-final-COG.tif'))[0]
        with rasterio.open(nlcd) as src:
            nlcd_rast = src.read(1)
            nlcd_meta = src.meta
        if rf_rast.shape != nlcd_rast.shape:
            rf_rast_stack = np.column_stack((rf_rast, np.linspace(255,255,num = rf_meta['height'])))
        else:
            rf_rast_stack = rf_rast

        urban = np.where((nlcd_rast >= 22) & (nlcd_rast <= 24), 255, np.nan)

        rf_urban_filt = np.where(urban == 255, #where urban is 255
                        255, #set 255
                        rf_rast_stack) #into rf array

        irr_area_urb_filt = np.count_nonzero(rf_urban_filt == 1) * pixel_area
        urb_masked_list.append({'region':region, 'year': int(year), 'area': irr_area_urb_filt})
    
    irr_area = irr_pixels * pixel_area

    print(f'{region} {year} irrigated area: {irr_area} km²')
    reg_output_list.append({'region':region, 'year': int(year), 'area': irr_area})

years = ['1987', '1997', '2000', '2004', '2007', '2010', '2014', '2015', '2016', '2023', '2025']
#loop through rasters and apply the function
for i in years:
    get_irr_area(i)

im_formatted = irrmapper_counts.drop(columns=['system:index', '.geo'])
im_formatted['im_area'] = im_formatted['im_count']*9e-4
im_formatted['im_masked_area'] = im_formatted['im_masked_count']*9e-4
#put the irrigated area into a dataframe
plotting_df = pd.DataFrame(reg_output_list).sort_values('year')

filtered_plotting_df = pd.DataFrame(urb_masked_list).sort_values('year')

#plot
fig, ax = plt.subplots()
sns.lineplot(plotting_df, ax = ax, y = 'area', x = 'year', color = 'green', marker= 'o')
sns.lineplot(im_formatted, y = 'im_area', x = 'year', color = 'blue')
ax.set_xlabel('Year')
for i in zip(plotting_df.groupby('year')):
    for x,y,s in i[0][1][['year','area','year']].values:
        if x == 2025:
            ax.text(x-3.5,y + 5,int(s))    
        else:
            ax.text(x+0.5,y + 5,int(s))
ax.set_ylabel('Area (km²)')
ax.set_title('Irrigated Area Unfiltered')

fig1, ax1 = plt.subplots()
sns.lineplot(filtered_plotting_df, ax = ax1, y = 'area', x = 'year', color = 'green', marker= 'o')
sns.lineplot(im_formatted, y = 'im_masked_area', x = 'year', color = 'blue')
ax1.set_xlabel('Year')
for i in zip(filtered_plotting_df.groupby('year')):
    for x,y,s in i[0][1][['year','area','year']].values:
        if x == 2025:
            ax1.text(x-3.5,y + 5,int(s))    
        else:
            ax1.text(x+0.5,y + 5,int(s))
ax1.set_ylabel('Area (km²)')
ax1.set_title('Irrigated Area without Urban area')

fig.show()
fig1.show()

#%%
#check on wspa 2015
with rasterio.open(r"D:\Geoprocessing\Data\TV\TV2015\raster\tv-2015-v20-classification-final-COG.tif", 'r') as src:
    wspa_2015 = src.read(1)
    wspa_2015 = np.where(wspa_2015 == 255, np.nan, wspa_2015)
    wspa_2015 = wspa_2015 * 15
    wspa_2015_meta = src.meta
plt.imshow(wspa_2015)
with rasterio.open(r"D:\Geoprocessing\Data\TV\TV2015\raster\tv-2015-v20-probability.tif", 'r') as src:
    wspa_2015_prob = src.read(1)
    wspa_2015_prob = np.where(wspa_2015 == 15, wspa_2015_prob, np.nan)
    wspa_2015_prob_meta = src.meta

with rasterio.open(r"D:\Geoprocessing\Data\TV\TV2010\rast\tv-2010-v2-classification-final-COG.tif", 'r') as src:
    wspa_2010 = src.read(1)
    wspa_2010 = np.where(wspa_2010 == 255, np.nan, wspa_2010)
    wspa_2010 = wspa_2010 * 10
    wspa_2010_meta = src.meta

with rasterio.open(r"D:\Geoprocessing\Data\TV\TV2023\rast\tv-2023-v11-classification-final-COG.tif", 'r') as src:
    wspa_2023 = src.read(1)
    wspa_2023 = np.where(wspa_2023 == 255, np.nan, wspa_2023)
    wspa_2023 = wspa_2023 * 23
    wspa_2023_meta = src.meta

one = np.add(wspa_2010, wspa_2015)
done = np.add(one, wspa_2023)

with rasterio.open(r'D:\Geoprocessing\Data\TV\added_wspa_rasters.tif', 'w', **wspa_2010_meta) as dat:
    dat.write_band(1, done)

import geopandas as gpd
sample = np.argwhere(one == 15)[np.random.choice(len(np.argwhere(one == 15)), size=200, replace=False)]

coords = []
probs = []
for x, y in sample:
    coords.append(rasterio.transform.xy(wspa_2015_meta['transform'], x, y))
    prob = wspa_2015_prob[x, y]
    probs.append(prob)
import statistics
statistics.mean(probs)
statistics.stdev(probs)
x_l = []
y_l = []
for x, y in coords:
    x_l.append(x)
    y_l.append(y)
df = pd.DataFrame({'x':x_l, 'y':y_l})
gdf = gpd.GeoDataFrame(gpd.points_from_xy(x = df['x'], y = df['y'], crs='EPSG:8826'))
gdf['change'] = 'added irr'
gdf = gdf.rename(columns={0:'geo'})

gdf.to_file(r'D:\Geoprocessing\Data\TV\wspa_irr_change_10_15.shp')

#%%
threshold_value = 0.54
wspa_2015_prob_mask = np.where(wspa_2015_prob <= threshold_value, np.nan, wspa_2015)
#import matplotlib.pyplot as plt
#plt.imshow(wspa_2015_prob_mask)

original_area = np.count_nonzero(wspa_2015/15 == 1) * 9e-4
masked_area = np.count_nonzero(wspa_2015_prob_mask/15 == 1) * 9e-4

#prob_masked in the fp means that I masked out non-irrigated pixels from proability raster before using the probability raster as a mask over the classification raster
    #it looks like I should be doing that anyway
print(f'threshold: {threshold_value}\noriginal: {original_area} \nmasked: {masked_area}')
with rasterio.open(fr'D:\Geoprocessing\Data\TV\wspa_2015_prob_mask{str(threshold_value)}_prob_masked.tif', 'w', **wspa_2010_meta) as dat:
    dat.write_band(1, wspa_2015_prob_mask)
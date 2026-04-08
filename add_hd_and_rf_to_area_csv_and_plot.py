# %%
'''The second code in the research pipeline. Code for adding random forest and hand digitized area's to the area dataframe created in the previous step.
This will also plot the dataset.'''

import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
import fnmatch
import numpy as np
from osgeo import gdal
import pathlib
from plotnine import *

#%%
#this cell brings in the hand digitzed data and gets the area for each year it exists
areas_df = pd.read_csv('C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV_ModelComparison\\nlcd_irrmapper_combos_for_tv.csv')

years = [1987, 1994, 1997, 2000, 2004, 2007, 2010, 2015]
hd_areas = {}
hd_data_location = 'C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\HD_data\\'
hd_area_df = pd.DataFrame(columns = ['year', 'hdIrr', 'hdNirr', 'hdSemi'])

for y in years:
    yStr = str(y)
    dat = gpd.read_file(f"{hd_data_location}TV_IrrigatedLands_{yStr}.shp")
    irr = dat.loc[dat[fnmatch.filter(list(dat.columns), 'STATUS*')[0]] == 'irrigated'].agg({'Acres': ['sum']}).rename(columns={'Acres':'SqMi'})/640
    nirr = dat.loc[dat[fnmatch.filter(list(dat.columns), 'STATUS*')[0]] == 'non-irrigated'].agg({'Acres': ['sum']}).rename(columns={'Acres':'SqMi'})/640
    semi = dat.loc[dat[fnmatch.filter(list(dat.columns), 'STATUS*')[0]] == 'semi-irrigated'].agg({'Acres': ['sum']}).rename(columns={'Acres':'SqMi'})/640
    hd_area_df.loc[len(hd_area_df)] = [y, float(irr.iloc[0]), float(nirr.iloc[0]), float(semi.iloc[0])]
    hd_areas.update({yStr:{f'{yStr}Irr':irr, f'{yStr}NIrr':nirr, f'{yStr}Semi':semi}})

updated_df = pd.merge(areas_df, hd_area_df, how='outer', on='year')

#%%
#this cell brings in the raster data 

#do you want to look at the bimodal change classification alongside the standard classification rasters? y/n
bimodal_included = 'y'

if bimodal_included == 'y':
    bimod = pd.read_csv("C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\bimodalChange\\bimodal_change_ForwardBackward_binary.csv").drop([10]).drop(['.geo', 'system:index'], axis = 1)
    bimod = bimod.assign(irrArea_mi = bimod['irrArea'] / 2.59).assign(nirrArea_mi = bimod['nirrArea'] / 2.59)


#do you want to look at the random forest classification with or without NLCD urban area burned in? w/wo
nlcd_urban_area_included = 'w'

if nlcd_urban_area_included == 'w':
    print('You are analyzing IDWR RF data with NLCD classified Urban area burned in.')
    raster04 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2004\\rast\\tv-2004-classification-wNLCD_clip.tif"
    raster15 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\tv-2015-classification-wNLCD_clip.tif"
    raster14 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2014\\rast\\tv-2014-classification-wNLCD_clip.tif"
    raster23 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2023\\rast\\tv-2023-classification-wNLCD_clip.tif"
    raster16 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2016\\rast\\tv-2016-classification-wNLCD_clip.tif"
elif nlcd_urban_area_included == 'wo':
    print('You are analyzing IDWR RF data with IDWR RF classified Urban area.')
    raster04 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2004\\rast\\tv-2004-v4-classification_noUrban.tif"
    raster14 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2014\\rast\\tv-2014-v8-classification_noUrban.tif"
    raster15 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\tv-2015-v11-classification_noUrban.tif"
    raster16 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2016\\rast\\tv-2016-v6-classification_noUrban.tif"
    raster23 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2023\\rast\\tv-2023-v9-classification.tif"
else:
    print('nlcd_urban_area_included needs to be w or wo to determine if you want NLCD data or not in the RF classification.')

imgs = [raster04, raster14, raster15, raster16, raster23]
rf_areas = pd.DataFrame(columns = ['year', 'rfIrr', 'rfNirr', 'rfUrb'])

for i in imgs:
    year = str(pathlib.Path(i).parts[-1].split('-')[1])

    dataset = gdal.Open(i)
    band = dataset.GetRasterBand(1)
    cols = dataset.RasterXSize
    rows = dataset.RasterYSize
    data = band.ReadAsArray(0, 0, cols, rows).astype(np.float32)

    class0 = data[data == 0]
    class1 = data[data == 1]
    class2 = data[data == 2]

    NIArea =  ((len(class0) * 900)/1e6)/2.59
    IrrArea = ((len(class1) * 900)/1e6)/2.59
    UrbArea = ((len(class2) * 900)/1e6)/2.59
    print(f'\n{year} Non-Irrigated Area (sqmi): {NIArea},\n{year} Irrigated Area (sqmi): {IrrArea},\n{year} Urban Area (sqmi): {UrbArea}')

    rf_areas.loc[len(rf_areas)] = [int(year), float(IrrArea), float(NIArea), float(UrbArea)]
    class_area = {'Non-Irrigated':NIArea,'Irrigated':IrrArea,'Urban':UrbArea}

complete_df = updated_df.merge(rf_areas, how= 'outer', on = 'year')

if bimodal_included == 'y':
    complete_df = complete_df.merge(bimod, how = 'outer', on = 'year')

csv_destination = 'C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV_ModelComparison\\area_dataframe_for_method_research_plotting.csv'
complete_df.to_csv(csv_destination, header=True, index = False)
#%%
#plot the completed df calculated above

p = (ggplot(complete_df, (aes(x = 'year'))) +
geom_line(aes(y = 'irrmapper', color = "'IRRMAPPER'"))+
geom_line(aes(y = 'nlcd',      color = "'NLCD'"))+
geom_line(aes(y = 'urb',       color = "'URBAN'"))+
geom_point(aes(y = 'hdSemi'), size = 3, color = 'grey') +
geom_point(aes(y = 'hdIrr'), size = 3, color = 'grey') +
geom_point(aes(y = 'rfIrr'), size = 3, color = 'grey') +
geom_point(aes(y = 'rfUrb'), size = 3, color = 'grey') +
geom_point(aes(y = 'hdIrr',    fill  = "'HDIRR'",  shape = "'HDIRR'"),  color = 'red', size = 2) +
geom_point(aes(y = 'hdSemi',   fill  = "'HDSEMI'", shape = "'HDSEMI'"), color = 'blue', size =2) +
geom_point(aes(y = 'rfIrr',    fill  = "'RFIRR'",  shape = "'RFIRR'"),  color = 'green', size = 2) + 
geom_point(aes(y = 'rfUrb',    fill  = "'RFURB'",  shape = "'RFURB'"),  color = 'grey', size = 2) +
labs(x = 'Year', y = 'Irrigated Area (mi$^2$)')+
theme_bw() + 
theme(legend_key = element_blank()) + 
scale_x_continuous(limits = [1985, 2024], expand = [0,0]) +
scale_y_continuous(limits = [100, 800], expand = [0,0])  +
scale_shape_manual(name = ' ', 
                   breaks = ['IRRMAPPER', 'NLCD', 'HDIRR', 'HDSEMI', 'RFIRR', 'RFURB', 'URBAN'],
                   values = ['o', 'o', 'o', 'o', 'o', 'o', 'o'],
                   labels = ['IrrMapper', 'NLCD Irrigated', 'HD Irrigated', 'HD Semi-Irrigated', 'Random Forest Irrigated', 'Random Forest Urban', 'NLCD Urban']) +
scale_fill_manual(name = ' ', 
                   breaks = ['IRRMAPPER', 'NLCD', 'HDIRR', 'HDSEMI', 'RFIRR', 'RFURB', 'URBAN'],
                   values = ['blue', 'green', 'red', 'blue', 'green', 'grey', 'black'],
                   labels = ['IrrMapper', 'NLCD Irrigated', 'HD Irrigated', 'HD Semi-Irrigated', 'Random Forest Irrigated', 'Random Forest Urban', 'NLCD Urban']) +
scale_color_manual(name = ' ', 
                   breaks = ['IRRMAPPER', 'NLCD', 'HDIRR', 'HDSEMI', 'RFIRR', 'RFURB', 'URBAN'],
                   values = ['blue', 'green', 'red', 'blue', 'green', 'grey', 'black'],
                   labels = ['IrrMapper', 'NLCD Irrigated', 'HD Irrigated', 'HD Semi-Irrigated', 'Random Forest Irrigated', 'Random Forest Urban', 'NLCD Urban'])
)
if bimodal_included == 'y':
    p = (p + geom_line(aes(y = 'irrArea_mi', color = "'BIMODAL'"), linetype = 'dashed') +
         scale_color_manual(name = ' ', 
                   breaks = ['IRRMAPPER', 'NLCD', 'HDIRR', 'HDSEMI', 'RFIRR', 'RFURB', 'URBAN', 'BIMODAL'],
                   values = ['blue', 'green', 'red', 'blue', 'green', 'grey', 'black', 'purple'],
                   labels = ['IrrMapper', 'NLCD Irrigated', 'HD Irrigated', 'HD Semi-Irrigated', 'Random Forest Irrigated', 'Random Forest Urban', 'NLCD Urban', 'Bimodal Change']))
p.show()
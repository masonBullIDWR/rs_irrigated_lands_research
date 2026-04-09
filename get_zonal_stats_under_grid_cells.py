#%%
'''This code will analyze raster pixel distributions within model grid cells. It is currently set up to work with 2015 only, so other years will need data gathered.'''
import rasterstats
import geopandas as gpd
from osgeo import ogr, gdal
import rasterio

#%%This section is for the standard comparison of the three different models

#data setup
#what grid cell size do you want to look at? [one] mile, [half] mile, or [quarter] mile
grid_cell_size = 'one'

if grid_cell_size =='one':
    grid = 'x:\\Spatial\\GroundWater\\TVModeling\\RestrictedUse\\TVGWFM\\TVGWFM_grid_cells.shp'
    size = 'oneMile'
    px_size = 1609.34
elif grid_cell_size =='half':
    grid = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TVGWFM_grid_cells_oneHalf.shp"
    size = 'halfMile'
    px_size = 804.672
elif grid_cell_size =='quarter':
    grid = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TVGWFM_grid_cells_oneQuarter.shp"
    size = 'quarterMile'
    px_size = 402.336
else:
    print('invalid selection. use one, half, or quarter to select grid cell size.')

im = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\irrMapper_TV_2015_w_urb_v3.tif"
rf = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\tv-2015-v9-classification.tif"
nlcd = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\NLCD_TV_2015_w_urb.tif"

model_list = [im, rf, nlcd]

#%%
#this will output 3 unique raster stat shapefiles for NLCD, IrrMapper, and RF. Each will have an shp for irrigated, urabn, and non-irrigated
for m in model_list:
    if 'irrMapper' in m:
        category_dictionary = {0: 'im_Non-Irrigated', 1: 'im_Irrigated', 2: 'im_Urban'}
        columns = ['geometry', 'im_Non-Irrigated', 'im_Urban', 'im_Irrigated']
        model = 'im'
    if 'NLCD' in m:
        category_dictionary = {0: 'nl_Non-Irrigated', 1: 'nl_Irrigated', 2: 'nl_Urban'}
        columns = ['geometry', 'nl_Non-Irrigated', 'nl_Urban', 'nl_Irrigated']
        model = 'nl'
    if 'classification' in m:
        category_dictionary = {0: 'rf_Non-Irrigated', 1: 'rf_Irrigated', 2: 'rf_Urban'}
        columns = ['geometry', 'rf_Non-Irrigated', 'rf_Urban', 'rf_Irrigated']
        model = 'rf'
    
    counts = rasterstats.zonal_stats(grid, m, nodata = 250, categorical = True, category_map = {0: f'{model}_Non-Irrigated', 1: f'{model}_Irrigated', 2: f'{model}_Urban'}, geojson_out = True)

    gdf = gpd.GeoDataFrame.from_features(counts, crs = 'EPSG:8826', columns=['geometry', f'{model}_Non-Irrigated', f'{model}_Urban', f'{model}_Irrigated'])
    gdf.to_file(f'C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\shp\\tv_{model}_2015_rasterStats_{size}.shp')
    gdf_NI =  gpd.GeoDataFrame.from_features(counts, crs='EPSG:8826', columns=['geometry', f'{model}_Non-Irrigated'])
    gdf_Urb = gpd.GeoDataFrame.from_features(counts, crs='EPSG:8826', columns=['geometry', f'{model}_Urban'])
    gdf_Irr = gpd.GeoDataFrame.from_features(counts, crs='EPSG:8826', columns=['geometry', f'{model}_Irrigated'])
    gdf_NI.to_file( f'C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\shp\\tv_{model}_2015_rasterStats_NonIrr_{size}.shp')
    gdf_Irr.to_file(f'C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\shp\\tv_{model}_2015_rasterStats_Irr_{size}.shp')
    gdf_Urb.to_file(f'C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\shp\\tv_{model}_2015_rasterStats_Urb_{size}.shp')

#%%This section is for the comparison of one RF image with the NLCD urban baked in

rf = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\tv-2015-v9-classification.tif" #standard 3 class rf image
rf10 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\rf_2015_FractionImpervious_10.tif" #irr/non-irr rf image with NLCD impervious >= 10
rf20 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\rf_2015_FractionImpervious_20.tif"#>= 20
rf40 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\rf_2015_FractionImpervious_40.tif"
rf60 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\rf_2015_FractionImpervious_60.tif"
rf80 = "C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\rf_2015_FractionImpervious_80.tif"

percs = {'0': rf, '10': rf10, '20': rf20, '40': rf40, '60': rf60, '80': rf80}
catMap = {0: 'Non-Irrigated', 1: 'Irrigated', 2: 'Urban'}

#This is a function to get the raster stats from an shp and convert them into a single stacked image depending on grid cell size

for i in percs.keys():
       count = rasterstats.zonal_stats(grid, percs[i], nodata = 250, categorical = True, category_map = catMap, geojson_out = True)

       gdf = gpd.GeoDataFrame.from_features(count, crs = 'EPSG:8826', columns=['geometry', 'Non-Irrigated', 'Urban', 'Irrigated'])
       gdf.to_file(f'C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\shp\\impComp\\rf_NLCD{i}_2015_rasterStats_{size}.shp')

       gdf_NI =  gpd.GeoDataFrame.from_features(count, crs='EPSG:8826', columns=['geometry', 'Non-Irrigated'])
       gdf_Urb = gpd.GeoDataFrame.from_features(count, crs='EPSG:8826', columns=['geometry', 'Urban'])
       gdf_Irr = gpd.GeoDataFrame.from_features(count, crs='EPSG:8826', columns=['geometry', 'Irrigated'])

       #convert the shp into a tiff
       bounds = gdf.total_bounds
       width = int((bounds[2] - bounds[0])/px_size)
       height = int((bounds[3] - bounds[1])/px_size)
       transform = rasterio.transform.from_origin(bounds[0], bounds[3], px_size, px_size)
       niRast = rasterio.features.rasterize(shapes = ((geom, value)
                 for geom, value in zip(gdf.geometry, gdf['Non-Irrigated'])), out_shape = (height, width), transform = transform, fill = -1, dtype = 'int32')
       irrRast = rasterio.features.rasterize(shapes = ((geom, value)
             for geom, value in zip(gdf.geometry, gdf['Irrigated'])), out_shape = (height, width), transform = transform, fill = -1, dtype = 'int32')
       urbRast = rasterio.features.rasterize(shapes = ((geom, value)
             for geom, value in zip(gdf.geometry, gdf['Urban'])), out_shape = (height, width), transform = transform, fill = -1, dtype = 'int32')    
       output = f'C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\impComp\\rf_NLCD{i}_2015_rasterStats_stack_{size}.tif'
       with rasterio.open(output, 'w', driver='GTiff', height=height, width=width, count=3,dtype='int32',crs=gdf.crs,transform=transform,nodata=-1) as dst:
           dst.write(niRast, 1)
           dst.write(irrRast, 2)
           dst.write(urbRast, 3) 
           dst.set_band_description(1, 'Non-Irrigated')
           dst.set_band_description(2, 'Irrigated')
           dst.set_band_description(3, 'Urban')

#%%Get the data to make one to one line scatter plots of grid cells for each model type

#this creates the the zonal stats shp for nlcd and irrmapper with the grid cell size specified above
nlcd = "C:\\Users\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\raster\\NLCD_TV_2015_w_urb_v3_v2.tif"

GDF = gpd.GeoDataFrame.from_file("C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV2015\\shp\\impComp\\rf_NLCD20_2015_rasterStats_oneMile.shp")
GDF.rename(columns = {'Non-Irriga': 'rf_Non-Irrigated', 'Irrigated': 'rf_Irrigated', 'Urban': 'rf_Urban'}, inplace= True)

nlcdCount = rasterstats.zonal_stats(grid, nlcd, nodata = 250, categorical = True, category_map = catMap, geojson_out = True)
nlcdGDF = gpd.GeoDataFrame.from_features(nlcdCount, crs = 'EPSG:8826', columns=['geometry', 'Non-Irrigated', 'Urban', 'Irrigated'])
nlcdGDF.rename(columns = {'Non-Irrigated': 'nl_Non-Irrigated', 'Irrigated': 'nl_Irrigated', 'Urban': 'nl_Urban'}, inplace = True)

irrmCount = rasterstats.zonal_stats(grid, im, nodata = 250, categorical = True, category_map = catMap, geojson_out = True)
irrmGDF = gpd.GeoDataFrame.from_features(irrmCount, crs = 'EPSG:8826', columns=['geometry', 'Non-Irrigated', 'Urban', 'Irrigated'])
irrmGDF.rename(columns = {'Non-Irrigated': 'im_Non-Irrigated', 'Irrigated': 'im_Irrigated', 'Urban': 'im_Urban'}, inplace = True)

df = GDF.merge(nlcdGDF, how = 'inner', on='geometry')
final_df = df.merge(irrmGDF, how = 'inner', on='geometry')

#%%plot the gdf created above
from plotnine import *

print('IRRIGATED AREA PIXEL COUNTS')
(ggplot(final_df, aes(x = 'rf_Irrigated', y = 'im_Irrigated')) + geom_point(color = 'green', alpha = 0.3) + labs(title='Irrigated', x = 'IDWR-RF', y = 'IrrMapper') + scale_x_continuous(limits= [0, 3000], expand = [0,0]) + scale_y_continuous(limits= [0, 3000], expand = [0,0]) + geom_abline(slope = (1), intercept = (0,0)) + theme_bw() + coord_fixed(1)).show()
(ggplot(final_df, aes(x = 'rf_Irrigated', y = 'nl_Irrigated')) + geom_point(color = 'green', alpha = 0.3) + labs(title='Irrigated', x = 'IDWR-RF', y = 'NLCD')      + scale_x_continuous(limits= [0, 3000], expand = [0,0]) + scale_y_continuous(limits= [0, 3000], expand = [0,0]) + geom_abline(slope = (1), intercept = (0,0)) + theme_bw() + coord_fixed(1)).show()
(ggplot(final_df, aes(x = 'nl_Irrigated', y = 'im_Irrigated')) + geom_point(color = 'green', alpha = 0.3) + labs(title='Irrigated', x = 'NLCD',    y = 'IrrMapper') + scale_x_continuous(limits= [0, 3000], expand = [0,0]) + scale_y_continuous(limits= [0, 3000], expand = [0,0]) + geom_abline(slope = (1), intercept = (0,0)) + theme_bw() + coord_fixed(1)).show()

print('\nURBAN AREA PIXEL COUNTS')
#(ggplot(aes(x = newDat['rf_Urban'], y = newDat['im_Urban'])) + geom_point(color = 'grey', alpha = 0.3) + labs(title='Urban', x = 'IDWR-RF', y = 'IrrMapper') + scale_x_continuous(limits= [0, 3000], expand = [0,0]) + scale_y_continuous(limits= [0, 3000], expand = [0,0]) + geom_abline(slope = (1), intercept = (0,0))  + theme_bw()).show()
(ggplot(final_df, aes(x = 'rf_Urban', y ='nl_Urban')) + geom_point(color = 'grey', alpha = 0.3) + labs(title='Urban', x = 'IDWR-RF', y = 'NLCD')      + scale_x_continuous(limits= [0, 3000], expand = [0,0]) + scale_y_continuous(limits= [0, 3000], expand = [0,0]) + geom_abline(slope = (1), intercept = (0,0)) + theme_bw() + coord_fixed(1)).show()
(ggplot(final_df) + geom_point(color = 'grey', alpha = 0.3) + labs(title='Urban', x = 'NLCD',    y = 'IrrMapper') + scale_x_continuous(limits= [0, 3000], expand = [0,0]) + scale_y_continuous(limits= [0, 3000], expand = [0,0]) + geom_abline(slope = (1), intercept = (0,0)) + theme_bw() + coord_fixed(1)).show()

print('\nNON-IRRIGATED AREA PIXEL COUNTS')
(ggplot(final_df, aes(x = 'rf_Non-Irrigated', y = 'im_Non-Irrigated')) + geom_point(color = 'orange', alpha = 0.3) + labs(title='Non-Irrigated', x = 'IDWR-RF', y = 'IrrMapper') + scale_x_continuous(limits= [0, 3000], expand = [0,0]) + scale_y_continuous(limits= [0, 3000], expand = [0,0]) + geom_abline(slope = (1), intercept = (0,0)) + theme_bw() + coord_fixed(1)).show()
(ggplot(final_df, aes(x = 'rf_Non-Irrigated', y = 'nl_Non-Irrigated')) + geom_point(color = 'orange', alpha = 0.3) + labs(title='Non-Irrigated', x = 'IDWR-RF', y = 'NLCD')      + scale_x_continuous(limits= [0, 3000], expand = [0,0]) + scale_y_continuous(limits= [0, 3000], expand = [0,0]) + geom_abline(slope = (1), intercept = (0,0)) + theme_bw() + coord_fixed(1)).show()
(ggplot(final_df, aes(x = 'nl_Non-Irrigated', y = 'im_Non-Irrigated')) + geom_point(color = 'orange', alpha = 0.3) + labs(title='Non-Irrigated', x = 'NLCD',    y = 'IrrMapper') + scale_x_continuous(limits= [0, 3000], expand = [0,0]) + scale_y_continuous(limits= [0, 3000], expand = [0,0]) + geom_abline(slope = (1), intercept = (0,0)) + theme_bw() + coord_fixed(1)).show()

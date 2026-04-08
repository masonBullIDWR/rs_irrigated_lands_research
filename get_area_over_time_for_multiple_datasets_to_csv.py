# %%
'''The first code to run in the research pipeline for method comparison. Code to calculate area over time for multiple datasets in a certain region AOI and save it to a csv.
This is only for datasets hosted on EE, not local datasets. Those come later.'''
import ee
import pandas as pd
import geemap
import geopandas as gpd

gcloud_project = 'idwr-450722'

ee.Authenticate()
ee.Initialize(project= gcloud_project)

#select the datasets to analyze
irrmapper = ee.ImageCollection("UMT/Climate/IrrMapper_RF/v1_2")
nlcd = ee.ImageCollection("projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER")

#specify the shp to use for reductions, just set shp to an ee asset if one exists
shp_local = gpd.read_file("X:\\Spatial\\GroundWater\\TVModeling\\RestrictedUse\\TVGWFM\\TVGWFM_boundary.shp")
shp = geemap.gdf_to_ee(shp_local)

date_range = range(1985, 2025)
#%%
#Do the calculation to get the area of each dataset for a year. This code is going to run for a while and eat up lots of EECU hours, so use it sparingly.

data = []
for y in date_range:
    nlcd = ee.Image(f"projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER/Annual_NLCD_LndCov_{y}_CU_C1V1").eq(82)
    urb1 = ee.Image(f"projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER/Annual_NLCD_LndCov_{y}_CU_C1V1").eq(22)
    urb2 = ee.Image(f"projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER/Annual_NLCD_LndCov_{y}_CU_C1V1").eq(23)
    urb3 = ee.Image(f"projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER/Annual_NLCD_LndCov_{y}_CU_C1V1").eq(24)
    urb = ee.ImageCollection.fromImages([urb1, urb2, urb3]).max()
    irr = ee.Image(f"UMT/Climate/IrrMapper_RF/v1_2/ID_{y}").eq(0).unmask()

    vals = (
        irr
        .addBands([nlcd, irr.And(nlcd), irr.Or(nlcd), urb]).rename(['irrmapper','nlcd','inner','union', 'urb'])
        .reduceRegion(ee.Reducer.sum(), shp.geometry(), scale=30, crs="EPSG:8826", maxPixels=27500000)
    )

    data.append({"year": y, **vals.getInfo()})

# %%
#convert list of areas to a df
df = pd.DataFrame(data)
df['inner'] = (df['inner']*900)/1e6
df['union'] = (df['union']*900)/1e6
df['irrmapper'] = ((df['irrmapper']*900)/1e6)/2.56
df['nlcd'] = ((df['nlcd']*900)/1e6)/2.56
df['urb'] = ((df['urb']*900)/1e6)/2.56
# %%
#save the df to a csv
csv_destination = 'C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\TV_ModelComparison\\nlcd_irrmapper_combos_for_tv.csv'
df.set_index('year')[["irrmapper","nlcd"]].plot()
df.to_csv(csv_destination, header=True, index = False)

#%%
import geopandas as gpd
import pandas as pd
import json
from pathlib import Path
from os import path
import re

class_dict = {1: 'Irrigated',
              0: 'Non-Irrigated'}
label_dict = {'Irrigated': 1,
              'Non-Irrigated': 0}
req_cols = ['Class', 'Label', 'Notes', 'Year', 'Region', 'geometry']

search_strings = ['Mask', 'mask']
manual_masks = set()
regions = set()

print('gathering mask files from N:\\')
for s in search_strings:
    for i in Path(r'N:\IrrigatedLands').glob(f'**/*{s}*.shp'):
        manual_masks.add(i)
        area = i.parts[2]
        regions.add(area)

final_masks = []
for i in regions:
    region_paths = [j for j in manual_masks if i in str(j)]
    years = set([re.findall('[0-9]{4}', s.name)[0] for s in region_paths if len(re.findall('[0-9]{4}', s.name)) > 0])
    region_masks = set()
    for y in years:
        mod_times = {}
        year_masks = [j for j in region_paths if y in str(j)]
        for m in year_masks:
            if 'rchive' in str(m):
                region_masks.add(m)
            else:
                mod_times.update({m: path.getmtime(m)})
        if len(mod_times) < 1:
            continue
        else:
            most_recent = max(mod_times, key=mod_times.get)
            region_masks.add(most_recent)
    for r in region_masks:
        final_masks.append(r)

parquet_files = []
for f in final_masks:
    gdf = gpd.read_file(f)
    if gdf.is_valid.sum() != gdf['geometry'].size:
        gdf['geometry'] = gdf['geometry'].make_valid()
    try:
        year = re.findall('[0-9]{4}', f.name)[0]
    except:
        year = re.findall('[0-9]{4}', str(f))[0]
    region = f.parts[2]
    if 'verestimation' in str(f):
        gdf['Label'] = 'overestimation'
        gdf['Class'] = 2
    print(f'\ngetting file for {region} {year} and making columns')
    gdf['Year'] = year
    gdf['Region'] = region
    gdf['Original_File'] = f.name
    cols = gdf.columns
    for c in cols:
        if c not in req_cols and c.lower() in [i.lower() for i in req_cols]:
            gdf[c.lower().capitalize()] = gdf[c]
            gdf = gdf.drop(columns = [c])
            cols = gdf.columns
        if c.lower() not in [i.lower() for i in req_cols]:
            gdf = gdf.drop(columns=[c])
            cols = gdf.columns
    for r in req_cols:
        if r not in cols:
            if r == 'Label':
                try:
                    print(f'missing "{r}" column, attempting fix')
                    gdf['Label'] = [class_dict[c] for c in gdf['Class']]
                    print('done')
                except:
                    print('no dice')
                    raise(ValueError(f'GDF {region} {year} is missing required columns "Class" and "Label"'))
            if r == 'Class':
                try:
                    print(f'missing "{r}" column, attempting fix')
                    gdf['Class'] = [label_dict[c] for c in gdf['Label']]
                    print('done')
                except:
                    print('no dice')
                    raise(ValueError(f'GDF {region} {year} is missing required columns "Class" and "Label"'))
            if r == 'Notes':
                print(f'missing "{r}" column, attempting fix')
                gdf['Notes'] = None
                print('done')
    print('Done, added to parquet')
    parquet_files.append(gdf.to_crs('EPSG:8826'))

final_parquet = gpd.GeoDataFrame(pd.concat(parquet_files, ignore_index=True), crs = 'EPSG:8826')
final_parquet.to_parquet('masks_parquet.parquet', index=False)

final_parquet[final_parquet['Region'] == 'Portneuf']
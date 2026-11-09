#%%
import geopandas as gpd
import pandas as pd
from pathlib import Path
from os import path
import re

class_dict = {1: 'Irrigated',
              0: 'Non-Irrigated'}
label_dict = {'Irrigated': 1,
              'Non-Irrigated': 0}
req_cols = ['Class', 'Label', 'Notes', 'Year', 'Region', 'geometry']

#%%Functions
def find_files(search_string = 'mask', target_drive = r'N:\IrrigatedLands') -> tuple:
    '''Find all of the files containing the word *search_string* from the *target_drive* drive.
    Args:
        search_string (str): String to find in file names on target location
        
        target_drive (str): String of path to the drive that holds the files to combine

    Returns:
        manual_masks (set): set of unique file names with path of .shp files that contain the search string
        
        regions (set): Set of regions that each file path contains'''
    manual_masks = set()
    regions = set()
    print(f'Finding all manual mask files on {target_drive}')
    #find all of the files with "mask" in the name on the N: drive
    for i in Path(target_drive).glob(f'**/*{search_string.lower()}*.shp'.lower()):
        manual_masks.add(i)
        area = i.parts[2]
        regions.add(area)
    print('Done.\n')
    return manual_masks, regions
def get_years(masks_list) -> set:
    '''Get all of the years that have a manual mask from the list of manual masks
    Args:
        masks_list (list): List of manual mask file paths, should be specific to a region to avoid confusion later
    
    Returns:
        years (set): Set of strings of unique years from provided file paths'''
    years = set()
    for m in masks_list:
        #only look for strings that are 4 numbers surrounded by no other numbers for the date
        year_strings = re.findall('(?<![0-9])[0-9]{4}(?![0-9])', str(m))
        if len(year_strings) > 0:
            year = year_strings[0]  
            years.add(year)
        else: 
            continue
    return years
def get_masks(path_list, year) -> set:
    '''Find the manual mask files that are the most recent for each region/year combination. 
    If a mask exists in an Archive folder it is prioritized.
    Args:
        path_list (list): List of filepaths to sort by modification time

        year (str): String of the year to filter path_list by.
    
    Returns:
        masks (set): Set of unique filepaths that are the most up to date versions 
        '''

    mod_times = {}
    masks = set()
    year_masks = [p for p in path_list if year in str(p)]

    for m in year_masks:
        if 'archive' in str(m).lower():
            masks.add(m)
        else:
            mod_times.update({m: path.getmtime(m)})
    if len(mod_times) > 0:
        most_recent = max(mod_times, key=mod_times.get)
        masks.add(most_recent)
    return masks
def isolate_masks(regions, masks) -> list:
    '''Find unique year/region combinations to filter manual mask files by and 
    take the most recent version of each pair if more than one exists.
    Args:
        regions (set): Set of unique regions found in the manual mask filepaths
        
        masks (set): Set of unique file paths containing manual mask .shp files
    Returns:
        final_masks (list): List of most recently edited manual mask files for each year/region pair'''
    final_masks = []
    for i in regions:
        print(f'\nFinding masks for {i};')
        region_paths = [j for j in masks if str(i) in str(j)]

        years = get_years(masks_list=region_paths)
        print(f'Found masks for {', '.join([j for j in years])}')
        for y in years:
            mask_list = get_masks(region_paths, y)
            for m in mask_list:
                final_masks.append(m)
    return final_masks
def check_columns(gdf) -> tuple:
    '''Check for required columns in the manual mask .shp file and remove unnecessary columns
    Args:
        gdf (gpd.GeoDataFrame): gdf representing the manual mask .shp
    Returns:
        gdf (gpd.GeoDataFrame): gdf representing the manual mask .shp with extra columns removed
        cols (list): List of gdf column names'''
    cols = gdf.columns
    for c in cols:
        if c.lower() not in [i.lower() for i in req_cols]:
            gdf = gdf.drop(columns=[c])
            cols = gdf.columns
        elif c not in req_cols and c.lower() in [i.lower() for i in req_cols]:
            gdf[c.lower().capitalize()] = gdf[c]
            gdf = gdf.drop(columns = [c])
            cols = gdf.columns
        else:
            continue
    return gdf, cols
def add_columns(gdf, cols, file) -> tuple:
    '''Find missing columns in a manual mask file and add them. If a file contains lowercase columns, 
    rename them in standardized capitalized format
    
    Args:
        gdf (gpd.GeoDataFrame): gdf representing the manual mask .shp file with no extra columns

        cols (list): list of gdf column names

        file (pathlib.Path): Path to manual mask .shp file

    Returns:
        gdf (gpd.GeoDataFrame): gdf with all necessary columns, named is standard capitalized format'''
    #if a required column is missing, add it by using the dictionaries at the top       
    check = len(list(set(req_cols) & set(cols))) == len(req_cols)
    if check == False:
        missing = set(req_cols) - set(cols)
        for m in missing:
            if m == 'Label':
                print(f'{file.name} needs coerced:')
                try:
                    print(f'missing "{m}" column, attempting fix')
                    gdf['Label'] = [class_dict[c] for c in gdf['Class']]
                    print('done')
                except:
                    raise(ValueError(f'GDF {gdf['Region']} {gdf['Year']} is missing required columns "Class" and "Label"'))
            if m == 'Class':
                try:
                    print(f'missing "{m}" column, attempting fix')
                    gdf['Class'] = [label_dict[c] for c in gdf['Label']]
                    print('done')
                except:
                    raise(ValueError(f'GDF {gdf['Region']} {gdf['Year']} is missing required columns "Class" and "Label"'))
            if m == 'Notes':
                print(f'missing "{m}" column, attempting fix')
                gdf['Notes'] = None
                print('done')
    #just as a precaution, add the original file's name to the gdf 
    gdf['Original_File'] = file.name

    return gdf
def standardize_files(file):
    '''Check that all geometries are valid in a file and set the columns to correct format. Also sets the gdf crs to EPSG:8826
    Args:
        file (pathlib.Path): Path to the manual mask .shp file to format
    
    Returns:
        gdf (gpd.GeoDataFrame): gdf of the manual mask .shp file with correct columns and crs'''
    #using the most recent masks, get them all into a standard format and put in a parquet
    gdf = gpd.read_file(file)

    #check for/make valid geometry
    if gdf.is_valid.sum() != gdf['geometry'].size:
        gdf['geometry'] = gdf['geometry'].make_valid()

    try:
        year = re.findall('[0-9]{4}', file.name)[0]
    except:
        year = re.findall('[0-9]{4}', str(file))[0]

    region = file.parts[2]

    #edge case in the portneuf overestimation masks
    if 'verestimation' in str(file):
        gdf['Label'] = 'overestimation'
        gdf['Class'] = 2
    
    gdf['Year'] = year
    gdf['Region'] = region

    gdf, cols = check_columns(gdf)
    gdf = add_columns(gdf, cols, file)

    gdf = gdf.to_crs('EPSG:8826')
    return gdf
#%%Running
manual_masks, regions = find_files('mask')
final_masks = isolate_masks(regions = regions, masks = manual_masks)
parquet_files = [standardize_files(f) for f in final_masks]

final_parquet = gpd.GeoDataFrame(pd.concat(parquet_files, ignore_index=True), crs = 'EPSG:8826')
final_parquet.to_parquet('outputs/masks_parquet.parquet', index=False)
Path().cwd().parent
#%%
from arcgis.gis import GIS
from pathlib import Path
from shutil import rmtree
from json import load

#this script will create an item in portal given the inputs from metadata creation in metadata_updating.py 
#portal is authorized via ArcGIS Pro on your machine, and will use whatever portal you have active as the destination portal
#make sure that your active portal in Arc is Enterprise Portal (https://gis.idwr.idaho.gov/portal), not AGOL(https://arcgis.com)

#get the necessary info from the metadata creation step
with open(str(Path.cwd()/'temp/publishing_json.json')) as j:
    file = load(j)
    file_title = file['file_title'] 
    TAC = file['TAC'] 
    tags = file['tags'] 
    description = file['description'] 
    temp_folder = file['temp_folder'] 
    summary = file['summary'] 
    thumbnail_link = file['thumbnail_link'] 
    x_drive_name = file['x_drive_name'] 
    year = file['year'] 
    abb_name = file['abb_name'] 
    x_staging_loc = file['x_staging_loc']

gis = GIS('pro')

zip_file_path = fr"//dwrwbpublic/GIS/Spatial/LandCover_Vegetation/{x_drive_name}/RF_IrrigatedLands_{year}_{abb_name}.zip"
portal_path ='https://research.idwr.idaho.gov/' + '/'.join(zip_file_path.split('/')[3:])

properties = {'type': 'Document Link',
              'title': file_title,
              'licenseInfo': TAC,
              'tags': tags,
              'credits': 'Idaho Department of Water Resources (IDWR)',
              'description': description,
              'snippet': summary,
              'url': portal_path,
              'categories': ['/Categories/Irrigated Lands'],
              'commentsEnabled': False,
              'accessInformation': 'Idaho Department of Water Resources (IDWR)',
              }
met = [i for i in Path(x_staging_loc).glob('*.tif.xml')][0]
zip_item = gis.content.add(item_properties = properties, data = zip_file_path, thumbnail = str(thumbnail_link), metadata = str(met))

#%%
rmtree(temp_folder)
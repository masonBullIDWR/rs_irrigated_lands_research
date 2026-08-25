#%%
from arcgis.gis import GIS
from pathlib import Path
from metadata_updating import file_title, TAC, tags, description, \
    summary, thumbnail_link, x_drive_name, year, abb_name, x_staging_loc
#this section will create an item in portal given the inputs from metadata creation above 
#portal is authorized via ArcGIS Pro on your machine, and will use whatever portal you have active as the destination portal
#make sure that your active portal in Arc is Enterprise Portal (https://gis.idwr.idaho.gov/portal), not AGOL(https://arcgis.com)
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
for i in Path(x_staging_loc).glob('*.tif.xml'):
    met = i
zip_item = gis.content.add(item_properties = properties, data = zip_file_path, thumbnail = str(thumbnail_link), metadata = str(met))
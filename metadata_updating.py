#%%
from pathlib import Path
from shutil import copy
from arcpy import metadata
from os.path import getmtime
from time import strftime, strptime, ctime, time
import xml.etree.ElementTree as ET
from docx import Document
from python_docx_replace import docx_replace
from RF_IrrigatedLands_Functions import LoadConfigFile

parent_dir = Path(__file__).parent.absolute()
config_file = parent_dir / "config_file.yml"
config = LoadConfigFile(config_file)
#year = config['year']
year = 2025

#a dictionary for file paths the key is the N: location name, value is X: location, abbreviated name, and full name
# None is inserted where one is missing in either path
location_dict = {'BearRiverCompact':        ['BearRiver',         'BR',       'Bear River'],
                 'Bigwood_AOI':             ['None',              'None',     'Big Wood River'],
                 'Bruneau-Grandview':       ['Bruneau-Grandview', 'BRG',      'Bruneau-Grandview Area'],
                 'Camas':                   ['Camas',             'Camas',    'Camas County Area'],
                 'EasternSnakePlainAquifer':['SnakePlain',        'ESPA',     'Eastern Snake Plain Aquifer'],
                 'LakeLowell':              ['None',              'None',     'Lake Lowell Area'],
                 'Malad':                   ['Malad',             'Malad',    'Malad Area'],
                 'MountainHome':            ['MountainHome',      'MH',       'Mountain Home Area'],
                 'NorthernIdaho':           ['CoeurdAlene',       'CDA',      "Coeur d'Alene Area"],
                 'None':                    ['Payette',           'Payette',  'Payette Area'],
                 'Portneuf':                ['Portneuf',          'Portneuf', 'Portneuf River Area'],
                 'RaftRiverStudy':          ['RaftRiverValley',   'RR',       'Raft River Study Area'],
                 'TreasureValley':          ['BoiseValley',       'TV',       'Treasure Valley'],
                 }
#region is a key lookup value for the location_dict (the N: location)
#area = config['area']
area = 'TreasureValley'
#region = [l for l in location_dict.keys() if area.casefold() == str(location_dict[l][1]).casefold()][0]
region = area

x_drive_name = location_dict[region][0]
abb_name = location_dict[region][1]
full_name = location_dict[region][2]

#----------------file locations--------------------
n_loc = f'N:\\IrrigatedLands\\{region}\\RandomForest_{year}\\forRelease'
x_spatial_loc = f'X:\\Spatial\\LandCover_Vegetation\\{x_drive_name}\\MachineLearning'
x_staging_loc = f'X:\\Staging_X_Y\\LandCover_Vegetation\\{x_drive_name}\\MachineLearning'
metadata_loc = f'N:\\IrrigatedLands\\rf_metadata_template.docx'

#metadata document in a docx format for easy editing when things need changed
doc = Document(r"N:\IrrigatedLands\rf_metadata_template.docx")

breaker = ahhhh

#----------------file setup------------------------
if not Path(x_staging_loc).exists():
    Path(x_staging_loc).mkdir(parents=True, exist_ok=True)

#because this xml file is edited so heavily, we should be able to grab any xml as a template
source_xml = list(Path(x_spatial_loc).glob('*.tif.xml'))[-1]
new_xml = f'{x_staging_loc}\\{abb_name} {year} Random Forest Land Classification.tif.xml'

#right now, it seems like if we always take a single template xml we can prevent most issues 
copy(r"X:\Spatial\LandCover_Vegetation\SnakePlain\MachineLearning\ESPA_2024_RandomForest.tif.xml",  new_xml)

#rename all files to the LOCATION_YYYY_RandomForest convention when copying to the x staging folder
for f in Path(n_loc).glob('*.*'):
    extension = '.'.join(f.name.split('.')[1:])
    if '.doc' not in extension:
        new_name = f'{abb_name}_{year}_RandomForest.{extension}'
        new_file = f'{x_staging_loc}/{new_name}'
        copy(f, new_file)
    
#----------------metadata elements------------------
#the sections of the metadata document to parse
sections = {'Summary':[], 'Description':[], 'Normal':[], 
            'Credits':[], 'Use limitations':[], 'Extras':[]}

#get the reporting doc to get the list of bands used out of it
root_path = Path(config['training_data']).parent.parent
dirs = []
for n in [f.name for f in root_path.glob('**/*') if f.is_dir()]:
    if 'reporting' in n:
        dirs.append(n)

#reporting_doc = Document(root_path / dirs[-1] / f'{area}-{year}-v{dirs[-1].split('V')[-1]}-classification_Irrigated_lands_reporting.docx')
reporting_doc = Document(r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\TV2025\reporting_V2\tv-2025-v2-classification_Irrigated_lands_reporting.docx")
doc_metadata_table = reporting_doc.tables[0]
t = []
for i in doc_metadata_table.column_cells(0):
    t.append(i.text)
    if i.text in 'Datasets Used':
        column_index = t.index(i.text)

#the list of datasets we used in classification NOTE: this currently does not include datasets used to post process
used_datasets = doc_metadata_table.cell(column_index, 1).text.strip("[]").replace("'", "").split(', ')
datasets_dict = {
            'NASA/HLS/HLSL30/v002': ['USGS Landsat and ESA Sentinel Harmonized HLSL imagery', 'https://developers.google.com/earth-engine/datasets/catalog/NASA_HLS_HLSL30_v002'],
            'NASA/HLS/HLSS30/v002': ['USGS Landsat and ESA Sentinel Harmonized HLSS imagery', 'https://developers.google.com/earth-engine/datasets/catalog/NASA_HLS_HLSS30_v002'],
            'projects/sat-io/open-datasets/OREGONSTATE/PRISM_800_MONTHLY': ['800m PRISM climate data', 'Daly, C., Halbleib, M., Smith, J.I., Gibson, W.P., Doggett, M.K., Taylor, G.H., Curtis, J. & Pasteris, P.A. (2008). Physiographically sensitive mapping of climatological temperature and precipitation across the conterminous United States. International Journal of Climatology, 28, 2031-2064. [doi:10.1002/joc.1688](https://doi.org/10.1002/joc.1688)'],
            'USGS/3DEP/10m_collection': ['USGS 3DEP national DEM', 'https://developers.google.com/earth-engine/datasets/catalog/USGS_3DEP_10m'],
            'projects/openet/assets/ensemble/conus/gridmet/monthly/v2_0': ['OpenET Ensemble Evpotranspiration, Version 2.0', 'https://developers.google.com/earth-engine/datasets/catalog/OpenET_ENSEMBLE_CONUS_GRIDMET_MONTHLY_v2_0'],
            'projects/openet/assets/ensemble/conus/gridmet/monthly/v2_1': ['OpenET Ensemble Evpotranspiration, Version 2.1', 'https://developers.google.com/earth-engine/datasets/catalog/OpenET_ENSEMBLE_CONUS_GRIDMET_MONTHLY_v2_1'],
            'LANDSAT/LT05/C02/T1_L2': ['USGS Landsat 5 Collection 2, Tier 1 imagery', 'https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LT05_C02_T1_L2'],
            'LANDSAT/LT07/C02/T1_L2': ['USGS Landsat 7 Collection 2, Tier 1 imagery', 'https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LT07_C02_T1_L2'],
            'users/gena/global-hand/hand-100': ['Height Above Nearest Drainage topography', 'Donchyts, G., Winsemius, H., Schellekens, J., Erickson, T., Gao, H., Savenije, H., & van de Giesen, N. (2016). Global 30m height above the nearest drainage (HAND). Geophysical Research Abstracts, 18, EGU2016-17445-3. EGU General Assembly 2016.'],
            'USDA/NASS/CDL': ['USDA Cropland Data Layer', 'https://developers.google.com/earth-engine/datasets/catalog/USDA_NASS_CDL'],
            'USDA/NAIP/DOQQ': ['USDA National Agriculture Imagery Program high resolution imagery', 'https://developers.google.com/earth-engine/datasets/catalog/USDA_NAIP_DOQQ'],
            'projects/idwr-450722/assets/METRIC': ['IDWR generated METRIC evapotranspiration imagery', 'https://data-idwr.hub.arcgis.com/pages/evapotranspiration'],
            'POU': ['IDWR Place of Use Water Right polygons', 'https://data-idwr.hub.arcgis.com/documents/dcadb8412de74f468ce802d61361ca0a/about'],
            'MERIT/Hydro/v1_0_1': ['MERIT Global Hydrography flow direction', 'https://developers.google.com/earth-engine/datasets/catalog/MERIT_Hydro_v1_0_1#description'],
            }

description_datasets = []
reference_datasets = []
post_process_datasets = []

#make individual lists for the datasets we used and their references 
for b in used_datasets:
    dataset = datasets_dict[b]
    num = used_datasets.index(b) + 2

    if b in ['USDA/NASS/CDL', 'USDA/NAIP/DOQQ']:
        w = f'{dataset[0]}({num})'
        post_process_datasets.append(w)
    else:
        w = f'{dataset[0]}({num})'
        description_datasets.append(w)

    r = f'({num}) {dataset[1]}'
    reference_datasets.append(r)

formatted_datasets = ', '.join(description_datasets)
formatted_references = '\n\n '.join(reference_datasets)
formatted_post_process = ', '.join(post_process_datasets)

#a dictionary of how to update the document text to make sure it is matching the correct values
dict = {'Region full': full_name,
        'Region abv.': abb_name,
        'Year': year,
        'Datasets': formatted_datasets,
        'References': formatted_references,
        'Post Process': formatted_post_process}
docx_replace(doc=doc, **dict)

#a loop to grab the strings from the updated document, get them into a single string, and fill out the dictionary
for s in sections.keys():
    for p in doc.paragraphs:
        # Filter for standard headings
        if p.style.name.startswith(s):
            sections[s].append(p.text)
    single = '\n '.join(sections[s])
    sections[s] = single

TAC = sections['Use limitations']
tags = f'Supervised Land Classification, Machine Learning, Random Forest, Water Budget, Monitoring, Hydrology, Groundwater, Surface Water, Irrigated Areas, Irrigation, Irrigated, Non-Irrigated, Regulatory, Farming, Idaho, ID, Idaho, Water, Water Use, {full_name}, {abb_name}, IDWR GIS Department, Environment'
place_keywords = f'{full_name}, {abb_name}, Idaho, ID'
file_title = f'{year} Irrigated Lands for the {full_name} ({abb_name}): Machine Learning Generated'
complete_file_name = f'{abb_name}_{year}_RandomForest'
description = sections['Description']
summary = sections['Summary']
extras = sections['Extras']
#to preserve the original thumbnail after arcpy steals it, I'm creating two links 
original_thumbnail_link = Path(Path(n_loc).parent / 'ForReview' / f'{abb_name}_{year}_thumbnail.png')
thumbnail_link = original_thumbnail_link.parent.parent / f'{abb_name}_{year}_thumbnail.png' #NOTE: for whatever reason, this seems to cause problems. The file keeps moving after the code runs, which stops the code from running, but the code runs fine if you run it twice.
copy(original_thumbnail_link, Path(thumbnail_link))                                         #which is why this line is here, to hedge our bets 
creation_date = strftime('%Y-%m-%d %H:%M:%S', strptime(ctime(getmtime(f'{n_loc}\\{abb_name} {year} Random Forest Land Classification.tif'))))
publication_date = strftime('%Y-%m-%d %H:%M:%S', strptime(ctime(time())))
edition_date = strftime('%Y-%m-%d', strptime(ctime(time())))

#----------------defining metadata----------------------
for i in Path(x_staging_loc).glob('*.tif'):
    target_tif = i
target_tif_meta = metadata.Metadata(target_tif)

#updating of metadata pieces through the ESRI interface
#NOTE: there might be a way we can skirt arcpy here? If we can manually edit the xml and overwrite it we could ostensibly save a complicated dependency, I'm not sure if that will work however, given that we have to specify metadata.Metadata()
target_tif_meta.title = file_title
target_tif_meta.accessConstraints = TAC
target_tif_meta.tags = tags
target_tif_meta.credits = 'Idaho Department of Water Resources (IDWR)'
target_tif_meta.thumbnailUri = str(thumbnail_link)
target_tif_meta.description = description
target_tif_meta.summary = summary

#this coming section updates dates within the xml file because ESRI does not have a built in md method for dates. It is, however, using the arc metadata template from the metadata object
xml_string = target_tif_meta.xml
root = ET.fromstring(xml_string)

other_metadata ={'.//Esri/CreaDate': strftime('%Y%m%d', strptime(creation_date, '%Y-%m-%d %H:%M:%S')),
                 './/Esri/ModDate': strftime('%Y%m%d', strptime(publication_date, '%Y-%m-%d %H:%M:%S')),
                 './/Esri/SyncDate': strftime('%Y%m%d', strptime(publication_date, '%Y-%m-%d %H:%M:%S')),
                 './/mdDateSt': strftime('%Y%m%d', strptime(creation_date, '%Y-%m-%d %H:%M:%S')),
                 './/dataIdInfo/idCitation/date': None,
                 './/dataIdInfo/idCitation/date/pubDate': publication_date,
                 './/dataIdInfo/idCitation/date/createDate': creation_date,
                 './/dataIdInfo/idCitation/resEdDate': edition_date,
                 './/dqInfo/dataLineage/prcStep/stepDateTm': publication_date,
                 './/eainfo/detailed/attr/begdatea': f'{year}0301',
                 './/eainfo/detailed/attr/enddatea': f'{year}1101',
                 './/dataIdInfo/placeKeys': place_keywords,
                 './/dataIdInfo/placeKeys/keyword': place_keywords,
                 './/dataIdInfo/tempKeys/keyword': year,
                 './/dataIdInfo/idCitation/resAltTitle': f'RF_IrrigatedLands_{year}_{abb_name}',
                 './/Esri/DataProperties/itemProps/itemName': f'{abb_name}_{year}_RandomForest.tif',
                 './/dataIdInfo/idCitation/datasetSeries/seriesName': file_title.split(' ', 1)[1],
                 './/Esri/DataProperties/itemProps/itemLocation': f'{x_spatial_loc}\\{abb_name}_{year}_RandomForest.tif',
                 './/Esri/DataProperties/itemProps/itemLocation/linkage':f'{x_spatial_loc}\\{abb_name}_{year}_RandomForest.tif',
                 './/dqInfo/dataLineage/prcStep/stepDesc': description,
                 './/dqInfo/dataLineage/prcStep/stepRat': extras,
                 './/dqInfo/dataLineage/statement': summary,
                 './/dataIdInfo/idCitation/otherCitDet': summary,
                 './/dqInfo/report[@type="DQConcConsis"]/measDesc': description,
                 './/dqInfo/report[@type="DQCompOm"]/measDesc': summary,
                 './/dqInfo/report[@type="DQCompOm"]/evalMethDesc': extras,
                 './/dqInfo/report[@type="DQQuanAttAcc"]/measDesc': description,
                 './/dataIdInfo/idCitation/datasetSeries/issId': year,
                 './/dataIdInfo/dataExt/exDesc': f'Irrigation status for the {year} growing season.',
                 './/dataIdInfo/dataExt/tempEle/TempExtent/exTemp/TM_Period/tmBegin': f'{year}-03-01T00:00:00',
                 './/dataIdInfo/dataExt/tempEle/TempExtent/exTemp/TM_Period/tmEnd': f'{year}-11-01T00:00:00',
                 './/dataIdInfo/tpCat': 'Irrigated Lands',
                 './/dataIdInfo/tpCat/TopicCatCd': 'Irrigated Lands',
                 }

#this looks for every item in the above dictionary in the root xml string, changes it, then finally updates the target xml file
for d in other_metadata:
    el = root.find(d)
    el.text = other_metadata[d]
target_tif_meta.xml = ET.tostring(root, encoding='unicode')

if not target_tif_meta.isReadOnly:
    target_tif_meta.save()

print(f'New metadata saved to the tif at {str(target_tif)}')

#%%
#helpers for checking your work without having to open arc catalog
for elem in root.iter():
    if 'date' in elem.tag.lower() or 'Date' in elem.tag:
        # build the path from root down to this element
        path = []
        e = elem
        # ElementTree doesn't track parents, so just print tag + text for now
        print(elem.tag, '->', elem.text)

#testing if a path is real on the next two lines
parsed = ET.parse(xml_string)
parsed.find('.//dqInfo/report[@type="DQConcConsis"]/measDesc').text

#a helper loop that finds instances of a string in the xml and prints the path to update the dicitonary with if needed
parent_map = {c: p for p in root.iter() for c in p}

def get_path(elem):
    path = [elem.tag]
    while elem in parent_map:
        elem = parent_map[elem]
        path.append(elem.tag)
    return '/'.join(reversed(path))

for elem in root.iter():
    if 'cat' in elem.tag.lower():
        print(get_path(elem), '=', elem.text)

#%%
#helper to view the xml in case you need to find a path for editing metadata 
import xml.dom.minidom as minidom

tgt_md = metadata.Metadata(target_tif)
pretty = minidom.parseString(tgt_md.xml).toprettyxml(indent='  ')
print(pretty)
#%%
from arcgis.gis import GIS
import getpass

#this section will automatically upload the item to AGOL, but I haven't gotten it to work for portal yet
#the data are mostly complete from what I can tell, I need another set of eyes on it to be sure, though
gis = GIS(username= input('input arcgis username'), password=getpass.getpass('ArcGIS Password: '))

zip_path = r"X:\Staging_X_Y\LandCover_Vegetation\BoiseValley\MachineLearning\RF_IrrigatedLands_2025_TV.zip"

properties = {'type': 'Document Link',
              'title': file_title,
              'licenseInfo': TAC,
              'tags': tags,
              'credits': 'Idaho Department of Water Resources (IDWR)',
              'description': description,
              'snippet': summary,
              'url': r'X:\Staging_X_Y\LandCover_Vegetation\BoiseValley\MachineLearning\RF_IrrigatedLands_2025_TV.zip',
              'categories': ['/Categories/Irrigated Lands'],
              'commentsEnabled': False,
              'accessInformation': 'Idaho Department of Water Resources (IDWR)',
              }
for i in Path(x_staging_loc).glob('*.tif.xml'):
    met = i
zip_item = gis.content.add(item_properties = properties, data = zip_path, thumbnail = str(thumbnail_link), metadata = str(met))
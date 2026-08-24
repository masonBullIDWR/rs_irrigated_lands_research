#%%
from pathlib import Path
from shutil import copy
from arcpy import metadata
from arcpy import mp
from arcpy import Describe
from arcpy import da
from arcpy import SpatialReference
from arcpy import SelectLayerByAttribute_management
from PIL import Image, ImageDraw, ImageFont
from os.path import getmtime
from time import strftime, strptime, ctime, time
import xml.etree.ElementTree as ET
from docx import Document
from python_docx_replace import docx_replace
from ruamel.yaml import YAML
import json

#parent_dir = Path(__file__).parent.absolute()
#config_file = parent_dir / "config_file.yml"
#yaml = YAML()
#yaml.preserve_quotes = (
#    True
#)
#with open(config_file) as f:
#    config = yaml.load(f)
#year = str(config['year'])
year = '2025'
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
                 'TreasureValley':          ['BoiseValley',       'WSPA',     'Western Snake Plain Aquifer'],
                 }
#region is a key lookup value for the location_dict (the N: location)
#area = config['area']
#if area != 'tv':
#    region = [l for l in location_dict.keys() if area.casefold() == str(location_dict[l][1]).casefold()][0]
#else:
#    region = 'TreasureValley'
region = 'TreasureValley'


x_drive_name = location_dict[region][0] #ie., BoiseValley
abb_name = location_dict[region][1] #ie., TV
full_name = location_dict[region][2] #ie., Treasure Valley

#----------------file locations--------------------
n_loc = f'N:\\IrrigatedLands\\{region}\\RandomForest_{year}\\forRelease'
x_spatial_loc = f'X:\\Spatial\\LandCover_Vegetation\\{x_drive_name}\\MachineLearning'
x_staging_loc = f'X:\\Staging_X_Y\\LandCover_Vegetation\\{x_drive_name}\\MachineLearning'
metadata_loc = f'N:\\IrrigatedLands\\rf_metadata_template.docx'

#metadata document in a docx format for easy editing when things need changed
doc = Document(r"N:\IrrigatedLands\rf_metadata_template.docx")

#%% This section makes the thumbnail for the portal item 
#section to make the map for the thumbnail
template_aprx = r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\ArcProProjects\template\template_3.aprx"
aprx = mp.ArcGISProject(template_aprx)
display_map = aprx.listMaps("DisplayMap")[0]
display_map.spatialReference = SpatialReference(8826)
tiff_layer = display_map.addLayer(mp.LayerFile(r"N:\IrrigatedLands\TreasureValley\RandomForest_2025\ForRelease\TV_2025_RandomForest.tif.lyrx"))[0]
tiff_layer.name = f'{abb_name}_{year}_classification'
layout = aprx.listLayouts('ThumbnailLayout')[0]
SelectLayerByAttribute_management(tiff_layer)
map_frame = layout.listElements()[0]
layer_description =Describe(tiff_layer)
layer_type = layer_description.dataType
map_frame.zoomToAllLayers(True)
layout.exportToPNG('insert.png', 72)

#this section creates the thumbnail image and title
white = (255,255,255)
gray = (142,142,142)
blue = (36,117,183)
banner_image = Image.new(mode = 'RGB', size = [720,130], color = blue)
banner_text = 'Zipped File'
banner_draw = ImageDraw.Draw(banner_image)
banner_draw.text([60, 7], banner_text, font = ImageFont.truetype(font = 'Avenir Next LT Pro Demi.otf', size = 120), anchor = 'lt')
banner = banner_image.rotate(90, expand=True)

thumbnail = Image.new(mode = 'RGB', size = [1080, 720], color = white)
logo = Image.open('IDWRLogo.png')
title_image = Image.new(mode = 'RGB', size = [820,240], color = white)
title_draw = ImageDraw.Draw(title_image)
font_size = 1
image_fraction = 0.9
title_text = f'{year} {full_name} Irrigated Lands Machine Learning'
title_font = ImageFont.truetype(font='Avenir Next LT Pro Demi.otf', size=font_size)
font_width = title_font.getbbox(title_text)[2] - title_font.getbbox(title_text)[0]
while font_width < image_fraction*title_image.size[0]:
    font_size +=1
    title_font = ImageFont.truetype(font='Avenir Next LT Pro Demi.otf', size=font_size)
    font_width = title_font.getbbox(title_text)[2] - title_font.getbbox(title_text)[0]
    if font_size >= 100:
        break
if font_size < 40:
    font_size = 50
    title_font = ImageFont.truetype(font='Avenir Next LT Pro Demi.otf', size=font_size)
    words = title_text.split()
    word_count = len(words)
    insert_index = -(word_count//-2) # Where a "\n" line break will go
    if word_count % 2 == 0: # I prefer more words to be on the top line than the bottom, this moves the "\n" later
        insert_index += 1
    words.insert(insert_index, "\n")
    words.append(" ")
    title_text = " ".join(words)
else:
    title_text = title_text

if font_size > 50:
    title_draw.text([410,70], title_text, fill=gray, font=title_font, anchor="mm", align="center")
else:
    title_draw.multiline_text([410,70], title_text, fill=gray, font=title_font, anchor="mm", align="center")
title_image_path = "thumbnail_title.png"
title_image.save(title_image_path)

#this combines the thumbnail and map images into a single thumbnail that gets saved
thumbnail_image = Image.new(mode="RGB", size=(1100, 720), color=white)
map_image = Image.open('insert.png')
thumbnail_image.paste(banner, (941,0))
thumbnail_image.paste(logo, (30,20))
thumbnail_image.paste(map_image, (240,-20))
thumbnail_image.paste(title_image, (100, 590))

background_image = Image.new(mode = 'RGB', size = (1280,720), color = white)
background_image.paste(thumbnail_image, (75,0))

background_image.save('thumbnail.png')
#%%
breaker = ahh

#----------------file setup------------------------
if not Path(x_staging_loc).exists():
    Path(x_staging_loc).mkdir(parents=True, exist_ok=True)

#because this xml file is edited so heavily, we should be able to grab any xml as a template
new_xml = f'{x_staging_loc}\\{abb_name}_{year}_RandomForest.tif.xml'

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

jsons = [i for i in Path(root_path / dirs[-1]).glob('*.json')]
if jsons[0].exists():
    classification_stats = json.dumps(open(jsons[0]))
    used_datasets = classification_stats['datasets']
else:
    #decide whether the reporting document is using old or new formatting (neww as of baileys updates on 8/12/2026)
    try:
        reporting_doc = Document(root_path / dirs[-1] / f'{area}_{year}_v{dirs[-1].split("V")[-1]}_Irrigated_Lands_Reporting.docx')
        check = 'new'
    except:
        reporting_doc = Document(root_path / dirs[-1] / f'{area}-{year}-v{dirs[-1].split("V")[-1]}-classification_Irrigated_lands_reporting.docx')
        check = 'old'

    #get the datasets used in processing
    if check == 'new':
        doc_metadata_table = reporting_doc.tables[1]
    else:
        doc_metadata_table = reporting_doc.tables[0]
    t = []
    for i in doc_metadata_table.column_cells(0):
        t.append(i.text)
        if 'dataset' in i.text or 'Dataset' in i.text:
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
formatted_references = '\n\n'.join(reference_datasets)
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
        # Filter for standard styles
        if p.style.name.startswith(s):
            sections[s].append(p.text)
    single = '\n\n'.join(sections[s])
    sections[s] = single

TAC = sections['Use limitations']
tags = f'Supervised Land Classification, Machine Learning, Random Forest, Water Budget, Monitoring, Hydrology, Groundwater, Surface Water, Irrigated Areas, Irrigation, Irrigated, Non-Irrigated, Regulatory, Farming, Idaho, ID, Idaho, Water, Water Use, {full_name}, {abb_name}, IDWR GIS Department, Environment'
place_keywords = f'{full_name}, {abb_name}, Idaho, ID'
if region == 'TreasureValley':
    file_title = f'{year} Irrigated Lands for the {full_name} Aquifer: Machine Learning Generated'
file_title = f'{year} Irrigated Lands for the {full_name} ({abb_name}): Machine Learning Generated'
complete_file_name = f'{abb_name}_{year}_RandomForest'
description = sections['Description']
summary = sections['Summary']
extras = sections['Extras']
#to preserve the original thumbnail after arcpy steals it, I'm creating two links 
original_thumbnail_link = 'thumbnail.png'
thumbnail_link = 'thumbnail_backup.png'         #NOTE: for whatever reason, this seems to cause problems. The file keeps moving after the code runs, which stops the code from running, but the code runs fine if you run it twice.
copy(original_thumbnail_link, thumbnail_link)   #which is why this line is here, to hedge our bets 
creation_date = strftime('%Y-%m-%d %H:%M:%S', strptime(ctime(getmtime(str(list(Path(n_loc).glob('*.tif'))[0])))))
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

#NOTE: we can probaly edit metadata in a few places, or omit, or some things need edits. Here is a list: (looking at ESPA 2024 for reference)
#DONE NEEDS REVIEW'Extents: Description' should be about the extent,
#TODO'Resource Contstraints' whole thing can be the same as access constraints or does it need to be different?,
#DONE, SHOULD GET REVIEWED 'Data Quality: Data Qaulity Report - Conceptual consistency' should proabably be something related to how we do QAQC for both measure reference and procedure
#DONE, SHOULD GET REVIEWED'Data Quality: Data Qaulity Report - Completeness Omission' I'm not sure what this is or hwo it is different than above so needs researched,
#TODO Pretty much everything in 'Data Quality' Needs more intel before we know what to put in there,
#TODO'Lineage: Lineage statment' Probably can be the general steps and tools we use to make the dataset maybe?,
#TODO'Lineage: Process Step' I dont know if this is just the last step or a specific line out of steps or how it relates to rationale,
#TODO'Geoprocessing History' I imagine this is the same as lineage, but it looks like it is just tracking the last tool used on the dataset in Arc,
#TODO'Fields': I dont know if we can or should alter any of this, except for changing how it references the .vat file, as it is referencing the wrong dataset
#TODO'Metadata Details': IS this similar to the lineage? I don't know why it is referencing such an old dataset, but also don't know if we can edit that
#TODO'Metadata Constraints':these are again constraints and limitations that may need to be refined for this section, but they may also be fine to mirror the other constraints

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
                 './/dqInfo/dataLineage/prcStep/stepDesc': None, #NOTE: It seems like these are just steps used to create the dataset, do we need to provide this or do the methods kind of sum it up?
                 './/dqInfo/dataLineage/prcStep/stepRat': None,
                 './/dqInfo/dataLineage/statement': summary,
                 './/dataIdInfo/idCitation/otherCitDet': None,
                 './/dqInfo/report[@type="DQConcConsis"]/measDesc': 'Each image in the Irrigated Lands dataset is post-processed by trained GTS staff before publication. GTS staff implement the NAIP, CDL, and METRIC ET datasets in post processing when the datasets are available. These datasets aid GTS staff by providing information on irrigated area that is unable to be effectively introduced to the classification model, or can be easier referenced as a standalone image. When a group of pixels that total an area greater than 160 acres (approximately a quarter-section) is determined to be misclassified via the additional datasets, a manual mask is applied to the classification raster. Areas less than 160 acres are generally inconsequential to overall model predictions and thus are left as the initial model prediction value.',
                 './/dqInfo/report[@type="DQConcConsis"]/evalMethDesc': 'Irrigation masks are only applied when there is sufficient evidence of irrigation from either evapotranspiration, spectral, or high-resolution imagery. If there is insufficient evidence of irrigation, then the model prediction is the default value assigned to a pixel and a mask is not applied. Masks cover less than ten percent of the study area. Ground truthing of irrigation maps is not completed by GTS staff.',
                 './/dqInfo/report[@type="DQCompOm"]/measDesc': None,
                 './/dqInfo/report[@type="DQCompOm"]/evalMethDesc': None,
                 './/dqInfo/report[@type="DQQuanAttAcc"]/measDesc': 'Data are not ground truthed by GTS staff. No guarantees or warranties are provided for physical ground accuracy with these data.',
                 './/dataIdInfo/idCitation/datasetSeries/issId': year,
                 './/dataIdInfo/dataExt/exDesc': f'Extent encompasses the {full_name} area for the purposes of classifying irrigated area. Extent shapefiles can be found at https://data-idwr.hub.arcgis.com/datasets/366d8c9764d346878038a10e346784b0_0/explore',
                 './/dataIdInfo/dataExt/tempEle/TempExtent/exTemp/TM_Period/tmBegin': f'{year}-03-01T00:00:00',
                 './/dataIdInfo/dataExt/tempEle/TempExtent/exTemp/TM_Period/tmEnd': f'{year}-11-01T00:00:00',
                 './/dataIdInfo/tpCat': 'Irrigated Lands',
                 './/dataIdInfo/tpCat/TopicCatCd': 'Irrigated Lands',
                 './/eainfo/detailed/enttyp/enttypl': f'{abb_name}_{year}_RandomForest.tif',
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
use_helpers = False
if use_helpers:
    for elem in root.iter():
        if 'date' in elem.tag.lower() or 'Date' in elem.tag:
            # build the path from root down to this element
            path = []
            e = elem
            # ElementTree doesn't track parents, so just print tag + text for now
            print(elem.tag, '->', elem.text)

    #a helper loop that finds instances of a string in the xml and prints the path to update the dicitonary with if needed
    parent_map = {c: p for p in root.iter() for c in p}

    def get_path(elem):
        path = [elem.tag]
        while elem in parent_map:
            elem = parent_map[elem]
            path.append(elem.tag)
        return '/'.join(reversed(path))

    for elem in root.iter():
        if 'enttypl' in elem.tag.lower():
            print(get_path(elem), '=', elem.text)

#%%
#helper to view the xml in case you need to find a path for editing metadata 
if use_helpers:
    import xml.dom.minidom as minidom
    
    tgt_md = metadata.Metadata(target_tif)
    pretty = minidom.parseString(tgt_md.xml).toprettyxml(indent='  ')
    print(pretty)

#%%
from arcgis.gis import GIS

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
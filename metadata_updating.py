#%%
from pathlib import Path
from shutil import copy
from arcpy import metadata, mp, SpatialReference
from PIL import Image, ImageDraw, ImageFont
from os.path import getmtime
from time import strftime, strptime, ctime, time
import xml.etree.ElementTree as ET
from docx import Document
from python_docx_replace import docx_replace
from ruamel.yaml import YAML
import json
from thumbnail_generation import generateThumbnail


#-----------------------static variables -------------------------
with open('metadata_dictionaries.json') as js:
    file = json.load(js)
    location_dict = file['location_dict']
    datasets_dict = file['datasets_dict']

#template metadata file for classified imagery
template_xml = r"X:\Spatial\LandCover_Vegetation\SnakePlain\MachineLearning\ESPA_2024_RandomForest.tif.xml"

#get the configuration info
parent_dir = Path(__file__).parent.absolute()
config_file = parent_dir / "config_file.yml"
yaml = YAML()
yaml.preserve_quotes = (True)
with open(config_file) as f:
    config = yaml.load(f)
    
year = str(config['year'])

#region is a key lookup value for the location_dict (the N: location)
area = config['area']

#this if is a weird edge case with the renaming of the Treasure Valley and how we are handling that moving forward
if area != 'tv':
    region = [l for l in location_dict.keys() if area.casefold() == str(location_dict[l][1]).casefold()][0]
else:
    region = 'TreasureValley'

#path to root folder of training data to find the reporting folder
root_path = Path(config['training_data']).parent.parent

x_drive_name = location_dict[region][0] #ie., BoiseValley
abb_name = location_dict[region][1] #ie., TV
full_name = location_dict[region][2] #ie., Treasure Valley

#----------------file locations--------------------
n_loc = f'N:\\IrrigatedLands\\{region}\\RandomForest_{year}\\forRelease'
x_spatial_loc = f'X:\\Spatial\\LandCover_Vegetation\\{x_drive_name}\\MachineLearning'
x_staging_loc = f'X:\\Staging_X_Y\\LandCover_Vegetation\\{x_drive_name}\\MachineLearning'
metadata_loc = f'N:\\IrrigatedLands\\rf_metadata_template.docx'

#metadata document in a docx format for easy editing when things need changed
doc = Document(metadata_loc)

if not Path(Path.cwd()/'temp').exists():
    Path(Path.cwd()/'temp').mkdir()
temp_folder = str(Path.cwd()/'temp')
#%%
#make the thumbnail for the portal item 
generateThumbnail(year, full_name, temp_folder, n_loc)

#----------------file setup------------------------
if not Path(x_staging_loc).exists():
    Path(x_staging_loc).mkdir(parents=True, exist_ok=True)

new_xml = f'{x_staging_loc}\\{abb_name}_{year}_RandomForest.tif.xml'

#because this xml file is edited so heavily, we should be able to grab any xml as a template
#right now, it seems like if we always take a single template xml we can prevent most issues 
copy(template_xml,  new_xml)

#rename all files to the LOCATION_YYYY_RandomForest convention when copying to the x staging folder
for f in Path(n_loc).glob('*.*'):
    extension = '.'.join(f.name.split('.')[1:])
    if '.doc' not in extension:
        new_name = f'{abb_name}_{year}_RandomForest.{extension}'
        new_file = f'{x_staging_loc}/{new_name}'
        copy(f, new_file)

#----------------metadata elements------------------
#get the reporting doc to get the list of bands used out of it
dirs = []
for n in [f.name for f in root_path.glob('**/*') if f.is_dir()]:
    if 'reporting' in n:
        dirs.append(n)

#the new method is to get reporting info in a json, but the old format is just a word doc
#this accounts for both methods automatically
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

#empty lists to be filled later 
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

#the sections of the metadata document to parse
sections = {'Summary':[], 'Description':[], 'Normal':[], 
            'Credits':[], 'Use limitations':[], 'Extras':[]}

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
original_thumbnail_link = Path(temp_folder) / 'thumbnail.png'
thumbnail_link = Path(temp_folder) / 'thumbnail_backup.png' #NOTE: for whatever reason, this seems to cause problems. The file keeps moving after the code runs, which stops the code from running, but the code runs fine if you run it twice.
copy(original_thumbnail_link, thumbnail_link)         #which is why this line is here, to hedge our bets 
creation_date = strftime('%Y-%m-%d %H:%M:%S', strptime(ctime(getmtime(str(list(Path(n_loc).glob('*.tif'))[0])))))
publication_date = strftime('%Y-%m-%d %H:%M:%S', strptime(ctime(time())))
edition_date = strftime('%Y-%m-%d', strptime(ctime(time())))

#----------------defining metadata----------------------
for i in Path(x_staging_loc).glob('*.tif'):
    target_tif = i
target_tif_meta = metadata.Metadata(target_tif)

#updating of metadata pieces through the ESRI interface
target_tif_meta.title = file_title
target_tif_meta.accessConstraints = TAC
target_tif_meta.tags = tags
target_tif_meta.credits = 'Idaho Department of Water Resources (IDWR)'
try:
    target_tif_meta.thumbnailUri = str(thumbnail_link)
except:
    target_tif_meta.thumbnailUri = str(original_thumbnail_link)
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


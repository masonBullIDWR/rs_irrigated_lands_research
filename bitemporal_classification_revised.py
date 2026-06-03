#Script for creating training data and classifying an image of change between two years
#%%
import ee, geemap
import geopandas as gpd
import pandas as pd
from plotnine import *
import seaborn as sns
import matplotlib.pyplot as plt
import fnmatch
from osgeo import gdal
import pathlib
import numpy as np
ee.Authenticate()
ee.Initialize(project = 'idwr-450722')
ee.data.setDefaultWorkloadTag('bimodal-change-classification')

#%%data gathering and setup
dateRange = ['2013','2024']

shp = ee.FeatureCollection('projects/idwr-450722/assets/TreasureValley/TVGWFM_boundary').geometry()
irrMapper = ee.ImageCollection("UMT/Climate/IrrMapper_RF/v1_2").filterBounds(shp).filterDate('1985-01-01', dateRange[1]+'-12-31').filter(ee.Filter.stringContains('system:index', 'ID'))
ls = ee.ImageCollection("NASA/HLS/HLSL30/v002").filterBounds(shp).filter('CLOUD_COVERAGE <= 30').filterDate(dateRange[0]+'-01-01', dateRange[1]+'-12-31')
etStart = ee.ImageCollection("projects/openet/assets/ensemble/conus/gridmet/monthly/v2_1").filterBounds(shp).filterDate(dateRange[0]+'-01-01', dateRange[1]+'-12-31').select('et_ensemble_mad')
et0 = ee.ImageCollection("projects/openet/assets/reference_et/conus/gridmet/daily/v1").filterBounds(shp).filterDate(dateRange[0]+'-01-01', dateRange[1]+'-12-31').select('eto')
dem = ee.ImageCollection('USGS/3DEP/10m_collection').filterBounds(shp).mosaic()
elevation = ee.Image(dem.select('elevation')).reproject(crs='EPSG:8826', scale=30)
aspect = ee.Terrain.aspect(ee.Image(elevation))
slope = ee.Terrain.slope(ee.Image(elevation))
cdl = ee.ImageCollection('USDA/NASS/CDL').filterDate(dateRange[0]+'-01-01', dateRange[1]+'-12-31')

#%%This cell will compute a single year's irrigation/non-irrigation as an image, and will do that for the input dateRange
#this won't compute the gain or loss between years, it's classifying a single year's total area for binary classification

#this cell should run everything that the code needs to put out some imagery
#filter and sum eto to monthly data
yearList = list(range(int(dateRange[0]), int(dateRange[1])+1))
monthList = list(range(4,11))

#this gets us the change in landcover according to IrrMapper
##we use this later to determine the backwards change direction of our training data
###this is not the most accurate way to do this, but it saves so much time and is not a bad approximation
def GetIrrMapperChange(y):
    year = ee.Number(y).format('%04d')
    year_2 = ee.Number(y).add(1).format('%04d')
    first_img = irrMapper.filterDate(ee.String(year).cat('-01-01'), ee.String(year).cat('-12-31')).first()
    second_img = irrMapper.filterDate(ee.String(year_2).cat('-01-01'), ee.String(year_2).cat('-12-31')).first()

    img_1 = first_img.add(1).unmask(0).remap( [0,1], [1,2]) #these remappings set us up for easier determination of changes in the next step
    img_2 = second_img.add(1).unmask(0).remap([0,1], [3,5])

    #the weird remapping gets us in the order of {Ni to Ir:0, Ir to Ir:1, Ir to Ni:2, Ni to Ir:3}
    forward_im_change = img_1.add(img_2).remap([4,5,6,7], [0,2,3,1]).set({'system:time_start':ee.String(year).cat('-01-01'),
                                                                          'system:time_end':ee.String(year_2).cat('-12-31'),
                                                                          'forward': ee.String(year).cat('_').cat(year_2)})
    backward_im_change = img_2.subtract(img_1).remap([1,2,3,4], [3,0,1,2]).set({'system:time_start':ee.String(year_2).cat('-01-01'),
                                                                                'system:time_end':ee.String(year).cat('-12-31'),
                                                                                'backward': ee.String(year_2).cat('_').cat(year)})
    im_change_col = ee.ImageCollection.fromImages([forward_im_change, backward_im_change]).set({'years': ee.String(year).cat('_').cat(year_2)})
    return im_change_col

irrMapper_changes = ee.List(yearList).map(GetIrrMapperChange)

etoMonthlyList = ee.List([])
et = ee.List([])
#function to calulate ET from ET0 and OpenET standard data
for y in yearList:
    if y < 2016:
         etStart = ee.ImageCollection("projects/openet/assets/ensemble/conus/gridmet/monthly/v2_0").filterBounds(shp).filterDate(dateRange[0]+'-01-01', dateRange[1]+'-12-31').select('et_ensemble_mad')
    for m in monthList:
        time =  ee.Number(y).format('%04d').cat(ee.Number(m).format('%02d'))        
        if m in [4, 6, 9, 11]:
            day = 30
        elif m in [1, 3, 5, 7, 8, 10, 12]:
            day = 31
        elif m == 2:
            day = 28
        etoSum = et0.filter(ee.Filter.stringContains('system:index', time)).sum()
        etoSum = etoSum.set({'date': time}).set('system:id', ee.String('eto_').cat(time)).rename(ee.String('eto_').cat(time))
        etoMonthlyList = etoMonthlyList.add(etoSum)
        etEns = etStart.filter(ee.Filter.stringContains('system:index', time)).first()
        etFin = etEns.divide(etoSum).rename('et_calculated').set({'et_date': ee.String('et_calculated_').cat(time)})
        etFin = etFin.set({'system:time_start':ee.Number(y).format('%04d').cat('-').cat(ee.Number(m).format('%02d')).cat('-01'),
                           'system:time_end':ee.Number(y).format('%04d').cat('-').cat(ee.Number(m).format('%02d')).cat('-').cat(ee.Number(day).format('%02d'))})
        et = et.add(ee.Image(etFin).toFloat())

etoMonthly = ee.ImageCollection.fromImages(etoMonthlyList)
et = ee.ImageCollection.fromImages(et)
# this is for taking the growing season comparisons
#seasonal averages
def setNDVI(img):
    ndvi = img.normalizedDifference(['B5', 'B4']).rename('ndvi')
    return img.addBands(ndvi)

#get all of the variables into one collection
def getImageData(y):
    year = ee.Number(y).format('%04d')
    startDateFormat = year.cat(ee.String('-04-01'))
    endDateFormat  =  year.cat(ee.String('-11-01'))  
    lsDat  = ls.filterDate( startDateFormat, endDateFormat).select(['B[2-7]']).map(setNDVI).mean().rename([
        ee.String('B2_').cat(year), ee.String('B3_').cat(year), ee.String('B4_').cat(year), ee.String('B5_').cat(year), 
        ee.String('B6_').cat(year), ee.String('B7_').cat(year), ee.String('averagedNdvi_').cat(year)
    ])
    etDat  = et.filterDate( startDateFormat, endDateFormat).mean().rename(ee.String('AveragedET_').cat(year))
    
    out_image = lsDat.addBands(etDat).set({'system:time_start': ee.String(year).cat('-01-01'),
                                           'system:time_end': ee.String(year).cat('-12-31')})

    return out_image

ls_et_combined_images = ee.ImageCollection.fromImages(ee.List(yearList).map(getImageData))

#Following Phil's advice to concatenate images instead of taking a quotient
def concatenate(img1, img2):
    firstImg  = ee.Image(img1).rename(['B2_first', 'B3_first', 'B4_first', 'B5_first', 'B6_first', 'B7_first', 'averagedNdvi_first', 'averagedET_first'])
    secondImg = ee.Image(img2).rename(['B2_second', 'B3_second', 'B4_second', 'B5_second', 'B6_second', 'B7_second', 'averagedNdvi_second', 'averagedET_second'])
    stack = firstImg.addBands([secondImg, elevation, slope, aspect])
    return stack

#this combines images in the forward direction
cat_images = ee.List([])
for i in yearList:
    j = i+1
    if j > yearList[-1]:
        break
    year_1 = ee.Number(i).format('%04d')
    year_2 = ee.Number(j).format('%04d')

    img_1_forward = ls_et_combined_images.filterDate(ee.String(year_1).cat('-01-01'), ee.String(year_1).cat('-12-31')).first()
    img_2_forward = ls_et_combined_images.filterDate(ee.String(year_2).cat('-01-01'), ee.String(year_2).cat('-12-31')).first()

    cat = concatenate(img_1_forward, img_2_forward).set('system:index', ee.String('cat').cat(ee.String(year_1.slice(2)).cat(ee.String(year_2.slice(2)))))
    cat_images = cat_images.add(cat)

#this combines images in the backwards direction
#we do this in two directions for the final binary classification to do some Bayesian stuff on
cat_images_reverse = ee.List([])
for i in yearList:
    j = i-1
    if j < yearList[0]:
        continue
    if i > yearList[-1]:
        break
    year_1_backward = ee.Number(i).format('%04d')
    year_2_backward = ee.Number(j).format('%04d')

    img_1_backward = ls_et_combined_images.filterDate(ee.String(year_1_backward).cat('-01-01'), ee.String(year_1_backward).cat('-12-31')).first()
    img_2_backward = ls_et_combined_images.filterDate(ee.String(year_2_backward).cat('-01-01'), ee.String(year_2_backward).cat('-12-31')).first()

    cat_backward = concatenate(img_1_backward, img_2_backward).set('system:index', ee.String('cat').cat(ee.String(year_1_backward.slice(2)).cat(ee.String(year_2_backward.slice(2)))))
    cat_images_reverse = cat_images_reverse.add(cat_backward)

training_image = ee.Image(cat_images.filter(ee.Filter.equals('system:index', 'cat1819')).get(0))
bands = training_image.bandNames()

client_points = gpd.GeoDataFrame.from_file("C:\\Users\\mason.bull\\OneDrive - State of Idaho\\Desktop\\Geoprocessing\\Data\\TV\\bimodalChange\\trainingData18_19_cat_moved.shp")
client_points_trimmed = client_points[['geometry', 'im_changeC']]
server_points = geemap.gdf_to_ee(client_points_trimmed)

forward_points = training_image.sampleRegions(
    collection= server_points,
    scale = 30,
    projection= 'EPSG:8826'
)
forward_points_props = forward_points.first().propertyNames()

status_change_dict = ee.Dictionary({'0':0, '1':1, '2':3, '3':2})
def reverseDirection(feat):
    firsts_names =  forward_points_props.filter(ee.Filter.stringContains('item', '_first')).sort() #get the list of properties with first in them
    seconds_names = forward_points_props.filter(ee.Filter.stringContains('item', '_second')).sort() #with second in them
    new_seconds = ee.Feature(feat).select(firsts_names, seconds_names) #rename the ones with first to second
    new_firsts = ee.Feature(feat).select(seconds_names, firsts_names) #vice versa
    new_status = status_change_dict.get(ee.Number(feat.get('im_changeC')).format('%01d')) #change the status if it needs changed
    new_feat = new_firsts.copyProperties(new_seconds).set('im_changeC', new_status).copyProperties(
        feat, ['elevation', 'aspect', 'slope']).set('system:index', ee.String(feat.get('system:index')).cat('_02')) #create the new feature that is looking in the opposite direction from the input
    return new_feat

backward_points = forward_points.map(reverseDirection)

forward_points = forward_points.randomColumn().filter(ee.Filter.notNull(forward_points_props))
backward_points = backward_points.randomColumn().filter(ee.Filter.notNull(forward_points_props))

forward_training = forward_points.filter('random <= 0.8')
forward_testing  = forward_points.filter('random > 0.8')

backward_training = backward_points.filter('random <= 0.8')
backward_testing  = backward_points.filter('random > 0.8')


forward_classifier = ee.Classifier.smileRandomForest(100).train(
        features = forward_training,
        classProperty = 'im_changeC',
        inputProperties = bands)
backward_classifier = ee.Classifier.smileRandomForest(100).train(
        features = backward_training,
        classProperty = 'im_changeC',
        inputProperties = bands)
forward_probability_classifier = ee.Classifier.smileRandomForest(100).setOutputMode('multiprobability').train(
      features = forward_training,
      classProperty = 'im_changeC',
      inputProperties = bands)
backward_probability_classifier = ee.Classifier.smileRandomForest(100).setOutputMode('multiprobability').train(
      features = backward_training,
      classProperty = 'im_changeC',
      inputProperties = bands)

def classifyImagePairsForward(img):
    imageName = ee.Image(img).get('system:index')
    imageClassified = ee.Image(img).classify(forward_classifier).rename('classification_forward')
    
    imageProb = ee.Image(img).classify(forward_probability_classifier, 'probability').rename('probability_forward')

    results = ee.Image(imageClassified).addBands(ee.Image(imageProb))

    namedResults = results.set('system:index', imageName)
    return namedResults
    
all_done_forward = cat_images.map(classifyImagePairsForward)

def classifyImagePairsBackward(img):
    imageName = ee.Image(img).get('system:index')
    imageClassified = ee.Image(img).classify(backward_classifier).rename('classification_backward')
    
    imageProb = ee.Image(img).classify(backward_probability_classifier, 'probability').rename('probability_backward')

    results = ee.Image(imageClassified).addBands(ee.Image(imageProb))

    namedResults = results.set('system:index', imageName)
    return namedResults
    
all_done_backward = cat_images_reverse.map(classifyImagePairsBackward)

flattenNames = ['NN', 'II', 'IN', 'NI']
maxSize = ee.Number(all_done_forward.size()).subtract(1)

#then use the classifier to classify every year individually via a function
def binaryClassification(item):
        num = all_done_forward.indexOf(item)
        conTest = ee.Number(num.add(1))
        num2 = ee.Algorithms.If(conTest.gt(maxSize),
                                num,
                                num.add(1))
        name_2_forward = ee.Image(all_done_forward.get(num2)).get('system:index')

        year = ee.String('20').cat(ee.String(ee.String(name_2_forward).split('cat').get(1)).slice(0, 2))

        beforeArrayForward = ee.Image(ee.Image(all_done_forward.get(num)).select('probability_forward')).toArray().arrayFlatten([flattenNames])
        afterArrayForward =  ee.Image(ee.Image(all_done_forward.get(num2)).select('probability_forward')).toArray().arrayFlatten([flattenNames])

        beforeArrayBackward = ee.Image(ee.Image(all_done_backward.get(num)).select('probability_backward')).toArray().arrayFlatten([flattenNames])
        afterArrayBackward =  ee.Image(ee.Image(all_done_backward.get(num2)).select('probability_backward')).toArray().arrayFlatten([flattenNames])

        irrProb = ee.Image(beforeArrayForward.select( 'II').add(
                           beforeArrayForward.select( 'NI'))).multiply(
                  ee.Image(afterArrayForward.select(  'II').add(
                           afterArrayForward.select(  'IN')))).multiply(
                  ee.Image(beforeArrayBackward.select('II').add(
                           beforeArrayBackward.select('IN')))).multiply(
                  ee.Image(afterArrayBackward.select( 'II').add(
                           afterArrayBackward.select( 'NI')
                        ))).rename('IrrProb')
        nirrProb = ee.Image(beforeArrayForward.select('NN').add(
                           beforeArrayForward.select('IN'))).multiply(
                  ee.Image(afterArrayForward.select( 'NN').add(
                           afterArrayForward.select( 'NI')))).multiply(
                  ee.Image(beforeArrayBackward.select('NN').add(
                           beforeArrayBackward.select('NI')))).multiply(
                  ee.Image(afterArrayBackward.select( 'NN').add(
                           afterArrayBackward.select( 'IN')
                        ))).rename('NIrrProb')
        stack = ee.Image(irrProb.gt(nirrProb).rename('classification')).set({'item': ee.String('binaryClass').cat(year),
                                                                             'system:time_start': year})
        return stack

binary_irrigation_images = ee.ImageCollection.fromImages(all_done_forward.map(binaryClassification).remove(-1))

sqm = 900
sqkm = 1e6

def getArea(img):
      name = ee.Image(img).get('item')
      year = ee.Image(img).get('system:time_start')
      classification = ee.Image(img).select('classification')
      irr = ee.Number(ee.Image(classification).eq(1).selfMask().reduceRegion(reducer = ee.Reducer.count(), geometry= shp, scale=30,crs='EPSG:8826').get('classification')).multiply(sqm).divide(sqkm)
      nirr = ee.Number(ee.Image(classification).eq(0).selfMask().reduceRegion(reducer = ee.Reducer.count(), geometry= shp, scale=30,crs='EPSG:8826').get('classification')).multiply(sqm).divide(sqkm)
      feature = ee.Feature(None, {'irrArea': irr,
                                  'nirrArea': nirr,
                                  'year': year,
                                  'id': name})
      return feature
output_areas = ee.FeatureCollection(binary_irrigation_images.map(getArea))

#%%
#single image export just for checking stuff out or creating training data
ee.batch.Export.image.toDrive(
    image=ee.Image(all_done_forward.get(4)).select('classification_forward'),
    fileNamePrefix= 'bitemporal_change_2017_2018',
    description='bitemporal_change_2017_2018_export',
    scale=30,
    crs='EPSG:8826',
    formatOptions= {'cloudOptimized': True},
    region= shp
).start()
ee.batch.Export.image.toDrive(
    image=ee.Image(all_done_forward.get(6)).select('classification_forward'),
    fileNamePrefix= 'bitemporal_change_2019_2020',
    description='bitemporal_change_2019_2020_export',
    scale=30,
    crs='EPSG:8826',
    formatOptions= {'cloudOptimized': True},
    region= shp
).start()
#%%export the Forward/Backward classification
ee.batch.Export.table.toDrive(output_areas,
                              description='bitemporal_change_irrigation_area_revised_export',
                              fileNamePrefix='bitemporal_change_irrigation_area_revised',
                              fileFormat='CSV').start()
#%%

dat = pd.read_csv(r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\bimodalChange\bitemporal_change_irrigation_area_revised.csv").drop(['.geo', 'system:index'], axis=1)
dat['irrAcres'] = dat['irrArea']*247
fig, ax = plt.subplots()
sns.lineplot(data = dat, x = 'year', y= 'irrAcres')
fig.show()
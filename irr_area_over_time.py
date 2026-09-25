#%%
#import setup libraries
import pathlib
import rasterio
import numpy as np
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt

#set the root directory to find the raster files
root = pathlib.Path(r'C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV')
#root = pathlib.Path(r'C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\bulc_stuff')

#get the list of raster images that are ready to be plotted 
rasters = list(root.glob('**/*_postProcessed.tif'))
[rasters.append(i) for i in list(root.glob('**/tv*-final-COG.tif'))]
#rasters = list(root.glob('**/tv_bulc_im_class_*_l0-0_mp0-05.tif'))

nlcd_rasters = list(root.glob('**/wspa_nlcd*-final-COG.tif'))
#assign an empty dictionary to be filled later
reg_output_list = []
urb_masked_list = []

def get_irr_area(year, region = 'wspa'):
    if region == 'wspa':
        rf = list(root.glob(f'**/tv-{year}*-final-COG.tif'))[0]
    else:
        rf = list(root.glob(f'**/{region}-{year}*-final-COG.tif'))[0]

    nlcd_check = list(root.glob(f'**/{region}_nlcd_{year}*-final-COG.tif'))[0] != None #check if nlcd images exist

    with rasterio.open(rf) as src:
        rf_rast = src.read(1)
        rf_meta = src.meta
        irr_pixels = np.count_nonzero(rf_rast == 1)
        pixel_area = abs(round(src.transform[0])*round(src.transform[4]))/1e6 #pixel area in square kilometers

    if nlcd_check:
        nlcd = list(root.glob(f'**/{region}_nlcd_{year}*-final-COG.tif'))[0]
        with rasterio.open(nlcd) as src:
            nlcd_rast = src.read(1)
            nlcd_meta = src.meta
        if rf_rast.shape != nlcd_rast.shape:
            rf_rast_stack = np.column_stack((rf_rast, np.linspace(255,255,num = rf_meta['height'])))
        else:
            rf_rast_stack = rf_rast

        urban = np.where((nlcd_rast >= 23) & (nlcd_rast <= 24), 255, np.nan)

        rf_urban_filt = np.where(urban == 255, #where urban is 255
                        255, #set 255
                        rf_rast_stack) #into rf array

        irr_area_urb_filt = np.count_nonzero(rf_urban_filt == 1) * pixel_area
        urb_masked_list.append({'region':region, 'year': int(year), 'area': irr_area_urb_filt})
    
    irr_area = irr_pixels * pixel_area

    print(f'{region} {year} irrigated area: {irr_area} km²')
    reg_output_list.append({'region':region, 'year': int(year), 'area': irr_area})

years = ['1987', '1997', '2000', '2004', '2007', '2010', '2015', '2023', '2025']
#loop through rasters and apply the function
for i in years:
    get_irr_area(i)

#put the irrigated area into a dataframe
plotting_df = pd.DataFrame(reg_output_list).sort_values('year')

filtered_plotting_df = pd.DataFrame(urb_masked_list).sort_values('year')

#plot
fig, ax = plt.subplots()
sns.lineplot(plotting_df, ax = ax, y = 'area', x = 'year', color = 'green', marker= 'o')
ax.set_xlabel('Year')
for i in zip(plotting_df.groupby('year')):
    for x,y,s in i[0][1][['year','area','year']].values:
        if x == 2025:
            ax.text(x-3.5,y + 5,int(s))    
        else:
            ax.text(x+0.5,y + 5,int(s))
ax.set_ylabel('Area (km²)')
ax.set_title('Unfiltered Irrigated Area')

fig1, ax1 = plt.subplots()
sns.lineplot(plotting_df, ax = ax1, y = 'area', x = 'year', color = 'green', marker= 'o')
ax1.set_xlabel('Year')
for i in zip(plotting_df.groupby('year')):
    for x,y,s in i[0][1][['year','area','year']].values:
        if x == 2025:
            ax1.text(x-3.5,y + 5,int(s))    
        else:
            ax1.text(x+0.5,y + 5,int(s))
ax1.set_ylabel('Area (km²)')
ax1.set_title('Irrigated Area without Urban area')

fig.show()
fig1.show()

#%%
#testing functionality
get_irr_area(pathlib.Path(r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\TV1997\rast\tv-1997-v3-classification-final-COG.tif"))

nlcd_97_path = nlcd_rasters[-2]
with rasterio.open(nlcd_97_path) as src:
    nlcd_97 = src.read(1)
    nlcd_97_meta = src.meta
with rasterio.open(r"C:\Users\mason.bull\OneDrive - State of Idaho\Desktop\Geoprocessing\Data\TV\TV1997\rast\tv-1997-v3-classification-final-COG.tif") as src:
    rf_97 = src.read(1)
    rf_97_meta = src.meta


rf_97_stack = np.column_stack((rf_97, np.linspace(255,255,num = rf_97_meta['height'])))
plt.imshow(rf_97)
plt.imshow(nlcd_97)

urban = np.where((nlcd_97 >= 23) & (nlcd_97 <= 24), 255, np.nan)
urban.shape
plt.imshow(urban)

fin = np.where(urban == 255, #where urban is 255
               255, #set 255
               rf_97_stack) #into rf array
plt.imshow(fin)

irr_pixels = np.count_nonzero(fin == 1)
pixel_area = abs(round(rf_97_meta['transform'][0])*round(rf_97_meta['transform'][4]))/1e6 #pixel area in square kilometers
irr_area = irr_pixels * pixel_area
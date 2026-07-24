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

#get the list of raster images that are ready to be plotted 
rasters = list(root.glob('**/*_postProcessed.tif'))

#assign an empty dictionary to be filled later
output_list = []

#define a function to get the irrigated area of each image
def get_irr_area(path):
    region, year, *other = path.name.split('-')

    with rasterio.open(path) as src:
        rast = src.read(1)
        irr_pixels = np.count_nonzero(rast == 1)
        pixel_area = abs(round(src.transform[0])*round(src.transform[4]))/1e6 #pixel area in square kilometers
        irr_area = irr_pixels * pixel_area

    print(f'{region} {year} irrigated area: {irr_area} km²')
    output_list.append({'region':region, 'year': int(year), 'area': irr_area})

#loop through rasters and apply the function
for i in rasters:
    get_irr_area(i)

#put the irrigated area into a dataframe
plotting_df = pd.DataFrame(output_list).sort_values('year')

#plot
fig, ax = plt.subplots()
sns.lineplot(plotting_df, ax = ax, y = 'area', x = 'year', color = 'green', marker= 'o')
ax.set_xlabel('Year')
for i in zip(plotting_df.groupby('year')):
    for x,y,s in i[0][1][['year','area','year']].values:
        if x == 2023:
            ax.text(x-3.5,y + 5,int(s))    
        else:
            ax.text(x+0.5,y + 5,int(s))
ax.set_ylabel('Area (km²)')
# Update Metadata of tiffs with ArcPy

This is the family of scripts that will automatically update the metadata for a tiff file that needs to end up on AGOL and portal. 
The script runs in two parts. 
* First, run metadata_updating.py, if the config file is set up correctly and you have arcpy in your environment it should be no problem. After this is run, you need to wait for GIS Admin to zip up the created files and move them onto X:\Spatial
* Second, after files are moved by Admin, run item_publishing.py. This moves the data onto Portal.

Most of the required packages are standard for a remote sensing workflow. You need to have arcpy and python_docx_replace in the environment
# Required Items
## _**Scripts**_:
### metadata_updating.py
* The main script for updating metadata. You should just be able to hit run and it will do most everything for you.

### thumbnail_generation.py
* The script that creates the thumbnail image that is displayed on Portal and AGOL.  
### item_publishing.py
* Script that moves data from X:\Spatial up to Portal

## _**Files**_:
### config_file.yml
* The configuration file for metadata_updating.py. Must be housed with the source folder in files folder. Be sure to set the items:
  *  **area**: the abbreviated name of the region you are working in (eg., espa for the ESPA, tv or wspa for the WSPA)
  * **year**:  the year of the image you are updating. An integer.
  * **training_data**: the path to the training data used in classification. This is used to find the reporting document for your metadata.
### metadata_dictionaries.json
* A json file that contains all of the metadata categories and their names that move into the metadata. Must be housed with the source folder in files folder.
### Avenir Next LT Pro Bold.otf | Avenir Next LT Pro Demi.otf
* fonts that get put onto the AGOL thumbnail. These can be found on the N:\ Drive if they are not in the files folder.
### IDWRLogo.png
* IDWR's color logo image file for the thumbnail. Can be found on the N:\ Drive if they are not in the files folder.


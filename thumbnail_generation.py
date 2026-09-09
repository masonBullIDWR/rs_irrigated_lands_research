'''
Script that creates a thumbnail for a Portal item from an aprx and stores it in a temporary folder in the source folder.
'''
#%%
from pathlib import Path
from shutil import copy
from arcpy import mp, SpatialReference
from PIL import Image, ImageDraw, ImageFont

template_aprx_path = r"N:\IrrigatedLands\portal_thumbnail_template_aprx\portal_thumbnail_template_aprx.aprx"
logo_path = 'IDWRLogo.png'
font_path = 'Avenir Next LT Pro Demi.otf'

if not Path(logo_path).exists():
    print('IDWR logo not found in source folder, using N: location instead.')
    logo_path = r"N:\IrrigatedLands\Misc\rf_metadata\IDWRLogo.png"
if not Path(font_path).exists():
    print('Avenir font files not found in source folder, using N: location instead.')
    font_path = r"N:\IrrigatedLands\Misc\rf_metadata\Avenir Next LT Pro Demi.otf"

white = (255,255,255)
gray = (142,142,142)
blue = (36,117,183)
image_fraction = 0.9

banner_size = [720, 130]
title_size = [820,240]
thumbnail_size = (1100, 720)
background_size = (1280,720)

def generateThumbnail(year, full_name, temp_folder, n_loc) -> None:
    '''Creates a thumbnail at the location temp/thumbnail.png
    
    Args:
        year: (string) of year of analysis

        full_name: (string) full name of analysis area and year

        temp_folder: (string) of path to temporary folder for storage

        n_loc: (string) to N:/Drive location of source data
        
    Returns:
        None
    '''

    title = f'{year} {full_name} Irrigated Lands Machine Learning'
    def makeMap(template_aprx = template_aprx_path, dpi = 72) -> str:
        '''Uses arcpy to create a scratch map copy of a template aprx to create a layout.
        Layout is then made into a png for putting into the thumbnail.

        Args:
            template_aprx: (string) of path to the the template aprx file used for map creation

            dpi: (integer) of dpi used in map png creation

        Returns:
            (string) of path to the created map'''

        scratch_path = Path(temp_folder) / 'scratch.aprx'
        if scratch_path.exists():
            try:
                scratch_path.unlink()
            except:
                pass

        copy(template_aprx, scratch_path)

        aprx = mp.ArcGISProject(scratch_path)
        display_map = aprx.listMaps("DisplayMap")[0]
        display_map.spatialReference = SpatialReference(8826)

        for i in n_loc.glob('*.tif.lyrx'):
            display_map.addLayer(mp.LayerFile(i))[0]

        layout = aprx.listLayouts('ThumbnailLayout')[0]
        map_frame = layout.listElements()[0]
        map_frame.zoomToAllLayers(True)

        map_image_path = Path(temp_folder)/'map.png'
        layout.exportToPNG(map_image_path, dpi)
        return map_image_path

    def makeBanner(text = 'Zipped File', font = font_path, color = blue, 
                   font_size = 120, banner_size = banner_size) -> Image:
        '''Makes a banner for the file type to display on Portal. Default is "Zipped File" 
        with a blue background.
        
        Args:
            text: (string) of text to display on thumbnail image banner

            font: (string) of path to font otf file

            color: (string) of color code to make the banner

            font_size: (integer) of font size for banner text

            banner_size: (integer) of the size the banner should display, in pixels

        Returns:
            Image
        '''

        banner_image = Image.new(mode = 'RGB', size = banner_size, color = color)
        banner_text = text
        banner_draw = ImageDraw.Draw(banner_image)
        banner_draw.text((60, 7), banner_text, 
                         font = ImageFont.truetype(font = font, size = font_size), anchor = 'lt')
        return banner_image.rotate(90, expand=True)

    def alignTitle(font_size, drawer, title, font) -> None:
        '''Decide how to display the title of the thumbnail image, multiline 
        or single line depending on font size.
        
        Args:
            font_size: (integer) of font size for thumbnail title

            drawer: (ImageDraw Object) containing the thumbnail title

            title: (string) of title for the thumbnail image

            font: (FreeFontType) font type for image title

        Returns:
            None
        '''

        if font_size > 50:
            drawer.text([410,70], title, fill=gray, font=font, anchor="mm", align="center")
        else:
            drawer.multiline_text([410,70], title, fill=gray, font=font, anchor="mm", align="center")

    def getTitleFont(title_text, title_image, font_type = font_path, font_size = 1) -> tuple:
        '''Sets the font size and type for the title. Takes into account the 
        amount of characters and spacing to pass to formatting function.
        
        Args:
            title_text: (string) of the complete title for the thumbnail image

            title_image: (Image object) containing the empty image to draw onto

            font_type: (FreeFontType) of desired font type for thumbnail title

            font_size: (integer) of desired font size for title. Default is to start at one and build until title fits in image.

        Returns:
            (tuple) of title's font, font size, and title text'''

        title_font = ImageFont.truetype(font=font_type, size=font_size)
        left, top, right, bottom = title_font.getbbox(title_text)
        font_width = right - left

        while font_width < image_fraction*title_image.size[0]:
            font_size +=1
            title_font = ImageFont.truetype(font=font_path, size=font_size)
            font_width = title_font.getbbox(title_text)[2] - title_font.getbbox(title_text)[0]
            if font_size >= 100:
                break
        if font_size < 50:
            font_size = 50
            title_font = ImageFont.truetype(font=font_path, size=font_size)
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

        return title_font, font_size, title_text

    def makeTitle(color = white) -> Image:
        '''Makes the title for the thumbnail using font size and type 
        created in formatting functions.
        
        Args:
            color: (string) of desired background color for title
        
        Returns:
            (Image) of title with text'''

        title_image = Image.new(mode = 'RGB', size = title_size, color = color)
        title_draw = ImageDraw.Draw(title_image)
        font, size, text = getTitleFont(title_text=title, title_image= title_image)
        alignTitle(size, title_draw, text, font)

        return title_image


    def makeThumbnail(thumbnail_image, color = white, logo_path = logo_path) -> None:
        '''Coalesce all of the parts of the thumbnail image into single png. 
        Saves png to temp folder.
        
        Args:
            thumbnail_image: (Image) of the empty thumbnail 

            color: (string) of color code for thumbnail background

            logo_path: (string) of path to the IDWR logo to paste on the thumbnail

        Returns:
            None'''

        logo = Image.open(logo_path)
        map_image = Image.open(makeMap())
        title_image = makeTitle()
        banner = makeBanner()
        thumbnail_image.paste(banner, (941,0))
        thumbnail_image.paste(logo, (30,20))
        thumbnail_image.paste(map_image, (240,-8))
        thumbnail_image.paste(title_image, (100, 590))

        background_image = Image.new(mode = 'RGB', size = background_size, color = color)
        background_image.paste(thumbnail_image, (75,0))

        background_image.save(Path(temp_folder) / 'thumbnail.png')

    thumbnail_image = Image.new(mode="RGB", size=thumbnail_size, color=white)
    makeThumbnail(thumbnail_image)
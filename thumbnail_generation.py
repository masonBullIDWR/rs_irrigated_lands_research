#%%
from pathlib import Path
from shutil import copy
from arcpy import mp, SpatialReference
from PIL import Image, ImageDraw, ImageFont

template_aprx_path = r"N:\IrrigatedLands\portal_thumbnail_template_aprx\portal_thumbnail_template_aprx.aprx"
logo_path = 'IDWRLogo.png'
font_path = 'Avenir Next LT Pro Demi.otf'


white = (255,255,255)
gray = (142,142,142)
blue = (36,117,183)
image_fraction = 0.9

banner_size = [720, 130]
title_size = [820,240]
thumbnail_size = (1100, 720)
background_size = (1280,720)
def generateThumbnail(year, full_name, temp_folder, n_loc):
    '''Creates a thumbnail at the location'''

    title = f'{year} {full_name} Irrigated Lands Machine Learning'
    def makeMap(template_aprx = template_aprx_path, dpi = 72):
        '''Uses arcpy to create a scratch map copy of a template aprx to create a layout.
        Layout is then made into a png for putting into the thumbnail.
        Returns a path to the map image held in a temp folder.'''

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
                   font_size = 120, banner_size = banner_size):
        '''Makes a banner for the file type to display on Portal. Default is "Zipped File" 
        with a blue background.'''

        banner_image = Image.new(mode = 'RGB', size = banner_size, color = color)
        banner_text = text
        banner_draw = ImageDraw.Draw(banner_image)
        banner_draw.text((60, 7), banner_text, 
                         font = ImageFont.truetype(font = font, size = font_size), anchor = 'lt')
        return banner_image.rotate(90, expand=True)

    def alignTitle(font_size, drawer, title, font):
        '''Decide how to display the title of the thumbnail image, multiline 
        or single line depending on font size.'''

        if font_size > 50:
            drawer.text([410,70], title, fill=gray, font=font, anchor="mm", align="center")
        else:
            drawer.multiline_text([410,70], title, fill=gray, font=font, anchor="mm", align="center")

    def getTitleFont(title_text, title_image, font_type = font_path, font_size = 1):
        '''Sets the font size and type for the title. Takes into account the 
        amount of characters and spacing to pass to formatting function.'''

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

    def makeTitle(color = white):
        '''Makes the title for the thumbnail using font size and type 
        created in formatting functions.'''

        title_image = Image.new(mode = 'RGB', size = title_size, color = color)
        title_draw = ImageDraw.Draw(title_image)
        font, size, text = getTitleFont(title_text=title, title_image= title_image)
        alignTitle(size, title_draw, text, font)

        return title_image


    def makeThumbnail(thumbnail_image, color = white, logo_path = logo_path):
        '''Coalesce all of the parts of the thumbnail image into single png. 
        Saves png to temp folder.'''

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
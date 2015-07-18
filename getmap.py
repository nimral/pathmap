import requests
import subprocess
import time
import os.path

from lxml import html
from lxml import etree

from PIL import Image, ImageDraw
from math import floor, sqrt
from latex import build_pdf
import tempfile

from shapely.geometry import LineString, Point
from shapely import affinity

from concurrent.futures import ThreadPoolExecutor

import pyproj

#def build_pdf(string, filename):
    #fd, tmp = tempfile.mkstemp()
    #with open(tmp, "w") as fout:
        #fout.write(string)

    #os.system("pdflatex " + tmp)
    #os.system("rm " + tmp)
    #os.system("mv " + os.path.basename(tmp) + ".pdf " + filename)

class MapDownloader:
    """Base class for map providers with maps consisting of image tiles"""

    def __init__(self):
        self.xres = None
        self.yres = None


    def lon_lat_to_tiles(self, lon, lat):
        """Should convert longitude and latitude to (x, y) tiles coordinates.

        Tiles compose a rectangular grid. Numbers of the column
        and row in which a tile lies should be equal to its upper left corner
        coordinates.
        """
        
        raise NotImplementedError("Please implement this method")


    def get_tile(self, x, y):
        """Should return a tile (PIL.Image) whose upper left corner has coordinates x, y"""

        raise NotImplementedError("Please implement this method")


    def get_rect(self, lon1, lat1, lon2, lat2, parallel=False):
        """Return a PIL.Image of a rectangular map whose upper left and bottom
        right corner correspond to longitude, latitude (lon1, lat1) and (lon2,
        lat2) respectively.

        parallel=True tries to speed up the acquiring of tiles by running the
        needed calls to get_tile() asynchronously. Default False.
        """
        
        x1, y1 = self.lon_lat_to_tiles(lon1, lat1)
        x2, y2 = self.lon_lat_to_tiles(lon2, lat2)

        return self.get_rect_tiles(x1, y1, x2, y2, parallel=parallel)


    def get_rect_tiles(self, x1, y1, x2, y2, parallel=False):
        """Return a PIL.Image of a rectangular map whose upper left and bottom right
        corner have tiles coordinates (x1, y1) and (x2, y2) respectively.

        If parallel=True: try to speed up the acquiring of tiles by running the
        needed calls to get_tile() asynchronously. Default False.
        """

        big = Image.new("RGB", (int((x2-x1) * self.xres), int((y2-y1) * self.yres)))

        #rows and columns of tiles containing (x1, y1) and (x2, y2)
        tiles_x1 = floor(x1)
        tiles_x2 = floor(x2)
        tiles_y1 = floor(y1)
        tiles_y2 = floor(y2)

        xdiff_pix = int(self.xres * (x1 - tiles_x1))
        ydiff_pix = int(self.yres * (y1 - tiles_y1))

        #acquire each tile needed and paste it into big
        if parallel:
            tiles_needed = [(x, y) for y in range(tiles_y1, tiles_y2+1) for x in range(tiles_x1, tiles_x2+1)]
            
            tpe = ThreadPoolExecutor(10)
            images = tpe.map(self.get_tile, *zip(*tiles_needed))
            for im, xy in zip(images, tiles_needed):
                x, y = xy
                big.paste(im, ((x-tiles_x1) * self.xres - xdiff_pix, (y-tiles_y1) * self.yres - ydiff_pix))

        else:
            for y in range(tiles_y1, tiles_y2+1):
                for x in range(tiles_x1, tiles_x2+1):
                    im = self.get_tile(x, y)
                    big.paste(im, ((x-tiles_x1) * self.xres - xdiff_pix, (y-tiles_y1) * self.yres - ydiff_pix))

        return big

class CykloserverMapDownloader(MapDownloader):
    """Can download maps from cykloserver.cz/cykloatlas"""

    def __init__(self):

        self.xres = 256
        self.yres = 256

        self.last_token_acquired = 0

        #longitude latitude
        self.proj_to = pyproj.Proj("+init=EPSG:3857")

        #display projection
        self.proj_from = pyproj.Proj("+init=EPSG:4326")

        #beta_x and beta_y for affine transformation of coordinates (after
        #changing projection) yielding the tiles coordinates. Approximated by
        #linear regression.
        self.bx = [4.09597540e+03, 2.04431397e-04]
        self.by = [4.09571512e+03, -2.04373254e-04]


    def _run_js_file(self, filename):
        """Run nodejs on filename and return its output"""

        process = subprocess.Popen(["nodejs", filename], stdout=subprocess.PIPE)
        return process.communicate()[0].decode('utf8')


    def _url2dict(self, url):
        """Build a dict from url parameters.
        
        Example: http://server.com/index.php?a=16&b=13 -> {'a': '16', 'b': '13'}"""

        a, b = url.split("?", 1)
        return {
            "url": a,
            "atributes": {y[0]: y[1] for y in [x.split("=") for x in b.split("&")]},
        }


    def _renew_token(self):
        """Prepare requests.Session self.s for subsequent downloading of
        tiles
        """

        self.s = requests.Session()
        url_atlas = 'http://www.cykloserver.cz/cykloatlas/'
        r_atlas = self.s.get(url_atlas)

        root = html.fromstring(r_atlas.content)

        # script which gets downloaded from readauthloader2.php has in its url id and hkey:
        #<script
        #src="http://www.cykloserver.cz/cykloatlas/readauthloader2.php?id=30380492&amp;hkey=95d99c2c1a50e7fdf3f15a521ce53d9d"
        #type="text/javascript"></script>
        url = [x for x in root.xpath('.//script') if x.get('src') and 'readauthloader2' in x.get('src')][0].get('src')
        self.atributes = self._url2dict(url)["atributes"]
        
        self.s.get('http://www.cykloserver.cz/cykloatlas/readautha4b2.php', params=self.atributes)

        #http://www.cykloserver.cz/cykloatlas/tagetpass2.php sends javascript
        #which needs to be evaluted in order to get password
        with open("file", "w") as fout:
            fout.write(self.s.post('http://www.cykloserver.cz/cykloatlas/tagetpass2.php', data=self.atributes).content.decode('utf8'))
            fout.write("console.log(_tt_pass)")
        tt_pass = self._run_js_file("file").strip()

        atributes = self.atributes.copy()
        atributes["pass"] = tt_pass

        #http://www.cykloserver.cz/cykloatlas/tagettoken2.php sends tokens
        #which need to be "descrambled". Easiest by evaluating the javascript.
        with open("file2", "w") as fout:
            fout.write("""
            function __tt_descramble(data) {
                    var res = '';
                    
                    var pos = 0;
                    
                    var chnk = data.substr(pos, 3);
                    while (chnk.length == 3) {
                            res+= String.fromCharCode(Number(chnk));
                            
                            pos+= 3;
                            chnk = data.substr(pos, 3);
                    }
                    
                    return res;
            }""")
            fout.write(self.s.post('http://www.cykloserver.cz/cykloatlas/tagettoken2.php', data=atributes).content.decode('utf8'))
            fout.write("""
                console.log(__tt_tokenm)
                console.log(__tt_tokent)
                console.log(__tt_tokenk)
            """)
        tt_tokenm, tt_tokent, tt_tokenk = self._run_js_file("file2").split()

        self.s.get('http://webtiles.timepress.cz/set_token', params={"token": tt_tokenk}).content.decode('utf8')
        #that's it. We should be ok for next 60 seconds.


    def lon_lat_to_tiles(self, lon, lat):
        """Convert longitude and latitude to (x, y) tiles coordinates.

        Tiles compose a rectangular grid. Numbers of the column
        and row in which a tile lies should be equal to its upper left corner
        coordinates.
        """

        trans_x, trans_y = pyproj.transform(self.proj_from, self.proj_to, lon, lat)

        return (self.bx[0] + self.bx[1] * trans_x, self.by[0] + self.by[1] * trans_y)


    def get_tile(self, x, y):
        """Return a tile (PIL.Image) whose upper left corner has coordinates x, y"""
        
        def tile_filename(x, y):
            return "tile_{}_{}.png".format(x, y)

        im = None
        while True:
            try:
                im = Image.open(tile_filename(x, y))
            except (IOError, FileNotFoundError):
            #if not os.path.isfile(tile_filename(x, y)):

                if time.time() - self.last_token_acquired > 60:
                    self._renew_token()
                
                r = self.s.get('http://webtiles.timepress.cz/cyklo_256/13/' + str(x) + '/' + str(y))

                with open(tile_filename(x, y), "wb") as fout:
                    fout.write(r.content)
            else:
                return im


    def gpx2path(self, filename):
        """Return list of (longitude, latitude) pairs stored as a trek in gpx file filename"""

        with open(filename, "r") as fin:
            gpx = "".join(fin.readlines()[1:])
            root = etree.fromstring(gpx)
            return [(float(e.get('lon')), float(e.get('lat'))) for e in root.getchildren()[0].getchildren()[0].getchildren()]

            
def path_surroundings(md, path, *,
                      radius_pix=130,
                      maxwidth_pix=1000,
                      maxheight_pix=800,
                      maxdist_pix=500,
                      path_color=(255, 100, 0),
                      shorten_by_rotating=True):
    """Create a generator of map images following a given path

    Arguments:

    md: MapDownloader, should provide get_rect() and get_rect_tiles() methods
        returning map images and xres, yres properties specifying width and height
        of a tile
    path: list of (longitude, latitude) coordinates representing the trip for
        which map should be generated
    radius_pix: distance from the path in pixels which should be covered by the
        generated map
    maxwidth_pix: maximum width of one map part in pixels
    maxheight_pix: maximum height of one map part in pixels
    maxdist_pix: maximum distance between two consecutive points in path (if it
        is higher, additional point gets inserted in between to allow split)
    path_color: color as (R, G, B) tuple, with which the path should by drawn
        into the map; or None if no path should be drawn.
    shorten_by_rotating: whether to try to reduce height of the images by
        rotating them. Consider path going from north to south: it is quite
        high, but usually not very wide (2 * radius). By rotating it by 90°, we
        can greatly reduce its height and thus maybe reduce the number of pages
        of the pdf file generated later by create_path_pdf. Default True.
    """

    def len_pix(ran):
        return int((ran[1] - ran[0]) * md.xres)
    def dist_pix(p, q):
        return sqrt(((p[0] - q[0]) * md.xres) ** 2 + ((p[1] - q[1]) * md.xres) ** 2)
    def draw_circle(draw, S, r, fill=1):
        draw.ellipse((S[0] - r, S[1] - r, S[0] + r, S[1] + r), fill)
        
    radius = radius_pix / md.xres

    path = [md.lon_lat_to_tiles(lon, lat) for lon, lat in reversed(path)]
    while path:
        
        #part of the map which is not bigger than the limits
        #(we shouldn't bite off more than we can chew)
        bite = [path.pop()]

        #bounds of the current part of the map (tiles coordinates)
        x_range = [bite[0][0] - radius, bite[0][0] + radius]
        y_range = [bite[0][1] - radius, bite[0][1] + radius]

        while path:
            #split first line of path until it is short enough
            while dist_pix(bite[-1], path[-1]) > maxdist_pix:
                path.append(((bite[-1][0] + path[-1][0]) / 2, (bite[-1][1] + path[-1][1]) / 2))

            #how will the ranges look like after we bite off the next point of path
            x_range2 = [0, 0]
            y_range2 = [0, 0]
            x_range2[0] = min(x_range[0], path[-1][0] - radius)
            x_range2[1] = max(x_range[1], path[-1][0] + radius)
            y_range2[0] = min(y_range[0], path[-1][1] - radius)
            y_range2[1] = max(y_range[1], path[-1][1] + radius)
            
            #if the map would become too big
            if len_pix(x_range2) > maxwidth_pix or len_pix(y_range2) > maxheight_pix:
                #stop building this bite
                #also copy the last point of bite back to path (starting point
                #of the next bite should be the same as the ending point of
                #this one)
                path.append(bite[-1])
                break
            else:
                bite.append(path.pop())
                x_range = x_range2
                y_range = y_range2

        white = (255, 255, 255)
        big = Image.new("RGBA", (len_pix(x_range), len_pix(y_range)), color=white)

        last = bite[0]
        #for each line (last--p) in bite get map of its surroundings (max
        #distance of radius) and copy it to big
        for p in bite[1:]:

            #get bounds of map covering this line
            x1, _, _, x2 = sorted([last[0] - radius, last[0] + radius, p[0] - radius, p[0] + radius])
            y1, _, _, y2 = sorted([last[1] - radius, last[1] + radius, p[1] - radius, p[1] + radius])

            #get the map rectangle for this line
            im = md.get_rect_tiles(x1, y1, x2, y2, parallel=False)

            #we would like to copy only surroundings, not the whole rectangle
            #so we create a mask -- black and white image of the same size.
            #area which is white in the mask gets copied
            mask = Image.new("1", im.size)
            draw = ImageDraw.Draw(mask)

            #convert coordinates of last and p from tiles to pixels with origin
            #in upper left corner of im
            last_pix = [(last[0] - x1) * md.xres, (last[1] - y1) * md.yres]
            p_pix = [(p[0] - x1) * md.xres, (p[1] - y1) * md.yres]

            #draw very thick line and circles at the end points
            draw.line((last_pix[0], last_pix[1], p_pix[0], p_pix[1]), width=int(2*radius*md.xres), fill=1)
            draw_circle(draw, last_pix, radius * md.xres)
            draw_circle(draw, p_pix, radius * md.xres)

            #mask is ready
            del draw

            #paste the surroundings to the right place in the big image (note
            #(x_range[0], y_range[0]) are the tiles coordinates of the upper
            #left corner of big)
            big.paste(im, (int((x1 - x_range[0]) * md.xres), int((y1 - y_range[0]) * md.yres)), mask=mask)

            last = p

        if path_color:
            #draw path to map
            draw = ImageDraw.Draw(big)
            last = bite[0]
            for p in bite[1:]:
                last_pix = [(last[0] - x_range[0]) * md.xres, (last[1] - y_range[0]) * md.yres]
                p_pix = [(p[0] - x_range[0]) * md.xres, (p[1] - y_range[0]) * md.yres]
                draw.line((last_pix[0], last_pix[1], p_pix[0], p_pix[1]), width=3, fill=path_color)
                last = p
            del draw

        if not shorten_by_rotating:
            yield big
        else:
            #attempt to lower the height of the image by rotating the
            #surroundings and cropping
            
            surroundings = LineString(bite).buffer(radius)

            angle = _best_angle(surroundings, maxwidth_pix/md.xres, maxheight_pix/md.yres)
            big = big.rotate(angle, resample=Image.BICUBIC, expand=True)
            
            #rotating will usually make the image bigger (new area gets filled
            #with alpha=0)
            #it needs to be cropped to include the surroundings only
            big = _crop_after_rotation(big, angle, md.xres, md.yres, surroundings)
        
            #the cropped area will usually contain some of the alpha=0
            #we remove it by pasting to new white image (alpha specifies mask,
            #alpha=0 does not get #copied)
            big2 = Image.new("RGBA", big.size, "white")
            big2.paste(big, mask=big)
            yield big2


def _best_angle(surroundings, maxwidth, maxheight):
    """Find the angle by which surroundings should be rotated.
    
    Try to minimalize surroundings' height while keeping its width
    under maxwidth. Also prefer smaller rotations over bigger ones.

    Arguments:

    surroundings: shapely.geometry.polygon.Polygon
    maxwidth: maximum allowed width of the surroundings bounding box
    maxheight: maximum allowed height of the surroundings bounding box

    Returns:
    
    angle in degrees (counterclockwise)
    """
    
    minheight = maxheight
    best = 0
    lowest_penalty = 1000
    for angle in range(-90, 90, 5):
        x1, y1, x2, y2 = affinity.rotate(surroundings, angle).bounds
        height = y2 - y1
        width = x2 - x1
        if width < maxwidth:
            penalty = height + abs(angle) / 100
            if penalty < lowest_penalty:
                lowest_penalty = penalty
                minheight = height
                best = angle

    #maps and shapely differ in the directions of their y-axes
    return -best
            

def _crop_after_rotation(im, angle, xres, yres, surroundings):
    """Crop image to the bounding box of bite's surroundings.

    Arguments:

    im: PIL.Image, rotated map part
    angle: by which the map has been rotated, in degrees (counterclockwise)
    xres: width of one tile in pixels
    yres: height of one tile in pixels
    surroundings: shapely.geometry.polygon.Polygon
    """

    #before rotation
    x1, y1, x2, y2 = surroundings.bounds
    old_bb_upper_left = Point(x1, y1)
    old_bb_upper_right = Point(x2, y1)
    old_bb_bottom_left = Point(x1, y2)
    old_bb_center = ((x1+x2)/2, (y1+y2)/2)

    #shapely y-axis goes upwards
    shapely_angle = -angle

    #after rotation
    x1, y1, x2, y2 = affinity.rotate(surroundings, shapely_angle, origin=old_bb_center).bounds
    crop_upper_left = Point(x1, y1)
    crop_width = x2 - x1
    crop_height = y2 - y1

    #points where old bounding box of surroundings (i.e. the old image) touches
    #its bounding box after rotation
    tl = None #touch at the left side of the new bounding box
    tt = None #touch at the top side of the new bounding box
    if angle > 0:
        tl = affinity.rotate(old_bb_upper_left, shapely_angle, origin=old_bb_center)
        tt = affinity.rotate(old_bb_upper_right, shapely_angle, origin=old_bb_center)
    else:
        tl = affinity.rotate(old_bb_bottom_left, shapely_angle, origin=old_bb_center)
        tt = affinity.rotate(old_bb_upper_left, shapely_angle, origin=old_bb_center)

    #upper left corner of ther new bounding box
    new_bb_upper_left = Point(tl.x, tt.y)

    #from these we get b: upper left corner of the crop area relative to new_bb_upper_left
    b = (crop_upper_left.x - new_bb_upper_left.x, crop_upper_left.y - new_bb_upper_left.y)

    #crop rectangle in pixels relative to new_bb_upper_left
    crop_box = [int(x) for x in [
        b[0] * xres,
        b[1] * yres,
        (b[0] + crop_width) * xres,
        (b[1] + crop_height) * yres
    ]]
    cropped = im.crop(box=crop_box)
    cropped.load()
    return cropped


def create_path_pdf(parts, filename):
    """Create a pdf file filename with images in parts.

    Arguments:
    
    parts: list of Image.PIL
    filename: str, name of the resulting file
    """
    header = r"""
        \documentclass[a4paper]{article}
        \usepackage[top=1.5cm, bottom=1.5cm, left=0.5cm, right=0.5cm]{geometry}
        \usepackage{graphicx}
        \sloppy
        \begin{document}
    """

    tdir = tempfile.TemporaryDirectory()

    fnames = []
    for i, im in enumerate(parts):
        fname = "{}/{}.png".format(tdir.name, i)
        fnames.append(fname)
        im.save(fname)
        
    images = "\n\n".join('\includegraphics[scale=0.5]{' + fname + '}' for fname in fnames)

    footer = r"""
        \end{document}
    """

    pdf = build_pdf("".join((header, images, footer)))
    pdf.save_to(filename)
    
    tdir.cleanup()

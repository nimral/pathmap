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
    def __init__(self):
        self.xres = None
        self.yres = None


    def lon_lat_to_tiles(self, lon, lat):
        raise NotImplementedError("Please implement this method")


    def get_tile(self, x, y):
        raise NotImplementedError("Please implement this method")


    def get_rect(self, lon1, lat1, lon2, lat2, parallel=False):
        
        x1, y1 = self.lon_lat_to_tiles(lon1, lat1)
        x2, y2 = self.lon_lat_to_tiles(lon2, lat2)

        return self.get_rect_tiles(x1, y1, x2, y2, parallel=parallel)


    def get_rect_tiles(self, x1, y1, x2, y2, parallel=False):

        big = Image.new("RGB", (int((x2-x1) * self.xres), int((y2-y1) * self.yres)))
        tiles_x1 = floor(x1)
        tiles_x2 = floor(x2)
        tiles_y1 = floor(y1)
        tiles_y2 = floor(y2)

        xdiff_pix = int(self.xres * (x1 - tiles_x1))
        ydiff_pix = int(self.yres * (y1 - tiles_y1))

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
    def __init__(self):

        self.xres = 256
        self.yres = 256

        self.last_token_acquired = 0

        self.proj_to = pyproj.Proj("+init=EPSG:3857")
        self.proj_from = pyproj.Proj("+init=EPSG:4326")

        self.bx = [4.09597540e+03, 2.04431397e-04]
        self.by = [4.09571512e+03, -2.04373254e-04]


    def _run_js_file(self, filename):
        process = subprocess.Popen(["nodejs", filename], stdout=subprocess.PIPE)
        return process.communicate()[0].decode('utf8')


    def _url2dict(self, url):
        a, b = url.split("?", 1)
        return {
            "url": a,
            "atributes": {y[0]: y[1] for y in [x.split("=") for x in b.split("&")]},
        }


    def _renew_token(self):

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
        #self.tt_id = self.atributes["id"]
        #self.tt_hkey = self.atributes["hkey"]
        
        # not sure if needed
        self.s.get('http://www.cykloserver.cz/cykloatlas/readautha4b2.php', params=self.atributes)

        with open("file", "w") as fout:
            fout.write(self.s.post('http://www.cykloserver.cz/cykloatlas/tagetpass2.php', data=self.atributes).content.decode('utf8'))
            fout.write("console.log(_tt_pass)")
        tt_pass = self._run_js_file("file").strip()

        atributes = self.atributes.copy()
        atributes["pass"] = tt_pass

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


    def lon_lat_to_tiles(self, lon, lat):

        print("lonlat", lon, lat)
        trans_x, trans_y = pyproj.transform(self.proj_from, self.proj_to, lon, lat)


        return (self.bx[0] + self.bx[1] * trans_x, self.by[0] + self.by[1] * trans_y)


    def get_tile(self, x, y):
        
        def tile_filename(x, y):
            return "tile_{}_{}.png".format(x, y)

        if not os.path.isfile(tile_filename(x, y)):

            if time.time() - self.last_token_acquired > 60:
                self._renew_token()
            
            r = self.s.get('http://webtiles.timepress.cz/cyklo_256/13/' + str(x) + '/' + str(y))

            with open(tile_filename(x, y), "wb") as fout:
                fout.write(r.content)

        return Image.open(tile_filename(x, y))


    def gpx2path(self, filename):
        with open(filename, "r") as fin:
            gpx = "".join(fin.readlines()[1:])
            root = etree.fromstring(gpx)
            return [(float(e.get('lon')), float(e.get('lat'))) for e in root.getchildren()[0].getchildren()[0].getchildren()]

            
        
def path_surroundings(md, path, *, radius=130/256, maxwidth_pix=1000, maxheight_pix=800, maxdist_pix=500, shorten_by_rotating=True):

    def len_pix(ran):
        return int((ran[1] - ran[0]) * md.xres)
    def dist_pix(p, q):
        return sqrt(((p[0] - q[0]) * md.xres) ** 2 + ((p[1] - q[1]) * md.xres) ** 2)
    def draw_circle(draw, S, r, fill=1):
        draw.ellipse((S[0] - r, S[1] - r, S[0] + r, S[1] + r), fill)

    path = [md.lon_lat_to_tiles(lon, lat) for lon, lat in reversed(path)]
    while path:
        bite = [path.pop()]
        x_range = [bite[0][0] - radius, bite[0][0] + radius]
        y_range = [bite[0][1] - radius, bite[0][1] + radius]

        while path:
            while dist_pix(bite[-1], path[-1]) > maxdist_pix:
                path.append(((bite[-1][0] + path[-1][0]) / 2, (bite[-1][1] + path[-1][1]) / 2))

            x_range2 = [0, 0]
            y_range2 = [0, 0]
            x_range2[0] = min(x_range[0], path[-1][0] - radius)
            x_range2[1] = max(x_range[1], path[-1][0] + radius)
            y_range2[0] = min(y_range[0], path[-1][1] - radius)
            y_range2[1] = max(y_range[1], path[-1][1] + radius)
            
            if len_pix(x_range2) > maxwidth_pix or len_pix(y_range2) > maxheight_pix:
                path.append(bite[-1])
                break

            bite.append(path.pop())
            x_range = x_range2
            y_range = y_range2

        white = (255, 255, 255)

        big = Image.new("RGBA", (len_pix(x_range), len_pix(y_range)), color=white)

        last = bite[0]
        for p in bite[1:]:

            x1, _, _, x2 = sorted([last[0] - radius, last[0] + radius, p[0] - radius, p[0] + radius])
            y1, _, _, y2 = sorted([last[1] - radius, last[1] + radius, p[1] - radius, p[1] + radius])

            im = md.get_rect_tiles(x1, y1, x2, y2, parallel=True)

            mask = Image.new("1", im.size)
            draw = ImageDraw.Draw(mask)

            last_pix = [(last[0] - x1) * md.xres, (last[1] - y1) * md.yres]
            p_pix = [(p[0] - x1) * md.xres, (p[1] - y1) * md.yres]

            draw.line((last_pix[0], last_pix[1], p_pix[0], p_pix[1]), width=int(2*radius*md.xres), fill=1)


            draw_circle(draw, last_pix, radius * md.xres)
            draw_circle(draw, p_pix, radius * md.xres)

            del draw

            
            big.paste(im, (int((x1 - x_range[0]) * md.xres), int((y1 - y_range[0]) * md.yres)), mask=mask)

            last = p

        draw = ImageDraw.Draw(big)
        last = bite[0]
        for p in bite[1:]:
            last_pix = [(last[0] - x_range[0]) * md.xres, (last[1] - y_range[0]) * md.yres]
            p_pix = [(p[0] - x_range[0]) * md.xres, (p[1] - y_range[0]) * md.yres]
            draw.line((last_pix[0], last_pix[1], p_pix[0], p_pix[1]), width=3, fill=(255, 100, 0))
            last = p
        del draw

        if shorten_by_rotating:
            angle = _best_angle(bite, radius, maxwidth_pix/md.xres, maxheight_pix/md.yres)
            big = big.rotate(angle, resample=Image.BICUBIC, expand=True)
            big = _crop_after_rotation(md, big, angle, radius, bite)
            big2 = Image.new("RGBA", big.size, "white")
            big2.paste(big, mask=big)
            yield big2
        else:
            yield big


def _best_angle(bite, radius, maxwidth, maxheight):
    line = LineString(bite)
    surroundings = line.buffer(radius)
    
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
            

def _crop_after_rotation(md, im, angle, radius, bite):

    line = LineString(bite)
    surroundings = line.buffer(radius)

    x1, y1, x2, y2 = surroundings.bounds
    old_bb_upper_left = Point(x1, y1)
    old_bb_upper_right = Point(x2, y1)
    old_bb_bottom_left = Point(x1, y2)
    old_bb_bottom_right = Point(x2, y2)
    old_bb_center = ((x1+x2)/2, (y1+y2)/2)

    shapely_angle = -angle

    x1, y1, x2, y2 = affinity.rotate(surroundings, shapely_angle, origin=old_bb_center).bounds
    crop_upper_left = Point(x1, y1)
    crop_width = x2 - x1
    crop_height = y2 - y1

    p1 = None
    p2 = None
    if angle > 0:
        p1 = affinity.rotate(old_bb_upper_left, shapely_angle, origin=old_bb_center)
        p2 = affinity.rotate(old_bb_upper_right, shapely_angle, origin=old_bb_center)
    else:
        p1 = affinity.rotate(old_bb_bottom_left, shapely_angle, origin=old_bb_center)
        p2 = affinity.rotate(old_bb_upper_left, shapely_angle, origin=old_bb_center)

    b = (crop_upper_left.x - p1.x, crop_upper_left.y - p2.y)

    crop_box = (int(md.xres * x) for x in (b[0], b[1], b[0] + crop_width, b[1] + crop_height))
    cropped = im.crop(box=crop_box)
    cropped.load()
    return cropped


def create_path_pdf(parts, filename):
    header = r'''
        \documentclass[a4paper]{article}
        \usepackage[top=1.5cm, bottom=1.5cm, left=0.5cm, right=0.5cm]{geometry}
        \usepackage{graphicx}
        \sloppy
        \begin{document}
    '''

    tdir = tempfile.TemporaryDirectory()

    fnames = []
    for i, im in enumerate(parts):
        fname = "{}/{}.png".format(tdir.name, i)
        fnames.append(fname)
        im.save(fname)
        
    images = "\n\n".join('\includegraphics[scale=0.5]{' + fname + '}' for fname in fnames)

    footer = r'''
        \end{document}
    '''

    pdf = build_pdf(header + images + footer)
    pdf.save_to(filename)
    
    #build_pdf(header + images + footer, filename)

    tdir.cleanup()

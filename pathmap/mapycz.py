from PIL import Image, ImageDraw
import requests
import subprocess
import time
from lxml import html
from lxml import etree
from concurrent.futures import ThreadPoolExecutor
import pyproj
from threading import Lock

from . getmap import MapDownloader


class MapyczMapDownloader(MapDownloader):
    """Can download maps from mapy.cz"""

    def __init__(self):

        self.s = requests.Session()

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

        self._renew_lock = Lock()


    def _url2dict(self, url):
        """Build a dict from url parameters.

        Example: http://server.com/index.php?a=16&b=13 -> {'a': '16', 'b': '13'}"""

        default = {
            "url": url,
            "atributes": {}
        }

        if '?' not in url:
            return default

        a, b = url.split("?", 1)

        if not b:
            d = default.copy()
            d["url"] = a
            return d

        return {
            "url": a,
            "atributes": {y[0]: y[1] for y in [x.split("=") for x in b.split("&")]},
        }


    def lon_lat_to_tiles(self, lon, lat):
        """Convert longitude and latitude to (x, y) tiles coordinates.

        Tiles compose a rectangular grid. Numbers of the column
        and row in which a tile lies should be equal to its upper left corner
        coordinates.
        """

        trans_x, trans_y = pyproj.transform(self.proj_from, self.proj_to, lon, lat)

        return (self.bx[0] + self.bx[1] * trans_x, self.by[0] + self.by[1] * trans_y)


    def _download_tile(self, x, y, filename):
        """Downloads a tile whose upper left corner has coordinates x, y

        Tile gets saved as filename."""

        print(x, y, filename)
        r = self.s.get('https://m3.mapserver.mapy.cz/wturist-m/13-{}-{}'.format(x, y))

        with open(filename, "wb") as fout:
            fout.write(r.content)


    def _tile_filename(self, x, y):
        return "mapycz_{}_{}.png".format(x, y)


    def get_tile(self, x, y):
        """Return a tile (PIL.Image) whose upper left corner has coordinates x, y"""

        filename = self._tile_filename(x, y)
        im = None
        while True:
            try:
                im = Image.open(filename)

            except (IOError, FileNotFoundError):
                self._download_tile(x, y, filename)

            else:
                return im


    def gpx2path(self, filename):
        """Return list of (longitude, latitude) pairs stored as a trek in gpx file filename"""

        with open(filename, "r") as fin:
            gpx = "".join(fin.readlines()[1:])
            root = etree.fromstring(gpx)
            return [(float(e.get('lon')), float(e.get('lat'))) for e in root.xpath(".//*[local-name()='trkpt']")]

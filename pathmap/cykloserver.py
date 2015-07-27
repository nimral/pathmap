from PIL import Image, ImageDraw
import requests
import subprocess
import time
from lxml import html
from lxml import etree
from concurrent.futures import ThreadPoolExecutor
import pyproj

from . getmap import MapDownloader


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


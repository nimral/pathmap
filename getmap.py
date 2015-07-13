import requests
import subprocess
import time
import os.path
from lxml import html
from PIL import Image
from math import floor

import linreg

def url2dict(url):
    a, b = url.split("?", 1)
    return {
        "url": a,
        "atributes": {y[0]: y[1] for y in [x.split("=") for x in b.split("&")]},
    }


def run_js_file(filename):
    process = subprocess.Popen(["nodejs", filename], stdout=subprocess.PIPE)
    return process.communicate()[0].decode('utf8')


class TileDownloader(object):
    def __init__(self):

        self.xres = 256
        self.yres = 256


        self.last_token_acquired = 0

    def renew_token(self):

        self.s = requests.Session()
        url_atlas = 'http://www.cykloserver.cz/cykloatlas/'
        r_atlas = self.s.get(url_atlas)

        root = html.fromstring(r_atlas.content)

        # script which gets downloaded from readauthloader2.php has in its url id and hkey:
        #<script
        #src="http://www.cykloserver.cz/cykloatlas/readauthloader2.php?id=30380492&amp;hkey=95d99c2c1a50e7fdf3f15a521ce53d9d"
        #type="text/javascript"></script>
        url = [x for x in root.xpath('.//script') if x.get('src') and 'readauthloader2' in x.get('src')][0].get('src')
        self.atributes = url2dict(url)["atributes"]
        #self.tt_id = self.atributes["id"]
        #self.tt_hkey = self.atributes["hkey"]
        
        # not sure if needed
        self.s.get('http://www.cykloserver.cz/cykloatlas/readautha4b2.php', params=self.atributes)

        with open("file", "w") as fout:
            fout.write(self.s.post('http://www.cykloserver.cz/cykloatlas/tagetpass2.php', data=self.atributes).content.decode('utf8'))
            fout.write("console.log(_tt_pass)")
        tt_pass = run_js_file("file").strip()

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
        tt_tokenm, tt_tokent, tt_tokenk = run_js_file("file2").split()

        self.s.get('http://webtiles.timepress.cz/set_token', params={"token": tt_tokenk}).content.decode('utf8')


    def get_tile(self, x, y):
        
        def tile_filename(x, y):
            return "tile_" + str(x) + "_" + str(y) + ".png"

        if not os.path.isfile(tile_filename(x, y)):

            if time.time() - self.last_token_acquired > 60:
                self.renew_token()
            
            r = self.s.get('http://webtiles.timepress.cz/cyklo_256/13/' + str(x) + '/' + str(y))

            with open(tile_filename(x, y), "wb") as fout:
                fout.write(r.content)

        return Image.open(tile_filename(x, y))


    def get_rect(self, x1, y1, x2, y2):
        big = Image.new("RGB", (int((x2-x1) * self.xres), int((y2-y1) * self.yres)))
        tiles_x1 = floor(x1)
        tiles_x2 = floor(x2)
        tiles_y1 = floor(y1)
        tiles_y2 = floor(y2)

        xdiff = int(x1 - tiles_x1)
        ydiff = int(y1 - tiles_y1)

        for y in range(tiles_y1, tiles_y2+1):
            for x in range(tiles_x1, tiles_x2+1):
                im = self.get_tile(x, y)
                big.paste(self.get_tile(x, y), ((x-tiles_x1) * self.xres - xdiff, (y-tiles_y1) * self.yres - ydiff))

        return big
            
        
        
        
        


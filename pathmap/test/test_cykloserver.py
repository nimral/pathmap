import unittest
import filecmp
import tempfile
from .. cykloserver import CykloserverMapDownloader


class TestCykloserver(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.c = CykloserverMapDownloader()

    def test__get_js_output_known_values(self):
        """_get_js_output should give known output for known input"""

        known_pairs = [
            ("", ""),
            ("1+2", ""),
            ("console.log(1+2)", "3"),
            ("""
                n = 1;
                for (i = 0; i < 10; i++) {
                    n += 1;
                }
                console.log(n)
            """, "11"),
        ]


        for inp, out in known_pairs:
            self.assertEqual(self.c._get_js_output(inp).strip(), out)


    def test__url2dict_known_values(self):
        """_url2dict should give known output for known input"""

        known_pairs = [
            (
                "",
                {
                    "url": "",
                    "atributes": {}
                }
            ),
            (
                "http://server.com/",
                {
                    "url": "http://server.com/",
                    "atributes": {}
                }
            ),
            (
                "http://server.com/index.php?",
                {
                    "url": "http://server.com/index.php",
                    "atributes": {}

                }
            ),
            (
                "http://server.com/index.php?par1=23&par2=45",
                {
                    "url": "http://server.com/index.php",
                    "atributes": {"par1": "23", "par2": "45"}
                }
            ),
        ]

        for url, d in known_pairs:
            self.assertEqual(self.c._url2dict(url), d)

    
    def test__renew_token(self):
        """should get 200 OK on http://webtiles.timepress.cz/cyklo_256/13/4493/2803
        
        after running _renew_token, that is
        """

        self.c._renew_token()
        url = 'http://webtiles.timepress.cz/cyklo_256/13/4493/2803'
        self.assertEqual(self.c.s.get(url).status_code, 200)
        

    def test_lon_lat_to_tiles_known(self):
        """should return known tiles coords for known lon lat pairs
        
        These are longitudes and latitudes of certain tiles' upper left
        corners.
        Compared with delta=0.01 (~ 2.56 px)
        """

        lon_lats = [
            (17.44593229, 49.32475974),
            (17.35827964, 49.32463261),
            (17.27046704, 49.35343943),
            (14.32647425, 50.09219194),
            (14.23799062, 50.09224200),
            (14.37016985, 50.06426084),
            (14.23841180, 48.89340921),
        ]

        tiles_coords = [
            (4493, 2802),
            (4491, 2802),
            (4489, 2801),
            (4422, 2775),
            (4420, 2775),
            (4423, 2776),
            (4420, 2817),
        ]

        for ll, tc in zip(lon_lats, tiles_coords):
            x, y = self.c.lon_lat_to_tiles(*ll)
            self.assertAlmostEqual(x, tc[0], delta=0.01)
            self.assertAlmostEqual(y, tc[1], delta=0.01)


    def test__download_tile_known(self):
        """Downloaded tiles should be the same as known tiles"""

        known = [(4492, 2804), (4497, 2804)]

        tdir = tempfile.TemporaryDirectory()
        for x, y in known:
            fname = "{}/{}".format(tdir.name, "file.png")
            self.c._download_tile(x, y, fname)
            self.assertEqual(filecmp.cmp(fname, self.c._tile_filename(x, y)), True)

        tdir.cleanup()


if __name__ == '__main__':
    unittest.main()

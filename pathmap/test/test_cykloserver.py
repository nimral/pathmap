import unittest
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
            ("", {}),
            ("http://server.com/", {}),
            ("http://server.com/index.php?", {}),
            ("http://server.com/index.php?par1=23&par2=45", {"par1": "23", "par2": "45"}),
        ]

        for url, d in known_pairs:
            self.assertEqual(self.c._url2dict(url), d)


if __name__ == '__main__':
    unittest.main()

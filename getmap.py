import requests
import subprocess
from lxml import html

def url2dict(url):
    a, b = url.split("?", 1)
    return {
        "url": a,
        "atributes": {y[0]: y[1] for y in [x.split("=") for x in b.split("&")]},
    }

def run_js_file(filename):
    process = subprocess.Popen(["nodejs", filename], stdout=subprocess.PIPE)
    return process.communicate()[0].decode('utf8')

def get_tile(x, y):

    s = requests.Session()
    url_atlas = 'http://www.cykloserver.cz/cykloatlas/'
    r_atlas = s.get(url_atlas)

    root = html.fromstring(r_atlas.content)
    print(root)
    url = [x for x in root.xpath('.//script') if x.get('src') and 'readauthloader2' in x.get('src')][0].get('src')
    d = url2dict(url)
    tt_id = d["atributes"]["id"]
    tt_hkey = d["atributes"]["hkey"]
    print(tt_id, tt_hkey)
    
    
    s.get('http://www.cykloserver.cz/cykloatlas/readautha4b2.php', params=d["atributes"])

    with open("file", "w") as fout:
        fout.write(s.post('http://www.cykloserver.cz/cykloatlas/tagetpass2.php', data=d["atributes"]).content.decode('utf8'))
        fout.write("console.log(_tt_pass)")
    tt_pass = run_js_file("file").strip()

    atributes = d["atributes"]
    atributes["pass"] = tt_pass
    print(atributes)

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
        fout.write(s.post('http://www.cykloserver.cz/cykloatlas/tagettoken2.php', data=atributes).content.decode('utf8'))
        fout.write("""
            console.log(__tt_tokenm)
            console.log(__tt_tokent)
            console.log(__tt_tokenk)
        """)
    tt_tokenm, tt_tokent, tt_tokenk = run_js_file("file2").split()
    print(tt_tokenm, tt_tokent, tt_tokenk)

    print(s.get('http://webtiles.timepress.cz/set_token', params={"token": tt_tokenk}).content.decode('utf8'))


    r = s.get('http://webtiles.timepress.cz/cyklo_256/13/' + str(x) + '/' + str(y))

    with open("tile.png", "wb") as fout:
        fout.write(r.content)









    return url

    

    #url = 'http://webtiles.timepress.cz/cyklo_256/13/' + str(x) + '/' + str(y)
    #print(url)
    #r = s.get(url)
    #return r1, r

	#var __tt_id = 30382116;
	#var __tt_hkey = '71b846f3300d2785dab7fab73ed39731';
	#var __tt_cb = null;
	#var __tt_tokenm = '';
	#var __tt_tokent = '';
	#var __tt_tokenk = '';
	#var __tt_ip = '';
	#var __tt_authloader = document.createElement("script");
	#__tt_authloader.type = "text/javascript";
    #__tt_authloader.src = "http://www.cykloserver.cz/cykloatlas/readautha4b2.php?id=30382116&hkey=71b846f3300d2785dab7fab73ed39731";
    #document.getElementsByTagName('head')[0].appendChild(__tt_authloader);


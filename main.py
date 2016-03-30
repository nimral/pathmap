from pathmap import getmap
from pathmap import cykloserver
from pathmap import mapycz
import argparse

def main():

    parser = argparse.ArgumentParser(
        description="Creates a pdf with map pieces covering given path")
    #parser.add_argument("-m", "--map-provider", default="cykloserver",
                        #help="Map provider. Default (and only option so far) "
                        #"is cykloserver.cz")
    parser.add_argument("-r", "--radius", default="130", type=int,
                        help="Radius of the covered map area around the path "
                        "in pixels. Default 130 px.")
    parser.add_argument("-c", "--color", default="red",
                        help="Color of the path in map image. Default red.")
    parser.add_argument("-o", "--output", default=None,
                        help="Name of the output pdf file. Default "
                        "<path.gpx>.pdf")
    parser.add_argument("path.gpx")

    args = vars(parser.parse_args())

    output = args["path.gpx"] + ".pdf"
    if args["output"]:
        output = args["output"]

    radius = int(args["radius"])

    #g = cykloserver.CykloserverMapDownloader()
    g = mapycz.MapyczMapDownloader()
    path = g.gpx2path(args["path.gpx"])
    s = list(getmap.path_surroundings(g, path, radius_pix=args["radius"],
            path_color=args["color"]))
    getmap.create_path_pdf(s, output)
    

if __name__ == "__main__":
    main()

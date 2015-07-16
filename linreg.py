import numpy as np
import pyproj

def transform(x, y):
    proj_to = pyproj.Proj("+init=EPSG:3857")
    proj_from = pyproj.Proj("+init=EPSG:4326")
    trans_x, trans_y = pyproj.transform(proj_from, proj_to, x, y)
    return trans_x, trans_y

longitudes = [
    17.44593229,
    17.35827964,
    17.27046704,
    14.32647425,
    14.23799062,
    14.37016985,
    14.23841180,
]

xcoords = [
    4493,
    4491,
    4489,
    4422,
    4420,
    4423,
    4420,
]


latitudes = [
    49.32475974,
    49.32463261,
    49.35343943,
    50.09219194,
    50.09224200,
    50.06426084,
    48.89340921,
]

ycoords = [
    2802,
    2802,
    2801,
    2775,
    2775,
    2776,
    2817,
]

longitudes, latitudes = zip(*[transform(x, y) for x, y in zip(longitudes, latitudes)])
print(longitudes, latitudes)

L_x = np.vstack([np.ones(len(longitudes)), longitudes]).T
C_x = np.matrix(xcoords).T

beta_x = np.linalg.lstsq(L_x, C_x)[0]

L_y = np.vstack([np.ones(len(latitudes)), latitudes]).T
C_y = np.matrix(ycoords).T

beta_y = np.linalg.lstsq(L_y, C_y)[0]


class Convertor(object):
    def __init__(self, bx, by):
        self.bx = bx
        self.by = by
    def LonLat2Tiles(self, *, x, y):
        trans_x, trans_y = transform(x, y)
        return (self.bx[0] + self.bx[1] * trans_x, self.by[0] + self.by[1] * trans_y)


#class Convertor:
    #def __init__(self):
        #self.proj_from = pyproj.Proj("+init=EPSG:4326")
        #self.proj_to = pyproj.Proj("+init=EPSG:3857")
    #def LonLat2Tiles(self, *, x, y):
        #maxresolution = 156543.0339
        #zoom = 13
        #resolution = (0.5 ** zoom) * maxresolution

        #maxextent = (-20037508.34, -20037508.34, 20037508.34, 20037508.34)
        #tilesize = (256, 256)

        #trans_x, trans_y = pyproj.transform(self.proj_from, self.proj_to, x, y)

        #tile_x = (trans_x - maxextent[0]) / (resolution * tilesize[0])
        #tile_y = (maxextent[1] - trans_y) / (resolution * tilesize[1])
		#var x = Math.round((bnds.left - this.maxExtent.left) / (res * this.tileSize.w));
		#var y = Math.round((this.maxExtent.top - bnds.top) / (res * this.tileSize.h));

        #return (tile_x, tile_y)


print(beta_x, beta_y)
print(longitudes, latitudes)
c = Convertor(beta_x.T.tolist()[0], beta_y.T.tolist()[0])

#c = Convertor()


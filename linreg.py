import numpy as np

latitudes = [
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



longitudes = [
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

L_x = np.vstack([np.ones(len(latitudes)), latitudes]).T
C_x = np.matrix(xcoords).T

beta_x = np.linalg.lstsq(L_x, C_x)[0]

L_y = np.vstack([np.ones(len(longitudes)), longitudes]).T
C_y = np.matrix(ycoords).T

beta_y = np.linalg.lstsq(L_y, C_y)[0]



class Convertor(object):
    def __init__(self, beta_x, beta_y):
        self.beta_x = beta_x
        self.beta_y = beta_y
    def LonLat2Tiles(self, *, x, y):
        return np.vstack([beta_x[0] + beta_x[1] * x, beta_y[0] + beta_y[1] * y])

c = Convertor(beta_x, beta_y)

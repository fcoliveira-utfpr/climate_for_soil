These observed meteorological data files were used to generate the gridded dataset 
of the paper:

Xavier, A.C., Scanlon, B.R., King, C.W. and Alves, A.I. (2022), New Improved Brazilian 
Daily Weather Gridded Data (1961-2020). Int J Climatol. https://doi.org/10.1002/joc.7731. 


If you found that this data is usefull for you, we appreciate that you cite
the paper.

If you have any question, please contact: alexandre.xavier@ufes.br


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
Example to open file name: pr.npz

Variables: precipitation (mm/day)
Period: 01/01/1961-31/12/2025

The "pr.npz" there are 4 numpy arrays, where: 
1) the precipitation data is file 'data', with each row 
is a single day and each column are rain gauges; 
2) 'lat_lon_alt' file lists the rain gauge latitude, longitude, altitude; 
3) the file 'ID', identifier of each rain gauges.

To open in Python:

#######################################################################################
import numpy as np
import pandas as pd

npzfile = np.load('pr.npz')
var = npzfile['data']
latlon = npzfile['lat_lon_alt']
id_station = npzfile['ID']
days = pd.date_range("1961-01-01", "2025-12-31")

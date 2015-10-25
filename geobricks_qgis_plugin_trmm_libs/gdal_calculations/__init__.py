'''
Name: gdal_calculations
Purpose: GDAL Dataset and Band abstraction for simple tiled raster calculations
         (AKA "map algebra")

Author: Luke Pinner
Contributors: Matt Gregory

Notes:
       - Can handle rasters with different extents,cellsizes and coordinate systems
         as long as they overlap. If extents/cellsizes/coordinate systems differ, the output
         extent/cellsize will the MINOF/MAXOF of input datasets, while the output
         coordinate system will be that of the leftmost Dataset in the expression
         unless Env.extent/Env.cellsize/Env.srs are specified.
       - gdal.Dataset and gdal.RasterBand and numpy.ndarray method and attribute calls are
         passed down to the underlying gdal.Dataset, gdal.RasterBand and ndarray objects.
       - If numexpr is installed, it can be used to evaluate your expressions, but note
         the limitations specified in the examples below.

Classes/Objects:
    Dataset(filepath_or_dataset ,*args)
        - Base Dataset class.
        - Instantiate by passing a path or gdal.Dataset object.
        - Supports gdal.Dataset and numpy.ndarray method and attribute calls.
        - Supports arithmetic operations (i.e ds1 + ds2)
    Band
        - Returned from Dataset[i] (zero based) or Dataset.GetRasterBand(j) (1 based)
          methods, not instantiated directly.
        - Supports gdal.RasterBand and numpy.ndarray method and attribute calls.
        - Supports arithmetic operations (i.e ds1[0] + ds2.GetRasterBand(1))
    ClippedDataset(dataset_or_band, extent)
        - Subclass of Dataset.
        - Uses VRT functionality to modify extent.
    ConvertedDataset(dataset_or_band, datatype)
        - Subclass of Dataset.
        - Uses VRT functionality to modify datatype.
        - Returned by the type conversion functions, not instantiated directly.
    TemporaryDataset(cols,rows,bands,datatype,srs='',gt=[],nodata=[])
        - Subclass of Dataset.
        - A temporary raster that only persists until it goes out of scope.
        - Stored in the Env.tempdir directory, which may be on disk or in
          memory (/vsimem).
        - Can be made permanent with the `save` method.
    WarpedDataset(dataset_or_band, wkt_srs, snap_ds=None, snap_cellsize=None)
        - Subclass of Dataset.
        - Uses VRT functionality to warp Dataset.
    ArrayDataset(array,extent=[],srs='',gt=[],nodata=[], prototype_ds=None)
        - Subclass of TemporaryDataset.
        - Instantiate by passing a numpy ndarray and georeferencing information
          or a prototype Dataset.
    DatasetStack(filepaths, band=0)
        - Stack of bands from multiple datasets
        - Similar to gdalbuildvrt -separate etc... functionality, except the class
          can handle rasters with different extents,cellsizes and coordinate systems
          as long as they overlap.
    Env - Object for setting various environment properties.
        - This is instantiated on import.
        - The following properties are supported:
            cellsize
              - one of 'DEFAULT','MINOF','MAXOF', [xres,yres], xyres
              - Default = "DEFAULT"
            enable_numexpr
              - this can break core numpy methods, such as numpy.sum([Dataset(foo),Dataset(bar)]
              - Default = False
            extent
              - one of "MINOF", "INTERSECT", "MAXOF", "UNION", [xmin,ymin,xmax,ymax]
              - Default = "MINOF"
            nodata
              - handle nodata using masked arrays - True/False
              - Default = False
            ntiles
              - number of tiles to process at a time
              - Default = 1
            overwrite
              - overwrite if required - True/False
              - Default = False
            reproject
              - reproject if required - True/False
              - datasets are projected to the SRS of the first input dataset in an expression
              - Default = False
            resampling
              - one of "AVERAGE"|"BILINEAR"|"CUBIC"|"CUBICSPLINE"|"LANCZOS"|"MODE"|"NEAREST"|gdal.GRA_*)
              - Default = "NEAREST"
            snap
              - a gdal_calculations.Dataset/Band object
              - Default = None
            srs
              - the output spatial reference system
              - one of osgeo.osr.SpatialReference (object)|WKT (string)|EPSG code (integer)
              - Default = None
            tempdir
              - temporary working directory
              - Default = tempfile.tempdir
            tempoptions
              - list of GTIFF creation options to use when creating temp rasters
              - Default = ['BIGTIFF=IF_SAFER']
            tiled
              - use tiled processing - True/False
              - Default = True
    Byte, UInt16, Int16, UInt32, Int32, Float32, Float64
        - Type conversions functions
        - Returns a ConvertedDataset object

Examples:

    from gdal_calculations import *
    from osgeo import gdal
    import numpy as np

    Env.extent = [xmin, ymin, xmax, ymax] # Other acceptable values:
                                          #  'INTERSECT' or 'MINOF' (default)
                                          #  'UNION' or 'MAXOF'
    Env.resampling = 'CUBIC'              # Other acceptable values:
                                          #  'NEAREST' (default)
                                          #  'AVERAGE'|'BILINEAR'|'CUBIC'
                                          #  'CUBICSPLINE'|'LANCZOS'|'MODE'
                                          #   gdal.GRA_* constant

    Env.reproject=True  #reproject on the fly if required

    Env.nodata=True  #Use a numpy.ma.MaskedArray to handle NoData values
                      #Note MaskedArrays are much slower...

    Env.overwrite=True

    gdal.UseExceptions()

    ds1=Dataset('../testdata/landsat_utm50.tif')#Projected coordinate system
    ds2=Dataset('../testdata/landsat_geo.tif')  #Geographic coordinate system

    #red=ds1[2].astype(np.float32) #You can use numpy type conversion (is slower)
    red=Float32(ds1[2]) #or use one of the provided type conversion functions (quicker as they use VRT's)
    nir=ds2[3]

    ndvi=(nir-red)/(nir+red)

    #Or in one go
    #ndvi=(ds2[3]-Float32(ds1[2])/(ds2[3]+Float32(ds1[2]))

    #Save the output
    ndvi=ndvi.save(r'../testdata/ndvi1.tif',options=['compress=LZW','TILED=YES'])

    #If you want to speed things up, use numexpr!
    #but there are a few limitations...
    import numexpr as ne

    #Must enable numexpr
    Env.enable_numexpr=True

    #Must not be tiled for numexpr
    Env.tiled=False

    #No subscripting or methods in the expression
    #red=ds1[2].astype(np.float32)
    red=Float32(ds1[2])
    nir=ds2[3] #Some Int*/UInt* datasets cause segfaults, workaround is cast to Float32

    #Must be same coordinate systems and dimensions
    #The check_extent method will reproject and clip if required
    #This is done using virtual rasters (VRT) so is very quick
    nir,red=nir.apply_environment(red)

    expr='(nir-red)/(nir+red)'
    ndvi=ne.evaluate(expr)

    #evaluate returns an ndarray not a Dataset
    #So need to write to a Temporary ArrayDataset
    ndvi=ArrayDataset(ndvi,prototype_ds=nir)
    ndvi=ndvi.save(r'../testdata/ndvi2.tif',options=['compress=LZW','TILED=YES'])

    #Get the raw numpy array data
    for block in red.ReadBlocksAsArray():
        print block.x_off,block.y_off,block.data.shape

    rawdata=red.ReadAsArray()
    print rawdata.shape

'''
# Copyright: (c) Luke Pinner 2013
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#-------------------------------------------------------------------------------
__version__='1.1'

from gdal_dataset import *
from conversions import *
from environment import *

from gdal_dataset import __all__ as __dall__
from conversions import __all__ as __call__
from environment import __all__ as __eall__
__all__=[]
__all__.extend(__dall__)
__all__.extend(__call__)
__all__.extend(__eall__)

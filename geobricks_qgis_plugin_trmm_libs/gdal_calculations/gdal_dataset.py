# -*- coding: UTF-8 -*-
'''
Name: gdal_dataset.py
Purpose: GDAL Dataset and Band abstraction for simple tiled raster calculations
         (AKA "map algebra")

Author: Luke Pinner
Contributors: Matt Gregory

Notes: - see __init__.py
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
__all__ = [ "Dataset",          "ArrayDataset",
            "ConvertedDataset", "ClippedDataset",
            "WarpedDataset",    "DatasetStack",
            "TemporaryDataset", "NewDataset",
            "Block"
          ]

import numpy as np
from osgeo import gdal, gdal_array, osr
import os, tempfile, operator, sys

from environment import Env,Progress
import geometry

gdal.UseExceptions()
osr.UseExceptions()

# Calculations classes
class Block(object):
    '''Block class thanks to Matt Gregory'''
    def __init__(self, dataset_or_band, x_off, y_off, x_size, y_size,*args,**kwargs):
        self.x_off = x_off
        self.y_off = y_off
        self.x_size = x_size
        self.y_size = y_size
        self.data = dataset_or_band.ReadAsArray(x_off, y_off, x_size, y_size,*args,**kwargs)

    def __getattr__(self, attr):
        '''Pass any other attribute or method calls
           through to the underlying ndarray object'''
        if attr in dir(np.ndarray):return getattr(self.data,attr)
        else:raise AttributeError("'Block' object has no attribute '%s'"%attr)

class RasterLike(object):
    '''Super class for Band and Dataset objects to avoid duplication '''

    def __init__(self):raise NotImplementedError

    #===========================================================================
    #Public methods
    #===========================================================================
    def apply_environment(self,other):
        ''' Apply various environment settings and checks
            including snapping/extents/cellsizes/coordinate systems
        '''
        dataset1,dataset2=self.__check_srs__(self,other)
        dataset1,dataset2=self.__check_cellsize__(dataset1,dataset2)
        dataset1,dataset2=self.__check_extent__(dataset1,dataset2)
        return dataset1,dataset2
    check_extent=apply_environment #synonym for backwards compatability with v. <0.5

    def create_copy(self,outpath,outformat='GTIFF',options=[]):
        ok=(os.path.exists(outpath) and Env.overwrite) or (not os.path.exists(outpath))
        if ok:
            if Env.progress.enabled:callback=gdal.TermProgress_nocb
            else:callback=None
            try:                   #Is it a Band
                ds=self.dataset._dataset
            except AttributeError: #No, it's a Dataset
                ds=self._dataset
            driver=gdal.GetDriverByName(outformat)
            ds=driver.CreateCopy(outpath,ds,options=options,callback=callback)
            ds=None
            del ds
            return Dataset(outpath)
        else:raise RuntimeError('Output %s exists and overwrite is not set.'%outpath)
    save=create_copy  # synonym for backwards compatibility

    def read_blocks_as_array(self, nblocks=None):
        '''Read GDAL Datasets/Bands block by block'''

        ncols=self._x_size
        nrows=self._y_size
        if nblocks is None:nblocks=Env.ntiles
        xblock,yblock=self._block_size

        if xblock==ncols:
            yblock*=nblocks
        else:
            xblock*=nblocks

        for yoff in xrange(0, nrows, yblock):

            if yoff + yblock < nrows:
                ysize = yblock
            else:
                ysize  = nrows - yoff

            for xoff in xrange(0, ncols, xblock):
                if xoff + xblock < ncols:
                    xsize  = xblock
                else:
                    xsize = ncols - xoff

                yield Block(self, xoff, yoff, xsize, ysize )
    #CamelCase synonym
    ReadBlocksAsArray=read_blocks_as_array

    #===========================================================================
    #Private methods
    #===========================================================================
    def __check_cellsize__(self,dataset1,dataset2):
        #Do we need to resample?
        if Env.cellsize=='MAXOF':
            px=max(dataset1._gt[1],dataset2._gt[1])
            py=max(abs(dataset1._gt[5]),abs(dataset2._gt[5]))
            if (dataset1._gt[1],abs(dataset1._gt[5]))!=(px,py):
                dataset1=WarpedDataset(dataset1,dataset1._srs, dataset1, (px,py))
            if (dataset2._gt[1],abs(dataset2._gt[5]))!=(px,py):
                dataset2=WarpedDataset(dataset2,dataset1._srs, dataset1, (px,py))
        elif Env.cellsize=='MINOF':
            px=min(dataset1._gt[1],dataset2._gt[1])
            py=min(abs(dataset1._gt[5]),abs(dataset2._gt[5]))
            if (dataset1._gt[1],abs(dataset1._gt[5]))!=(px,py):
                dataset1=WarpedDataset(dataset1,dataset1._srs, dataset1, (px,py))
            if (dataset2._gt[1],abs(dataset2._gt[5]))!=(px,py):
                dataset2=WarpedDataset(dataset2,dataset1._srs, dataset1, (px,py))
        elif Env.cellsize!='DEFAULT':
            if (dataset1._gt[1],abs(dataset1._gt[5]))!=Env.cellsize:
                dataset1=WarpedDataset(dataset1,dataset1._srs, dataset1,Env.cellsize)
            if (dataset2._gt[1],abs(dataset2._gt[5]))!=Env.cellsize:
                dataset2=WarpedDataset(dataset2,dataset2._srs, dataset2,Env.cellsize)
        else: #Env.cellsize=='DEFAULT'
            if (dataset2._gt[1],abs(dataset2._gt[5]))!=(dataset1._gt[1],abs(dataset1._gt[5])):
                dataset2=WarpedDataset(dataset2,dataset1._srs, dataset1, (dataset1._gt[1],abs(dataset1._gt[5])))

        return dataset1,dataset2

    def __check_extent__(self,dataset1,dataset2):
        ext=Env.extent

        #Do they overlap
        geom1=geometry.GeomFromExtent(dataset1.extent)
        geom2=geometry.GeomFromExtent(dataset2.extent)

        if not geom1.Intersects(geom2):
            raise RuntimeError('Input datasets do not overlap')

        #Do we need to modify the extent?
        try:
            if ext.upper() in ['MINOF','INTERSECT']:
                ext=dataset1.__minextent__(dataset2)
            elif ext.upper() in ['MAXOF','UNION']:
                ext=dataset1.__maxextent__(dataset2)
        except AttributeError: #ext is [xmin,ymin,xmax,ymax]
            if Env.snap:
                s_ext=Env.snap.extent
                s_gt=Env.snap._gt
                gt=[ext[0], dataset1._gt[1], dataset1._gt[2], ext[3], dataset1._gt[5], dataset1._gt[5]]
                ext=geometry.SnapExtent(ext, gt, s_ext, s_gt)

        if dataset1.extent!=ext: dataset1=ClippedDataset(dataset1,ext)
        if dataset2.extent!=ext: dataset2=ClippedDataset(dataset2,ext)

        return dataset1,dataset2

    def __check_srs__(self,dataset1,dataset2):
        srs=Env.srs

        srs1=osr.SpatialReference(dataset1._srs)
        srs2=osr.SpatialReference(dataset2._srs)

        #Do we need to reproject?
        if srs:
            if not srs1.IsSame(srs):
                dataset1=WarpedDataset(dataset1,srs.ExportToWkt(), Env.snap)
            if not srs2.IsSame(srs):
                dataset2=WarpedDataset(dataset2,srs.ExportToWkt(), dataset1)
        elif not srs1.IsSame(srs2):
            if  Env.reproject:
                dataset2=WarpedDataset(dataset2,dataset1._srs, dataset1)
            else:raise RuntimeError('Coordinate systems differ and Env.reproject==False')

        return dataset1,dataset2

    def __get_extent__(self):
        #Returns [(ulx,uly),(llx,lly),(lrx,lry),(urx,urx)]
        ext=geometry.GeoTransformToExtent(self._gt,self._x_size,self._y_size)
        return [ext[1][0],ext[1][1],ext[3][0],ext[3][1]]

    def __getnodes__(self, root, nodetype, name, index=True):
        '''Function for handling serialised VRT XML'''
        #Originally based on the  _xmlsearch function in GDAL autotest/gdrivers/vrtderived.py
        nodes=[]
        for i,node in enumerate(root[2:]):
            if node[0] == nodetype and node[1] == name:
                if index:nodes.append(i+2)
                else:nodes.append(node)
        return nodes

    def __minextent__(self,other):
        ext=geometry.MinExtent(self.extent,other.extent)
        if not Env.snap:return ext
        else:
            s_ext=Env.snap.extent
            s_gt=Env.snap._gt
            gt=[ext[0], self._gt[1], self._gt[2], ext[3], self._gt[5], self._gt[5]]
            ext=geometry.SnapExtent(ext, gt, s_ext, s_gt)
            return ext

    def __maxextent__(self,other):
        ext=geometry.MaxExtent(self.extent,other.extent)
        if not Env.snap:return ext
        else:
            s_ext=Env.snap.extent
            s_gt=Env.snap._gt
            gt=[ext[0], self._gt[1], self._gt[2], ext[3], self._gt[5], self._gt[5]]
            ext=geometry.SnapExtent(ext, gt, s_ext, s_gt)
            return ext

    def __read_vsimem__(self,fn):
        '''Read GDAL vsimem files'''
        vsifile = gdal.VSIFOpenL(fn,'r')
        gdal.VSIFSeekL(vsifile, 0, 2)
        vsileng = gdal.VSIFTellL(vsifile)
        gdal.VSIFSeekL(vsifile, 0, 0)
        return gdal.VSIFReadL(1, vsileng, vsifile)

    def __write_vsimem__(self,fn,data):
        '''Write GDAL vsimem files'''
        vsifile = gdal.VSIFOpenL(fn,'w')
        size = len(data)
        gdal.VSIFWriteL(data, 1, size, vsifile)
        return gdal.VSIFCloseL(vsifile)

    #===========================================================================
    #gdal.Dataset/Band and ndarray attribute calls
    #===========================================================================
    def __ndarrayattribute__(self,attr):
        '''Pass attribute gets down to ndarray'''
        #if attr[:8] == '__array_': return None #This breaks numexpr
        if attr[:8] == '__array_':
            if not Env.enable_numexpr:return None
            if Env.enable_numexpr and Env.tiled:raise RuntimeError('Env.tiled must be False to use numexpr.eval.')

        if Env.tiled:
            '''Pass attribute gets down to the first block.
               Obviously won't work for b.shape etc...'''
            for b in self.ReadBlocksAsArray():
                return getattr(b,attr)
        else:
            return getattr(self.ReadAsArray(),attr)

    def __ndarraymethod__(self,attr):
        '''Pass method calls down to ndarrays and return a temporary dataset.'''

        def __method__(*args,**kwargs):
            if attr[:8] == '__array_': return None #This breaks numexpr

            if Env.tiled:
                reader=self.ReadBlocksAsArray()
                xblock,yblock=self._block_size
                Env.progress.steps = (self._x_size*self._y_size)/(xblock*yblock*Env.ntiles)
            else: reader=[Block(self,0, 0,self._x_size, self._y_size)]

            tmpds=None
            for b in reader:

                if Env.nodata:
                    if b.data.ndim==2:mask=(b.data==self._nodata[0])
                    else:mask=np.array([b.data[i,:,:]==self._nodata[i] for i in range(b.data.shape[0])])
                    b.data=np.ma.MaskedArray(b.data,mask)
                    b.data.fill_value=self._nodata[0]
                    nodata=[self._nodata[0]]*self._nbands
                else:nodata=self._nodata

                data=getattr(b.data,attr)(*args,**kwargs)

                #Sanity check - returns array of same dimensions as block
                if data.shape not in [((b.y_size,b.x_size)),(self._nbands,b.y_size,b.x_size)]:
                    if Env.tiled:raise RuntimeError('When Env.tiled==True, the "%s" method is not supported.'%attr)
                    else:return data

                if not tmpds:
                    #GDAL casts unknown types to Float64... bools don't need to be that big
                    if data.dtype==np.bool:data=data.astype(np.uint8)
                    datatype=gdal_array.NumericTypeCodeToGDALTypeCode(data.dtype.type)

                    if datatype is None:raise RuntimeError('Unsupported operation: "%s"'%attr)
                    if data.ndim==2:nbands=1
                    else:nbands=data.shape[0]

                    tmpds=TemporaryDataset(self._x_size,self._y_size,nbands,
                                           datatype,self._srs,self._gt, nodata)

                tmpds.write_data(data, b.x_off, b.y_off)
                Env.progress.update_progress()

            try:tmpds.FlushCache() #Fails when file is in /vsimem
            except:pass

            return tmpds

        return __method__

    def __operation__(self,op,other=None,swapped=False,*args,**kwargs):
        ''' Perform arithmetic/bitwise/boolean and return a temporary dataset.
            Set `swapped` to True to perform the operation
            with reflected (swapped) operands.
        '''
        dataset1,dataset2=self,other
        if isinstance(other,RasterLike):
            if swapped:
                dataset2,dataset1=other.check_extent(self)
            else:
                dataset1,dataset2=self.check_extent(other)

        if Env.tiled:
            reader=dataset1.ReadBlocksAsArray()
            xblock,yblock=self._block_size
            Env.progress.steps = (self._x_size*self._y_size)/(xblock*yblock*Env.ntiles)
        else: reader=[Block(dataset1,0, 0,dataset1.RasterXSize, dataset1.RasterYSize)]
        tmpds=None
        for b1 in reader:
            if Env.nodata:
                if b1.data.ndim==2:mask=(b1.data==dataset1._nodata[0])
                else:mask=np.array([b1.data[i,:,:]==dataset1._nodata[i] for i in range(b1.data.shape[0])])
                b1.data=np.ma.MaskedArray(b1.data,mask)
                b1.data.fill_value=dataset1._nodata[0]
                nodata=[dataset1._nodata[0]]*dataset1._nbands
            else:nodata=dataset1._nodata

            if dataset2 is not None: #zero is valid
                if isinstance(dataset2,RasterLike):
                    b2=Block(dataset2,b1.x_off, b1.y_off,b1.x_size, b1.y_size)

                    if Env.nodata:
                        if b2.data.ndim==2:mask=(b2.data==dataset2._nodata[0])
                        else:mask=np.array([b2.data[i,:,:]==dataset2._nodata[i] for i in range(b2.data.shape[0])])
                        b2.data=np.ma.MaskedArray(b2.data,mask)
                        b2.data.fill_value=dataset1._nodata[0]
                        nodata=[dataset1._nodata[0]]*dataset2._nbands
                    else:nodata=dataset1._nodata

                    if swapped:data=op(b2.data, b1.data)
                    else:data=op(b1.data, b2.data)
                else: #Not a Band/Dataset, try the op directly
                    if swapped:data=op(dataset2, b1.data)
                    else:data=op(b1.data,dataset2)
            else:
                data=op(b1.data)
            if data.dtype==np.bool:data=data.astype(np.uint8)
            if not tmpds:
                datatype=gdal_array.NumericTypeCodeToGDALTypeCode(data.dtype.type)
                if not datatype:datatype=gdal.GDT_Byte
                try:tmpds=TemporaryDataset(dataset1._x_size,dataset1._y_size,dataset1._nbands,
                                       datatype,dataset1._srs,dataset1._gt,nodata)
                except:tmpds=TemporaryDataset(dataset2._x_size,dataset2._y_size,dataset2._nbands,
                                       datatype,dataset1._srs,dataset1._gt,nodata)
            tmpds.write_data(data, b1.x_off, b1.y_off)
            Env.progress.update_progress()

        try:tmpds.FlushCache()
        except:pass
        return tmpds

    #===========================================================================
    #Arithmetic operations
    #===========================================================================
    def __add__(self,other):
        return self.__operation__(operator.__add__,other)
    def __sub__(self,other):
        return self.__operation__(operator.__sub__,other)
    def __mul__(self,other):
        return self.__operation__(operator.__mul__,other)
    def __div__(self,other):
        return self.__operation__(operator.__div__,other)
    def __truediv__(self,other):
        return self.__operation__(operator.__truediv__,other)
    def __floordiv__(self,other):
        return self.__operation__(operator.__floordiv__,other)
    def __mod__(self,other):
        return self.__operation__(operator.__mod__,other)
    def __pow__(self,other):
        return self.__operation__(operator.__pow__,other)
    def __pos__(self):
        return self.__operation__(operator.__pos__,other)
    def __neg__(self):
        return self.__operation__(operator.__neg__)
    #For when the dataset is the right operand
    def __radd__(self,other):
        return self.__operation__(operator.__add__,other, swapped=1)  #not that it really matters for + and *...
    def __rsub__(self,other):
        return self.__operation__(operator.__sub__,other, swapped=1)
    def __rmul__(self,other):
        return self.__operation__(operator.__mul__,other, swapped=1)
    def __rdiv__(self,other):
        return self.__operation__(operator.__div__,other, swapped=1)
    def __rtruediv__(self,other):
        return self.__operation__(operator.__truediv__,other, swapped=1)
    def __rfloordiv__(self,other):
        return self.__operation__(operator.__floordiv__,other, swapped=1)
    def __rmod__(self,other):
        return self.__operation__(operator.__mod__,other, swapped=1)
    def __rpow__(self,other):
        return self.__operation__(operator.__pow__,other, swapped=1)
    #===========================================================================
    #Bitwise operations
    #===========================================================================
    def __and__(self,other):
        return self.__operation__(operator.__and__,other)
    def __inv__(self):
        return self.__operation__(operator.__inv__)
    def __lshift__(self,other):
        return self.__operation__(operator.__lshift__,other)
    def __rshift__(self,other):
        return self.__operation__(operator.__rshift__,other)
    def __or__(self,other):
        return self.__operation__(operator.__or__,other)
    def __xor__(self,other):
        return self.__operation__(operator.__xor__,other)
    #For when the dataset is the right operand
    def __rand__(self,other):
        return self.__operation__(operator.__and__,other, swapped=1)
    def __rlshift__(self,other):
        return self.__operation__(operator.__lshift__,other, swapped=1)
    def __rrshift__(self,other):
        return self.__operation__(operator.__rshift__,other, swapped=1)
    def __ror__(self,other):
        return self.__operation__(operator.__or__,other, swapped=1)
    def __rxor__(self,other):
        return self.__operation__(operator.__xor__,other, swapped=1)

    #===========================================================================
    #Boolean operations
    #===========================================================================
    def __lt__(self,other):
        return self.__operation__(operator.__lt__,other)
    def __le__(self,other):
        return self.__operation__(operator.__le__,other)
    def __eq__(self,other):
        return self.__operation__(operator.__eq__,other)
    def __ne__(self,other):
        return self.__operation__(operator.__ne__,other)
    def __ge__(self,other):
        return self.__operation__(operator.__ge__,other)
    def __gt__(self,other):
        return self.__operation__(operator.__gt__,other)

class Band(RasterLike):
    ''' Subclass a GDALBand object without _actually_ subclassing it
        so we can add new methods.

        The 'magic' bit is using getattr to pass attribute or method calls
        through to the underlying GDALBand/ndarray objects
    '''
    def __init__(self,band,dataset,bandnum=0):
        self._band = band
        self.dataset=dataset #Keep a link to the parent Dataset object

        self._x_size=dataset._x_size
        self._y_size=dataset._y_size
        self._nbands=1
        self._bands=[bandnum]#Keep track of band number, zero based index
        self._data_type=self.DataType
        self._srs=dataset.GetProjectionRef()
        self._gt=dataset.GetGeoTransform()
        self._block_size=self.GetBlockSize()
        self._nodata=[band.GetNoDataValue()]
        self.extent=self.__get_extent__()

    def get_raster_band(self,*args,**kwargs):
        '''So we can sort of treat Band and Dataset interchangeably'''
        return self
    GetRasterBand=get_raster_band

    def __getattr__(self, attr):
        '''Pass any other attribute or method calls
           through to the underlying GDALBand/ndarray objects'''
        if attr=='dtype':raise TypeError #so numpy ufuncs work
        #if attr in ('dtype','__array__struct__'):raise TypeError #so numpy ufuncs work
        if attr in dir(gdal.Band):return getattr(self._band, attr)
        elif attr in dir(np.ndarray):
            if callable(getattr(np.ndarray,attr)):return self.__ndarraymethod__(attr)
            else:return self.__ndarrayattribute__(attr)
        else:raise AttributeError("'Band' object has no attribute '%s'"%attr)

class Dataset(RasterLike):
    ''' Subclass a GDALDataset object without _actually_ subclassing it
        so we can add new methods.

        The 'magic' bit is using getattr to pass attribute or method calls
        through to the underlying GDALDataset/ndarray objects
    '''
    def __init__(self,filepath_or_dataset=None,*args):
        gdal.UseExceptions()

        fp=filepath_or_dataset

        if type(fp) is gdal.Dataset:
            self._dataset = fp
        elif fp is not None:
            if os.path.exists(fp):
                self._dataset = gdal.Open(os.path.abspath(fp),*args)
            else:
                self._dataset = gdal.Open(fp,*args)

        #Issue 8
        self._gt=self.GetGeoTransform()
        if self._gt[5] > 0: #positive NS pixel res.
            tmp_ds = gdal.AutoCreateWarpedVRT(self._dataset)
            tmp_fn = '/vsimem/%s.vrt'%tempfile._RandomNameSequence().next()
            self._dataset = gdal.GetDriverByName('VRT').CreateCopy(tmp_fn,tmp_ds)
            self._gt = self.GetGeoTransform()

        self._x_size=self.RasterXSize
        self._y_size=self.RasterYSize
        self._nbands=self.RasterCount
        self._bands=range(self.RasterCount)
        self._data_type=self.GetRasterBand(1).DataType
        self._srs=self.GetProjectionRef()
        self._block_size=self.GetRasterBand(1).GetBlockSize()
        self._nodata=[b.GetNoDataValue() for b in self]
        
        self.extent=self.__get_extent__()

    def __del__(self):
        self._dataset=None
        del self._dataset

    def __getattr__(self, attr):
        '''Pass any other attribute or method calls
           through to the underlying GDALDataset object'''
        if attr=='dtype':raise TypeError #so numpy ufuncs work
        #if attr in ('dtype','__array__struct__'):raise TypeError #so numpy ufuncs work
        if attr in dir(gdal.Dataset):return getattr(self._dataset, attr)
        elif attr in dir(np.ndarray):
            if callable(getattr(np.ndarray,attr)):return self.__ndarraymethod__(attr)
            else:return self.__ndarrayattribute__(attr)
        else:raise AttributeError("'Dataset' object has no attribute '%s'"%attr)

    def __getitem__(self, key):
        ''' Enable "somedataset[bandnum]" syntax'''
        return Band(self._dataset.GetRasterBand(key+1),self, key) #GDAL Dataset Band indexing starts at 1

    def __delitem__(self, key):
        ''' Enable "somedataset[bandnum]" syntax'''
        raise RuntimeError('Bands can not be deleted')

    def __setitem__(self, key):
        ''' Enable "somedataset[bandnum]" syntax'''
        raise RuntimeError('Bands can not be added or modifed')

    def __len__(self):
        ''' Enable "somedataset[bandnum]" syntax'''
        return self.RasterCount

    def __iter__(self):
        ''' Enable "for band in somedataset:" syntax'''
        for i in xrange(self.RasterCount):
            yield Band(self.GetRasterBand(i+1),self,i) #GDAL Dataset Band indexing starts at 1

    def get_raster_band(self,i=1): #GDAL Dataset Band indexing starts at 1
        return Band(self._dataset.GetRasterBand(i),self,i-1)

    #CamelCase synonym
    GetRasterBand=get_raster_band

    def band_read_blocks_as_array(self,i,*args,**kwargs):
        return Band(self.GetRasterBand(i), self, i-1).ReadBlocksAsArray(*args,**kwargs)

    #CamelCase synonym
    BandReadBlocksAsArray=band_read_blocks_as_array

class ClippedDataset(Dataset):
    '''Use a VRT to "clip" to min extent of two rasters'''

    def __init__(self,dataset_or_band,extent):
        self._tmpds=None
        self._parentds=dataset_or_band #keep a reference so it doesn't get garbage collected
        use_exceptions=gdal.GetUseExceptions()
        gdal.UseExceptions()

        try:                   #Is it a Band
            orig_ds=dataset_or_band.dataset._dataset
        except AttributeError: #No, it's a Dataset
            orig_ds=dataset_or_band._dataset

        #Basic info
        bands=dataset_or_band._bands
        gt = dataset_or_band._gt
        xoff,yoff,clip_xsize,clip_ysize=self._extent_to_offsets(extent,gt)
        #ulx,uly=geometry.PixelToMap(xoff,yoff,gt)
        ulx,uly=extent[0],extent[3]
        clip_gt=(ulx,gt[1],gt[2],uly,gt[4],gt[5])

        #Temp in memory VRT file
        fn='/vsimem/%s.vrt'%tempfile._RandomNameSequence().next()
        driver=gdal.GetDriverByName('VRT')
        driver.CreateCopy(fn,orig_ds)

        #Read XML from vsimem, requires gdal VSIF*
        vrtxml = self.__read_vsimem__(fn)
        gdal.Unlink(fn)

        #Parse the XML,
        #use gdals built-in XML handling to reduce external dependencies
        vrttree = gdal.ParseXMLString(vrtxml)
        getnodes=self.__getnodes__

        #Handle warped VRTs
        wo=getnodes(vrttree, gdal.CXT_Element, 'GDALWarpOptions')
        if wo:vrttree=self._create_simple_VRT(orig_ds,bands)

        rasterXSize = getnodes(vrttree, gdal.CXT_Attribute, 'rasterXSize')[0]
        rasterYSize = getnodes(vrttree, gdal.CXT_Attribute, 'rasterYSize')[0]
        GeoTransform = getnodes(vrttree, gdal.CXT_Element, 'GeoTransform')[0]

        #Set new values
        vrttree[rasterXSize][2][1]=str(clip_xsize)
        vrttree[rasterYSize][2][1]=str(clip_ysize)
        vrttree[GeoTransform][2][1]='%f, %f, %f, %f, %f, %f'%clip_gt

        #Loop through bands #TODO Handle warped VRTs
        vrtbandnodes=getnodes(vrttree, gdal.CXT_Element, 'VRTRasterBand',False)
        vrtbandkeys=getnodes(vrttree, gdal.CXT_Element, 'VRTRasterBand')
        for key in reversed(vrtbandkeys): del vrttree[key]#Reverse so we can delete from the end
                                                          #Don't assume bands are the last elements...
        i=0
        for node in vrtbandnodes:

            #Skip to next band if required
            bandnum=getnodes(node, gdal.CXT_Attribute, 'band')[0]
            #GDAL band indexing starts at one, internal band counter is zero based
            #if not int(node[sourcekey][sourceband][2][1])-1 in bands:continue
            if not int(node[bandnum][2][1])-1 in bands:continue

            try:
                NoDataValue=getnodes(node, gdal.CXT_Element, 'NoDataValue')[0]
                nodata=node[NoDataValue][2][1]
                node[NoDataValue][2][1]='0' #if clipping results in a bigger XSize/YSize, gdal initialises with 0
            except IndexError:nodata='0' #pass

            for source in ['SimpleSource','ComplexSource','AveragedSource','KernelFilteredSource']:
                try:
                    sourcekey=getnodes(node, gdal.CXT_Element, source)[0]
                    break
                except IndexError:pass

            if source=='SimpleSource':node[sourcekey][1]='ComplexSource' #so the <NODATA> element can be used
            sourcefilename=getnodes(node[sourcekey], gdal.CXT_Element, 'SourceFilename')[0]
            relativeToVRT=getnodes(node[sourcekey][sourcefilename], gdal.CXT_Attribute, 'relativeToVRT')[0]
            if node[sourcekey][sourcefilename][relativeToVRT][2][1]=='1':
                node[sourcekey][sourcefilename][relativeToVRT][2][1]='0'
                node[sourcekey][sourcefilename][3][1]=os.path.join(os.path.dirname(fn),node[sourcekey][sourcefilename][3][1])
            sourceband=getnodes(node[sourcekey], gdal.CXT_Element, 'SourceBand')[0]

            #Skip to next band if required
            #GDAL band indexing starts at one, internal band counter is zero based
            #if not int(node[sourcekey][sourceband][2][1])-1 in bands:continue

            i+=1 #New band num
            vrtbandnum=getnodes(node, gdal.CXT_Attribute, 'band')[0]
            node[vrtbandnum][2][1]=str(i)

            srcrect=getnodes(node[sourcekey], gdal.CXT_Element, 'SrcRect')[0]
            srcXOff = getnodes(node[sourcekey][srcrect], gdal.CXT_Attribute, 'xOff')[0]
            srcYOff = getnodes(node[sourcekey][srcrect], gdal.CXT_Attribute, 'yOff')[0]
            srcXSize = getnodes(node[sourcekey][srcrect], gdal.CXT_Attribute, 'xSize')[0]
            srcYSize = getnodes(node[sourcekey][srcrect], gdal.CXT_Attribute, 'ySize')[0]
            node[sourcekey][srcrect][srcXOff][2][1]=str(xoff)
            node[sourcekey][srcrect][srcYOff][2][1]=str(yoff)
            node[sourcekey][srcrect][srcXSize][2][1]=str(clip_xsize)
            node[sourcekey][srcrect][srcYSize][2][1]=str(clip_ysize)

            dstrect=getnodes(node[sourcekey], gdal.CXT_Element, 'DstRect')[0]
            dstXOff = getnodes(node[sourcekey][srcrect], gdal.CXT_Attribute, 'xOff')[0]
            dstYOff = getnodes(node[sourcekey][srcrect], gdal.CXT_Attribute, 'yOff')[0]
            dstXSize = getnodes(node[sourcekey][dstrect], gdal.CXT_Attribute, 'xSize')[0]
            dstYSize = getnodes(node[sourcekey][dstrect], gdal.CXT_Attribute, 'ySize')[0]
            node[sourcekey][dstrect][dstXOff][2][1]='0'
            node[sourcekey][dstrect][dstYOff][2][1]='0'
            node[sourcekey][dstrect][dstXSize][2][1]=str(clip_xsize)
            node[sourcekey][dstrect][dstYSize][2][1]=str(clip_ysize)

            try: #Populate <NODATA> element with band NoDataValue as it might not be 0
                NODATA=getnodes(node[sourcekey], gdal.CXT_Element, 'NODATA')[0]
                node[sourcekey][NODATA][2][1]=nodata
            except IndexError:
                node[sourcekey].append([gdal.CXT_Element, 'NODATA', [gdal.CXT_Text, nodata]])

            vrttree.insert(key,node)

        #Open new clipped dataset
        vrtxml=gdal.SerializeXMLTree(vrttree)
        self._filename='/vsimem/%s.vrt'%tempfile._RandomNameSequence().next()
        self.__write_vsimem__(self._filename,vrtxml)
        self._dataset=gdal.Open(self._filename)

        if not use_exceptions:gdal.DontUseExceptions()

        Dataset.__init__(self)

    def _create_simple_VRT(self,warped_ds,bands):
        ''' Create a simple VRT XML string from a warped VRT (GDALWarpOptions)'''

        vrt=[]
        vrt.append('<VRTDataset rasterXSize="%s" rasterYSize="%s">' % (warped_ds.RasterXSize,warped_ds.RasterYSize))
        vrt.append('  <SRS>%s</SRS>' % warped_ds.GetProjection())
        vrt.append('  <GeoTransform>%s</GeoTransform>' % ', '.join(map(str,warped_ds.GetGeoTransform())))
        for i,band in enumerate(bands):
            rb=warped_ds.GetRasterBand(band+1) #gdal band index start at 1
            nodata=rb.GetNoDataValue()
            path=warped_ds.GetDescription()
            rel=not os.path.isabs(path)
            vrt.append('  <VRTRasterBand dataType="%s" band="%s">' % (gdal.GetDataTypeName(rb.DataType), i+1))
            vrt.append('    <SimpleSource>')
            vrt.append('      <SourceFilename relativeToVRT="%s">%s</SourceFilename>' % (int(rel),path))
            vrt.append('      <SourceBand>%s</SourceBand>'%(band+1))
            vrt.append('      <SrcRect xOff="0" yOff="0" xSize="%s" ySize="%s" />' % (warped_ds.RasterXSize,warped_ds.RasterYSize))
            vrt.append('      <DstRect xOff="0" yOff="0" xSize="%s" ySize="%s" />' % (warped_ds.RasterXSize,warped_ds.RasterYSize))
            vrt.append('    </SimpleSource>')
            if nodata is not None: # 0 is a valid value
                vrt.append('    <NoDataValue>%s</NoDataValue>' % nodata)
            vrt.append('  </VRTRasterBand>')
        vrt.append('</VRTDataset>')

        vrt='\n'.join(vrt)
        vrttree=gdal.ParseXMLString(vrt)
        return vrttree

    def _extent_to_offsets(self,extent,gt):
        xoff,yoff=geometry.MapToPixel(extent[0],extent[3],gt) #xmin,ymax in map coords
        xmax,ymin=geometry.MapToPixel(extent[2],extent[1],gt) #
        xsize=xmax-xoff
        ysize=ymin-yoff #Pixel coords start from upper left
        return (int(xoff+0.5),int(yoff+0.5),int(xsize+0.5),int(ysize+0.5))

    def __del__(self):
        try:gdal.Unlink(self._filename)
        except:pass
        self._dataset=None
        del self._dataset
        self._parent=None
        del self._parent

class ConvertedDataset(Dataset):
    '''Use a VRT to "convert" between datatypes'''

    def __init__(self,dataset_or_band,datatype):
        self._parentds=dataset_or_band #keep a reference so it doesn't get garbage collected
        use_exceptions=gdal.GetUseExceptions()
        gdal.UseExceptions()

        try:                   #Is it a Band
            orig_ds=dataset_or_band.dataset._dataset
        except AttributeError: #No, it's a Dataset
            orig_ds=dataset_or_band._dataset

        #Temp in memory VRT file
        fn='/vsimem/%s.vrt'%tempfile._RandomNameSequence().next()
        driver=gdal.GetDriverByName('VRT')
        driver.CreateCopy(fn,orig_ds)

        #Read XML from vsimem, requires gdal VSIF*
        vrtxml =self.__read_vsimem__(fn)
        gdal.Unlink(fn)

        #Parse the XML,
        #use gdals built-in XML handling to reduce external dependencies
        vrttree = gdal.ParseXMLString(vrtxml)
        getnodes=self.__getnodes__

        #Loop through bands, remove the bands, modify
        #then reinsert in case we are dealing with a "Band" object
        vrtbandnodes=getnodes(vrttree, gdal.CXT_Element, 'VRTRasterBand',False)
        vrtbandkeys=getnodes(vrttree, gdal.CXT_Element, 'VRTRasterBand')
        for key in reversed(vrtbandkeys): del vrttree[key]#Reverse so we can delete from the end
                                                          #Don't assume bands are the last elements...
        for i,band in enumerate(dataset_or_band._bands):
            node=getnodes(vrtbandnodes[band], gdal.CXT_Attribute, 'dataType')[0]
            try:vrtbandnodes[band][node][2][1]=gdal.GetDataTypeName(datatype)
            except TypeError:vrtbandnodes[band][node][2][1]=datatype
            node=getnodes(vrtbandnodes[band], gdal.CXT_Attribute, 'band')[0]
            vrtbandnodes[band][node][2][1]=str(i+1)
            vrttree.insert(vrtbandkeys[i],vrtbandnodes[band])

        #Handle warped VRTs
        wo=getnodes(vrttree, gdal.CXT_Element, 'GDALWarpOptions')
        if wo:
            wo=wo[0]
            bl=getnodes(vrttree[wo], gdal.CXT_Element, 'BandList')[0]
            warpbandnodes=getnodes(vrttree[wo][bl], gdal.CXT_Element, 'BandMapping',False)
            warpbandkeys=getnodes(vrttree[wo][bl], gdal.CXT_Element, 'BandMapping')
            for key in reversed(warpbandkeys): del vrttree[wo][bl][key]#Reverse so we can delete from the end
            for i,band in enumerate(dataset_or_band._bands):
                src=getnodes(warpbandnodes[band], gdal.CXT_Attribute, 'src')[0]
                dst=getnodes(warpbandnodes[band], gdal.CXT_Attribute, 'dst')[0]
                warpbandnodes[band][src][2][1]=str(band+1)
                warpbandnodes[band][dst][2][1]=str(i+1)
                vrttree[wo][bl].insert(key,warpbandnodes[band])

        vrtxml=gdal.SerializeXMLTree(vrttree)

        #Temp in memory VRT file
        self._fn='/vsimem/%s.vrt'%tempfile._RandomNameSequence().next()
        self.__write_vsimem__(self._fn, vrtxml)
        self._dataset=gdal.Open(self._fn)

        if not use_exceptions:gdal.DontUseExceptions()

        Dataset.__init__(self)

    def __del__(self):
        try:Dataset.__del__(self)
        except:pass
        try:gdal.Unlink(self._fn)
        except:pass

class NewDataset(Dataset):
    def __init__(self,filename,outformat='GTIFF',
                 cols=None,rows=None,bands=None,datatype=None,
                 srs='',gt=[],nodata=[],options=[],prototype_ds=None):
        use_exceptions=gdal.GetUseExceptions()
        gdal.UseExceptions()

        if prototype_ds is not None:
            if cols is None:cols=prototype_ds._x_size
            if rows is None:rows=prototype_ds._y_size
            if bands is None:bands=prototype_ds._nbands
            if datatype is None:datatype=prototype_ds._data_type
            if not srs:srs=prototype_ds._srs
            if not gt:gt=prototype_ds._gt
            if nodata==[]:nodata=prototype_ds._nodata
        else:
            if cols is None:raise TypeError('Expected "cols" or "prototype_ds", got None')
            if rows is None:raise TypeError('Expected "rows" or "prototype_ds", got None')
            if bands is None:raise TypeError('Expected "bands" or "prototype_ds", got None')
            if datatype is None:raise TypeError('Expected "datatype" or "prototype_ds", got None')
            if not gt:gt=(0.0, 1.0, 0.0, 0.0, 0.0, 1.0)

        self._filename=filename
        self._driver=gdal.GetDriverByName(outformat)
        self._dataset=self._driver.Create (self._filename,cols,rows,bands,datatype,options)

        if not use_exceptions:gdal.DontUseExceptions()
        self._dataset.SetGeoTransform(gt)
        self._dataset.SetProjection(srs)
        for i,val in enumerate(nodata[:bands]):
            try:self._dataset.GetRasterBand(i+1).SetNoDataValue(val)
            except TypeError:pass
        Dataset.__init__(self)

    def create_copy(self,outpath,outformat='GTIFF',options=[]):
        try:self.FlushCache()
        except:pass
        return Dataset.create_copy(self,outpath,outformat,options)

    def write_data(self, data, x_off=0, y_off=0):
        if data.ndim==2:
            tmpbnd=self._dataset.GetRasterBand(1)
            tmpbnd.WriteArray(data, x_off, y_off)
        else:
            for i in range(data.shape[0]):
                tmpbnd=self._dataset.GetRasterBand(i+1)
                tmpbnd.WriteArray(data[i,:,:], x_off, y_off)

class TemporaryDataset(NewDataset):
    def __init__(self,cols,rows,bands,datatype,srs='',gt=[],nodata=[]):
        use_exceptions=gdal.GetUseExceptions()
        gdal.UseExceptions()

        #print cols,rows,bands,datatype,srs,gt,nodata
        if Env.tempdir == '/vsimem':
            #Test to see if enough memory
            tmpdriver=gdal.GetDriverByName('MEM')
            tmpds=tmpdriver.Create('',cols,rows,bands,datatype)
            tmpds=None
            del tmpds

            self._filedescriptor=-1
            self._filename='/vsimem/%s.tif'%tempfile._RandomNameSequence().next()

        else:
            self._filedescriptor,self._filename=tempfile.mkstemp(suffix='.tif')

        NewDataset.__init__(self,self._filename,'GTIFF',
                            cols,rows,bands,datatype,srs,gt,
                            options=Env.tempoptions)

    save=NewDataset.create_copy #synonym for backwards compatibility

    def __del__(self):
        self._dataset=None
        del self._dataset
        try:os.close(self._filedescriptor)
        except:pass
        try:self._driver.Delete(self._filename)
        except:pass

class WarpedDataset(Dataset):

    def __init__(self,dataset_or_band, wkt_srs, snap_ds=None, snap_cellsize=None):

        use_exceptions=gdal.GetUseExceptions()
        gdal.UseExceptions()

        self._simple_fn='/vsimem/%s.vrt'%tempfile._RandomNameSequence().next()
        self._warped_fn='/vsimem/%s.vrt'%tempfile._RandomNameSequence().next()

        try:                   #Is it a Band
            orig_ds=dataset_or_band.dataset._dataset
        except AttributeError: #No, it's a Dataset
            orig_ds=dataset_or_band._dataset

        try: #Generate a warped VRT
            warped_ds=gdal.AutoCreateWarpedVRT(orig_ds,orig_ds.GetProjection(),wkt_srs, Env.resampling)
            #AutoCreateWarpedVRT doesn't create a vsimem filename and we need one
            warped_ds=gdal.GetDriverByName('VRT').CreateCopy(self._warped_fn,warped_ds)

        except Exception as e:
            raise RuntimeError('Unable to project on the fly. '+e.message)

        #Disable the following check as this will allow us to use a WarpedDataset to
        #resample Datasets and creating an AutoCreateWarpedVRT where input srs==output srs
        #will allways fail the test below...
        #if warped_ds.GetGeoTransform()==orig_ds.GetGeoTransform():
        #    raise RuntimeError('Unable to project on the fly. Make sure all input datasets have projections set.')

        if snap_ds:warped_ds=self._modify_vrt(warped_ds, orig_ds, snap_ds, snap_cellsize)
        self._dataset=self._create_simple_VRT(warped_ds,dataset_or_band)

        if not use_exceptions:gdal.DontUseExceptions()
        Dataset.__init__(self)

    def _create_simple_VRT(self,warped_ds,dataset_or_band):
        ''' Create a simple VRT XML string from a warped VRT (GDALWarpOptions)'''

        vrt=[]
        vrt.append('<VRTDataset rasterXSize="%s" rasterYSize="%s">' % (warped_ds.RasterXSize,warped_ds.RasterYSize))
        vrt.append('<SRS>%s</SRS>' % warped_ds.GetProjection())
        vrt.append('<GeoTransform>%s</GeoTransform>' % ', '.join(map(str,warped_ds.GetGeoTransform())))
        for i,band in enumerate(dataset_or_band._bands):
            rb=warped_ds.GetRasterBand(band+1) #gdal band index start at 1
            nodata=rb.GetNoDataValue()
            vrt.append('  <VRTRasterBand dataType="%s" band="%s">' % (gdal.GetDataTypeName(rb.DataType), i+1))
            vrt.append('    <SimpleSource>')
            vrt.append('      <SourceFilename relativeToVRT="0">%s</SourceFilename>' % (self._warped_fn))
            vrt.append('      <SourceBand>%s</SourceBand>'%(band+1))
            vrt.append('      <SrcRect xOff="0" yOff="0" xSize="%s" ySize="%s" />' % (warped_ds.RasterXSize,warped_ds.RasterYSize))
            vrt.append('      <DstRect xOff="0" yOff="0" xSize="%s" ySize="%s" />' % (warped_ds.RasterXSize,warped_ds.RasterYSize))
            vrt.append('    </SimpleSource>')
            if nodata is not None: # 0 is a valid value
                vrt.append('    <NoDataValue>%s</NoDataValue>' % nodata)
            vrt.append('  </VRTRasterBand>')
        vrt.append('</VRTDataset>')

        vrt='\n'.join(vrt)
        self.__write_vsimem__(self._simple_fn,vrt)
        return gdal.Open(self._simple_fn)

    def _modify_vrt(self, warp_ds, orig_ds, snap_ds, snap_cellsize):
        '''Modify the warped VRT to control pixel size and extent'''

        orig_gt=orig_ds.GetGeoTransform()
        orig_invgt=gdal.InvGeoTransform(orig_gt)[1]
        orig_cols = orig_ds.RasterXSize
        orig_rows = orig_ds.RasterYSize
        orig_ext=geometry.GeoTransformToExtent(orig_gt,orig_cols,orig_rows)
        orig_ext=[orig_ext[1][0],orig_ext[1][1],orig_ext[3][0],orig_ext[3][1]]
        blocksize=orig_ds.GetRasterBand(1).GetBlockSize()

        warp_gt=warp_ds.GetGeoTransform()
        warp_cols = warp_ds.RasterXSize
        warp_rows = warp_ds.RasterYSize
        warp_ext=geometry.GeoTransformToExtent(warp_gt,warp_cols,warp_rows)
        warp_ext=geometry.GeoTransformToExtent(warp_gt,warp_cols,warp_rows)
        warp_ext=[warp_ext[1][0],warp_ext[1][1],warp_ext[3][0],warp_ext[3][1]]

        snap_gt=list(snap_ds._gt)
        if snap_cellsize:
            snap_px,snap_py=snap_cellsize
            snap_gt[1]=snap_px
            snap_gt[5]=-snap_px
            snap_cols = int(snap_ds._gt[1]/snap_px*snap_ds._x_size)
            snap_rows = int(abs(snap_ds._gt[5])/snap_py*snap_ds._y_size)
        else:
            snap_px=snap_gt[1]
            snap_py=abs(snap_gt[5])
            snap_cols = snap_ds._x_size
            snap_rows = snap_ds._y_size
        snap_ext=geometry.GeoTransformToExtent(snap_gt,snap_cols,snap_rows)
        snap_ext=[snap_ext[1][0],snap_ext[1][1],snap_ext[3][0],snap_ext[3][1]]

        new_ext=geometry.SnapExtent(warp_ext, warp_gt, snap_ext, snap_gt)
        new_px=snap_px
        new_py=snap_py
        new_cols = round((new_ext[2]-new_ext[0])/new_px)
        new_rows = round((new_ext[3]-new_ext[1])/new_py)
        new_gt=(new_ext[0],new_px,0,new_ext[3],0,-new_py)
        new_invgt=gdal.InvGeoTransform(new_gt)[1]

        #Read XML from vsimem, requires gdal VSIF*
        vrtxml = self.__read_vsimem__(self._warped_fn)

        #Parse the XML,
        #use gdals built-in XML handling to reduce external dependencies
        vrttree = gdal.ParseXMLString(vrtxml)
        getnodes=self.__getnodes__

        #Set new values
        rasterXSize = getnodes(vrttree, gdal.CXT_Attribute, 'rasterXSize')[0]
        rasterYSize = getnodes(vrttree, gdal.CXT_Attribute, 'rasterYSize')[0]
        GeoTransform = getnodes(vrttree, gdal.CXT_Element, 'GeoTransform')[0]
        BlockXSize = getnodes(vrttree, gdal.CXT_Element, 'BlockXSize')[0]
        BlockYSize = getnodes(vrttree, gdal.CXT_Element, 'BlockYSize')[0]

        wo = getnodes(vrttree, gdal.CXT_Element, 'GDALWarpOptions')[0]
        tr = getnodes(vrttree[wo], gdal.CXT_Element, 'Transformer')[0]
        gi = getnodes(vrttree[wo][tr], gdal.CXT_Element, 'GenImgProjTransformer')[0]
        sgt = getnodes(vrttree[wo][tr][gi], gdal.CXT_Element, 'SrcGeoTransform')[0]
        sigt = getnodes(vrttree[wo][tr][gi], gdal.CXT_Element, 'SrcInvGeoTransform')[0]
        dgt = getnodes(vrttree[wo][tr][gi], gdal.CXT_Element, 'DstGeoTransform')[0]
        digt = getnodes(vrttree[wo][tr][gi], gdal.CXT_Element, 'DstInvGeoTransform')[0]

        vrttree[rasterXSize][2][1]=str(new_cols)
        vrttree[rasterYSize][2][1]=str(new_rows)
        vrttree[GeoTransform][2][1]='%f, %f, %f, %f, %f, %f'%new_gt
        vrttree[BlockXSize][2][1]=str(blocksize[0])
        vrttree[BlockYSize][2][1]=str(blocksize[1])
        vrttree[wo][tr][gi][sgt][2][1]='%f, %f, %f, %f, %f, %f'%orig_gt
        vrttree[wo][tr][gi][sigt][2][1]='%f, %f, %f, %f, %f, %f'%orig_invgt
        vrttree[wo][tr][gi][dgt][2][1]='%f, %f, %f, %f, %f, %f'%new_gt
        vrttree[wo][tr][gi][digt][2][1]='%f, %f, %f, %f, %f, %f'%new_invgt

        #Open new dataset
        vrtxml=gdal.SerializeXMLTree(vrttree)
        self.__write_vsimem__(self._warped_fn, vrtxml)
        return gdal.Open(self._warped_fn)

    def __del__(self):
        try:Dataset.__del__(self)
        except:pass
        try:gdal.Unlink(self._warped_fn)
        except:pass
        try:gdal.Unlink(self._simple_fn)
        except:pass

class ArrayDataset(TemporaryDataset):
    def __init__(self,array,extent=[],srs='',gt=[],nodata=[],prototype_ds=None):
        use_exceptions=gdal.GetUseExceptions()
        gdal.UseExceptions()

        #datatype=gdal_array.NumericTypeCodeToGDALTypeCode(array.dtype.type)
        #Work around numexpr issue #112 - http://code.google.com/p/numexpr/issues/detail?id=112
        #until http://trac.osgeo.org/gdal/ticket/5223 is implemented.
        datatype=gdal_array.NumericTypeCodeToGDALTypeCode(array.view(str(array.dtype)).dtype.type)

        if array.ndim==2:
            rows,cols=array.shape
            bands=1
        else:
            rows,cols,bands=array.shape

        if prototype_ds:
            if not gt:gt=prototype_ds._gt
            if not srs:srs=prototype_ds._srs
            if not nodata:nodata=prototype_ds._nodata

        if extent:
            xmin,ymin,xmax,ymax=extent
            px,py=(xmax-xmin)/cols,(ymax-ymin)/rows
            gt=[xmin,px,0,ymax,0,-py]

        TemporaryDataset.__init__(self,cols,rows,bands,datatype,srs,gt,nodata)
        self.write_data(array,0,0)

class DatasetStack(Dataset):
    ''' Stack of bands from multiple datasets
    '''
    def __init__(self, filepaths, band=0):
        self._datasets=[]#So they don't go out of scope and get GC'd

        #Get a reference dataset so can apply env setting to all datasets
        reference_ds=Dataset(filepaths[0])
        for f in filepaths[1:]:
            d=Dataset(f)
            reference_ds,d=reference_ds.apply_environment(d)

        vrtxml=self.buildvrt(reference_ds, filepaths, band)

        #Temp in memory VRT file
        self._filename='/vsimem/%s.vrt'%tempfile._RandomNameSequence().next()
        self.__write_vsimem__(self._filename,vrtxml)
        self._dataset=gdal.Open(self._filename)

        Dataset.__init__(self)

    def buildvrt(self, reference_ds, filepaths, band):
        ''' Create a simple VRT stack'''
        vrt=[]
        vrt.append('<VRTDataset rasterXSize="%s" rasterYSize="%s">' % (reference_ds.RasterXSize,reference_ds.RasterYSize))
        vrt.append('  <SRS>%s</SRS>' % reference_ds.GetProjection())
        vrt.append('  <GeoTransform>%s</GeoTransform>' % ', '.join(map(str,reference_ds.GetGeoTransform())))

        for f in filepaths:
            d=Dataset(f)
            reference_ds,d=reference_ds.apply_environment(d)
            self._datasets.append(d)

            rb=d.GetRasterBand(band+1) #gdal band index start at 1
            nodata=rb.GetNoDataValue()
            path=d.GetDescription()
            rel=not os.path.isabs(path)
            vrt.append('  <VRTRasterBand dataType="%s" band="%s">' % (gdal.GetDataTypeName(rb.DataType), band+1))
            vrt.append('    <SimpleSource>')
            vrt.append('      <SourceFilename relativeToVRT="%s">%s</SourceFilename>' % (int(rel),path))
            vrt.append('      <SourceBand>%s</SourceBand>'%(band+1))
            vrt.append('      <SrcRect xOff="0" yOff="0" xSize="%s" ySize="%s" />' % (d.RasterXSize,d.RasterYSize))
            vrt.append('      <DstRect xOff="0" yOff="0" xSize="%s" ySize="%s" />' % (d.RasterXSize,d.RasterYSize))
            vrt.append('    </SimpleSource>')
            if nodata is not None: # 0 is a valid value
                vrt.append('    <NoDataValue>%s</NoDataValue>' % nodata)
            vrt.append('  </VRTRasterBand>')
        vrt.append('</VRTDataset>')

        vrt='\n'.join(vrt)
        return vrt

    def __del__(self):
        self._dataset=None
        del self._dataset
        try:gdal.Unlink(self._filename)
        except:pass

if __name__=='__main__':
    #Examples
    gdal.UseExceptions()

    Env.extent='MAXOF'
    Env.resampling='CUBIC'
    Env.overwrite=True
    Env.reproject=True
    Env.nodata=True

    ds1=Dataset('../testdata/landsat_utm50.tif')#Projected coordinate system
    ds2=Dataset('../testdata/landsat_geo.tif')  #Geographic coordinate system

    #red=ds1[2].astype(np.float32) #You can use numpy type conversion (is slower)
    red=Float32(ds1[2]) #or use one of the provided type conversion functions (quicker as they use VRT's)
    nir=ds2[3]

    ndvi=(nir-red)/(nir+red)

    #Or in one go
    #ndvi=(ds2[3]-Float32(ds1[2])/(ds2[3]+Float32(ds1[2]))
    ndvi=ndvi.save(r'../testdata/ndvi1.tif')

    #If you want to speed things up... use numexpr!
    #but there are a few limitations...
    import numexpr as ne

    #Must not be tiled for numexpr
    Env.tiled=False

    #No subscripting or methods in the expression
    #red=ds1[2].astype(np.float32)
    red=Float32(ds1[2])
    nir=ds2[3] #Some Int*/UInt* datasets cause segfaults, workaround is cast to Float32

    #Must be same coordinate systems and dimensions
    #The check_extent method will reproject and clip if required
    #This is done using virtual rasters (VRT) so is very quick
    nir,red=nir.check_extent(red)

    expr='(nir-red)/(nir+red)'
    ndvi=ne.evaluate(expr)

    #evaluate returns an ndarray not a Dataset
    #So need to write to a Temporary ArrayDataset
    ndvi=ArrayDataset(ndvi,prototype_ds=nir)
    ndvi=ndvi.save(r'../testdata/ndvi2.tif',options=['compress=LZW','TILED=YES'])

    ##Get the raw numpy array data
    #for block in red.ReadBlocksAsArray():
    #    print block.x_off,block.y_off,block.data.shape
    #
    #rawdata=red.ReadAsArray()
    #print rawdata.shape


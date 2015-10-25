# -*- coding: UTF-8 -*-
'''
Name: environment.py
Purpose: Environment and progress classes

Author: Luke Pinner
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
__all__ = [ "Env", "Progress"]

import sys,os,tempfile
import numpy as np
from osgeo import gdal, osr

# Processing environment
class Env(object):
    ''' Class for setting various environment properties
        Notes: - see __init__.py
    '''

    #Properties
    enable_numexpr=False
    nodata=False
    ntiles=1
    overwrite=False
    progress=False
    reproject=False
    tiled=True
    tempoptions=['BIGTIFF=IF_SAFER']

    @property
    def cellsize(self):
        try:return self._cellsize
        except AttributeError:
            self._cellsize='DEFAULT'
            return self._cellsize

    @cellsize.setter
    def cellsize(self, value):
        try:
            if value.upper() in ['DEFAULT','MINOF','MAXOF']:
                self._cellsize = value.upper()
                return
        except:pass
        try:
            self._cellsize=[float(n) for n in value] #Is it an iterable
            return
        except:pass
        try:
            self._cellsize=[float(value),float(value)] #Is it a single value
            return
        except:pass
        raise AttributeError('%s not one of "DEFAULT"|"MINOF"|"MAXOF"|[xsize,ysize]|xysize'%repr(value))

    @property
    def extent(self):
        try:return self._extent
        except AttributeError:
            self._extent='MINOF'
            return self._extent

    @extent.setter
    def extent(self, value):
        try:
            if value.upper() in ['MINOF','MAXOF','INTERSECT','UNION']:
                self._extent = value.upper()
                return
        except:pass
        try:
            xmin,ymin,xmax,ymax=[float(i) for i in value]
            self._extent = [xmin,ymin,xmax,ymax]
            return
        except:pass
        raise AttributeError('%s not one of "MINOF"|"INTERSECT"|"MAXOF"|"UNION"|[xmin,ymin,xmax,ymax]'%repr(value))

    @property
    def resampling(self):
        try:return self._resampling
        except AttributeError:
            self._resampling=gdal.GRA_NearestNeighbour
            return self._resampling

    @resampling.setter
    def resampling(self, value):
        lut={ 'BILINEAR':gdal.GRA_Bilinear,
              'CUBIC':gdal.GRA_Cubic,
              'CUBICSPLINE':gdal.GRA_CubicSpline,
              'LANCZOS':gdal.GRA_Lanczos,
              'NEAREST':gdal.GRA_NearestNeighbour}

        if int(gdal.VersionInfo("VERSION_NUM"))>=1100000:
            lut['AVERAGE']=gdal.GRA_Average
            lut['MODE']=gdal.GRA_Mode
            
        try:
            value=value.upper()
            self._resampling=lut[value]
            return
        except:pass
        try:
            index=lut.values().index(value)
            self._resampling=value
            return
        except:pass
        raise AttributeError('%s not one of "AVERAGE"|"BILINEAR"|"CUBIC"|"CUBICSPLINE"|"LANCZOS"|"MODE"|"NEAREST"|gdal.GRA_*'%repr(value))

    @property
    def snap(self):
        try:return self._snap
        except AttributeError:
            self._snap=None
            return self._snap

    @snap.setter
    def snap(self, value):
        try:a=value._gt #Instead of checking isinstance(RasterLike,value) to avoid cyclic import
        except:raise RuntimeError('%s is not a Dataset/Band object'%value)
        self._snap=value

    @property
    def srs(self):
        try:return self._srs
        except AttributeError:
            self._srs=None
            return self._srs

    @srs.setter
    def srs(self, value):
        try:
            #EPSG?
            epsg=int(value)
            ret=osr.SpatialReference()
            if ret.ImportFromEPSG(epsg)>0:raise Exception
        except ValueError:
            #WKT
            ret=osr.SpatialReference(value)
        except TypeError:
            #SpatialReference
            ret=value
        except Exception:
            #It's invalid
            raise RuntimeError('not a valid SpatialReference: %s'%repr(value))

        try:
            #Was the EPSG/WKT/SRS valid?
            self._srs=ret.Clone()
            self.reproject=True
        except TypeError:
            #It's invalid
            raise RuntimeError('not a valid SpatialReference: %s'%repr(value))

    @property
    def tempdir(self):
        try:return self._tempdir
        except AttributeError:
            self._tempdir=tempfile.tempdir
            return self._tempdir
        #return tempfile.tempdir

    @tempdir.setter
    def tempdir(self, value):
        if value.lower()=='/vsimem':
            self._tempdir=value
        elif not os.path.isdir(value):
            raise RuntimeError('%s is not a directory'%value)
        else:
            tempfile.tempdir=value
            self._tempdir=value

Env=Env()

class Progress(object):
    def __init__(self,operations=0):
        self.steps = 1 #n. steps per operation
        self.operations=float(operations)
        self.progress=0
        self.enabled=operations>0
        if self.enabled:
            gdal.TermProgress_nocb(0)

    def reset(self,operations=0):
        self.__init__(operations)

    def update_progress(self):
        if self.enabled:
            self.progress+=1.0
            gdal.TermProgress_nocb(self.progress/(self.operations*self.steps))

Env.progress=Progress()


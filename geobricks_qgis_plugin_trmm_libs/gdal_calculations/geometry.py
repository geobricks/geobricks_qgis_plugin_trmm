# -*- coding: utf-8 -*-
# Copyright (c) 2013 Australian Government, Department of Sustainability,
# Environment, Water, Population and Communities.
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

''' Geometry helper functions '''

import os,math,warnings,tempfile,re
from osgeo import gdal
from osgeo import gdalconst
from osgeo import osr
from osgeo import ogr

def ApplyGeoTransform(inx,iny,gt):
    ''' Apply a geotransform
        @param  inx:       Input x coordinate (double)
        @param  iny:       Input y coordinate (double)
        @param  gt:        Input geotransform (six doubles)

        @return: outx,outy Output coordinates (two doubles)
    '''
    outx = gt[0] + inx*gt[1] + iny*gt[2]
    outy = gt[3] + inx*gt[4] + iny*gt[5]
    return (outx,outy)

def CellSize(gt):
    ''' Get cell size from a geotransform

        @type gt:  C{tuple/list}
        @param gt: geotransform
        @rtype:    C{(float,float)}
        @return:   (x,y) cell size
    '''
    cellx=round(math.hypot(gt[1],gt[4]),7)
    celly=round(math.hypot(gt[2],gt[5]),7)
    return (cellx,celly)

def ExtentToGCPs(ext,cols,rows):
    ''' Form a gcp list from the 4 corners.

        This function is meant to be used to convert an extent
        to gcp's for use in the gdal.GCPsToGeoTransform function.

        @type ext:   C{tuple/list}
        @param ext:  Extent, must be in order: [[ulx,uly],[urx,ury],[lrx,lry],[llx,lly]]
        @type cols: C{int}
        @param cols: Number of columns in the dataset
        @type rows: C{int}
        @param rows: Number of rows in the dataset
        @rtype:    C{[gcp,...,gcp]}
        @return:   List of GCP objects
    '''
    gcp_list=[]
    parr=[0,cols]
    larr=[rows,0]
    id=0
    if len(ext)==5: #Assume ext[0]==ext[4]
        ext=ext[:-1]
    if len(ext)!=4:
        raise ValueError, 'Extent must be a tuple/list with 4 elements, each an XY pair'

    for px in parr:
        for py in larr:
            cgcp=gdal.GCP()
            cgcp.Id=str(id)
            cgcp.GCPX=ext[id][0]
            cgcp.GCPY=ext[id][1]
            cgcp.GCPZ=0.0
            cgcp.GCPPixel=px
            cgcp.GCPLine=py
            id+=1
            gcp_list.append(cgcp)
        larr.reverse()

    return gcp_list

def GeoTransformToExtent(gt,cols,rows):
    ''' Form a extent list from a geotransform using the 4 corners.

        @type gt:   C{tuple/list}
        @param gt: geotransform to convert to extent
        @type cols:   C{int}
        @param cols: number of columns in the dataset
        @type rows:   C{int}
        @param rows: number of rows in the dataset
        @rtype:    C{[[float,float],...,[float,float]]}
        @return:   List of x,y coordinate pairs
    '''
    ###############################################################################
    # This code is modified from the GeoTransformToGCPs function
    # in the OpenEV module vrtutils.py
    ###############################################################################
    # $Id: vrtutils.py,v 1.17 2005/07/07 21:36:06 gmwalter Exp $
    #
    # Project:  OpenEV
    # Purpose:  Utilities for creating vrt files.
    # Author:   Gillian Walter, gwal...@atlsci.com
    #
    ###############################################################################
    # Copyright (c) 2000, Atlantis Scientific Inc. (www.atlsci.com)
    #
    # This library is free software; you can redistribute it and/or
    # modify it under the terms of the GNU Library General Public
    # License as published by the Free Software Foundation; either
    # version 2 of the License, or (at your option) any later version.
    #
    # This library is distributed in the hope that it will be useful,
    # but WITHOUT ANY WARRANTY; without even the implied warranty of
    # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    # Library General Public License for more details.
    #
    # You should have received a copy of the GNU Library General Public
    # License along with this library; if not, write to the
    # Free Software Foundation, Inc., 59 Temple Place - Suite 330,
    # Boston, MA 02111-1307, USA.
    ###############################################################################

    extent=[]
    parr=[0,cols]
    larr=[0,rows]
    id=0
    for px in parr:
        for py in larr:
            x=gt[0]+(px*gt[1])+(py*gt[2])
            y=gt[3]+(px*gt[4])+(py*gt[5])
            extent.append((x,y))
        larr.reverse()
    return extent

def GeoTransformToGCPs(gt,cols,rows):
    ''' Form a gcp list from a geotransform using the 4 corners.

        This function is meant to be used to convert a geotransform
        to gcp's so that the geocoded information can be reprojected.

        @type gt:   C{tuple/list}
        @param gt: geotransform to convert to gcps
        @type cols:   C{int}
        @param cols: number of columns in the dataset
        @type rows:   C{int}
        @param rows: number of rows in the dataset
        @rtype:    C{[gcp,...,gcp]}
        @return:   List of GCP objects
    '''
    ###############################################################################
    # This code is modified from the GeoTransformToGCPs function
    # in the OpenEV module vrtutils.py
    ###############################################################################
    # $Id: vrtutils.py,v 1.17 2005/07/07 21:36:06 gmwalter Exp $
    #
    # Project:  OpenEV
    # Purpose:  Utilities for creating vrt files.
    # Author:   Gillian Walter, gwal...@atlsci.com
    #
    ###############################################################################
    # Copyright (c) 2000, Atlantis Scientific Inc. (www.atlsci.com)
    #
    # This library is free software; you can redistribute it and/or
    # modify it under the terms of the GNU Library General Public
    # License as published by the Free Software Foundation; either
    # version 2 of the License, or (at your option) any later version.
    #
    # This library is distributed in the hope that it will be useful,
    # but WITHOUT ANY WARRANTY; without even the implied warranty of
    # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    # Library General Public License for more details.
    #
    # You should have received a copy of the GNU Library General Public
    # License along with this library; if not, write to the
    # Free Software Foundation, Inc., 59 Temple Place - Suite 330,
    # Boston, MA 02111-1307, USA.
    ###############################################################################

    gcp_list=[]
    parr=[0,cols]
    larr=[0,rows]
    id=0
    for px in parr:
        for py in larr:
            cgcp=gdal.GCP()
            cgcp.Id=str(id)
            cgcp.GCPX=gt[0]+(px*gt[1])+(py*gt[2])
            cgcp.GCPY=gt[3]+(px*gt[4])+(py*gt[5])
            cgcp.GCPZ=0.0
            cgcp.GCPPixel=px
            cgcp.GCPLine=py
            id+=1
            gcp_list.append(cgcp)
        larr.reverse()
    return gcp_list

def GeomFromExtent(ext,srs=None,srs_wkt=None):
    ''' Get and OGR geometry object from a extent list

        @type ext:  C{tuple/list}
        @param ext: extent coordinates
        @type srs:  C{str}
        @param srs: SRS WKT string
        @rtype:     C{ogr.Geometry}
        @return:    Geometry object
    '''
    if type(ext[0]) is list or type(ext[0]) is tuple: #is it a list of xy pairs
        if ext[0] != ext[-1]:ext.append(ext[0])
        wkt = 'POLYGON ((%s))' % ','.join(map(' '.join, [map(str, i) for i in ext]))
    else: #it's a list of xy values
        xmin,ymin,xmax,ymax=ext
        template = 'POLYGON ((%(minx)f %(miny)f, %(minx)f %(maxy)f, %(maxx)f %(maxy)f, %(maxx)f %(miny)f, %(minx)f %(miny)f))'
        r1 = {'minx': xmin, 'miny': ymin, 'maxx':xmax, 'maxy':ymax}
        wkt = template % r1
    if srs_wkt is not None:srs=osr.SpatialReference(wkt=srs_wkt)
    geom = ogr.CreateGeometryFromWkt(wkt,srs)
    return geom

def InvGeoTransform(gt_in):
    '''
     ************************************************************************
     *                        InvGeoTransform(gt_in)
     ************************************************************************

     **
     * Invert Geotransform.
     *
     * This function will invert a standard 3x2 set of GeoTransform coefficients.
     *
     * @param  gt_in  Input geotransform (six doubles - unaltered).
     * @return gt_out Output geotransform (six doubles - updated) on success,
     *                None if the equation is uninvertable.
    '''
    #    ******************************************************************************
    #    * This code ported from GDALInvGeoTransform() in gdaltransformer.cpp
    #    * as it isn't exposed in the python SWIG bindings until GDAL 1.7
    #    * copyright & permission notices included below as per conditions.
    #
    #    ******************************************************************************
    #    * $Id: gdaltransformer.cpp 15024 2008-07-24 19:25:06Z rouault $
    #    *
    #    * Project:  Mapinfo Image Warper
    #    * Purpose:  Implementation of one or more GDALTrasformerFunc types, including
    #    *           the GenImgProj (general image reprojector) transformer.
    #    * Author:   Frank Warmerdam, warmerdam@pobox.com
    #    *
    #    ******************************************************************************
    #    * Copyright (c) 2002, i3 - information integration and imaging
    #    *                          Fort Collin, CO
    #    *
    #    * Permission is hereby granted, free of charge, to any person obtaining a
    #    * copy of this software and associated documentation files (the "Software"),
    #    * to deal in the Software without restriction, including without limitation
    #    * the rights to use, copy, modify, merge, publish, distribute, sublicense,
    #    * and/or sell copies of the Software, and to permit persons to whom the
    #    * Software is furnished to do so, subject to the following conditions:
    #    *
    #    * The above copyright notice and this permission notice shall be included
    #    * in all copies or substantial portions of the Software.
    #    *
    #    * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    #    * OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    #    * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    #    * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    #    * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    #    * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    #    * DEALINGS IN THE SOFTWARE.
    #    ****************************************************************************

    # we assume a 3rd row that is [1 0 0]

    # Compute determinate
    det = gt_in[1] * gt_in[5] - gt_in[2] * gt_in[4]

    if( abs(det) < 0.000000000000001 ):
        return

    inv_det = 1.0 / det

    # compute adjoint, and divide by determinate
    gt_out = [0,0,0,0,0,0]
    gt_out[1] =  gt_in[5] * inv_det
    gt_out[4] = -gt_in[4] * inv_det

    gt_out[2] = -gt_in[2] * inv_det
    gt_out[5] =  gt_in[1] * inv_det

    gt_out[0] = ( gt_in[2] * gt_in[3] - gt_in[0] * gt_in[5]) * inv_det
    gt_out[3] = (-gt_in[1] * gt_in[3] + gt_in[0] * gt_in[4]) * inv_det

    return gt_out

def MapToPixel(mx,my,gt):
    ''' Convert map to pixel coordinates
        @param  mx:    Input map x coordinate (double)
        @param  my:    Input map y coordinate (double)
        @param  gt:    Input geotransform (six doubles)
        @return: px,py Output coordinates (two ints)

        @change: changed int(p[x,y]+0.5) to int(p[x,y]) as per http://lists.osgeo.org/pipermail/gdal-dev/2010-June/024956.html
        @change: return floats
        @note:   0,0 is UL corner of UL pixel, 0.5,0.5 is centre of UL pixel
    '''
    if gt[2]+gt[4]==0: #Simple calc, no inversion required
        px = (mx - gt[0]) / gt[1]
        py = (my - gt[3]) / gt[5]
    else:
        px,py=ApplyGeoTransform(mx,my,InvGeoTransform(gt))
    #return int(px),int(py)
    return px,py

def MaxExtent(ext1,ext2):
    xmin=min(ext1[0],ext2[0])
    ymin=min(ext1[1],ext2[1])
    xmax=max(ext1[2],ext2[2])
    ymax=max(ext1[3],ext2[3])

    return [xmin,ymin,xmax,ymax]

def MinExtent(ext1,ext2):
    xmin=max(ext1[0],ext2[0])
    ymin=max(ext1[1],ext2[1])
    xmax=min(ext1[2],ext2[2])
    ymax=min(ext1[3],ext2[3])

    return [xmin,ymin,xmax,ymax]

def PixelToMap(px,py,gt):
    ''' Convert pixel to map coordinates
        @param  px:    Input pixel x coordinate (double)
        @param  py:    Input pixel y coordinate (double)
        @param  gt:    Input geotransform (six doubles)
        @return: mx,my Output coordinates (two doubles)

        @note:   0,0 is UL corner of UL pixel, 0.5,0.5 is centre of UL pixel
    '''
    mx,my=ApplyGeoTransform(px,py,gt)
    return mx,my

def ReprojectGeom(geom,src_srs,tgt_srs):
    ''' Reproject a geometry object.

        @type geom:     C{ogr.Geometry}
        @param geom:    OGR geometry object
        @type src_srs:  C{osr.SpatialReference}
        @param src_srs: OSR SpatialReference object
        @type tgt_srs:  C{osr.SpatialReference}
        @param tgt_srs: OSR SpatialReference object
        @rtype:         C{ogr.Geometry}
        @return:        OGRGeometry object
    '''
    gdal.ErrorReset()
    gdal.PushErrorHandler( 'CPLQuietErrorHandler' )
    geom.AssignSpatialReference(src_srs)
    geom.TransformTo(tgt_srs)
    err = gdal.GetLastErrorMsg()
    if err:warnings.warn(err.replace('\n',' '))
    gdal.PopErrorHandler()
    gdal.ErrorReset()
    return geom

def Rotation(gt):
    ''' Get rotation angle from a geotransform
        @type gt: C{tuple/list}
        @param gt: geotransform
        @rtype: C{float}
        @return: rotation angle
    '''
    try:return math.degrees(math.tanh(gt[2]/gt[5]))
    except:return 0

def SceneCentre(gt,cols,rows):
    ''' Get scene centre from a geotransform.

        @type gt: C{tuple/list}
        @param gt: geotransform
        @type cols: C{int}
        @param cols: Number of columns in the dataset
        @type rows: C{int}
        @param rows: Number of rows in the dataset
        @rtype:    C{(float,float)}
        @return:   Scene centre coordinates
    '''
    px = cols/2
    py = rows/2
    x=gt[0]+(px*gt[1])+(py*gt[2])
    y=gt[3]+(px*gt[4])+(py*gt[5])
    return x,y

def SnapExtent(in_ext,in_gt,snap_ext,snap_gt):
    '''Snap in_ext to snap_ext

        @type in_ext:  C{tuple/list}
        @param in_ext: extent coordinates
        @type in_gt:   C{tuple/list}
        @param in_gt: geotransform
        @type snap_ext:  C{tuple/list}
        @param snap_ext: extent coordinates
        @type snap_gt:   C{tuple/list}
        @param snap_gt: geotransform
        @rtype:    C{[[float,float],...,[float,float]]}
        @return:   List of x,y coordinate pairs
    '''

    #Input grid dimensions
    ixmin,iymin,ixmax,iymax = in_ext
    ix,iy=in_gt[1],abs(in_gt[5])
    icols=round((ixmax-ixmin)/ix)
    irows=round((iymax-iymin)/iy)

    #Snap grid dimensions
    sxmin,symin,sxmax,symax = snap_ext
    sx,sy=snap_gt[1],abs(snap_gt[5])
    scols=round((sxmax-sxmin)/sx)
    srows=round((symax-symin)/sy)

    #----------------------------------------------------
    #Shift in_ext
    #----------------------------------------------------
    #how many pixels difference?
    xmindif = (sxmin-ixmin) / ix
    ymindif = (symin-iymin) / iy

    #how far (part pixel) do we need to shift it?
    xminmod = (((((xmindif % 1) * ix) / sx) % 1) * sx) / ix
    yminmod = (((((ymindif % 1) * iy) / sy) % 1) * sy) / iy

    #shift to the nearest pixel
    if abs(xminmod) >= 0.5:   #shift to the nearest pixel
        if abs(xminmod) == xminmod:xminmod =  0-(1-xminmod)
        else: xminmod = 1+xminmod
    if abs(yminmod) >= 0.5:   #shift to the nearest pixel
        if abs(yminmod) == yminmod:yminmod =  0-(1-yminmod)
        else: yminmod = 1+yminmod

    #Output origin
    oxmin=ixmin+xminmod*ix
    oymin=iymin+yminmod*iy
    oxmax=oxmin+icols*ix
    oymax=oymin+irows*iy

    return [oxmin,oymin,oxmax,oymax]

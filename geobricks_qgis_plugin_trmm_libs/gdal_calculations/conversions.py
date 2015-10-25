# -*- coding: UTF-8 -*-
'''
Name: conversions.py
Purpose: Datatype conversion functions

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
__all__ = [ "Byte","UInt16","Int16",
            "UInt32","Int32",
            "Float32","Float64"]

from osgeo import gdal
from gdal_dataset import ConvertedDataset

# Type conversion helper functions
def Byte(dataset_or_band):
    return ConvertedDataset(dataset_or_band, gdal.GDT_Byte)
def UInt16(dataset_or_band):
    return ConvertedDataset(dataset_or_band, gdal.GDT_UInt16)
def Int16(dataset_or_band):
    return ConvertedDataset(dataset_or_band, gdal.GDT_Int16)
def UInt32(dataset_or_band):
    return ConvertedDataset(dataset_or_band, gdal.GDT_UInt32)
def Int32(dataset_or_band):
    return ConvertedDataset(dataset_or_band, gdal.GDT_Int32)
def Float32(dataset_or_band):
    return ConvertedDataset(dataset_or_band, gdal.GDT_Float32)
def Float64(dataset_or_band):
    return ConvertedDataset(dataset_or_band, gdal.GDT_Float64)


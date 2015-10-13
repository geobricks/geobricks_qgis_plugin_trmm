# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GeobricksTRMM
                                 A QGIS plugin
 Download TRMM daily data.
                             -------------------
        begin                : 2015-10-06
        copyright            : (C) 2015 by Geobricks
        email                : info@geobricks.org
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load GeobricksTRMM class from file GeobricksTRMM.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .geobricks_trmm_qgis import GeobricksTRMM
    return GeobricksTRMM(iface)

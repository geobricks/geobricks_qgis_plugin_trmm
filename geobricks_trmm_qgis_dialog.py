# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GeobricksTRMMDialog
                                 A QGIS plugin
 Download TRMM daily data.
                             -------------------
        begin                : 2015-10-06
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Geobricks
        email                : info@geobricks.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from PyQt4 import QtGui, uic
from qgis.gui import QgsMessageBar
from PyQt4.QtGui import QSizePolicy
from PyQt4.QtGui import QGridLayout
from PyQt4.QtGui import QDialogButtonBox

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'geobricks_trmm_qgis_dialog_base.ui'))


class GeobricksTRMMDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(GeobricksTRMMDialog, self).__init__(parent)
        self.setupUi(self)

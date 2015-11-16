# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GeobricksTRMM
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
import os.path
from geobricks_qgis_plugin_trmm_libs.gdal_calculations import Dataset
from geobricks_qgis_plugin_trmm_libs.gdal_calculations import Env
from geobricks_qgis_plugin_trmm_libs.geobricks_trmm.core.trmm_core import date_range
from geobricks_qgis_plugin_trmm_libs.geobricks_trmm.core.trmm_core import list_layers
from geobricks_qgis_plugin_trmm_libs.geobricks_trmm.core.trmm_core import open_browser_registration
from PyQt4.QtCore import QSettings
from PyQt4.QtCore import QTranslator
from PyQt4.QtCore import qVersion
from PyQt4.QtCore import QCoreApplication
from PyQt4.QtCore import QDate
from PyQt4.QtGui import QAction
from PyQt4.QtGui import QIcon
from PyQt4.QtGui import QFileDialog
from PyQt4.QtGui import QMessageBox
from PyQt4.QtGui import QColor
from PyQt4.QtGui import QFrame
from PyQt4.QtGui import QCheckBox
from PyQt4.QtGui import QProgressBar
from qgis.gui import QgsMessageBar
from PyQt4.QtGui import QSizePolicy
from qgis.core import QgsColorRampShader
from qgis.core import QgsRasterShader
from qgis.core import QgsSingleBandPseudoColorRenderer
from geobricks_trmm_qgis_dialog import GeobricksTRMMDialog
import os.path
from PyQt4.QtGui import QVBoxLayout
from PyQt4.QtGui import QHBoxLayout
from PyQt4.QtGui import QWidget
from PyQt4.QtGui import QLabel
from PyQt4.QtGui import QLineEdit
from PyQt4.QtGui import QPalette
from PyQt4.QtGui import QComboBox
from PyQt4.QtGui import QCalendarWidget
from PyQt4.QtGui import QPushButton
from qgis.core import QgsMessageLog


class GeobricksTRMM:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'geobricks_trmm_qgis_{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
        self.layout = QVBoxLayout()
        self.username = QLineEdit()
        self.username.setPlaceholderText(self.tr('e.g. name.surname@example.com'))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText(self.tr('e.g. name.surname@example.com'))
        self.download_folder = QLineEdit()
        try:
            if self.last_download_folder is not None:
                self.download_folder.setText(self.last_download_folder)
        except:
            self.last_download_folder = None
        self.frequency = QComboBox()
        self.frequency.addItem(self.tr('Daily Sum'), 'SUM')
        self.frequency.addItem(self.tr('Daily Average'), 'AVG')
        self.frequency.addItem(self.tr('None'), 'NONE')
        self.from_date = QCalendarWidget()
        self.to_date = QCalendarWidget()
        self.bar = QgsMessageBar()
        self.lbl_0 = QLabel('<b>' + self.tr('Username') + '</b>')
        self.lbl_1 = QLabel('<b>' + self.tr('Password') + '</b>')
        self.lbl_2 = QLabel('<b>' + self.tr('Aggregation') + '</b>')
        self.from_date_label = QLabel('<b>' + self.tr('From Date') + '</b>: ' + QDate(2015, 7, 31).toString('MMMM d, yyyy'))
        self.to_date_label = QLabel('<b>' + self.tr('To Date') + '</b>: ' + QDate(2015, 7, 31).toString('MMMM d, yyyy'))
        self.lbl_5 = QLabel('<b>' + self.tr('Download Folder') + '</b>')
        self.lbl_6 = QLabel('<i style="color: blue;">' + self.tr('Create an account') + '</i>')
        self.lbl_7 = QLabel('<b>' + self.tr('Data availability') + '</b>: ' + self.tr('from January 1st 1998 to July 31st 2015'))
        self.palette = QPalette()
        self.from_date_widget = QWidget()
        self.from_date_widget_layout = QVBoxLayout()
        self.dates_widget = QWidget()
        self.dates_widget_layout = QHBoxLayout()
        self.username_widget = QWidget()
        self.username_layout = QVBoxLayout()
        self.password_widget = QWidget()
        self.password_layout = QVBoxLayout()
        self.progressBar = QProgressBar()
        self.progress_label = QLabel('<b>' + self.tr('Progress') + '</b>')
        self.login_widget = QWidget()
        self.login_layout = QHBoxLayout()
        self.download_folder_widget = QWidget()
        self.download_folder_layout = QHBoxLayout()
        self.download_folder_button = QPushButton(self.tr('...'))
        self.download_button = QPushButton(self.tr('Start Download'))
        self.close_button = QPushButton(self.tr('Close Window'))
        self.add_to_canvas = QCheckBox(self.tr('Add output layer to canvas'))
        self.add_to_canvas.setChecked(True)
        self.to_date_widget = QWidget()
        self.to_date_widget_layout = QVBoxLayout()
        self.spacing = 16

        self.dlg = GeobricksTRMMDialog()
        self.actions = []
        self.menu = self.tr('Download Data')
        self.toolbar = self.iface.addToolBar(self.tr('TRMM Data Downloader'))
        self.toolbar.setObjectName('TRMMDataDownloader')
        self.is_rendered = False

    def run(self):

        # Build UI
        self.build_ui()

    def build_ui(self):

        # Link label
        self.lbl_6.mousePressEvent = open_browser_registration
        self.palette.setColor(QPalette.Foreground, QColor('blue'))
        self.lbl_6.setPalette(self.palette)

        # Calendars
        self.from_date.setMinimumDate(QDate(1998, 1, 1))
        self.from_date.setMaximumDate(QDate(2015, 7, 31))
        self.to_date.setMinimumDate(QDate(1998, 1, 1))
        self.to_date.setMaximumDate(QDate(2015, 7, 31))

        # Message bar
        self.bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.layout.addWidget(self.bar)

        # From date panel
        self.from_date_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.from_date_widget_layout.setSpacing(self.spacing)
        self.from_date_widget.setLayout(self.from_date_widget_layout)
        self.from_date_widget_layout.addWidget(self.from_date_label)
        self.from_date_widget_layout.addWidget(self.from_date)
        self.from_date.clicked[QDate].connect(self.update_from_label)

        # To date panel
        self.to_date_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.to_date_widget_layout.setSpacing(self.spacing)
        self.to_date_widget.setLayout(self.to_date_widget_layout)
        self.to_date_widget_layout.addWidget(self.to_date_label)
        self.to_date_widget_layout.addWidget(self.to_date)
        self.to_date.clicked[QDate].connect(self.update_to_label)

        # Dates panel
        self.dates_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.dates_widget_layout.setSpacing(self.spacing)
        self.dates_widget.setLayout(self.dates_widget_layout)
        self.dates_widget_layout.addWidget(self.from_date_widget)
        self.dates_widget_layout.addWidget(self.to_date_widget)

        # Username panel
        self.username_layout.setContentsMargins(0, 0, 0, 0)
        self.username_layout.setSpacing(self.spacing)
        self.username_widget.setLayout(self.username_layout)
        self.username_layout.addWidget(self.lbl_0)
        self.username_layout.addWidget(self.username)

        # Password panel
        self.password_layout.setContentsMargins(0, 0, 0, 0)
        self.password_layout.setSpacing(self.spacing)
        self.password_widget.setLayout(self.password_layout)
        self.password_layout.addWidget(self.lbl_1)
        self.password_layout.addWidget(self.password)

        # Login panel
        self.login_layout.setContentsMargins(0, 0, 0, 0)
        self.login_layout.setSpacing(self.spacing)
        self.login_widget.setLayout(self.login_layout)
        self.login_layout.addWidget(self.username_widget)
        self.login_layout.addWidget(self.password_widget)

        # Download folder panel
        self.download_folder_layout.setContentsMargins(0, 0, 0, 0)
        self.download_folder_layout.setSpacing(0)
        self.download_folder_widget.setLayout(self.download_folder_layout)
        self.download_folder_button.clicked.connect(self.select_output_file)
        self.download_folder_layout.addWidget(self.download_folder)
        self.download_folder_layout.addWidget(self.download_folder_button)

        # Download button
        self.download_button.clicked.connect(self.start)

        # Close button
        self.close_button.clicked.connect(self.close)

        # Add widgets to layout
        self.layout.addWidget(self.login_widget)
        self.layout.addWidget(self.lbl_6)
        self.layout.addWidget(self.lbl_2)
        self.layout.addWidget(self.frequency)
        self.layout.addWidget(self.dates_widget)
        self.layout.addWidget(self.lbl_5)
        self.layout.addWidget(self.download_folder_widget)
        self.layout.addWidget(self.add_to_canvas)
        self.layout.addWidget(self.download_button)
        self.layout.addWidget(self.progress_label)
        self.layout.addWidget(self.progressBar)
        self.layout.addWidget(self.close_button)

        # Set layout
        self.dlg.setLayout(self.layout)

        # Show dialog
        self.dlg.show()

    def update_from_label(self, date):
        self.from_date_label.setText('<b>' + self.tr('From Date') + '</b>: ' + date.toString('MMMM d, yyyy'))

    def update_to_label(self, date):
        self.to_date_label.setText('<b>' + self.tr('To Date') + '</b>: ' + date.toString('MMMM d, yyyy'))

    def select_output_file(self):
        filename = QFileDialog.getExistingDirectory(self.dlg, self.tr('Select Folder'))
        self.last_download_folder = filename
        self.download_folder.setText(self.last_download_folder)

    def tr(self, message):
        return QCoreApplication.translate('geobricks_trmm_qgis', message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = ':/plugins/geobricks_qgis_plugin_trmm/icon.png'
        self.add_action(
            icon_path,
            text=self.tr('TRMM Data Downloader'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                'TRMMDataDownloader',
                action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def close(self):
        self.dlg.close()

    def start(self):
        p = self.collect_parameters()
        if p is not None:
            self.progressBar.setMaximum(100)
            self.progressBar.setValue(0)
            i = 0
            try:
                range = date_range(p['from_date'], p['to_date'])
                for current_date in range:
                    layers = list_layers(p['username'], p['password'], current_date.year, current_date.month, current_date.day, p['download_path'])
                    if p['frequency'] is not 'NONE':
                        self.aggregate_layers(layers, current_date)
                    else:
                        if p['open_in_qgis'] is True:
                            for l in layers:
                                if '.tfw' not in l:
                                    self.iface.addRasterLayer(l, str(l))
                    i += 1
                    percent = (i/float(len(range))) * 100
                    self.progressBar.setValue(percent)
            except Exception, e:
                self.bar.pushMessage(None, str(e), level=QgsMessageBar.CRITICAL)

    def collect_parameters(self):
        p = {
            'username': self.username.text(),
            'password': self.password.text(),
            'frequency': self.frequency.itemData(self.frequency.currentIndex()),
            'from_date': self.from_date.selectedDate().toPyDate(),
            'to_date': self.to_date.selectedDate().toPyDate(),
            'download_path': self.download_folder.text(),
            'open_in_qgis': self.add_to_canvas.isChecked()
        }
        if p['username'] is None or len(p['username']) == 0:
            self.bar.pushMessage(None, self.tr('Please insert the username'), level=QgsMessageBar.CRITICAL)
        elif p['password'] is None or len(p['password']) == 0:
            self.bar.pushMessage(None, self.tr('Please insert the password'), level=QgsMessageBar.CRITICAL)
        elif p['download_path'] is None or len(p['download_path']) == 0:
            self.bar.pushMessage(None, self.tr('Please select the download folder'), level=QgsMessageBar.CRITICAL)
        else:
            return p

    def aggregate_layers(self, layers, d):
        aggregation = self.frequency.itemData(self.frequency.currentIndex())
        month = str(d.month)
        month = month if len(month) == 2 else '0' + month
        day = str(d.day)
        day = day if len(day) == 2 else '0' + day
        filtered_layers = filter(lambda x: '.tif' in x, layers)
        datasets = []
        file_name = None
        for l in filtered_layers:
            datasets.append(Dataset(l))
        sum = datasets[0]
        for i in range(1,len(datasets)-1):
            sum += datasets[i]
        if aggregation == 'SUM':
            Env.overwrite = True
            avg = sum
            file_name = self.download_folder.text() + '/' + str(d.year) + '_' + month + '_' + day + '_SUM.tif'
            avg.save(file_name)
        elif aggregation == 'AVG':
            Env.overwrite = True
            avg = sum
            avg /= len(datasets)
            file_name = self.download_folder.text() + '/' + str(d.year) + '_' + month + '_' + day + '_AVG.tif'
            avg.save(file_name)
        if self.add_to_canvas.isChecked() is True:
            self.bar.pushMessage(None, str(file_name), level=QgsMessageBar.INFO)
            title = None
            if aggregation == 'SUM':
                title = self.tr('TRMM Aggregate (Sum): ') + str(d.year) + '-' + str(month) + '-' + str(day)
            elif aggregation == 'AVG':
                title = self.tr('TRMM Aggregate (Average): ') + str(d.year) + '-' + str(month) + '-' + str(day)
            rl = self.iface.addRasterLayer(file_name, title)
            fcn = QgsColorRampShader()
            fcn.setColorRampType(QgsColorRampShader.INTERPOLATED)
            lst = [
                QgsColorRampShader.ColorRampItem(0, QColor(247, 251, 255, 0), '< 2.6 [mm]'),
                QgsColorRampShader.ColorRampItem(2.6, QColor(222, 235, 247), '< 5.2 [mm]'),
                QgsColorRampShader.ColorRampItem(5.2, QColor(199, 220, 239), '< 7.8 [mm]'),
                QgsColorRampShader.ColorRampItem(7.8, QColor(162, 203, 226), '< 10.4 [mm]'),
                QgsColorRampShader.ColorRampItem(10.4, QColor(114, 178, 215), '< 13 [mm]'),
                QgsColorRampShader.ColorRampItem(13, QColor(73, 151, 201), '< 15.6 [mm]'),
                QgsColorRampShader.ColorRampItem(15.6, QColor(40, 120, 184), '< 18 [mm]'),
                QgsColorRampShader.ColorRampItem(18, QColor(13, 87, 161), '< 20 [mm]'),
                QgsColorRampShader.ColorRampItem(20, QColor(8, 48, 107), '>= 20 [mm]')
            ]
            fcn.setColorRampItemList(lst)
            shader = QgsRasterShader()
            shader.setRasterShaderFunction(fcn)
            renderer = QgsSingleBandPseudoColorRenderer(rl.dataProvider(), 1, shader)
            rl.setRenderer(renderer)
            rl.triggerRepaint()

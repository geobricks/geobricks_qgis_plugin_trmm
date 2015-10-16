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
import datetime
import processing
from gdal_calculations import Dataset, Env
import os.path
import subprocess
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QFileInfo
from PyQt4.QtGui import QAction, QIcon, QFileDialog, QProgressBar, QDialogButtonBox, QSizePolicy, QGridLayout, QMessageBox, QColor
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsColorRampShader
from qgis.gui import QgsMessageBar
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
from qgis.core import QgsRasterLayer, QgsRasterShader, QgsSingleBandPseudoColorRenderer
from ftplib import FTP
from shutil import copyfile
from config.trmm_config import config as conf

# Initialize Qt resources from file resources.py
# Import the code for the dialog
from geobricks_trmm_qgis_dialog import GeobricksTRMMDialog
import os.path


class GeobricksTRMM:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GeobricksTRMM_{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
        self.dlg = GeobricksTRMMDialog()
        self.actions = []
        self.menu = self.tr(u'&TRMM Data Downloader')
        self.toolbar = self.iface.addToolBar(u'TRMM Data Downloader')
        self.toolbar.setObjectName(u'TRMM Data Downloader')
        self.dlg.download_path.clear()
        self.dlg.pushButton.clicked.connect(self.select_output_file)
        self.is_rendered = False

    def select_output_file(self):
        filename = QFileDialog.getExistingDirectory(self.dlg, "Select Directory")
        self.dlg.download_path.setText(filename)

    def tr(self, message):
        return QCoreApplication.translate('GeobricksTRMM', message)

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
            text=self.tr(u'TRMM Data Downloader'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&TRMM Data Downloader'),
                action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def start(self):
        p = self.collect_parameters()
        self.dlg.progressBar.setMaximum(100)
        self.dlg.progressBar.setValue(0)
        i = 0
        try:
            range = date_range(p['from_date'], p['to_date'])
            for current_date in range:
                layers = list_layers(p['username'], p['password'], current_date.year, current_date.month, current_date.day, p['download_path'])
                if p['frequency'] == 'Daily':
                    self.aggregate_layers(layers, current_date)
                else:
                    if p['open_in_qgis'] is True:
                        for l in layers:
                            if '.tfw' not in l:
                                self.iface.addRasterLayer(l, str(l))
                i += 1
                percent = (i/float(len(range))) * 100
                self.dlg.progressBar.setValue(percent)
            QMessageBox.information(None, "INFO:", "Download complete")
        except:
            pass

    def collect_parameters(self):
        p = {}
        p['username'] = self.dlg.username.text()
        p['password'] = self.dlg.password.text()
        p['country'] = self.dlg.country.currentText()
        p['frequency'] = self.dlg.frequency.currentText()
        p['from_date'] = self.dlg.from_date.date().toPyDate()
        p['to_date'] = self.dlg.to_date.date().toPyDate()
        p['download_path'] = self.dlg.download_path.text()
        p['open_in_qgis'] = self.dlg.open_in_qgis.isChecked()
        if p['username'] is None or len(p['username']) == 0:
            QMessageBox.critical(None, 'Error', 'Please insert a username')
        if p['password'] is None or len(p['password']) == 0:
            QMessageBox.critical(None, 'Error', 'Please insert a password')
        if p['download_path'] is None or len(p['download_path']) == 0:
            QMessageBox.critical(None, 'Error', 'Please insert a download path')
        return p

    def aggregate_layers(self, layers, d):
        month = str(d.month)
        month = month if len(month) == 2 else '0' + month
        day = str(d.day)
        day = day if len(day) == 2 else '0' + day
        filtered_layers = filter(lambda x: '.tif' in x, layers)
        datasets = []
        for l in filtered_layers:
            datasets.append(Dataset(l))
        sum = datasets[0]
        for i in range(1,len(datasets)-1):
            sum += datasets[i]
        Env.overwrite = True
        avg = sum
        avg /= len(datasets)
        file_name = self.dlg.download_path.text() + '/' + str(d.year) + '_' + month + '_' + day + '.tif'
        avg.save(file_name)
        if self.dlg.open_in_qgis.isChecked() is True:
            rl = self.iface.addRasterLayer(file_name, str('TRMM Estimate Rainfall Daily Aggregate for ' + str(d.year) + '-' + month + '-' + day))
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
            # fileInfo = QFileInfo(file_name)
            # baseName = fileInfo.baseName()
            # rl = QgsRasterLayer(file_name, baseName)
            renderer = QgsSingleBandPseudoColorRenderer(rl.dataProvider(), 1, shader)
            rl.setRenderer(renderer)
            rl.triggerRepaint()

    def run(self):
        if self.is_rendered is False:
            self.dlg.show()
            yesterday = datetime.date.fromordinal(datetime.date.today().toordinal()-180)
            # self.dlg.from_date.setDate(yesterday)
            # self.dlg.to_date.setDate(yesterday)
            self.dlg.username.setPlaceholderText('e.g. name.surname@example.com')
            self.dlg.password.setPlaceholderText('e.g. name.surname@example.com')
            self.dlg.start_button.clicked.connect(self.start)
            self.is_rendered = True

def create_account():
    QgsMessageLog.logMessage('create_account!', 'Geobricks TRMM')

def list_layers(username, password, year, month, day, download_path):
    month = month if type(month) is str else str(month)
    month = month if len(month) == 2 else '0' + month
    day = day if type(day) is str else str(day)
    day = day if len(day) == 2 else '0' + day
    if conf['source']['type'] == 'FTP':
        ftp = FTP(conf['source']['ftp']['base_url'])
        ftp.login(username, password)
        ftp.cwd(conf['source']['ftp']['data_dir'])
        ftp.cwd(str(year))
        ftp.cwd(month)
        ftp.cwd(day)
        l = ftp.nlst()
        l.sort()
        fao_layers = l
        out = []
        final_folder = os.path.join(download_path, str(year), str(month), str(day))
        if not os.path.exists(final_folder):
            os.makedirs(final_folder)
        for layer in fao_layers:
            if '.7.' in layer or '.7A.' in layer:
                local_filename = os.path.join(final_folder, layer)
                out.append(local_filename)
                if os.path.isfile(local_filename) is False:
                    file = open(local_filename, 'wb+')
                    ftp.retrbinary('RETR %s' % layer, file.write)
        ftp.quit()
        return out

def date_range(start_date, end_date):
    dates = []
    delta = end_date - start_date
    for i in range(delta.days + 1):
        dates.append(start_date + datetime.timedelta(days=i))
    return dates

def accept():
    QgsMessageLog.logMessage('custom: ', 'Geobricks TRMM')

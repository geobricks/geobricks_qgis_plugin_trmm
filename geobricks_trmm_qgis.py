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
import os.path
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QAction, QIcon, QFileDialog, QProgressBar, QDialogButtonBox, QSizePolicy, QGridLayout, QMessageBox
from qgis.core import QgsMessageLog
from qgis.gui import QgsMessageBar
from ftplib import FTP
from config.trmm_config import config as conf

# Initialize Qt resources from file resources.py
# Import the code for the dialog
from geobricks_trmm_qgis_dialog import GeobricksTRMMDialog
import os.path


class GeobricksTRMM:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
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

        # Create the dialog (after translation) and keep reference
        self.dlg = GeobricksTRMMDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&GeobricksTRMM')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'GeobricksTRMM')
        self.toolbar.setObjectName(u'GeobricksTRMM')

        self.dlg.download_path.clear()
        self.dlg.pushButton.clicked.connect(self.select_output_file)

    def select_output_file(self):
        filename = QFileDialog.getExistingDirectory(self.dlg, "Select Directory")
        self.dlg.download_path.setText(filename)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
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
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

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
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/GeobricksTRMM/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Geobricks TRMM'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&GeobricksTRMM'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def start(self):
        username = self.dlg.username.text()
        password = self.dlg.password.text()
        country = self.dlg.country.currentText()
        from_date = self.dlg.from_date.date().toPyDate()
        to_date = self.dlg.to_date.date().toPyDate()
        download_path = self.dlg.download_path.text()
        open_in_qgis = self.dlg.open_in_qgis.isChecked()
        QgsMessageLog.logMessage(
            '****************************************************************************************************',
            'Geobricks TRMM')
        QgsMessageLog.logMessage('Hallo, World!', 'Geobricks TRMM')
        QgsMessageLog.logMessage('username: ' + str(username), 'Geobricks TRMM')
        QgsMessageLog.logMessage('password: ' + str(password), 'Geobricks TRMM')
        QgsMessageLog.logMessage('country: ' + str(country), 'Geobricks TRMM')
        QgsMessageLog.logMessage('from_date.year: ' + str(from_date.year), 'Geobricks TRMM')
        QgsMessageLog.logMessage('from_date.month: ' + str(from_date.month), 'Geobricks TRMM')
        QgsMessageLog.logMessage('from_date.day: ' + str(from_date.day), 'Geobricks TRMM')
        QgsMessageLog.logMessage('to_date.year: ' + str(to_date.year), 'Geobricks TRMM')
        QgsMessageLog.logMessage('to_date.month: ' + str(to_date.month), 'Geobricks TRMM')
        QgsMessageLog.logMessage('to_date.day: ' + str(to_date.day), 'Geobricks TRMM')
        QgsMessageLog.logMessage('download_path: ' + str(download_path), 'Geobricks TRMM')
        QgsMessageLog.logMessage('open_in_qgis: ' + str(open_in_qgis), 'Geobricks TRMM')
        QgsMessageLog.logMessage(
            '****************************************************************************************************',
            'Geobricks TRMM')
        QgsMessageLog.logMessage('TEST: ' + str(self.date_range(from_date, to_date)), 'Geobricks TRMM')
        for current_date in self.date_range(from_date, to_date):
            QgsMessageLog.logMessage('\tdate: ' + str(current_date), 'Geobricks TRMM')
            layers = self.list_layers(username, password, current_date.year, current_date.month, current_date.day, download_path)
            if open_in_qgis is True:
                for l in layers:
                    QgsMessageLog.logMessage('Add raster layer: ' + str(l), 'Geobricks TRMM')
                    self.iface.addRasterLayer(l, str(l))
        QMessageBox.information(None, "INFO:", "Download complete")

    def run(self):

        # Show the dialog
        self.dlg.show()

        # Set yesterday's date
        yesterday = datetime.date.fromordinal(datetime.date.today().toordinal()-180)
        self.dlg.from_date.setDate(yesterday)
        self.dlg.to_date.setDate(yesterday)

        # Placeholders
        self.dlg.username.setPlaceholderText('e.g. name.surname@example.com')
        self.dlg.password.setPlaceholderText('e.g. name.surname@example.com')

        # Link start button
        self.dlg.start_button.clicked.connect(self.start)
        # self.dlg.create_account_label.clicked.connect(self.create_account)

    def create_account(self):
        QgsMessageLog.logMessage('create_account!', 'Geobricks TRMM')

    def list_layers(self, username, password, year, month, day, download_path):
        month = month if type(month) is str else str(month)
        month = month if len(month) == 2 else '0' + month
        day = day if type(day) is str else str(day)
        day = day if len(day) == 2 else '0' + day
        QgsMessageLog.logMessage('list_layers: ' + str(year), 'Geobricks TRMM')
        QgsMessageLog.logMessage('list_layers: ' + str(month), 'Geobricks TRMM')
        QgsMessageLog.logMessage('list_layers: ' + str(day), 'Geobricks TRMM')
        if conf['source']['type'] == 'FTP':
            ftp = FTP(conf['source']['ftp']['base_url'])
            ftp.login(username, password)
            ftp.cwd(conf['source']['ftp']['data_dir'])
            ftp.cwd(str(year))
            ftp.cwd(month)
            ftp.cwd(day)
            l = ftp.nlst()
            l.sort()
            fao_layers = filter(lambda x: '.tif' in x, l)
            out = []
            # Create final folder with year, month and day
            final_folder = os.path.join(download_path, str(year), str(month), str(day))
            if not os.path.exists(final_folder):
                os.makedirs(final_folder)
            # Download layers
            for layer in fao_layers:
                if '.7.' in layer or '.7A.' in layer:
                    local_filename = os.path.join(final_folder, layer)
                    out.append(local_filename)
                    if os.path.isfile(local_filename) is False:
                        file = open(local_filename, 'wb+')
                        ftp.retrbinary('RETR %s' % layer, file.write)
                        QgsMessageLog.logMessage('list_layers: ' + str(layer), 'Geobricks TRMM')
            ftp.quit()
            return out

    def date_range(self, start_date, end_date):
        dates = []
        delta = end_date - start_date
        for i in range(delta.days + 1):
            dates.append(start_date + datetime.timedelta(days=i))
        return dates

    def accept(self):
        QgsMessageLog.logMessage('custom: ', 'Geobricks TRMM')

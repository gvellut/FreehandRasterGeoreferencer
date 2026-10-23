"""
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

from qgis.core import QgsProject
from qgis.PyQt.QtGui import QAction
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMenu, QMessageBox

from . import utils
from .qt_ui import adjust_dialog_to_content, configure_message_box, load_ui
from .raster_io import RasterLoadError, probe_raster_size


class FreehandRasterGeoreferencerDialog(QDialog):
    REPLACE = 2
    DUPLICATE = 3

    def __init__(self, *, parent):
        QDialog.__init__(self, parent)
        load_ui(self, "freehandrastergeoreferencerdialog.ui")
        adjust_dialog_to_content(self)
        self.configure_advanced_menu()
        self.pushButtonAdd.clicked.connect(self.add_new)
        self.pushButtonCancel.clicked.connect(self.reject)
        self.pushButtonBrowse.clicked.connect(self.show_browser_dialog)
        self.toolButtonAdvanced.clicked.connect(self.show_advanced_menu)

    def clear(self, layer):
        self.layer = layer
        if layer is None:
            image_path = ""
        else:
            image_path = layer.filepath

        self.lineEditImagePath.setText(image_path)
        self.lineEditImagePath.setToolTip(image_path)
        adjust_dialog_to_content(self)

    def show_browser_dialog(self):
        browser_dir, found = QgsProject.instance().readEntry(
            utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, None
        )
        if not found or not browser_dir or not os.path.isdir(browser_dir):
            browser_dir = os.path.expanduser("~")

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select raster",
            browser_dir,
            "Rasters (*.png *.bmp *.jpg *.jpeg *.tif *.tiff *.pdf *.jp2 *.ecw);;"
            "All files (*)",
        )

        if filepath:
            self.lineEditImagePath.setText(filepath)
            self.lineEditImagePath.setToolTip(filepath)
            browser_dir, _ = os.path.split(filepath)
            QgsProject.instance().writeEntry(
                utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, browser_dir
            )

    def configure_advanced_menu(self):
        action1 = QAction("Replace image for selected layer", self)
        action2 = QAction("Duplicate selected layer", self)

        action1.triggered.connect(self.replace_image)
        action2.triggered.connect(self.duplicate_layer)

        menu = QMenu(self)
        menu.addAction(action1)
        menu.addAction(action2)

        self.toolButtonAdvanced.setMenu(menu)

    def show_advanced_menu(self):
        self.toolButtonAdvanced.showMenu()

    def replace_image(self):
        self.accept(self.REPLACE)

    def duplicate_layer(self):
        self.accept(self.DUPLICATE, False)

    def add_new(self):
        self.accept()

    def accept(self, return_value=QDialog.DialogCode.Accepted, validate=True):
        if not validate:
            self.done(return_value)
            return

        result, message, details = self.validate()
        if result:
            self.done(return_value)
        else:
            message_box = QMessageBox(self)
            try:
                message_box.setWindowTitle("Error")
                message_box.setText(message)
                message_box.setDetailedText(details)
                message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                configure_message_box(message_box)
                message_box.exec()
            finally:
                message_box.deleteLater()

    def validate(self):
        result = True
        message = ""
        details = ""

        self.image_path = self.lineEditImagePath.text()
        if not os.path.isfile(self.image_path):
            result = False
            details += "The path must be an image file"
        else:
            try:
                probe_raster_size(self.image_path)
            except RasterLoadError as ex:
                result = False
                if len(details) > 0:
                    details += "\n"
                details += str(ex)

        if not result:
            message = "There were errors in the form"

        return result, message, details

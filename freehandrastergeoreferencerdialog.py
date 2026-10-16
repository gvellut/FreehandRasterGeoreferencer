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

from PyQt5.QtWidgets import QAction, QDialog, QFileDialog, QMenu, QMessageBox
from qgis.core import QgsProject

from . import utils
from .ui_freehandrastergeoreferencer import Ui_FreehandRasterGeoreferencer


class FreehandRasterGeoreferencerDialog(QDialog, Ui_FreehandRasterGeoreferencer):
    REPLACE = 2
    DUPLICATE = 3

    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.configureAdvancedMenu()
        self.pushButtonAdd.clicked.connect(self.addNew)
        self.pushButtonCancel.clicked.connect(self.reject)
        self.pushButtonBrowse.clicked.connect(self.showBrowserDialog)
        self.toolButtonAdvanced.clicked.connect(self.showAdvancedMenu)

    def clear(self, layer):
        self.layer = layer
        if layer is None:
            imagepath = ""
        else:
            imagepath = layer.filepath

        self.lineEditImagePath.setText(imagepath)

    def showBrowserDialog(self):
        bDir, found = QgsProject.instance().readEntry(
            utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, None
        )
        if not found:
            bDir = os.path.expanduser("~")

        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select image", bDir, "Images (*.png *.bmp *.jpg *.tif *.tiff *.pdf *.webp)"
        )

        if filepath:
            self.lineEditImagePath.setText(filepath)
            bDir, _ = os.path.split(filepath)
            QgsProject.instance().writeEntry(
                utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, bDir
            )

    def configureAdvancedMenu(self):
        action1 = QAction("Replace image for selected layer", self)
        action2 = QAction("Duplicate selected layer", self)

        action1.triggered.connect(self.replaceImage)
        action2.triggered.connect(self.duplicateLayer)

        menu = QMenu(self)
        menu.addAction(action1)
        menu.addAction(action2)

        self.toolButtonAdvanced.setMenu(menu)

    def showAdvancedMenu(self):
        self.toolButtonAdvanced.showMenu()

    def replaceImage(self):
        self.accept(self.REPLACE)

    def duplicateLayer(self):
        self.accept(self.DUPLICATE, False)

    def addNew(self):
        self.accept()

    def accept(self, retValue=QDialog.Accepted, validate=True):
        if not validate:
            self.done(retValue)
            return

        result, message, details = self.validate()
        if result:
            self.done(retValue)
        else:
            msgBox = QMessageBox()
            msgBox.setWindowTitle("Error")
            msgBox.setText(message)
            msgBox.setDetailedText(details)
            msgBox.setStandardButtons(QMessageBox.Ok)
            msgBox.exec_()

    def validate(self):
        result = True
        message = ""
        details = ""

        self.imagePath = self.lineEditImagePath.text()
        _, extension = os.path.splitext(self.imagePath)
        extension = extension.lower()
        if not os.path.isfile(self.imagePath) or (
            extension not in [".jpg", ".bmp", ".png", ".tif", ".tiff", ".pdf", ".webp"]
        ):
            result = False
            if len(details) > 0:
                details += "\n"
            details += "The path must be an image file"

        if not result:
            message = "There were errors in the form"

        return result, message, details

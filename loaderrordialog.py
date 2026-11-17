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

from PyQt5.QtCore import qDebug, Qt
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from qgis.core import QgsProject

from . import utils
from .ui_loaderrordialog import Ui_LoadError


class LoadErrorDialog(QDialog, Ui_LoadError):
    def __init__(self, filepath):
        QDialog.__init__(self)
        self.setupUi(self)

        self.lblError.setText("File '%s' not found." % filepath)
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        self.pushButtonBrowse.clicked.connect(self.showBrowserDialog)

    def clear(self):
        self.lineEditImagePath.setText("")

    def showBrowserDialog(self):
        bDir, found = QgsProject.instance().readEntry(
            utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, None
        )

        if not found or not os.path.isdir(bDir):
            bDir = os.path.expanduser("~")

        qDebug(bDir.encode())
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select image", bDir, "Images (*.png *.bmp *.jpg *.tif *.tiff *.pdf *.webp)"
        )
        self.lineEditImagePath.setText(filepath)

        if filepath:
            bDir, _ = os.path.split(filepath)
            QgsProject.instance().writeEntry(
                utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, bDir
            )

    def done(self, ack):
        QApplication.restoreOverrideCursor()
        super(LoadErrorDialog, self).done(ack)

    def accept(self):
        result, message, details = self.validate()
        if result:
            self.done(QDialog.Accepted)
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

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

from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox

from .qt_ui import adjust_dialog_to_content, configure_message_box, load_ui


class ExportGeorefRasterDialog(QDialog):
    def __init__(self, *, parent):
        QDialog.__init__(self, parent)
        load_ui(self, "exportgeorefrasterdialog.ui")
        adjust_dialog_to_content(self)

        self.pushButtonBrowse.clicked.connect(self.show_browser_dialog)
        self.checkBoxOnlyWorldFile.stateChanged.connect(self.setup_only_world_file)

    def clear(self, layer):
        self.lineEditImagePath.setText("")
        self.lineEditImagePath.setToolTip("")
        self.checkBoxRotationMode.setChecked(False)
        self.checkBoxRotationMode.setEnabled(True)
        self.checkBoxOnlyWorldFile.setChecked(False)

        default_path, _ = os.path.splitext(layer.filepath)
        self.default_path = default_path + "_georeferenced.png"
        self.lineEditImagePath.setPlaceholderText(self.default_path)

    def setup_only_world_file(self):
        if self.checkBoxOnlyWorldFile.isChecked():
            self._originalCheckBoxRotationModeChecked = (
                self.checkBoxRotationMode.isChecked()
            )
            self.checkBoxRotationMode.setChecked(True)
            self.checkBoxRotationMode.setEnabled(False)

        else:
            self.checkBoxRotationMode.setChecked(
                self._originalCheckBoxRotationModeChecked
            )
            self.checkBoxRotationMode.setEnabled(True)

    def show_browser_dialog(self):
        if self.lineEditImagePath.text():
            filepath_dialog = self.lineEditImagePath.text()
        else:
            filepath_dialog = self.default_path

        if not self.checkBoxOnlyWorldFile.isChecked():
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Export georeferenced raster",
                filepath_dialog,
                "Images (*.png *.bmp *.jpg *.tif *.tiff)",
            )
        else:
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "Export world file for raster",
                filepath_dialog,
                "Images (*.png *.bmp *.jpg *.tif *.tiff)",
            )

        if filepath:
            self.lineEditImagePath.setText(filepath)
            self.lineEditImagePath.setToolTip(filepath)

    def accept(self):
        result, message, details = self.validate()
        if result:
            self.done(QDialog.DialogCode.Accepted)
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

        self.is_put_rotation_in_world_file = self.checkBoxRotationMode.isChecked()
        self.is_export_only_world_file = self.checkBoxOnlyWorldFile.isChecked()

        self.image_path = self.lineEditImagePath.text()
        if not self.image_path:
            result = False
            details += "A file must be selected"

        if result:
            _, extension = os.path.splitext(self.image_path)
            extension = extension.lower()
            if extension not in [".jpg", ".bmp", ".png", ".tif", ".tiff"]:
                result = False
                if len(details) > 0:
                    details += "\n"
                details += "The file must be an image"

        if not result:
            message = "There were errors in the form"

        return result, message, details

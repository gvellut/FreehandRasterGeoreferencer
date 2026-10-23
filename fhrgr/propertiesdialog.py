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

from qgis.PyQt.QtWidgets import QDialog

from .qt_ui import load_ui


class PropertiesDialog(QDialog):
    def __init__(self, layer, *, parent):
        QDialog.__init__(self, parent)
        load_ui(self, "propertiesdialog.ui")
        self.setWindowTitle(f"{self.tr('Layer Properties')} - {layer.name()}")

        self.layer = layer
        self.horizontalSlider_Transparency.valueChanged.connect(self.slider_changed)
        self.spinBox_Transparency.valueChanged.connect(self.spin_box_changed)

        self.textEdit_Properties.setText(layer.freehand_metadata())
        self.spinBox_Transparency.setValue(layer.transparency)

    def slider_changed(self, val):
        s = self.spinBox_Transparency
        s.blockSignals(True)
        s.setValue(val)
        s.blockSignals(False)

    def spin_box_changed(self, val):
        s = self.horizontalSlider_Transparency
        s.blockSignals(True)
        s.setValue(val)
        s.blockSignals(False)

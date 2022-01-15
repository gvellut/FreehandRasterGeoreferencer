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

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QDialog, QDoubleSpinBox
from qgis.core import QgsApplication, QgsMapLayer, QgsProject

from . import resources_rc  # noqa
from .exportgeorefrasterdialog import ExportGeorefRasterDialog
from .freehandrastergeoreferencer_commands import ExportGeorefRasterCommand
from .freehandrastergeoreferencer_layer import (
    FreehandRasterGeoreferencerLayer,
    FreehandRasterGeoreferencerLayerType,
)
from .freehandrastergeoreferencer_maptools import (
    AdjustRasterMapTool,
    GeorefRasterBy2PointsMapTool,
    MoveRasterMapTool,
    RotateRasterMapTool,
    ScaleRasterMapTool,
)
from .freehandrastergeoreferencerdialog import FreehandRasterGeoreferencerDialog


class FreehandRasterGeoreferencer(object):

    PLUGIN_MENU = "&Freehand Raster Georeferencer"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.layers = {}
        QgsProject.instance().layerRemoved.connect(self.layerRemoved)
        self.iface.currentLayerChanged.connect(self.currentLayerChanged)

    def initGui(self):
        # Create actions
        self.actionAddLayer = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconAdd.png"),
            "Add raster for interactive georeferencing",
            self.iface.mainWindow(),
        )
        self.actionAddLayer.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_AddLayer"
        )
        self.actionAddLayer.triggered.connect(self.addLayer)

        self.actionMoveRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconMove.png"),
            "Move raster",
            self.iface.mainWindow(),
        )
        self.actionMoveRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_MoveRaster"
        )
        self.actionMoveRaster.triggered.connect(self.moveRaster)
        self.actionMoveRaster.setCheckable(True)

        self.actionRotateRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconRotate.png"),
            "Rotate raster",
            self.iface.mainWindow(),
        )
        self.actionRotateRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_RotateRaster"
        )
        self.actionRotateRaster.triggered.connect(self.rotateRaster)
        self.actionRotateRaster.setCheckable(True)

        self.actionScaleRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconScale.png"),
            "Scale raster",
            self.iface.mainWindow(),
        )
        self.actionScaleRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_ScaleRaster"
        )
        self.actionScaleRaster.triggered.connect(self.scaleRaster)
        self.actionScaleRaster.setCheckable(True)

        self.actionAdjustRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconAdjust.png"),
            "Adjust sides of raster",
            self.iface.mainWindow(),
        )
        self.actionAdjustRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_AdjustRaster"
        )
        self.actionAdjustRaster.triggered.connect(self.adjustRaster)
        self.actionAdjustRaster.setCheckable(True)

        self.actionGeoref2PRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/icon2Points.png"),
            "Georeference raster with 2 points",
            self.iface.mainWindow(),
        )
        self.actionGeoref2PRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_Georef2PRaster"
        )
        self.actionGeoref2PRaster.triggered.connect(self.georef2PRaster)
        self.actionGeoref2PRaster.setCheckable(True)

        self.actionIncreaseTransparency = QAction(
            QIcon(
                ":/plugins/freehandrastergeoreferencer/" "iconTransparencyIncrease.png"
            ),
            "Increase transparency",
            self.iface.mainWindow(),
        )
        self.actionIncreaseTransparency.triggered.connect(self.increaseTransparency)
        self.actionIncreaseTransparency.setShortcut("Alt+Ctrl+N")

        self.actionDecreaseTransparency = QAction(
            QIcon(
                ":/plugins/freehandrastergeoreferencer/" "iconTransparencyDecrease.png"
            ),
            "Decrease transparency",
            self.iface.mainWindow(),
        )
        self.actionDecreaseTransparency.triggered.connect(self.decreaseTransparency)
        self.actionDecreaseTransparency.setShortcut("Alt+Ctrl+B")

        self.actionExport = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconExport.png"),
            "Export raster with world file",
            self.iface.mainWindow(),
        )
        self.actionExport.triggered.connect(self.exportGeorefRaster)

        self.actionUndo = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconUndo.png"),
            u"Undo",
            self.iface.mainWindow(),
        )
        self.actionUndo.triggered.connect(self.undo)

        # Add toolbar button and menu item for AddLayer
        self.iface.layerToolBar().addAction(self.actionAddLayer)
        self.iface.insertAddLayerAction(self.actionAddLayer)
        self.iface.addPluginToRasterMenu(
            FreehandRasterGeoreferencer.PLUGIN_MENU, self.actionAddLayer
        )

        # create rotation value input field in toolbar
        self.spinBoxRotate = QDoubleSpinBox(self.iface.mainWindow())
        self.spinBoxRotate.setDecimals(3)
        self.spinBoxRotate.setMinimum(-180)
        self.spinBoxRotate.setMaximum(180)
        self.spinBoxRotate.setSingleStep(0.1)
        self.spinBoxRotate.setValue(0.0)
        self.spinBoxRotate.setToolTip("Rotation value (-180 to 180)")
        self.spinBoxRotate.setObjectName("FreehandRasterGeoreferencer_spinbox_rotate")
        self.spinBoxRotate.setKeyboardTracking(False)
        self.spinBoxRotate.valueChanged.connect(self.spinBoxRotateValueChangeEvent)
        self.spinBoxRotate.setFocusPolicy(Qt.ClickFocus)
        self.spinBoxRotate.focusInEvent = self.spinBoxFocusInEvent

        # create scale value X input field in toolbar
        self.spinBoxScaleX = QDoubleSpinBox(self.iface.mainWindow())
        self.spinBoxScaleX.setDecimals(3)
        self.spinBoxScaleX.setMinimum(0.001)
        self.spinBoxScaleX.setMaximum(100)
        self.spinBoxScaleX.setSingleStep(0.01)
        self.spinBoxScaleX.setValue(1.0)
        self.spinBoxScaleX.setToolTip("Scale value X (0.001 to 100)")
        self.spinBoxScaleX.setObjectName("FreehandRasterGeoreferencer_spinbox_scaleX")
        self.spinBoxScaleX.setKeyboardTracking(False)
        self.spinBoxScaleX.valueChanged.connect(self.spinBoxScaleXValueChangeEvent)
        self.spinBoxScaleX.setFocusPolicy(Qt.ClickFocus)
        self.spinBoxScaleX.focusInEvent = self.spinBoxFocusInEvent

        # create scale value Y input field in toolbar
        self.spinBoxScaleY = QDoubleSpinBox(self.iface.mainWindow())
        self.spinBoxScaleY.setDecimals(3)
        self.spinBoxScaleY.setMinimum(0.001)
        self.spinBoxScaleY.setMaximum(100)
        self.spinBoxScaleY.setSingleStep(0.01)
        self.spinBoxScaleY.setValue(1.0)
        self.spinBoxScaleY.setToolTip("Scale value Y (0.001 to 100)")
        self.spinBoxScaleY.setObjectName("FreehandRasterGeoreferencer_spinbox_scaleY")
        self.spinBoxScaleY.setKeyboardTracking(False)
        self.spinBoxScaleY.valueChanged.connect(self.spinBoxScaleYValueChangeEvent)
        self.spinBoxScaleY.setFocusPolicy(Qt.ClickFocus)
        self.spinBoxScaleY.focusInEvent = self.spinBoxFocusInEvent

        # create toolbar for this plugin
        self.toolbar = self.iface.addToolBar("Freehand raster georeferencing")
        self.toolbar.addAction(self.actionAddLayer)
        self.toolbar.addAction(self.actionMoveRaster)
        self.toolbar.addAction(self.actionRotateRaster)
        self.toolbar.addWidget(self.spinBoxRotate)
        self.toolbar.addAction(self.actionScaleRaster)
        self.toolbar.addWidget(self.spinBoxScaleX)
        self.toolbar.addWidget(self.spinBoxScaleY)
        self.toolbar.addAction(self.actionAdjustRaster)
        self.toolbar.addAction(self.actionGeoref2PRaster)
        self.toolbar.addAction(self.actionDecreaseTransparency)
        self.toolbar.addAction(self.actionIncreaseTransparency)
        self.toolbar.addAction(self.actionExport)
        self.toolbar.addAction(self.actionUndo)

        # Register plugin layer type
        self.layerType = FreehandRasterGeoreferencerLayerType(self)
        QgsApplication.pluginLayerRegistry().addPluginLayerType(self.layerType)

        self.dialogAddLayer = FreehandRasterGeoreferencerDialog()
        self.dialogExportGeorefRaster = ExportGeorefRasterDialog()

        self.moveTool = MoveRasterMapTool(self.iface)
        self.moveTool.setAction(self.actionMoveRaster)
        self.rotateTool = RotateRasterMapTool(self.iface)
        self.rotateTool.setAction(self.actionRotateRaster)
        self.scaleTool = ScaleRasterMapTool(self.iface)
        self.scaleTool.setAction(self.actionScaleRaster)
        self.adjustTool = AdjustRasterMapTool(self.iface)
        self.adjustTool.setAction(self.actionAdjustRaster)
        self.georef2PTool = GeorefRasterBy2PointsMapTool(self.iface)
        self.georef2PTool.setAction(self.actionGeoref2PRaster)
        self.currentTool = None

        # default state for toolbar
        self.checkCurrentLayerIsPluginLayer()

    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.layerToolBar().removeAction(self.actionAddLayer)
        self.iface.removeAddLayerAction(self.actionAddLayer)
        self.iface.removePluginRasterMenu(
            FreehandRasterGeoreferencer.PLUGIN_MENU, self.actionAddLayer
        )

        # Unregister plugin layer type
        QgsApplication.pluginLayerRegistry().removePluginLayerType(
            FreehandRasterGeoreferencerLayer.LAYER_TYPE
        )

        QgsProject.instance().layerRemoved.disconnect(self.layerRemoved)
        self.iface.currentLayerChanged.disconnect(self.currentLayerChanged)

        del self.toolbar

    def layerRemoved(self, layerId):
        if layerId in self.layers:
            del self.layers[layerId]
            self.checkCurrentLayerIsPluginLayer()

    def currentLayerChanged(self, layer):
        self.checkCurrentLayerIsPluginLayer()

    def checkCurrentLayerIsPluginLayer(self):
        layer = self.iface.activeLayer()
        if (
            layer
            and layer.type() == QgsMapLayer.PluginLayer
            and layer.pluginLayerType() == FreehandRasterGeoreferencerLayer.LAYER_TYPE
        ):
            self.actionMoveRaster.setEnabled(True)
            self.actionRotateRaster.setEnabled(True)
            self.actionScaleRaster.setEnabled(True)
            self.actionAdjustRaster.setEnabled(True)
            self.actionGeoref2PRaster.setEnabled(True)
            self.actionDecreaseTransparency.setEnabled(True)
            self.actionIncreaseTransparency.setEnabled(True)
            self.actionExport.setEnabled(True)
            self.spinBoxRotate.setEnabled(True)
            self.spinBoxScaleX.setEnabled(True)
            self.spinBoxScaleY.setEnabled(True)
            self.spinBoxValueSetValue(self.spinBoxRotate, layer.rotation, self.spinBoxRotateValueChangeEvent)
            self.spinBoxValueSetValue(self.spinBoxScaleX, layer.xScale, self.spinBoxScaleXValueChangeEvent)
            self.spinBoxValueSetValue(self.spinBoxScaleY, layer.yScale, self.spinBoxScaleYValueChangeEvent)
            try:
                # self.layer is the previously selected layer
                # in case it was a FRGR layer, disconnect the spinBoxes
                self.layer.transformParametersChanged.disconnect()
            except Exception:
                pass
            layer.transformParametersChanged.connect(self.spinBoxRotateUpdate)
            layer.transformParametersChanged.connect(self.spinBoxScaleXUpdate)
            layer.transformParametersChanged.connect(self.spinBoxScaleYUpdate)
            self.dialogAddLayer.toolButtonAdvanced.setEnabled(True)
            self.actionUndo.setEnabled(True)
            self.layer = layer

            if self.currentTool:
                self.currentTool.reset()
                self.currentTool.setLayer(layer)
        else:
            self.actionMoveRaster.setEnabled(False)
            self.actionRotateRaster.setEnabled(False)
            self.actionScaleRaster.setEnabled(False)
            self.actionAdjustRaster.setEnabled(False)
            self.actionGeoref2PRaster.setEnabled(False)
            self.actionDecreaseTransparency.setEnabled(False)
            self.actionIncreaseTransparency.setEnabled(False)
            self.actionExport.setEnabled(False)
            self.spinBoxRotate.setEnabled(False)
            self.spinBoxScaleX.setEnabled(False)
            self.spinBoxScaleY.setEnabled(False)
            self.spinBoxValueSetValue(self.spinBoxRotate, 0, self.spinBoxRotateValueChangeEvent)
            self.spinBoxValueSetValue(self.spinBoxScaleX, 1, self.spinBoxScaleXValueChangeEvent)
            self.spinBoxValueSetValue(self.spinBoxScaleY, 1, self.spinBoxScaleYValueChangeEvent)
            try:
                self.layer.transformParametersChanged.disconnect()
            except Exception:
                pass
            self.dialogAddLayer.toolButtonAdvanced.setEnabled(False)
            self.actionUndo.setEnabled(False)
            self.layer = None

            if self.currentTool:
                self.currentTool.reset()
                self.currentTool.setLayer(None)
                self._uncheckCurrentTool()

    def addLayer(self):
        self.dialogAddLayer.clear(self.layer)
        self.dialogAddLayer.show()
        result = self.dialogAddLayer.exec_()
        if result == QDialog.Accepted:
            self.createFreehandRasterGeoreferencerLayer()
        elif result == FreehandRasterGeoreferencerDialog.REPLACE:
            self.replaceImage()
        elif result == FreehandRasterGeoreferencerDialog.DUPLICATE:
            self.duplicateLayer()

    def replaceImage(self):
        imagepath = self.dialogAddLayer.lineEditImagePath.text()
        imagename, _ = os.path.splitext(os.path.basename(imagepath))
        self.layer.replaceImage(imagepath, imagename)

    def duplicateLayer(self):
        layer = self.iface.activeLayer().clone()
        QgsProject.instance().addMapLayer(layer)
        self.layers[layer.id()] = layer

    def createFreehandRasterGeoreferencerLayer(self):
        imagePath = self.dialogAddLayer.lineEditImagePath.text()
        imageName, _ = os.path.splitext(os.path.basename(imagePath))
        screenExtent = self.iface.mapCanvas().extent()

        layer = FreehandRasterGeoreferencerLayer(
            self, imagePath, imageName, screenExtent
        )
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self.layers[layer.id()] = layer
            self.iface.setActiveLayer(layer)

    def _toggleTool(self, tool):
        if self.currentTool is tool:
            # Toggle
            self._uncheckCurrentTool()
        else:
            self.currentTool = tool
            layer = self.iface.activeLayer()
            tool.setLayer(layer)
            self.iface.mapCanvas().setMapTool(tool)

    def _uncheckCurrentTool(self):
        # Toggle
        self.iface.mapCanvas().unsetMapTool(self.currentTool)
        # replace tool with Pan
        self.iface.actionPan().trigger()
        self.currentTool = None

    def moveRaster(self):
        self._toggleTool(self.moveTool)

    def rotateRaster(self):
        self._toggleTool(self.rotateTool)

    def scaleRaster(self):
        self._toggleTool(self.scaleTool)

    def adjustRaster(self):
        self._toggleTool(self.adjustTool)

    def georef2PRaster(self):
        self._toggleTool(self.georef2PTool)

    def increaseTransparency(self):
        layer = self.iface.activeLayer()
        # clamp to 100
        tr = min(layer.transparency + 10, 100)
        layer.transparencyChanged(tr)

    def decreaseTransparency(self):
        layer = self.iface.activeLayer()
        # clamp to 0
        tr = max(layer.transparency - 10, 0)
        layer.transparencyChanged(tr)

    def exportGeorefRaster(self):
        layer = self.iface.activeLayer()
        self.dialogExportGeorefRaster.clear(layer)
        self.dialogExportGeorefRaster.show()
        result = self.dialogExportGeorefRaster.exec_()
        if result == 1:
            exportCommand = ExportGeorefRasterCommand(self.iface)
            exportCommand.exportGeorefRaster(
                layer,
                self.dialogExportGeorefRaster.imagePath,
                self.dialogExportGeorefRaster.isPutRotationInWorldFile,
                self.dialogExportGeorefRaster.isExportOnlyWorldFile,
            )

    def spinBoxRotateUpdate(self, newParameters):
        self.spinBoxValueSetValue(self.spinBoxRotate, self.layer.rotation, self.spinBoxRotateValueChangeEvent)

    def spinBoxScaleXUpdate(self, newParameters):
        self.spinBoxValueSetValue(self.spinBoxScaleX, self.layer.xScale, self.spinBoxScaleXValueChangeEvent)

    def spinBoxScaleYUpdate(self, newParameters):
        self.spinBoxValueSetValue(self.spinBoxScaleY, self.layer.yScale, self.spinBoxScaleYValueChangeEvent)

    def spinBoxRotateValueChangeEvent(self, val):
        layer = self.layer
        layer.history.append(
            {"action": "rotation", "rotation": layer.rotation, "center": layer.center}
        )
        layer.setRotation(val)
        layer.repaint()
        layer.commitTransformParameters()

    def spinBoxScaleXValueChangeEvent(self, val):
        layer = self.layer
        layer.history.append(
            {"action": "scale", "xScale": self.layer.xScale, "yScale": self.layer.yScale}
        )
        layer.setScale(val, self.layer.yScale)
        layer.repaint()
        layer.commitTransformParameters()

    def spinBoxScaleYValueChangeEvent(self, val):
        layer = self.layer
        layer.history.append(
            {"action": "scale", "xScale": self.layer.xScale, "yScale": self.layer.yScale}
        )
        layer.setScale(self.layer.xScale, val)
        layer.repaint()
        layer.commitTransformParameters()

    def spinBoxValueSetValue(self, spinBox, val, event):
        # for changing only the spinbox value
        spinBox.valueChanged.disconnect()
        spinBox.setValue(val)
        spinBox.valueChanged.connect(event)

    def spinBoxFocusInEvent(self, event):
        # for clear 2point rubberband
        if self.currentTool:
            layer = self.iface.activeLayer()
            self.currentTool.reset()
            self.currentTool.setLayer(layer)

    def undo(self):
        layer = self.iface.activeLayer()
        if self.currentTool:
            self.currentTool.reset()  # for clear 2point rubberband
            self.currentTool.setLayer(layer)
        if len(layer.history) > 0:
            act = layer.history.pop()
            if act["action"] == "move":
                layer.setCenter(act["center"])
            elif act["action"] == "scale":
                layer.setScale(act["xScale"], act["yScale"])
            elif act["action"] == "rotation":
                layer.setRotation(act["rotation"])
                layer.setCenter(act["center"])
            elif act["action"] == "adjust":
                layer.setCenter(act["center"])
                layer.setScale(act["xScale"], act["yScale"])
            elif act["action"] == "2pointsA":
                layer.setCenter(act["center"])
            elif act["action"] == "2pointsB":
                layer.setRotation(act["rotation"])
                layer.setCenter(act["center"])
                layer.setScale(act["xScale"], act["yScale"])
                layer.setScale(act["xScale"], act["yScale"])
            layer.repaint()
            layer.commitTransformParameters()

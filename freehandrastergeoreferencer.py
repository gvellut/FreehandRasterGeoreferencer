# -*- coding: utf-8 -*-
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

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QDoubleSpinBox, QMessageBox
from qgis.core import QgsApplication, QgsMapLayer, QgsProject

from .freehandrastergeoreferencer_commands import ExportGeorefRasterCommand
from .freehandrastergeoreferencer_layer import (
    FreehandRasterGeoreferencerLayerType, FreehandRasterGeoreferencerLayer)
from .freehandrastergeoreferencer_maptools import \
    (MoveRasterMapTool,
     RotateRasterMapTool,
     ScaleRasterMapTool,
     AdjustRasterMapTool,
     GeorefRasterBy2PointsMapTool)
from .freehandrastergeoreferencerdialog import (
    FreehandRasterGeoreferencerDialog)
from .exportgeorefrasterdialog import (
    ExportGeorefRasterDialog)
from . import resources_rc  # noqa
from . import utils


class FreehandRasterGeoreferencer(object):

    PLUGIN_MENU = "&Freehand Raster Georeferencer"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.layers = {}
        QgsProject.instance().layerRemoved.connect(self.layerRemoved)
        self.iface.currentLayerChanged.connect(
            self.currentLayerChanged)

    def initGui(self):
        # Create actions
        self.actionAddLayer = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconAdd.png"),
            "Add raster for interactive georeferencing",
            self.iface.mainWindow())
        self.actionAddLayer.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_AddLayer")
        self.actionAddLayer.triggered.connect(self.addLayer)

        self.actionMoveRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconMove.png"),
            "Move raster",
            self.iface.mainWindow())
        self.actionMoveRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_MoveRaster")
        self.actionMoveRaster.triggered.connect(self.moveRaster)
        self.actionMoveRaster.setCheckable(True)

        self.actionRotateRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconRotate.png"),
            "Rotate raster", self.iface.mainWindow())
        self.actionRotateRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_RotateRaster")
        self.actionRotateRaster.triggered.connect(self.rotateRaster)
        self.actionRotateRaster.setCheckable(True)

        self.actionScaleRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconScale.png"),
            "Scale raster", self.iface.mainWindow())
        self.actionScaleRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_ScaleRaster")
        self.actionScaleRaster.triggered.connect(self.scaleRaster)
        self.actionScaleRaster.setCheckable(True)

        self.actionAdjustRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconAdjust.png"),
            "Adjust sides of raster", self.iface.mainWindow())
        self.actionAdjustRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_AdjustRaster")
        self.actionAdjustRaster.triggered.connect(self.adjustRaster)
        self.actionAdjustRaster.setCheckable(True)

        self.actionGeoref2PRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/icon2Points.png"),
            "Georeference raster with 2 points", self.iface.mainWindow())
        self.actionGeoref2PRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_Georef2PRaster")
        self.actionGeoref2PRaster.triggered.connect(self.georef2PRaster)
        self.actionGeoref2PRaster.setCheckable(True)

        self.actionIncreaseTransparency = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/"
                  "iconTransparencyIncrease.png"),
            "Increase transparency", self.iface.mainWindow())
        self.actionIncreaseTransparency.triggered.connect(
            self.increaseTransparency)
        self.actionIncreaseTransparency.setShortcut("Alt+Ctrl+N")

        self.actionDecreaseTransparency = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/"
                  "iconTransparencyDecrease.png"),
            "Decrease transparency", self.iface.mainWindow())
        self.actionDecreaseTransparency.triggered.connect(
            self.decreaseTransparency)
        self.actionDecreaseTransparency.setShortcut("Alt+Ctrl+B")

        self.actionExport = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconExport.png"),
            "Export raster with world file", self.iface.mainWindow())
        self.actionExport.triggered.connect(self.exportGeorefRaster)

        # Add toolbar button and menu item for AddLayer
        self.iface.layerToolBar().addAction(self.actionAddLayer)
        self.iface.insertAddLayerAction(self.actionAddLayer)
        self.iface.addPluginToRasterMenu(
            FreehandRasterGeoreferencer.PLUGIN_MENU, self.actionAddLayer)

        self.spinBox = QDoubleSpinBox(self.iface.mainWindow())
        self.spinBox.setDecimals(1)
        self.spinBox.setMinimum(-180)
        self.spinBox.setMaximum(180)
        self.spinBox.setSingleStep(0.1)
        self.spinBox.setValue(0.0)
        self.spinBox.setToolTip("Rotation value")
        self.spinBox.setObjectName("FreehandRasterGeoreferencer_spinbox")
        self.spinBox.setKeyboardTracking(False)
        self.spinBox.valueChanged.connect(self.spinboxValueChangeEvent)

        # create toolbar for this plugin
        self.toolbar = self.iface.addToolBar("Freehand raster georeferencing")
        self.toolbar.addAction(self.actionAddLayer)
        self.toolbar.addAction(self.actionMoveRaster)
        self.toolbar.addAction(self.actionRotateRaster)
        self.toolbar.addWidget(self.spinBox)
        self.toolbar.addAction(self.actionScaleRaster)
        self.toolbar.addAction(self.actionAdjustRaster)
        self.toolbar.addAction(self.actionGeoref2PRaster)
        self.toolbar.addAction(self.actionDecreaseTransparency)
        self.toolbar.addAction(self.actionIncreaseTransparency)
        self.toolbar.addAction(self.actionExport)

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
            FreehandRasterGeoreferencer.PLUGIN_MENU, self.actionAddLayer)

        # Unregister plugin layer type
        QgsApplication.pluginLayerRegistry().removePluginLayerType(
            FreehandRasterGeoreferencerLayer.LAYER_TYPE)

        QgsProject.instance().layerRemoved.disconnect(self.layerRemoved)
        self.iface.currentLayerChanged.disconnect(
            self.currentLayerChanged)

        del self.toolbar

    def layerRemoved(self, layerId):
        if layerId in self.layers:
            del self.layers[layerId]
            self.checkCurrentLayerIsPluginLayer()

    def currentLayerChanged(self, layer):
        self.checkCurrentLayerIsPluginLayer()

    def checkCurrentLayerIsPluginLayer(self):
        layer = self.iface.activeLayer()
        if (layer and
            layer.type() == QgsMapLayer.PluginLayer and
                layer.pluginLayerType() ==
                FreehandRasterGeoreferencerLayer.LAYER_TYPE):
            self.actionMoveRaster.setEnabled(True)
            self.actionRotateRaster.setEnabled(True)
            self.actionScaleRaster.setEnabled(True)
            self.actionAdjustRaster.setEnabled(True)
            self.actionGeoref2PRaster.setEnabled(True)
            self.actionDecreaseTransparency.setEnabled(True)
            self.actionIncreaseTransparency.setEnabled(True)
            self.actionExport.setEnabled(True)
            self.spinBox.setEnabled(True)
            self.spinBox.setValue(layer.rotation)

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
            self.spinBox.setEnabled(False)

            if self.currentTool:
                self.currentTool.reset()
                self.currentTool.setLayer(None)
                self.iface.mapCanvas().unsetMapTool(self.currentTool)
                self.iface.actionPan().trigger()
                self.currentTool = None

    def addLayer(self):
        self.dialogAddLayer.clear()
        self.dialogAddLayer.show()
        result = self.dialogAddLayer.exec_()
        if result == 1:
            self.createFreehandRasterGeoreferencerLayer()

    def createFreehandRasterGeoreferencerLayer(self):
        imagePath = self.dialogAddLayer.lineEditImagePath.text()
        imagePath = utils.toRelativeToQGS(imagePath)

        imageName = os.path.basename(imagePath)
        imageName, _ = os.path.splitext(imageName)
        screenExtent = self.iface.mapCanvas().extent()
        useScale = self.dialogAddLayer.checkBoxUseScale.isChecked()
        scale = self.dialogAddLayer.doubleSpinBoxScale.value()
        dpi = self.dialogAddLayer.doubleSpinBoxDPI.value()

        layer = FreehandRasterGeoreferencerLayer(self, imagePath , imageName, screenExtent, useScale, scale, dpi)
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self.layers[layer.id()] = layer
            self.iface.setActiveLayer(layer)

    def moveRaster(self):
        self.currentTool = self.moveTool
        layer = self.iface.activeLayer()
        self.moveTool.setLayer(layer)
        self.iface.mapCanvas().setMapTool(self.moveTool)

    def rotateRaster(self):
        self.currentTool = self.rotateTool
        layer = self.iface.activeLayer()
        self.rotateTool.setLayer(layer)
        self.iface.mapCanvas().setMapTool(self.rotateTool)

    def scaleRaster(self):
        self.currentTool = self.scaleTool
        layer = self.iface.activeLayer()
        self.scaleTool.setLayer(layer)
        self.iface.mapCanvas().setMapTool(self.scaleTool)

    def adjustRaster(self):
        self.currentTool = self.adjustTool
        layer = self.iface.activeLayer()
        self.adjustTool.setLayer(layer)
        self.iface.mapCanvas().setMapTool(self.adjustTool)

    def georef2PRaster(self):
        self.currentTool = self.georef2PTool
        layer = self.iface.activeLayer()
        self.georef2PTool.setLayer(layer)
        self.iface.mapCanvas().setMapTool(self.georef2PTool)

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
                layer, self.dialogExportGeorefRaster.imagePath,
                self.dialogExportGeorefRaster.isPutRotationInWorldFile)

    def spinboxValueChangeEvent(self, val):
        layer = self.iface.activeLayer()
        layer.setRotation(val)
        layer.repaint()
        layer.commitTransformParameters()
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

from qgis.core import Qgis, QgsApplication, QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QAction, QIcon
from qgis.PyQt.QtWidgets import QDialog, QDoubleSpinBox

from .export import ExportGeorefRasterCommand
from .exportgeorefrasterdialog import ExportGeorefRasterDialog
from .freehandrastergeoreferencer_maptools import (
    AdjustRasterMapTool,
    GeorefRasterBy2PointsMapTool,
    MoveRasterMapTool,
    RotateRasterMapTool,
    ScaleRasterMapTool,
)
from .freehandrastergeoreferencerdialog import FreehandRasterGeoreferencerDialog
from .icons import icon_path
from .layer import (
    FreehandRasterGeoreferencerLayer,
    FreehandRasterGeoreferencerLayerType,
)


class FreehandRasterGeoreferencer:
    PLUGIN_MENU = "&Freehand raster georeferencer"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.layers = {}
        QgsProject.instance().layerRemoved.connect(self.layer_removed)
        self.iface.currentLayerChanged.connect(self.current_layer_changed)

    def initGui(self):
        # Create actions
        self.actionAddLayer = QAction(
            QIcon(icon_path("iconAdd.png")),
            "Add raster for interactive georeferencing",
            self.iface.mainWindow(),
        )
        self.actionAddLayer.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_AddLayer"
        )
        self.actionAddLayer.triggered.connect(self.add_layer)

        self.actionMoveRaster = QAction(
            QIcon(icon_path("iconMove.png")),
            "Move raster",
            self.iface.mainWindow(),
        )
        self.actionMoveRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_MoveRaster"
        )
        self.actionMoveRaster.triggered.connect(self.move_raster)
        self.actionMoveRaster.setCheckable(True)

        self.actionRotateRaster = QAction(
            QIcon(icon_path("iconRotate.png")),
            "Rotate raster",
            self.iface.mainWindow(),
        )
        self.actionRotateRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_RotateRaster"
        )
        self.actionRotateRaster.triggered.connect(self.rotate_raster)
        self.actionRotateRaster.setCheckable(True)

        self.actionScaleRaster = QAction(
            QIcon(icon_path("iconScale.png")),
            "Scale raster",
            self.iface.mainWindow(),
        )
        self.actionScaleRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_ScaleRaster"
        )
        self.actionScaleRaster.triggered.connect(self.scale_raster)
        self.actionScaleRaster.setCheckable(True)

        self.actionAdjustRaster = QAction(
            QIcon(icon_path("iconAdjust.png")),
            "Adjust sides of raster",
            self.iface.mainWindow(),
        )
        self.actionAdjustRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_AdjustRaster"
        )
        self.actionAdjustRaster.triggered.connect(self.adjust_raster)
        self.actionAdjustRaster.setCheckable(True)

        self.actionGeoref2PRaster = QAction(
            QIcon(icon_path("icon2Points.png")),
            "Georeference raster with 2 points",
            self.iface.mainWindow(),
        )
        self.actionGeoref2PRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_Georef2PRaster"
        )
        self.actionGeoref2PRaster.triggered.connect(self.georef_2p_raster)
        self.actionGeoref2PRaster.setCheckable(True)

        self.actionIncreaseTransparency = QAction(
            QIcon(icon_path("iconTransparencyIncrease.png")),
            "Increase transparency",
            self.iface.mainWindow(),
        )
        self.actionIncreaseTransparency.triggered.connect(self.increase_transparency)
        self.actionIncreaseTransparency.setShortcut("Alt+Ctrl+N")

        self.actionDecreaseTransparency = QAction(
            QIcon(icon_path("iconTransparencyDecrease.png")),
            "Decrease transparency",
            self.iface.mainWindow(),
        )
        self.actionDecreaseTransparency.triggered.connect(self.decrease_transparency)
        self.actionDecreaseTransparency.setShortcut("Alt+Ctrl+B")

        self.actionExport = QAction(
            QIcon(icon_path("iconExport.png")),
            "Export raster with world file",
            self.iface.mainWindow(),
        )
        self.actionExport.triggered.connect(self.export_georef_raster)

        self.actionUndo = QAction(
            QIcon(icon_path("iconUndo.png")),
            "Undo",
            self.iface.mainWindow(),
        )
        self.actionUndo.triggered.connect(self.undo)

        # Add toolbar button and menu item for AddLayer
        self.iface.layerToolBar().addAction(self.actionAddLayer)
        self.iface.insertAddLayerAction(self.actionAddLayer)
        self.iface.addPluginToRasterMenu(
            FreehandRasterGeoreferencer.PLUGIN_MENU, self.actionAddLayer
        )

        self.spinBoxRotate = QDoubleSpinBox(self.iface.mainWindow())
        self.spinBoxRotate.setDecimals(3)
        self.spinBoxRotate.setMinimum(-180)
        self.spinBoxRotate.setMaximum(180)
        self.spinBoxRotate.setSingleStep(0.1)
        self.spinBoxRotate.setValue(0.0)
        self.spinBoxRotate.setToolTip("Rotation value (-180 to 180)")
        self.spinBoxRotate.setObjectName("FreehandRasterGeoreferencer_spinbox")
        self.spinBoxRotate.setKeyboardTracking(False)
        self.spinBoxRotate.valueChanged.connect(self.spin_box_rotate_value_change_event)
        self.spinBoxRotate.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.spinBoxRotate.focusInEvent = self.spin_box_rotate_focus_in_event

        # create toolbar for this plugin
        self.toolbar = self.iface.addToolBar("Freehand raster georeferencing")
        self.toolbar.addAction(self.actionAddLayer)
        self.toolbar.addAction(self.actionMoveRaster)
        self.toolbar.addAction(self.actionRotateRaster)
        self.toolbar.addWidget(self.spinBoxRotate)
        self.toolbar.addAction(self.actionScaleRaster)
        self.toolbar.addAction(self.actionAdjustRaster)
        self.toolbar.addAction(self.actionGeoref2PRaster)
        self.toolbar.addAction(self.actionDecreaseTransparency)
        self.toolbar.addAction(self.actionIncreaseTransparency)
        self.toolbar.addAction(self.actionExport)
        self.toolbar.addAction(self.actionUndo)

        # Register plugin layer type
        self.layerType = FreehandRasterGeoreferencerLayerType(self)
        QgsApplication.pluginLayerRegistry().addPluginLayerType(self.layerType)

        self.dialogAddLayer = FreehandRasterGeoreferencerDialog(
            parent=self.iface.mainWindow()
        )
        self.dialogExportGeorefRaster = ExportGeorefRasterDialog(
            parent=self.iface.mainWindow()
        )

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
        self.check_current_layer_is_plugin_layer()

    def unload(self):
        # Release reusable dialogs owned by the QGIS main window.
        for dialog in (self.dialogAddLayer, self.dialogExportGeorefRaster):
            dialog.close()
            dialog.deleteLater()
        self.dialogAddLayer = None
        self.dialogExportGeorefRaster = None

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

        QgsProject.instance().layerRemoved.disconnect(self.layer_removed)
        self.iface.currentLayerChanged.disconnect(self.current_layer_changed)

        del self.toolbar

    def layer_removed(self, layer_id):
        if layer_id in self.layers:
            del self.layers[layer_id]
            self.check_current_layer_is_plugin_layer()

    def current_layer_changed(self, layer):
        self.check_current_layer_is_plugin_layer()

    def check_current_layer_is_plugin_layer(self):
        layer = self.iface.activeLayer()
        if (
            layer
            and layer.type() == Qgis.LayerType.Plugin
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
            self.spin_box_rotate_value_set_value(layer.rotation)
            try:
                # self.layer is the previously selected layer
                # in case it was a FRGR layer, disconnect the spinBox
                self.layer.transform_parameters_changed.disconnect()
            except Exception:
                pass
            layer.transform_parameters_changed.connect(self.spin_box_rotate_update)
            self.dialogAddLayer.toolButtonAdvanced.setEnabled(True)
            self.actionUndo.setEnabled(True)
            self.layer = layer

            if self.currentTool:
                self.currentTool.reset()
                self.currentTool.set_layer(layer)
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
            self.spin_box_rotate_value_set_value(0)
            try:
                self.layer.transform_parameters_changed.disconnect()
            except Exception:
                pass
            self.dialogAddLayer.toolButtonAdvanced.setEnabled(False)
            self.actionUndo.setEnabled(False)
            self.layer = None

            if self.currentTool:
                self.currentTool.reset()
                self.currentTool.set_layer(None)
                self._uncheck_current_tool()

    def add_layer(self):
        self.dialogAddLayer.clear(self.layer)
        self.dialogAddLayer.show()
        result = self.dialogAddLayer.exec()
        if result == QDialog.DialogCode.Accepted:
            self.create_freehand_raster_georeferencer_layer()
        elif result == FreehandRasterGeoreferencerDialog.REPLACE:
            self.replace_image()
        elif result == FreehandRasterGeoreferencerDialog.DUPLICATE:
            self.duplicate_layer()

    def replace_image(self):
        image_path = self.dialogAddLayer.lineEditImagePath.text()
        image_name, _ = os.path.splitext(os.path.basename(image_path))
        self.layer.replace_image(image_path, image_name)

    def duplicate_layer(self):
        layer = self.iface.activeLayer().clone()
        QgsProject.instance().addMapLayer(layer)
        self.layers[layer.id()] = layer

    def create_freehand_raster_georeferencer_layer(self):
        image_path = self.dialogAddLayer.lineEditImagePath.text()
        image_name, _ = os.path.splitext(os.path.basename(image_path))
        screen_extent = self.iface.mapCanvas().extent()

        layer = FreehandRasterGeoreferencerLayer(
            self, image_path, image_name, screen_extent
        )
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self.layers[layer.id()] = layer
            self.iface.setActiveLayer(layer)

    def _toggle_tool(self, tool):
        if self.currentTool is tool:
            # Toggle
            self._uncheck_current_tool()
        else:
            self.currentTool = tool
            layer = self.iface.activeLayer()
            tool.set_layer(layer)
            self.iface.mapCanvas().setMapTool(tool)

    def _uncheck_current_tool(self):
        # Toggle
        self.iface.mapCanvas().unsetMapTool(self.currentTool)
        # replace tool with Pan
        self.iface.actionPan().trigger()
        self.currentTool = None

    def move_raster(self):
        self._toggle_tool(self.moveTool)

    def rotate_raster(self):
        self._toggle_tool(self.rotateTool)

    def scale_raster(self):
        self._toggle_tool(self.scaleTool)

    def adjust_raster(self):
        self._toggle_tool(self.adjustTool)

    def georef_2p_raster(self):
        self._toggle_tool(self.georef2PTool)

    def increase_transparency(self):
        layer = self.iface.activeLayer()
        # clamp to 100
        tr = min(layer.transparency + 10, 100)
        layer.transparency_changed(tr)

    def decrease_transparency(self):
        layer = self.iface.activeLayer()
        # clamp to 0
        tr = max(layer.transparency - 10, 0)
        layer.transparency_changed(tr)

    def export_georef_raster(self):
        layer = self.iface.activeLayer()
        self.dialogExportGeorefRaster.clear(layer)
        self.dialogExportGeorefRaster.show()
        result = self.dialogExportGeorefRaster.exec()
        if result == QDialog.DialogCode.Accepted:
            exportCommand = ExportGeorefRasterCommand(self.iface)
            exportCommand.export_georef_raster(
                layer,
                self.dialogExportGeorefRaster.image_path,
                self.dialogExportGeorefRaster.is_put_rotation_in_world_file,
                self.dialogExportGeorefRaster.is_export_only_world_file,
            )

    def spin_box_rotate_update(self, newParameters):
        self.spin_box_rotate_value_set_value(self.layer.rotation)

    def spin_box_rotate_value_change_event(self, val):
        layer = self.layer
        layer.history.append({
            "action": "rotation",
            "rotation": layer.rotation,
            "center": layer.center,
        })
        layer.set_rotation(val)
        layer.repaint()
        layer.commit_transform_parameters()

    def spin_box_rotate_value_set_value(self, val):
        # for changing only the spinbox value
        self.spinBoxRotate.valueChanged.disconnect()
        self.spinBoxRotate.setValue(val)
        self.spinBoxRotate.valueChanged.connect(self.spin_box_rotate_value_change_event)

    def spin_box_rotate_focus_in_event(self, event):
        # for clear 2point rubberband
        if self.currentTool:
            layer = self.iface.activeLayer()
            self.currentTool.reset()
            self.currentTool.set_layer(layer)

    def undo(self):
        layer = self.iface.activeLayer()
        if self.currentTool:
            self.currentTool.reset()  # for clear 2point rubberband
            self.currentTool.set_layer(layer)
        if len(layer.history) > 0:
            act = layer.history.pop()
            if act["action"] == "move":
                layer.set_center(act["center"])
            elif act["action"] == "scale":
                layer.set_scale(act["x_scale"], act["y_scale"])
            elif act["action"] == "rotation":
                layer.set_rotation(act["rotation"])
                layer.set_center(act["center"])
            elif act["action"] == "adjust":
                layer.set_center(act["center"])
                layer.set_scale(act["x_scale"], act["y_scale"])
            elif act["action"] == "2pointsA":
                layer.set_center(act["center"])
            elif act["action"] == "2pointsB":
                layer.set_rotation(act["rotation"])
                layer.set_center(act["center"])
                layer.set_scale(act["x_scale"], act["y_scale"])
                layer.set_scale(act["x_scale"], act["y_scale"])
            layer.repaint()
            layer.commit_transform_parameters()

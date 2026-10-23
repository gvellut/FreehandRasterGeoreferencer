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

import os

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataProvider,
    QgsMapLayerRenderer,
    QgsMessageLog,
    QgsPluginLayer,
    QgsPluginLayerType,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QPointF, QRectF, Qt, pyqtSignal, qDebug
from qgis.PyQt.QtGui import QColor, QPainter, QPen
from qgis.PyQt.QtWidgets import QDialog

from . import transform as transform_math, utils
from .loaderrordialog import LoadErrorDialog
from .raster_io import RasterLoadError, load_raster_for_display


class LayerDefaultSettings:
    TRANSPARENCY = 30
    BLEND_MODE = "SourceOver"


class FreehandRasterGeoreferencerLayer(QgsPluginLayer):
    LAYER_TYPE = "FreehandRasterGeoreferencerLayer"
    transform_parameters_changed = pyqtSignal(tuple)

    def __init__(self, plugin, filepath, title, screen_extent):
        QgsPluginLayer.__init__(
            self, FreehandRasterGeoreferencerLayer.LAYER_TYPE, title
        )
        self.plugin = plugin
        self.iface = plugin.iface

        self.title = title
        self.filepath = filepath
        self.screen_extent = screen_extent
        self.history = []
        # set custom properties
        self.setCustomProperty("title", title)
        self.setCustomProperty("filepath", self.filepath)

        self.setValid(True)

        self.set_transparency(LayerDefaultSettings.TRANSPARENCY)
        self.set_blend_mode_by_name(LayerDefaultSettings.BLEND_MODE)

        # dummy data: real init is done in intializeLayer
        self.center = QgsPointXY(0, 0)
        self.rotation = 0.0
        self.x_scale = 1.0
        self.y_scale = 1.0

        self.image = None
        self._raster_display = None
        self.raster_warnings = []
        self.load_error = ""
        self._extent = None

        self.error = False
        self.initializing = False
        self.initialized = False
        self.initialize_layer(screen_extent)

        self.provider = FreehandRasterGeoreferencerLayerProvider(self)

    def dataProvider(self):
        # issue with DBManager if the dataProvider of the QgsLayerPlugin
        # returns None
        return self.provider

    def set_scale(self, x_scale, y_scale):
        self.x_scale = x_scale
        self.y_scale = y_scale

    def set_rotation(self, rotation):
        # 3 decimals ought to be enough for everybody
        rotation = round(rotation, 3)
        # keep in -180,180 interval
        if rotation < -180:
            rotation += 360
        if rotation > 180:
            rotation -= 360
        self.rotation = rotation

    def set_center(self, center):
        self.center = center

    def commit_transform_parameters(self):
        QgsProject.instance().setDirty(True)
        self._extent = None
        self.setCustomProperty("x_scale", self.x_scale)
        self.setCustomProperty("y_scale", self.y_scale)
        self.setCustomProperty("rotation", self.rotation)
        self.setCustomProperty("x_center", self.center.x())
        self.setCustomProperty("y_center", self.center.y())
        self.transform_parameters_changed.emit((
            self.x_scale,
            self.y_scale,
            self.rotation,
            self.center,
        ))

    def reproject_transform_parameters(self, old_crs, new_crs):
        transform = QgsCoordinateTransform(old_crs, new_crs, QgsProject.instance())

        new_center = transform.transform(self.center)
        new_extent = transform.transform(self.extent())

        # transform the parameters except rotation
        # TODO rotation could be better handled (maybe check rotation between
        # old and new extent)
        # but not really worth the effort ?
        self.setCrs(new_crs)
        self.set_center(new_center)
        self.reset_scale(new_extent.width(), new_extent.height())

    def reset_transform_parameters_to_new_crs(self):
        """
        Attempts to keep the layer on the same region of the map when
        the map CRS is changed
        """
        old_crs = self.crs()
        new_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        self.reproject_transform_parameters(old_crs, new_crs)
        self.commit_transform_parameters()

    def setup_crs_events(self):
        layer_id = self.id()

        def remove_crs_change_handler(layer_ids):
            if layer_id in layer_ids:
                try:
                    self.iface.mapCanvas().destinationCrsChanged.disconnect(
                        self.reset_transform_parameters_to_new_crs
                    )
                except Exception:
                    pass
                try:
                    QgsProject.instance().disconnect(remove_crs_change_handler)
                except Exception:
                    pass

        self.iface.mapCanvas().destinationCrsChanged.connect(
            self.reset_transform_parameters_to_new_crs
        )
        QgsProject.instance().layersRemoved.connect(remove_crs_change_handler)

    def setup_crs(self):
        map_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        self.setCrs(map_crs)

        self.setup_crs_events()

    def repaint(self):
        self.repaintRequested.emit()

    def transform_parameters(self):
        return (self.center, self.rotation, self.x_scale, self.y_scale)

    def initialize_layer(self, screen_extent=None):
        if self.error or self.initialized or self.initializing:
            return

        if self.filepath is None:
            return

        self.initializing = True
        try:
            abs_path = self.get_absolute_filepath()
            replacement_filepath = None

            if not os.path.exists(abs_path):
                load_error_dialog = LoadErrorDialog(
                    self.title,
                    abs_path,
                    self.expected_image_size(),
                    parent=self.iface.mainWindow(),
                )
                try:
                    result = load_error_dialog.exec()
                    if result == QDialog.DialogCode.Accepted:
                        abs_path = load_error_dialog.lineEditImagePath.text()
                        replacement_filepath = utils.to_relative_to_qgs(abs_path)
                    else:
                        self.load_error = f"Raster image was not found: {abs_path}"
                        self.error = True
                        self.setValid(False)
                        return
                finally:
                    # Release the temporary dialog even when recovery is cancelled.
                    load_error_dialog.deleteLater()

            display = load_raster_for_display(abs_path)
            if replacement_filepath is not None:
                self.filepath = replacement_filepath
                self.setCustomProperty("filepath", self.filepath)
                QgsProject.instance().setDirty(True)
            self._apply_raster_display(display)
            self.setup_crs()

            if screen_extent:
                self.initialize_transform_parameters(screen_extent, display)
        except RasterLoadError as ex:
            self.load_error = str(ex)
            self.error = True
            self.setValid(False)
            self.show_bar_message(
                "Raster load failed",
                self.load_error,
                Qgis.MessageLevel.Critical,
                8,
            )
        finally:
            self.initializing = False

    def _apply_raster_display(self, display):
        self._raster_display = display
        self.image = display.qimage
        self.raster_warnings = list(display.warnings)
        self.load_error = ""
        self.error = False
        self.initialized = True
        self.setValid(True)
        self._extent = None
        self.setCustomProperty("imageWidth", display.width)
        self.setCustomProperty("imageHeight", display.height)
        for warning in self.raster_warnings:
            self.show_bar_message(
                "Raster display",
                warning,
                Qgis.MessageLevel.Warning,
                10,
            )

    def initialize_transform_parameters(self, screen_extent, display):
        if display.geotransform and not self.is_default_geotransform(
            display.geotransform
        ):
            raster_georef = transform_math.georeference_from_geotransform(
                display.geotransform,
                display.width,
                display.height,
                display.crs_wkt,
            )
            self.initialize_existing_georeferencing(raster_georef)
        else:
            self.set_center(screen_extent.center())
            self.set_rotation(0.0)
            self.reset_scale(screen_extent.width(), screen_extent.height())
            self.commit_transform_parameters()

    def initialize_existing_georeferencing(self, raster_georef):
        center = QgsPointXY(raster_georef.center.x, raster_georef.center.y)

        qDebug(
            repr(raster_georef.rotation)
            + " "
            + repr((raster_georef.x_scale, raster_georef.y_scale))
            + " "
            + repr(center)
        )

        self.set_rotation(raster_georef.rotation)
        self.set_center(center)
        self.set_scale(raster_georef.x_scale, raster_georef.y_scale)
        self.commit_transform_parameters()

        message_shown = False
        if raster_georef.crs_wkt:
            q_crs = QgsCoordinateReferenceSystem(raster_georef.crs_wkt)
            # TODO check change
            if q_crs.description() != self.crs().description():
                # reproject
                try:
                    self.reproject_transform_parameters(q_crs, self.crs())
                    self.commit_transform_parameters()
                    self.show_bar_message(
                        "Transform parameters changed: ",
                        "Found existing georeferencing in raster but "
                        "its CRS does not match the CRS of the map. "
                        "Reprojected the extent.",
                        Qgis.MessageLevel.Warning,
                        25,
                    )
                    message_shown = True
                except Exception as ex:
                    QgsMessageLog.logMessage(repr(ex))
                    self.show_bar_message(
                        "CRS does not match",
                        "Found existing georeferencing in raster but "
                        "its CRS does not match the CRS of the map. "
                        "Unable to reproject.",
                        Qgis.MessageLevel.Warning,
                        5,
                    )
                    message_shown = True
        # if no projection info, assume it is the same CRS
        # as the map and no warning
        if not message_shown:
            self.show_bar_message(
                "Georeferencing loaded",
                "Found existing georeferencing in raster",
                Qgis.MessageLevel.Info,
                3,
            )

        # zoom (assume the user wants to work on the image)
        self.iface.mapCanvas().setExtent(self.extent())

    def is_default_geotransform(self, georef):
        """
        Check if there is really a transform or if it is just the default
        made up by GDAL
        """
        return transform_math.is_default_geotransform(georef)

    def reset_scale(self, sw, sh):
        x_scale, y_scale = transform_math.fit_scale_to_extent(
            self.image.width(), self.image.height(), sw, sh
        )
        self.set_scale(x_scale, y_scale)

    def replace_image(self, filepath, title):
        try:
            display = load_raster_for_display(filepath)
        except RasterLoadError as ex:
            QgsMessageLog.logMessage(repr(ex))
            self.show_bar_message(
                "Raster load failed",
                str(ex),
                Qgis.MessageLevel.Critical,
                8,
            )
            return False

        self.title = title
        self.filepath = filepath

        # set custom properties
        self.setCustomProperty("title", title)
        self.setCustomProperty("filepath", self.filepath)
        self.setName(title)

        self._apply_raster_display(display)
        QgsProject.instance().setDirty(True)
        self.repaint()
        return True

    def clone(self):
        layer = FreehandRasterGeoreferencerLayer(
            self.plugin, self.filepath, self.title, self.screen_extent
        )
        layer.center = self.center
        layer.rotation = self.rotation
        layer.x_scale = self.x_scale
        layer.y_scale = self.y_scale
        layer.commit_transform_parameters()
        return layer

    def get_absolute_filepath(self):
        if not self.filepath:
            return ""
        if not os.path.isabs(self.filepath):
            # relative to QGS file
            qgs_path = QgsProject.instance().fileName()
            qgs_folder, _ = os.path.split(qgs_path)
            filepath = os.path.join(qgs_folder, self.filepath)
        else:
            filepath = self.filepath

        return filepath

    def expected_image_size(self):
        width = int(self.customProperty("imageWidth", 0) or 0)
        height = int(self.customProperty("imageHeight", 0) or 0)
        if width > 0 and height > 0:
            return (width, height)
        if self.image is not None:
            return (self.image.width(), self.image.height())
        return None

    def extent(self):
        self.initialize_layer()
        if not self.initialized:
            qDebug("Not Initialized")
            return QgsRectangle(0, 0, 1, 1)

        if self._extent:
            return self._extent

        corners = tuple(
            self._point_from_qgs(point) for point in self.corner_coordinates()
        )
        left, bottom, right, top = transform_math.extent_from_corners(corners)

        # recenter + create rectangle
        self._extent = QgsRectangle(left, bottom, right, top)
        return self._extent

    def corner_coordinates(self):
        return self.transformed_corner_coordinates(
            self.center, self.rotation, self.x_scale, self.y_scale
        )

    def transformed_corner_coordinates(self, center, rotation, x_scale, y_scale):
        return tuple(
            self._qgs_point_from_point(point)
            for point in transform_math.corner_coordinates(
                self.image.width(),
                self.image.height(),
                self._point_from_qgs(center),
                rotation,
                x_scale,
                y_scale,
            )
        )

    def transformed_corner_coordinates_from_point(
        self, start_point, rotation, x_scale, y_scale
    ):
        return tuple(
            self._qgs_point_from_point(point)
            for point in transform_math.corner_coordinates_from_point(
                self.image.width(),
                self.image.height(),
                self._point_from_qgs(self.center),
                self.rotation,
                self.x_scale,
                self.y_scale,
                self._point_from_qgs(start_point),
                rotation,
                x_scale,
                y_scale,
            )
        )

    def move_center_from_point_rotate(self, start_point, rotation, x_scale, y_scale):
        center = transform_math.center_from_point_transform(
            self.image.width(),
            self.image.height(),
            self._point_from_qgs(self.center),
            self.rotation,
            self.x_scale,
            self.y_scale,
            self._point_from_qgs(start_point),
            rotation,
            x_scale,
            y_scale,
        )
        self.center = self._qgs_point_from_point(center)

    def _point_from_qgs(self, point):
        return transform_math.Point(point.x(), point.y())

    def _qgs_point_from_point(self, point):
        return QgsPointXY(point.x, point.y)

    def createMapRenderer(self, renderer_context):
        return FreehandRasterGeoreferencerLayerRenderer(self, renderer_context)

    def set_blend_mode_by_name(self, mode_name):
        self.blend_mode_name = mode_name
        blend_mode = getattr(
            QPainter.CompositionMode,
            "CompositionMode_" + mode_name,
            QPainter.CompositionMode.CompositionMode_SourceOver,
        )
        self.setBlendMode(blend_mode)
        self.setCustomProperty("blend_mode", mode_name)

    def set_transparency(self, transparency):
        self.transparency = transparency
        self.setCustomProperty("transparency", transparency)

    def draw(self, render_context):
        if render_context.extent().isEmpty():
            qDebug("Drawing is skipped because map extent is empty.")
            return True

        self.initialize_layer()
        if not self.initialized:
            qDebug("Drawing is skipped because nothing to draw.")
            return True

        painter = render_context.painter()
        painter.save()
        self.prepare_style(painter)
        self.draw_raster(render_context)
        painter.restore()

        return True

    def draw_raster(self, render_context):
        painter = render_context.painter()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.map2pixel = render_context.mapToPixel()

        scale_x = self.x_scale / self.map2pixel.mapUnitsPerPixel()
        scale_y = self.y_scale / self.map2pixel.mapUnitsPerPixel()

        rect = QRectF(
            QPointF(-self.image.width() / 2.0, -self.image.height() / 2.0),
            QPointF(self.image.width() / 2.0, self.image.height() / 2.0),
        )
        map_center = self.map2pixel.transform(self.center)

        # draw the image on the map canvas
        painter.translate(QPointF(map_center.x(), map_center.y()))
        painter.rotate(self.rotation)
        painter.scale(scale_x, scale_y)
        painter.drawImage(rect, self.image)

        painter.setOpacity(1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen()
        pen.setColor(QColor(0, 0, 0))
        pen.setWidth(3)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRect(rect)

    def prepare_style(self, painter):
        painter.setOpacity(1.0 - self.transparency / 100.0)

    def readXml(self, node, context):
        self.readCustomProperties(node)
        self.title = self.customProperty("title", "")
        self.filepath = self.customProperty("filepath", "")
        self.x_scale = float(self.customProperty("x_scale", 1.0))
        self.y_scale = float(self.customProperty("y_scale", 1.0))
        self.rotation = float(self.customProperty("rotation", 0.0))
        x_center = float(self.customProperty("x_center", 0.0))
        y_center = float(self.customProperty("y_center", 0.0))
        self.center = QgsPointXY(x_center, y_center)
        self.set_transparency(
            int(self.customProperty("transparency", LayerDefaultSettings.TRANSPARENCY))
        )
        self.set_blend_mode_by_name(
            self.customProperty("blend_mode", LayerDefaultSettings.BLEND_MODE)
        )
        return True

    def writeXml(self, node, doc, context):
        element = node.toElement()
        self.writeCustomProperties(node, doc)
        element.setAttribute("type", "plugin")
        element.setAttribute("name", FreehandRasterGeoreferencerLayer.LAYER_TYPE)
        return True

    def freehand_metadata(self):
        lines = []
        fmt = "%s:\t%s"
        lines.append(fmt % (self.tr("Title"), self.title))
        stored_path = self.filepath or ""
        resolved_path = self.get_absolute_filepath()
        if resolved_path:
            resolved_path = os.path.normpath(resolved_path)
        lines.append(fmt % (self.tr("Stored path"), stored_path))
        lines.append(fmt % (self.tr("Resolved path"), resolved_path))
        lines.append(
            fmt
            % (
                self.tr("File exists"),
                str(bool(resolved_path and os.path.exists(resolved_path))),
            )
        )
        lines.append(fmt % (self.tr("Layer initialized"), str(self.initialized)))
        if self.load_error:
            lines.append(fmt % (self.tr("Load error"), self.load_error))
        expected_size = self.expected_image_size()
        image_width = self.image.width() if self.image is not None else 0
        image_height = self.image.height() if self.image is not None else 0
        if expected_size is not None and image_width == 0 and image_height == 0:
            image_width, image_height = expected_size
        lines.append(fmt % (self.tr("Image Width"), str(image_width)))
        lines.append(fmt % (self.tr("Image Height"), str(image_height)))
        lines.append(fmt % (self.tr("Rotation (CW)"), str(self.rotation)))
        lines.append(fmt % (self.tr("X center"), str(self.center.x())))
        lines.append(fmt % (self.tr("Y center"), str(self.center.y())))
        lines.append(fmt % (self.tr("X scale"), str(self.x_scale)))
        lines.append(fmt % (self.tr("Y scale"), str(self.y_scale)))
        lines.append(
            self.tr(
                "Plugin layer source is stored in custom properties; an empty "
                "layer-tree source and dummy provider URI are expected."
            )
        )

        return "\n".join(lines)

    def log(self, msg):
        qDebug(msg)

    def dump(self, detail=False, bbox=None):
        pass

    def show_status_message(self, msg, timeout):
        self.iface.mainWindow().statusBar().showMessage(msg, timeout)

    def show_bar_message(self, title, text, level, duration):
        self.iface.messageBar().pushMessage(title, text, level, duration)

    def transparency_changed(self, val):
        QgsProject.instance().setDirty(True)
        self.set_transparency(val)
        self.repaintRequested.emit()

    def setTransformContext(self, transform_context):
        pass


class FreehandRasterGeoreferencerLayerType(QgsPluginLayerType):
    def __init__(self, plugin):
        QgsPluginLayerType.__init__(self, FreehandRasterGeoreferencerLayer.LAYER_TYPE)
        self.plugin = plugin

    def createLayer(self):
        return FreehandRasterGeoreferencerLayer(self.plugin, None, "", None)

    def showLayerProperties(self, layer):
        from .propertiesdialog import PropertiesDialog

        dialog = PropertiesDialog(layer, parent=self.plugin.iface.mainWindow())
        dialog.horizontalSlider_Transparency.valueChanged.connect(
            layer.transparency_changed
        )
        dialog.spinBox_Transparency.valueChanged.connect(layer.transparency_changed)

        try:
            dialog.exec()
        finally:
            # Disconnect layer signals before releasing the temporary dialog.
            dialog.horizontalSlider_Transparency.valueChanged.disconnect(
                layer.transparency_changed
            )
            dialog.spinBox_Transparency.valueChanged.disconnect(
                layer.transparency_changed
            )
            dialog.deleteLater()
        return True


class FreehandRasterGeoreferencerLayerProvider(QgsDataProvider):
    def __init__(self, layer):
        QgsDataProvider.__init__(self, "dummyURI")
        self.layer = layer

    def name(self):
        return "FreehandRasterGeoreferencerLayerProvider"

    def description(self):
        return "Freehand raster georeferencer layer provider"

    def isValid(self):
        return True

    def crs(self):
        return self.layer.crs()

    def extent(self):
        return self.layer.extent()


class FreehandRasterGeoreferencerLayerRenderer(QgsMapLayerRenderer):
    """
    Custom renderer: in QGIS3 no implementation is provided for
    QgsPluginLayers
    """

    def __init__(self, layer, renderer_context):
        QgsMapLayerRenderer.__init__(self, layer.id())
        self.layer = layer
        self.renderer_context = renderer_context

    def render(self):
        # same implementation as for QGIS2
        return self.layer.draw(self.renderer_context)

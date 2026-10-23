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

import math
from operator import itemgetter

from qgis.core import Qgis, QgsGeometry, QgsPointXY
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication, QInputDialog, QMessageBox

from .rastershadowmapcanvasitem import RasterShadowMapCanvasItem
from .utils import tryfloat


def event_pos(event):
    return event.position().toPoint()


def is_layer_visible(iface, layer):
    # TODO Really ???? See if there is something simpler
    vl = iface.layerTreeView().layerTreeModel().rootGroup().findLayer(layer)
    return vl.itemVisibilityChecked()


def set_layer_visible(iface, layer, visible):
    vl = iface.layerTreeView().layerTreeModel().rootGroup().findLayer(layer)
    vl.setItemVisibilityChecked(visible)


class MoveRasterMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.raster_shadow = RasterShadowMapCanvasItem(self.canvas)

        self.rubber_band_displacement = QgsRubberBand(
            self.canvas, Qgis.GeometryType.Line
        )
        self.rubber_band_displacement.setColor(Qt.GlobalColor.red)
        self.rubber_band_displacement.setWidth(1)

        self.rubber_band_extent = QgsRubberBand(self.canvas, Qgis.GeometryType.Line)
        self.rubber_band_extent.setColor(Qt.GlobalColor.red)
        self.rubber_band_extent.setWidth(1)

        self.is_layer_visible = True

        self.reset()

    def set_layer(self, layer):
        self.layer = layer

    def reset(self):
        self.start_point = self.end_point = None
        self.is_emitting_point = False
        self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        self.raster_shadow.reset()
        self.layer = None

    def canvasPressEvent(self, e):
        self.start_point = self.toMapCoordinates(event_pos(e))
        self.end_point = self.start_point
        self.is_emitting_point = True
        self.original_center = self.layer.center
        # this tool do the displacement itself TODO update so it is done by
        # transformed coordinates + new center)
        self.original_corner_points = self.layer.transformed_corner_coordinates(
            *self.layer.transform_parameters()
        )

        self.is_layer_visible = is_layer_visible(self.iface, self.layer)
        set_layer_visible(self.iface, self.layer, False)

        self.show_displacement(self.start_point, self.end_point)
        self.layer.history.append({"action": "move", "center": self.layer.center})

    def canvasReleaseEvent(self, e):
        self.is_emitting_point = False

        self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        self.raster_shadow.reset()

        x = self.original_center.x() + self.end_point.x() - self.start_point.x()
        y = self.original_center.y() + self.end_point.y() - self.start_point.y()
        self.layer.set_center(QgsPointXY(x, y))

        set_layer_visible(self.iface, self.layer, self.is_layer_visible)
        self.layer.repaint()

        self.layer.commit_transform_parameters()

    def canvasMoveEvent(self, e):
        if not self.is_emitting_point:
            return

        self.end_point = self.toMapCoordinates(event_pos(e))
        self.show_displacement(self.start_point, self.end_point)

    def show_displacement(self, start_point, end_point):
        self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
        point1 = QgsPointXY(start_point.x(), start_point.y())
        point2 = QgsPointXY(end_point.x(), end_point.y())
        self.rubber_band_displacement.addPoint(point1, False)
        self.rubber_band_displacement.addPoint(point2, True)  # true to update canvas
        self.rubber_band_displacement.show()

        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        for point in self.original_corner_points:
            self._add_displacement_to_point(self.rubber_band_extent, point, False)
        # for closing
        self._add_displacement_to_point(
            self.rubber_band_extent, self.original_corner_points[0], True
        )
        self.rubber_band_extent.show()

        self.raster_shadow.reset(self.layer)
        self.raster_shadow.set_delta_displacement(
            self.end_point.x() - self.start_point.x(),
            self.end_point.y() - self.start_point.y(),
            True,
        )
        self.raster_shadow.show()

    def _add_displacement_to_point(self, rubber_band, point, do_update):
        x = point.x() + self.end_point.x() - self.start_point.x()
        y = point.y() + self.end_point.y() - self.start_point.y()
        self.rubber_band_extent.addPoint(QgsPointXY(x, y), do_update)


# move the mouse in the Y axis to rotate


class RotateRasterMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.raster_shadow = RasterShadowMapCanvasItem(self.canvas)

        self.rubber_band_extent = QgsRubberBand(self.canvas, Qgis.GeometryType.Line)
        self.rubber_band_extent.setColor(Qt.GlobalColor.red)
        self.rubber_band_extent.setWidth(1)

        # In case of rotation around pressed point (ctrl)
        # Use rubber_band for displaying an horizontal line.
        self.rubber_band_displacement = QgsRubberBand(
            self.canvas, Qgis.GeometryType.Line
        )
        self.rubber_band_displacement.setColor(Qt.GlobalColor.red)
        self.rubber_band_displacement.setWidth(1)

        self.reset()

    def set_layer(self, layer):
        self.layer = layer

    def reset(self):
        self.start_point = self.end_point = None
        self.is_emitting_point = False
        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
        self.raster_shadow.reset()
        self.layer = None

    def canvasPressEvent(self, e):
        self.start_y = event_pos(e).y()
        self.end_y = self.start_y
        self.is_emitting_point = True
        self.height = self.canvas.height()

        modifiers = QApplication.keyboardModifiers()
        self.is_rotation_around_point = bool(
            modifiers & Qt.KeyboardModifier.ControlModifier
        )
        self.start_point = self.toMapCoordinates(event_pos(e))
        self.end_point = self.start_point

        self.is_layer_visible = is_layer_visible(self.iface, self.layer)
        set_layer_visible(self.iface, self.layer, False)

        rotation = self.compute_rotation()
        self.show_rotation(rotation)

        self.layer.history.append({
            "action": "rotation",
            "rotation": self.layer.rotation,
            "center": self.layer.center,
        })  # rotation set

    def canvasReleaseEvent(self, e):
        self.is_emitting_point = False

        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
        self.raster_shadow.reset()

        rotation = self.compute_rotation()
        if self.is_rotation_around_point:
            self.layer.move_center_from_point_rotate(self.start_point, rotation, 1, 1)
        val = self.layer.rotation + rotation

        self.layer.set_rotation(val)

        set_layer_visible(self.iface, self.layer, self.is_layer_visible)
        self.layer.repaint()

        self.layer.commit_transform_parameters()

    def canvasMoveEvent(self, e):
        if not self.is_emitting_point:
            return

        self.end_y = event_pos(e).y()
        rotation = self.compute_rotation()
        self.show_rotation(rotation)

        self.end_point = self.toMapCoordinates(event_pos(e))

    def compute_rotation(self):
        if self.is_rotation_around_point:
            d_x = self.end_point.x() - self.start_point.x()
            d_y = self.end_point.y() - self.start_point.y()
            return math.degrees(math.atan2(-d_y, d_x))
        else:
            d_y = self.end_y - self.start_y
            return 90.0 * d_y / self.height

    def show_rotation(self, rotation):
        if self.is_rotation_around_point:
            corner_points = self.layer.transformed_corner_coordinates_from_point(
                self.start_point, rotation, 1, 1
            )

            self.raster_shadow.reset(self.layer)
            self.raster_shadow.set_delta_rotation_from_point(
                rotation, self.start_point, True
            )
            self.raster_shadow.show()

            self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
            point0 = QgsPointXY(self.start_point.x() + 10, self.start_point.y())
            point1 = QgsPointXY(self.start_point.x(), self.start_point.y())
            point2 = QgsPointXY(self.end_point.x(), self.end_point.y())
            self.rubber_band_displacement.addPoint(point0, False)
            self.rubber_band_displacement.addPoint(point1, False)
            self.rubber_band_displacement.addPoint(
                point2, True
            )  # true to update canvas
            self.rubber_band_displacement.show()
        else:
            center, original_rotation, x_scale, y_scale = (
                self.layer.transform_parameters()
            )
            new_rotation = rotation + original_rotation
            corner_points = self.layer.transformed_corner_coordinates(
                center, new_rotation, x_scale, y_scale
            )

            self.raster_shadow.reset(self.layer)
            self.raster_shadow.set_delta_rotation(rotation, True)
            self.raster_shadow.show()

        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        for point in corner_points:
            self.rubber_band_extent.addPoint(point, False)
        # for closing
        self.rubber_band_extent.addPoint(corner_points[0], True)
        self.rubber_band_extent.show()


# move the map in x or y axis to scale in x or y dimensions of the
# image (no rotation of the coordinate system)
class ScaleRasterMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.raster_shadow = RasterShadowMapCanvasItem(self.canvas)

        self.rubber_band_extent = QgsRubberBand(self.canvas, Qgis.GeometryType.Line)
        self.rubber_band_extent.setColor(Qt.GlobalColor.red)
        self.rubber_band_extent.setWidth(1)

        self.reset()

    def set_layer(self, layer):
        self.layer = layer

    def reset(self):
        self.start_point = self.end_point = None
        self.is_emitting_point = False
        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        self.raster_shadow.reset()
        self.layer = None

    def canvasPressEvent(self, e):
        pressed_button = e.button()
        if pressed_button == Qt.MouseButton.LeftButton:
            self.start_point = event_pos(e)
            self.end_point = self.start_point
            self.is_emitting_point = True
            self.height = float(self.canvas.height())
            self.width = float(self.canvas.width())

            modifiers = QApplication.keyboardModifiers()
            self.is_keep_relative_scale = bool(
                modifiers & Qt.KeyboardModifier.ControlModifier
            )

            self.is_layer_visible = is_layer_visible(self.iface, self.layer)
            set_layer_visible(self.iface, self.layer, False)

            scaling = self.compute_scaling()
            self.show_scaling(*scaling)
        self.layer.history.append({
            "action": "scale",
            "x_scale": self.layer.x_scale,
            "y_scale": self.layer.y_scale,
        })

    def canvasReleaseEvent(self, e):
        pressed_button = e.button()
        if pressed_button == Qt.MouseButton.LeftButton:
            self.is_emitting_point = False

            self.rubber_band_extent.reset(Qgis.GeometryType.Line)
            self.raster_shadow.reset()

            x_scale, y_scale = self.compute_scaling()
            self.layer.set_scale(
                x_scale * self.layer.x_scale, y_scale * self.layer.y_scale
            )

            set_layer_visible(self.iface, self.layer, self.is_layer_visible)
        elif pressed_button == Qt.MouseButton.RightButton:
            number, ok = QInputDialog.getText(
                self.iface.mainWindow(),
                "Scale & DPI",
                "Enter scale,dpi (e.g. 3000,96)",
            )
            if not ok:
                self.layer.history.pop()
                return
            scales = number.split(",")
            if len(scales) != 2:
                self.layer.history.pop()
                QMessageBox.information(
                    self.iface.mainWindow(), "Error", "Must be 2 numbers"
                )
                return
            scale = tryfloat(scales[0])
            dpi = tryfloat(scales[1])
            if scale and dpi:
                x_scale = scale / (dpi / 0.0254)
                y_scale = x_scale
            else:
                self.layer.history.pop()
                QMessageBox.information(
                    self.iface.mainWindow(),
                    "Error",
                    "Bad format: Must be scale,dpi (e.g. 3000,96)",
                )
                return

            self.layer.set_scale(x_scale, y_scale)

        self.layer.repaint()
        self.layer.commit_transform_parameters()

    def canvasMoveEvent(self, e):
        if not self.is_emitting_point:
            return

        self.end_point = event_pos(e)
        scaling = self.compute_scaling()
        self.show_scaling(*scaling)

    def compute_scaling(self):
        d_x = -(self.end_point.x() - self.start_point.x())
        d_y = self.end_point.y() - self.start_point.y()
        x_scale = 1.0 - (d_x / (self.width * 1.1))
        y_scale = 1.0 - (d_y / (self.height * 1.1))

        if self.is_keep_relative_scale:
            # keep same scale in both dimensions
            return (x_scale, x_scale)
        else:
            return (x_scale, y_scale)

    def show_scaling(self, x_scale, y_scale):
        if x_scale == 0 and y_scale == 0:
            return

        center, rotation, original_x_scale, original_y_scale = (
            self.layer.transform_parameters()
        )
        new_x_scale = x_scale * original_x_scale
        new_y_scale = y_scale * original_y_scale
        corner_points = self.layer.transformed_corner_coordinates(
            center, rotation, new_x_scale, new_y_scale
        )

        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        for point in corner_points:
            self.rubber_band_extent.addPoint(point, False)
        # for closing
        self.rubber_band_extent.addPoint(corner_points[0], True)
        self.rubber_band_extent.show()

        self.raster_shadow.reset(self.layer)
        self.raster_shadow.set_delta_scale(x_scale, y_scale, True)
        self.raster_shadow.show()


class AdjustRasterMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.raster_shadow = RasterShadowMapCanvasItem(self.canvas)

        self.rubber_band_extent = QgsRubberBand(self.canvas, Qgis.GeometryType.Line)
        self.rubber_band_extent.setColor(Qt.GlobalColor.red)
        self.rubber_band_extent.setWidth(1)

        self.rubber_band_adjust_side = QgsRubberBand(
            self.canvas, Qgis.GeometryType.Line
        )
        self.rubber_band_adjust_side.setColor(Qt.GlobalColor.red)
        self.rubber_band_adjust_side.setWidth(3)

        self.reset()

    def set_layer(self, layer):
        self.layer = layer

    def reset(self):
        self.start_point = self.end_point = None
        self.is_emitting_point = False
        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        self.rubber_band_adjust_side.reset(Qgis.GeometryType.Line)
        self.raster_shadow.reset()
        self.layer = None

    def canvasPressEvent(self, e):
        # find the side of the rectangle closest to the click and some data
        # necessary to compute the new cneter and scale
        top_left, top_right, bottom_right, bottom_left = self.layer.corner_coordinates()
        top = [top_left, top_right]
        right = [bottom_right, top_right]
        bottom = [bottom_right, bottom_left]
        left = [bottom_left, top_left]

        click = QgsGeometry.fromPointXY(self.toMapCoordinates(event_pos(e)))

        # order is important (for reference_side)
        sides = [top, right, bottom, left]
        distances = [click.distance(QgsGeometry.fromPolylineXY(side)) for side in sides]
        self.index_side = self.min_distance(distances)
        self.side = sides[self.index_side]
        self.side_point = self.center(self.side)
        self.vector = self.direction_vector(self.side)
        # side that does not move (opposite of index_side)
        self.reference_side = sides[(self.index_side + 2) % 4]
        self.reference_point = self.center(self.reference_side)
        self.reference_distance = self.distance(self.side_point, self.reference_point)
        self.is_x_scale = self.index_side % 2 == 1

        self.start_point = click.asPoint()
        self.end_point = self.start_point
        self.is_emitting_point = True

        self.is_layer_visible = is_layer_visible(self.iface, self.layer)
        set_layer_visible(self.iface, self.layer, False)

        adjustment = self.compute_adjustment()
        self.show_adjustment(*adjustment)
        self.layer.history.append({
            "action": "adjust",
            "center": self.layer.center,
            "x_scale": self.layer.x_scale,
            "y_scale": self.layer.y_scale,
        })

    def min_distance(self, distances):
        sorted_distances = [
            i[0] for i in sorted(enumerate(distances), key=itemgetter(1))
        ]
        # first is min
        return sorted_distances[0]

    def direction_vector(self, side):
        side_center = self.center(side)
        layer_center = self.layer.center
        vector = [
            side_center.x() - layer_center.x(),
            side_center.y() - layer_center.y(),
        ]
        norm = math.sqrt(vector[0] ** 2 + vector[1] ** 2)
        normed_vector = [vector[0] / norm, vector[1] / norm]
        return normed_vector

    def center(self, side):
        return QgsPointXY(
            (side[0].x() + side[1].x()) / 2, (side[0].y() + side[1].y()) / 2
        )

    def distance(self, pt1, pt2):
        return math.sqrt((pt1.x() - pt2.x()) ** 2 + (pt1.y() - pt2.y()) ** 2)

    def canvasReleaseEvent(self, e):
        self.is_emitting_point = False

        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        self.rubber_band_adjust_side.reset(Qgis.GeometryType.Line)
        self.raster_shadow.reset()

        center, x_scale, y_scale = self.compute_adjustment()
        self.layer.set_center(center)
        self.layer.set_scale(x_scale * self.layer.x_scale, y_scale * self.layer.y_scale)

        set_layer_visible(self.iface, self.layer, self.is_layer_visible)
        self.layer.repaint()

        self.layer.commit_transform_parameters()

    def canvasMoveEvent(self, e):
        if not self.is_emitting_point:
            return

        self.end_point = self.toMapCoordinates(event_pos(e))

        adjustment = self.compute_adjustment()
        self.show_adjustment(*adjustment)

    def compute_adjustment(self):
        d_x = self.end_point.x() - self.start_point.x()
        d_y = self.end_point.y() - self.start_point.y()
        # project on vector
        dp = d_x * self.vector[0] + d_y * self.vector[1]

        # do not go beyond 5% of the current size of side
        if dp < -0.95 * self.reference_distance:
            dp = -0.95 * self.reference_distance

        updated_side_point = QgsPointXY(
            self.side_point.x() + dp * self.vector[0],
            self.side_point.y() + dp * self.vector[1],
        )

        center = self.center([self.reference_point, updated_side_point])
        scale_factor = self.distance(self.reference_point, updated_side_point)
        if self.is_x_scale:
            x_scale = scale_factor / self.reference_distance
            y_scale = 1.0
        else:
            x_scale = 1.0
            y_scale = scale_factor / self.reference_distance

        return (center, x_scale, y_scale)

    def show_adjustment(self, center, x_scale, y_scale):
        _, rotation, original_x_scale, original_y_scale = (
            self.layer.transform_parameters()
        )
        new_x_scale = x_scale * original_x_scale
        new_y_scale = y_scale * original_y_scale
        corner_points = self.layer.transformed_corner_coordinates(
            center, rotation, new_x_scale, new_y_scale
        )

        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        for point in corner_points:
            self.rubber_band_extent.addPoint(point, False)
        # for closing
        self.rubber_band_extent.addPoint(corner_points[0], True)
        self.rubber_band_extent.show()

        # show rubberband for side
        # see def of index_side in init:
        # cornerpoints are (top_left, top_right, bottom_right, bottom_left)
        self.rubber_band_adjust_side.reset(Qgis.GeometryType.Line)
        self.rubber_band_adjust_side.addPoint(corner_points[self.index_side % 4], False)
        self.rubber_band_adjust_side.addPoint(
            corner_points[(self.index_side + 1) % 4], True
        )
        self.rubber_band_adjust_side.show()

        self.raster_shadow.reset(self.layer)
        dx = center.x() - self.layer.center.x()
        dy = center.y() - self.layer.center.y()
        self.raster_shadow.set_delta_displacement(dx, dy, False)
        self.raster_shadow.set_delta_scale(x_scale, y_scale, True)
        self.raster_shadow.show()


class GeorefRasterBy2PointsMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.raster_shadow = RasterShadowMapCanvasItem(self.canvas)

        self.first_point = None

        self.rubber_band_origin = QgsRubberBand(self.canvas, Qgis.GeometryType.Point)
        self.rubber_band_origin.setColor(Qt.GlobalColor.red)
        self.rubber_band_origin.setIcon(QgsRubberBand.ICON_CIRCLE)
        self.rubber_band_origin.setIconSize(7)
        self.rubber_band_origin.setWidth(2)

        self.rubber_band_displacement = QgsRubberBand(
            self.canvas, Qgis.GeometryType.Line
        )
        self.rubber_band_displacement.setColor(Qt.GlobalColor.red)
        self.rubber_band_displacement.setWidth(1)

        self.rubber_band_extent = QgsRubberBand(self.canvas, Qgis.GeometryType.Line)
        self.rubber_band_extent.setColor(Qt.GlobalColor.red)
        self.rubber_band_extent.setWidth(2)

        self.is_layer_visible = True

        self.reset()

    def set_layer(self, layer):
        self.layer = layer

    def reset(self):
        self.start_point = self.end_point = self.first_point = None
        self.is_emitting_point = False
        self.rubber_band_origin.reset(Qgis.GeometryType.Point)
        self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        self.raster_shadow.reset()
        self.layer = None

    def deactivate(self):
        QgsMapToolEmitPoint.deactivate(self)
        self.reset()

    def canvasPressEvent(self, e):
        if self.first_point is None:
            self.start_point = self.toMapCoordinates(event_pos(e))
            self.end_point = self.start_point
            self.is_emitting_point = True
            self.original_center = self.layer.center
            # this tool do the displacement itself TODO update so it is done by
            # transformed coordinates + new center)
            self.original_corner_points = self.layer.transformed_corner_coordinates(
                *self.layer.transform_parameters()
            )

            self.is_layer_visible = is_layer_visible(self.iface, self.layer)
            set_layer_visible(self.iface, self.layer, False)

            self.show_displacement(self.start_point, self.end_point)
            self.layer.history.append({
                "action": "2pointsA",
                "center": self.layer.center,
            })
        else:
            self.start_point = self.toMapCoordinates(event_pos(e))
            self.end_point = self.start_point

            self.start_y = event_pos(e).y()
            self.end_y = self.start_y
            self.is_emitting_point = True
            self.height = self.canvas.height()

            self.is_layer_visible = is_layer_visible(self.iface, self.layer)
            set_layer_visible(self.iface, self.layer, False)

            rotation = self.compute_rotation()
            x_scale = y_scale = self.compute_scale()
            self.show_rotation_scale(rotation, x_scale, y_scale)
            self.layer.history.append({
                "action": "2pointsB",
                "center": self.layer.center,
                "x_scale": self.layer.x_scale,
                "y_scale": self.layer.y_scale,
                "rotation": self.layer.rotation,
            })

    def canvasReleaseEvent(self, e):
        self.is_emitting_point = False

        self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        self.raster_shadow.reset()

        if self.first_point is None:
            x = self.original_center.x() + self.end_point.x() - self.start_point.x()
            y = self.original_center.y() + self.end_point.y() - self.start_point.y()
            self.layer.set_center(QgsPointXY(x, y))
            self.first_point = self.end_point

            set_layer_visible(self.iface, self.layer, self.is_layer_visible)
            self.layer.repaint()

            self.layer.commit_transform_parameters()
        else:
            rotation = self.compute_rotation()
            x_scale = y_scale = self.compute_scale()
            self.layer.move_center_from_point_rotate(
                self.first_point, rotation, x_scale, y_scale
            )
            self.layer.set_rotation(self.layer.rotation + rotation)
            self.layer.set_scale(
                self.layer.x_scale * x_scale, self.layer.y_scale * y_scale
            )

            set_layer_visible(self.iface, self.layer, self.is_layer_visible)
            self.layer.repaint()

            self.layer.commit_transform_parameters()

            self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
            self.rubber_band_extent.reset(Qgis.GeometryType.Line)
            self.rubber_band_origin.reset(Qgis.GeometryType.Point)
            self.raster_shadow.reset()

            self.first_point = None
            self.start_point = self.end_point = None

    def canvasMoveEvent(self, e):
        if not self.is_emitting_point:
            return

        self.end_point = self.toMapCoordinates(event_pos(e))

        if self.first_point is None:
            self.show_displacement(self.start_point, self.end_point)
        else:
            self.end_y = event_pos(e).y()
            rotation = self.compute_rotation()
            x_scale = y_scale = self.compute_scale()
            self.show_rotation_scale(rotation, x_scale, y_scale)

    def compute_rotation(self):
        # The angle is the difference between angle
        # horizontal/end_point-first_point and horizontal/start_point-first_point.
        d_x0 = self.start_point.x() - self.first_point.x()
        d_y0 = self.start_point.y() - self.first_point.y()
        d_x = self.end_point.x() - self.first_point.x()
        d_y = self.end_point.y() - self.first_point.y()
        return math.degrees(math.atan2(-d_y, d_x) - math.atan2(-d_y0, d_x0))

    def compute_scale(self):
        # The scale is the ratio between end_point-first_point and
        # start_point-first_point.
        d_x0 = self.start_point.x() - self.first_point.x()
        d_y0 = self.start_point.y() - self.first_point.y()
        d_x = self.end_point.x() - self.first_point.x()
        d_y = self.end_point.y() - self.first_point.y()
        return math.sqrt((d_x * d_x + d_y * d_y) / (d_x0 * d_x0 + d_y0 * d_y0))

    def show_rotation_scale(self, rotation, x_scale, y_scale):
        center, _, _, _ = self.layer.transform_parameters()
        # new_rotation = rotation + original_rotation
        corner_points = self.layer.transformed_corner_coordinates_from_point(
            self.first_point, rotation, x_scale, y_scale
        )

        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        for point in corner_points:
            self.rubber_band_extent.addPoint(point, False)
        self.rubber_band_extent.addPoint(corner_points[0], True)
        self.rubber_band_extent.show()

        # Calculate the displacement of the center due to the rotation from
        # another point.
        new_center_dx = (corner_points[0].x() + corner_points[2].x()) / 2 - center.x()
        new_center_dy = (corner_points[0].y() + corner_points[2].y()) / 2 - center.y()
        self.raster_shadow.reset(self.layer)
        self.raster_shadow.set_delta_displacement(new_center_dx, new_center_dy, False)
        self.raster_shadow.set_delta_scale(x_scale, y_scale, False)
        self.raster_shadow.set_delta_rotation(rotation, True)
        self.raster_shadow.show()

        self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
        point0 = QgsPointXY(self.start_point.x(), self.start_point.y())
        point1 = QgsPointXY(self.first_point.x(), self.first_point.y())
        point2 = QgsPointXY(self.end_point.x(), self.end_point.y())
        self.rubber_band_displacement.addPoint(point0, False)
        self.rubber_band_displacement.addPoint(point1, False)
        self.rubber_band_displacement.addPoint(point2, True)  # true to update canvas
        self.rubber_band_displacement.show()

    def show_displacement(self, start_point, end_point):
        self.rubber_band_origin.reset(Qgis.GeometryType.Point)
        self.rubber_band_origin.addPoint(end_point, True)
        self.rubber_band_origin.show()

        self.rubber_band_displacement.reset(Qgis.GeometryType.Line)
        point1 = QgsPointXY(start_point.x(), start_point.y())
        point2 = QgsPointXY(end_point.x(), end_point.y())
        self.rubber_band_displacement.addPoint(point1, False)
        self.rubber_band_displacement.addPoint(point2, True)  # true to update canvas
        self.rubber_band_displacement.show()

        self.rubber_band_extent.reset(Qgis.GeometryType.Line)
        for point in self.original_corner_points:
            self._add_displacement_to_point(self.rubber_band_extent, point, False)
        # for closing
        self._add_displacement_to_point(
            self.rubber_band_extent, self.original_corner_points[0], True
        )
        self.rubber_band_extent.show()

        self.raster_shadow.reset(self.layer)
        self.raster_shadow.set_delta_displacement(
            self.end_point.x() - self.start_point.x(),
            self.end_point.y() - self.start_point.y(),
            True,
        )
        self.raster_shadow.show()

    def _add_displacement_to_point(self, rubber_band, point, do_update):
        x = point.x() + self.end_point.x() - self.start_point.x()
        y = point.y() + self.end_point.y() - self.start_point.y()
        self.rubber_band_extent.addPoint(QgsPointXY(x, y), do_update)

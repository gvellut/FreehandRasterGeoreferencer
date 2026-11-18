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

from qgis.core import QgsPointXY, QgsRectangle
from qgis.gui import QgsMapCanvasItem
from qgis.PyQt.QtCore import QPointF, QRectF
from qgis.PyQt.QtGui import QPainter


class RasterShadowMapCanvasItem(QgsMapCanvasItem):
    def __init__(self, canvas):
        QgsMapCanvasItem.__init__(self, canvas)

        self.canvas = canvas
        self.reset()

    def reset(self, layer=None):
        self.layer = layer
        self.setVisible(False)

        self.dx = 0
        self.dy = 0
        self.drotation = 0
        self.fxscale = 1
        self.fyscale = 1

    def set_delta_displacement(self, dx, dy, do_update):
        self.dx = dx
        self.dy = dy
        if do_update:
            self.setVisible(self.layer is None)
            self.update_rect()
            self.update()

    def set_delta_rotation(self, rotation, do_update):
        self.drotation = rotation
        if do_update:
            self.update_rect()
            self.update()

    def set_delta_rotation_from_point(self, rotation, start_point, do_update):
        # Rotation around a point other than center of raster
        self.drotation = rotation
        if do_update:
            self.update_rect_from_point(start_point)
            self.update()

    def set_delta_scale(self, xscale, yscale, do_update):
        self.fxscale = xscale
        self.fyscale = yscale
        if do_update:
            self.update_rect()
            self.update()

    def update_rect(self):
        top_left, top_right, bottom_right, bottom_left = self.corner_coordinates()

        left = min(top_left.x(), top_right.x(), bottom_right.x(), bottom_left.x())
        right = max(top_left.x(), top_right.x(), bottom_right.x(), bottom_left.x())
        top = max(top_left.y(), top_right.y(), bottom_right.y(), bottom_left.y())
        bottom = min(top_left.y(), top_right.y(), bottom_right.y(), bottom_left.y())

        self.setRect(QgsRectangle(left, bottom, right, top))

    def update_rect_from_point(self, start_point):
        top_left, top_right, bottom_right, bottom_left = (
            self.corner_coordinates_from_point(start_point)
        )

        left = min(top_left.x(), top_right.x(), bottom_right.x(), bottom_left.x())
        right = max(top_left.x(), top_right.x(), bottom_right.x(), bottom_left.x())
        top = max(top_left.y(), top_right.y(), bottom_right.y(), bottom_left.y())
        bottom = min(top_left.y(), top_right.y(), bottom_right.y(), bottom_left.y())

        self.setRect(QgsRectangle(left, bottom, right, top))

    def corner_coordinates(self):
        center = QgsPointXY(
            self.layer.center.x() + self.dx, self.layer.center.y() + self.dy
        )
        return self.layer.transformed_corner_coordinates(
            center,
            self.layer.rotation + self.drotation,
            self.layer.x_scale * self.fxscale,
            self.layer.y_scale * self.fyscale,
        )

    def corner_coordinates_from_point(self, start_point):
        return self.layer.transformed_corner_coordinates_from_point(
            start_point, self.drotation, 1, 1
        )

    def paint(self, painter, options, widget):
        painter.save()
        self.prepare_style(painter)
        self.draw_raster(painter)
        painter.restore()

    def draw_raster(self, painter):
        map_units_per_pixel = self.canvas.mapUnitsPerPixel()

        scale_x = self.layer.x_scale * self.fxscale / map_units_per_pixel
        scale_y = self.layer.y_scale * self.fyscale / map_units_per_pixel

        rect = QRectF(
            QPointF(-self.layer.image.width() / 2.0, -self.layer.image.height() / 2.0),
            QPointF(self.layer.image.width() / 2.0, self.layer.image.height() / 2.0),
        )
        target_rect = self.boundingRect()

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # draw the image on the canvas item rectangle
        # center displacement already taken into account in canvas
        # item rectangle so no update
        painter.translate(target_rect.center())
        painter.rotate(self.layer.rotation + self.drotation)
        painter.scale(scale_x, scale_y)
        painter.drawImage(rect, self.layer.image)

    def prepare_style(self, painter):
        painter.setOpacity(min(0.5, 1 - self.layer.transparency / 100.0))

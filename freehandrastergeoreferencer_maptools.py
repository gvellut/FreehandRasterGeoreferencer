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

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QInputDialog, QMessageBox
from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand

from .rastershadowmapcanvasitem import RasterShadowMapCanvasItem
from .utils import tryfloat


def isLayerVisible(iface, layer):
    # TODO Really ???? See if there is something simpler
    vl = iface.layerTreeView().layerTreeModel().rootGroup().findLayer(layer)
    return vl.itemVisibilityChecked()


def setLayerVisible(iface, layer, visible):
    vl = iface.layerTreeView().layerTreeModel().rootGroup().findLayer(layer)
    vl.setItemVisibilityChecked(visible)


class MoveRasterMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.rasterShadow = RasterShadowMapCanvasItem(self.canvas)

        self.rubberBandDisplacement = QgsRubberBand(
            self.canvas, QgsWkbTypes.LineGeometry
        )
        self.rubberBandDisplacement.setColor(Qt.red)
        self.rubberBandDisplacement.setWidth(1)

        self.rubberBandExtent = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubberBandExtent.setColor(Qt.red)
        self.rubberBandExtent.setWidth(1)

        self.isLayerVisible = True

        self.reset()

    def setLayer(self, layer):
        self.layer = layer

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        self.rasterShadow.reset()
        self.layer = None

    def canvasPressEvent(self, e):
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.originalCenter = self.layer.center
        # this tool do the displacement itself TODO update so it is done by
        # transformed coordinates + new center)
        self.originalCornerPoints = self.layer.transformedCornerCoordinates(
            *self.layer.transformParameters()
        )

        self.isLayerVisible = isLayerVisible(self.iface, self.layer)
        setLayerVisible(self.iface, self.layer, False)

        self.showDisplacement(self.startPoint, self.endPoint)
        self.layer.history.append({"action": "move", "center": self.layer.center})

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False

        self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        self.rasterShadow.reset()

        x = self.originalCenter.x() + self.endPoint.x() - self.startPoint.x()
        y = self.originalCenter.y() + self.endPoint.y() - self.startPoint.y()
        self.layer.setCenter(QgsPointXY(x, y))

        setLayerVisible(self.iface, self.layer, self.isLayerVisible)
        self.layer.repaint()

        self.layer.commitTransformParameters()

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())
        self.showDisplacement(self.startPoint, self.endPoint)

    def showDisplacement(self, startPoint, endPoint):
        self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(endPoint.x(), endPoint.y())
        self.rubberBandDisplacement.addPoint(point1, False)
        self.rubberBandDisplacement.addPoint(point2, True)  # true to update canvas
        self.rubberBandDisplacement.show()

        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        for point in self.originalCornerPoints:
            self._addDisplacementToPoint(self.rubberBandExtent, point, False)
        # for closing
        self._addDisplacementToPoint(
            self.rubberBandExtent, self.originalCornerPoints[0], True
        )
        self.rubberBandExtent.show()

        self.rasterShadow.reset(self.layer)
        self.rasterShadow.setDeltaDisplacement(
            self.endPoint.x() - self.startPoint.x(),
            self.endPoint.y() - self.startPoint.y(),
            True,
        )
        self.rasterShadow.show()

    def _addDisplacementToPoint(self, rubberBand, point, doUpdate):
        x = point.x() + self.endPoint.x() - self.startPoint.x()
        y = point.y() + self.endPoint.y() - self.startPoint.y()
        self.rubberBandExtent.addPoint(QgsPointXY(x, y), doUpdate)


# move the mouse in the Y axis to rotate


class RotateRasterMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.rasterShadow = RasterShadowMapCanvasItem(self.canvas)

        self.rubberBandExtent = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubberBandExtent.setColor(Qt.red)
        self.rubberBandExtent.setWidth(1)

        # In case of rotation around pressed point (ctrl)
        # Use rubberBand for displaying an horizontal line.
        self.rubberBandDisplacement = QgsRubberBand(
            self.canvas, QgsWkbTypes.LineGeometry
        )
        self.rubberBandDisplacement.setColor(Qt.red)
        self.rubberBandDisplacement.setWidth(1)

        self.reset()

    def setLayer(self, layer):
        self.layer = layer

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
        self.rasterShadow.reset()
        self.layer = None

    def canvasPressEvent(self, e):
        self.startY = e.pos().y()
        self.endY = self.startY
        self.isEmittingPoint = True
        self.height = self.canvas.height()

        modifiers = QApplication.keyboardModifiers()
        self.isRotationAroundPoint = bool(modifiers & Qt.ControlModifier)
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint

        self.isLayerVisible = isLayerVisible(self.iface, self.layer)
        setLayerVisible(self.iface, self.layer, False)

        rotation = self.computeRotation()
        self.showRotation(rotation)

        self.layer.history.append(
            {
                "action": "rotation",
                "rotation": self.layer.rotation,
                "center": self.layer.center,
            }
        )  # rotation set

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False

        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
        self.rasterShadow.reset()

        rotation = self.computeRotation()
        if self.isRotationAroundPoint:
            self.layer.moveCenterFromPointRotate(self.startPoint, rotation, 1, 1)
        val = self.layer.rotation + rotation

        self.layer.setRotation(val)

        setLayerVisible(self.iface, self.layer, self.isLayerVisible)
        self.layer.repaint()

        self.layer.commitTransformParameters()

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endY = e.pos().y()
        rotation = self.computeRotation()
        self.showRotation(rotation)

        self.endPoint = self.toMapCoordinates(e.pos())

    def computeRotation(self):
        if self.isRotationAroundPoint:
            dX = self.endPoint.x() - self.startPoint.x()
            dY = self.endPoint.y() - self.startPoint.y()
            return math.degrees(math.atan2(-dY, dX))
        else:
            dY = self.endY - self.startY
            return 90.0 * dY / self.height

    def showRotation(self, rotation):
        if self.isRotationAroundPoint:
            cornerPoints = self.layer.transformedCornerCoordinatesFromPoint(
                self.startPoint, rotation, 1, 1
            )

            self.rasterShadow.reset(self.layer)
            self.rasterShadow.setDeltaRotationFromPoint(rotation, self.startPoint, True)
            self.rasterShadow.show()

            self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
            point0 = QgsPointXY(self.startPoint.x() + 10, self.startPoint.y())
            point1 = QgsPointXY(self.startPoint.x(), self.startPoint.y())
            point2 = QgsPointXY(self.endPoint.x(), self.endPoint.y())
            self.rubberBandDisplacement.addPoint(point0, False)
            self.rubberBandDisplacement.addPoint(point1, False)
            self.rubberBandDisplacement.addPoint(point2, True)  # true to update canvas
            self.rubberBandDisplacement.show()
        else:
            center, originalRotation, xScale, yScale = self.layer.transformParameters()
            newRotation = rotation + originalRotation
            cornerPoints = self.layer.transformedCornerCoordinates(
                center, newRotation, xScale, yScale
            )

            self.rasterShadow.reset(self.layer)
            self.rasterShadow.setDeltaRotation(rotation, True)
            self.rasterShadow.show()

        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        for point in cornerPoints:
            self.rubberBandExtent.addPoint(point, False)
        # for closing
        self.rubberBandExtent.addPoint(cornerPoints[0], True)
        self.rubberBandExtent.show()


# move the map in x or y axis to scale in x or y dimensions of the
# image (no rotation of the coordinate system)
class ScaleRasterMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.rasterShadow = RasterShadowMapCanvasItem(self.canvas)

        self.rubberBandExtent = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubberBandExtent.setColor(Qt.red)
        self.rubberBandExtent.setWidth(1)

        self.reset()

    def setLayer(self, layer):
        self.layer = layer

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        self.rasterShadow.reset()
        self.layer = None

    def canvasPressEvent(self, e):
        pressed_button = e.button()
        if pressed_button == 1:
            self.startPoint = e.pos()
            self.endPoint = self.startPoint
            self.isEmittingPoint = True
            self.height = float(self.canvas.height())
            self.width = float(self.canvas.width())

            modifiers = QApplication.keyboardModifiers()
            self.isKeepRelativeScale = bool(modifiers & Qt.ControlModifier)

            self.isLayerVisible = isLayerVisible(self.iface, self.layer)
            setLayerVisible(self.iface, self.layer, False)

            scaling = self.computeScaling()
            self.showScaling(*scaling)
        self.layer.history.append(
            {
                "action": "scale",
                "xScale": self.layer.xScale,
                "yScale": self.layer.yScale,
            }
        )

    def canvasReleaseEvent(self, e):
        pressed_button = e.button()
        if pressed_button == 1:
            self.isEmittingPoint = False

            self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
            self.rasterShadow.reset()

            xScale, yScale = self.computeScaling()
            self.layer.setScale(xScale * self.layer.xScale, yScale * self.layer.yScale)

            setLayerVisible(self.iface, self.layer, self.isLayerVisible)
        elif pressed_button == 2:
            number, ok = QInputDialog.getText(
                None, "Scale & DPI", "Enter scale,dpi (e.g. 3000,96)"
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
                xScale = scale / (dpi / 0.0254)
                yScale = xScale
            else:
                self.layer.history.pop()
                QMessageBox.information(
                    self.iface.mainWindow(),
                    "Error",
                    "Bad format: Must be scale,dpi (e.g. 3000,96)",
                )
                return

            self.layer.setScale(xScale, yScale)

        self.layer.repaint()
        self.layer.commitTransformParameters()

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = e.pos()
        scaling = self.computeScaling()
        self.showScaling(*scaling)

    def computeScaling(self):
        dX = -(self.endPoint.x() - self.startPoint.x())
        dY = self.endPoint.y() - self.startPoint.y()
        xScale = 1.0 - (dX / (self.width * 1.1))
        yScale = 1.0 - (dY / (self.height * 1.1))

        if self.isKeepRelativeScale:
            # keep same scale in both dimensions
            return (xScale, xScale)
        else:
            return (xScale, yScale)

    def showScaling(self, xScale, yScale):
        if xScale == 0 and yScale == 0:
            return

        center, rotation, originalXScale, originalYScale = (
            self.layer.transformParameters()
        )
        newXScale = xScale * originalXScale
        newYScale = yScale * originalYScale
        cornerPoints = self.layer.transformedCornerCoordinates(
            center, rotation, newXScale, newYScale
        )

        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        for point in cornerPoints:
            self.rubberBandExtent.addPoint(point, False)
        # for closing
        self.rubberBandExtent.addPoint(cornerPoints[0], True)
        self.rubberBandExtent.show()

        self.rasterShadow.reset(self.layer)
        self.rasterShadow.setDeltaScale(xScale, yScale, True)
        self.rasterShadow.show()


class AdjustRasterMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.rasterShadow = RasterShadowMapCanvasItem(self.canvas)

        self.rubberBandExtent = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubberBandExtent.setColor(Qt.red)
        self.rubberBandExtent.setWidth(1)

        self.rubberBandAdjustSide = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubberBandAdjustSide.setColor(Qt.red)
        self.rubberBandAdjustSide.setWidth(3)

        self.reset()

    def setLayer(self, layer):
        self.layer = layer

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandAdjustSide.reset(QgsWkbTypes.LineGeometry)
        self.rasterShadow.reset()
        self.layer = None

    def canvasPressEvent(self, e):
        # find the side of the rectangle closest to the click and some data
        # necessary to compute the new cneter and scale
        topLeft, topRight, bottomRight, bottomLeft = self.layer.cornerCoordinates()
        top = [topLeft, topRight]
        right = [bottomRight, topRight]
        bottom = [bottomRight, bottomLeft]
        left = [bottomLeft, topLeft]

        click = QgsGeometry.fromPointXY(self.toMapCoordinates(e.pos()))

        # order is important (for referenceSide)
        sides = [top, right, bottom, left]
        distances = [click.distance(QgsGeometry.fromPolylineXY(side)) for side in sides]
        self.indexSide = self.minDistance(distances)
        self.side = sides[self.indexSide]
        self.sidePoint = self.center(self.side)
        self.vector = self.directionVector(self.side)
        # side that does not move (opposite of indexSide)
        self.referenceSide = sides[(self.indexSide + 2) % 4]
        self.referencePoint = self.center(self.referenceSide)
        self.referenceDistance = self.distance(self.sidePoint, self.referencePoint)
        self.isXScale = self.indexSide % 2 == 1

        self.startPoint = click.asPoint()
        self.endPoint = self.startPoint
        self.isEmittingPoint = True

        self.isLayerVisible = isLayerVisible(self.iface, self.layer)
        setLayerVisible(self.iface, self.layer, False)

        adjustment = self.computeAdjustment()
        self.showAdjustment(*adjustment)
        self.layer.history.append(
            {
                "action": "adjust",
                "center": self.layer.center,
                "xScale": self.layer.xScale,
                "yScale": self.layer.yScale,
            }
        )

    def minDistance(self, distances):
        sortedDistances = [
            i[0] for i in sorted(enumerate(distances), key=itemgetter(1))
        ]
        # first is min
        return sortedDistances[0]

    def directionVector(self, side):
        sideCenter = self.center(side)
        layerCenter = self.layer.center
        vector = [sideCenter.x() - layerCenter.x(), sideCenter.y() - layerCenter.y()]
        norm = math.sqrt(vector[0] ** 2 + vector[1] ** 2)
        normedVector = [vector[0] / norm, vector[1] / norm]
        return normedVector

    def center(self, side):
        return QgsPointXY(
            (side[0].x() + side[1].x()) / 2, (side[0].y() + side[1].y()) / 2
        )

    def distance(self, pt1, pt2):
        return math.sqrt((pt1.x() - pt2.x()) ** 2 + (pt1.y() - pt2.y()) ** 2)

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False

        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandAdjustSide.reset(QgsWkbTypes.LineGeometry)
        self.rasterShadow.reset()

        center, xScale, yScale = self.computeAdjustment()
        self.layer.setCenter(center)
        self.layer.setScale(xScale * self.layer.xScale, yScale * self.layer.yScale)

        setLayerVisible(self.iface, self.layer, self.isLayerVisible)
        self.layer.repaint()

        self.layer.commitTransformParameters()

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())

        adjustment = self.computeAdjustment()
        self.showAdjustment(*adjustment)

    def computeAdjustment(self):
        dX = self.endPoint.x() - self.startPoint.x()
        dY = self.endPoint.y() - self.startPoint.y()
        # project on vector
        dp = dX * self.vector[0] + dY * self.vector[1]

        # do not go beyond 5% of the current size of side
        if dp < -0.95 * self.referenceDistance:
            dp = -0.95 * self.referenceDistance

        updatedSidePoint = QgsPointXY(
            self.sidePoint.x() + dp * self.vector[0],
            self.sidePoint.y() + dp * self.vector[1],
        )

        center = self.center([self.referencePoint, updatedSidePoint])
        scaleFactor = self.distance(self.referencePoint, updatedSidePoint)
        if self.isXScale:
            xScale = scaleFactor / self.referenceDistance
            yScale = 1.0
        else:
            xScale = 1.0
            yScale = scaleFactor / self.referenceDistance

        return (center, xScale, yScale)

    def showAdjustment(self, center, xScale, yScale):
        _, rotation, originalXScale, originalYScale = self.layer.transformParameters()
        newXScale = xScale * originalXScale
        newYScale = yScale * originalYScale
        cornerPoints = self.layer.transformedCornerCoordinates(
            center, rotation, newXScale, newYScale
        )

        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        for point in cornerPoints:
            self.rubberBandExtent.addPoint(point, False)
        # for closing
        self.rubberBandExtent.addPoint(cornerPoints[0], True)
        self.rubberBandExtent.show()

        # show rubberband for side
        # see def of indexSide in init:
        # cornerpoints are (topLeft, topRight, bottomRight, bottomLeft)
        self.rubberBandAdjustSide.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandAdjustSide.addPoint(cornerPoints[self.indexSide % 4], False)
        self.rubberBandAdjustSide.addPoint(cornerPoints[(self.indexSide + 1) % 4], True)
        self.rubberBandAdjustSide.show()

        self.rasterShadow.reset(self.layer)
        dx = center.x() - self.layer.center.x()
        dy = center.y() - self.layer.center.y()
        self.rasterShadow.setDeltaDisplacement(dx, dy, False)
        self.rasterShadow.setDeltaScale(xScale, yScale, True)
        self.rasterShadow.show()


class GeorefRasterBy2PointsMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.rasterShadow = RasterShadowMapCanvasItem(self.canvas)

        self.firstPoint = None

        self.rubberBandOrigin = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.rubberBandOrigin.setColor(Qt.red)
        self.rubberBandOrigin.setIcon(QgsRubberBand.ICON_CIRCLE)
        self.rubberBandOrigin.setIconSize(7)
        self.rubberBandOrigin.setWidth(2)

        self.rubberBandDisplacement = QgsRubberBand(
            self.canvas, QgsWkbTypes.LineGeometry
        )
        self.rubberBandDisplacement.setColor(Qt.red)
        self.rubberBandDisplacement.setWidth(1)

        self.rubberBandExtent = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubberBandExtent.setColor(Qt.red)
        self.rubberBandExtent.setWidth(2)

        self.isLayerVisible = True

        self.reset()

    def setLayer(self, layer):
        self.layer = layer

    def reset(self):
        self.startPoint = self.endPoint = self.firstPoint = None
        self.isEmittingPoint = False
        self.rubberBandOrigin.reset(QgsWkbTypes.PointGeometry)
        self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        self.rasterShadow.reset()
        self.layer = None

    def deactivate(self):
        QgsMapToolEmitPoint.deactivate(self)
        self.reset()

    def canvasPressEvent(self, e):
        if self.firstPoint is None:
            self.startPoint = self.toMapCoordinates(e.pos())
            self.endPoint = self.startPoint
            self.isEmittingPoint = True
            self.originalCenter = self.layer.center
            # this tool do the displacement itself TODO update so it is done by
            # transformed coordinates + new center)
            self.originalCornerPoints = self.layer.transformedCornerCoordinates(
                *self.layer.transformParameters()
            )

            self.isLayerVisible = isLayerVisible(self.iface, self.layer)
            setLayerVisible(self.iface, self.layer, False)

            self.showDisplacement(self.startPoint, self.endPoint)
            self.layer.history.append(
                {"action": "2pointsA", "center": self.layer.center}
            )
        else:
            self.startPoint = self.toMapCoordinates(e.pos())
            self.endPoint = self.startPoint

            self.startY = e.pos().y()
            self.endY = self.startY
            self.isEmittingPoint = True
            self.height = self.canvas.height()

            self.isLayerVisible = isLayerVisible(self.iface, self.layer)
            setLayerVisible(self.iface, self.layer, False)

            rotation = self.computeRotation()
            xScale = yScale = self.computeScale()
            self.showRotationScale(rotation, xScale, yScale)
            self.layer.history.append(
                {
                    "action": "2pointsB",
                    "center": self.layer.center,
                    "xScale": self.layer.xScale,
                    "yScale": self.layer.yScale,
                    "rotation": self.layer.rotation,
                }
            )

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False

        self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        self.rasterShadow.reset()

        if self.firstPoint is None:
            x = self.originalCenter.x() + self.endPoint.x() - self.startPoint.x()
            y = self.originalCenter.y() + self.endPoint.y() - self.startPoint.y()
            self.layer.setCenter(QgsPointXY(x, y))
            self.firstPoint = self.endPoint

            setLayerVisible(self.iface, self.layer, self.isLayerVisible)
            self.layer.repaint()

            self.layer.commitTransformParameters()
        else:
            rotation = self.computeRotation()
            xScale = yScale = self.computeScale()
            self.layer.moveCenterFromPointRotate(
                self.firstPoint, rotation, xScale, yScale
            )
            self.layer.setRotation(self.layer.rotation + rotation)
            self.layer.setScale(self.layer.xScale * xScale, self.layer.yScale * yScale)

            setLayerVisible(self.iface, self.layer, self.isLayerVisible)
            self.layer.repaint()

            self.layer.commitTransformParameters()

            self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
            self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
            self.rubberBandOrigin.reset(QgsWkbTypes.PointGeometry)
            self.rasterShadow.reset()

            self.firstPoint = None
            self.startPoint = self.endPoint = None

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())

        if self.firstPoint is None:
            self.showDisplacement(self.startPoint, self.endPoint)
        else:
            self.endY = e.pos().y()
            rotation = self.computeRotation()
            xScale = yScale = self.computeScale()
            self.showRotationScale(rotation, xScale, yScale)

    def computeRotation(self):
        # The angle is the difference between angle
        # horizontal/endPoint-firstPoint and horizontal/startPoint-firstPoint.
        dX0 = self.startPoint.x() - self.firstPoint.x()
        dY0 = self.startPoint.y() - self.firstPoint.y()
        dX = self.endPoint.x() - self.firstPoint.x()
        dY = self.endPoint.y() - self.firstPoint.y()
        return math.degrees(math.atan2(-dY, dX) - math.atan2(-dY0, dX0))

    def computeScale(self):
        # The scale is the ratio between endPoint-firstPoint and
        # startPoint-firstPoint.
        dX0 = self.startPoint.x() - self.firstPoint.x()
        dY0 = self.startPoint.y() - self.firstPoint.y()
        dX = self.endPoint.x() - self.firstPoint.x()
        dY = self.endPoint.y() - self.firstPoint.y()
        return math.sqrt((dX * dX + dY * dY) / (dX0 * dX0 + dY0 * dY0))

    def showRotationScale(self, rotation, xScale, yScale):
        center, _, _, _ = self.layer.transformParameters()
        # newRotation = rotation + originalRotation
        cornerPoints = self.layer.transformedCornerCoordinatesFromPoint(
            self.firstPoint, rotation, xScale, yScale
        )

        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        for point in cornerPoints:
            self.rubberBandExtent.addPoint(point, False)
        self.rubberBandExtent.addPoint(cornerPoints[0], True)
        self.rubberBandExtent.show()

        # Calculate the displacement of the center due to the rotation from
        # another point.
        newCenterDX = (cornerPoints[0].x() + cornerPoints[2].x()) / 2 - center.x()
        newCenterDY = (cornerPoints[0].y() + cornerPoints[2].y()) / 2 - center.y()
        self.rasterShadow.reset(self.layer)
        self.rasterShadow.setDeltaDisplacement(newCenterDX, newCenterDY, False)
        self.rasterShadow.setDeltaScale(xScale, yScale, False)
        self.rasterShadow.setDeltaRotation(rotation, True)
        self.rasterShadow.show()

        self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
        point0 = QgsPointXY(self.startPoint.x(), self.startPoint.y())
        point1 = QgsPointXY(self.firstPoint.x(), self.firstPoint.y())
        point2 = QgsPointXY(self.endPoint.x(), self.endPoint.y())
        self.rubberBandDisplacement.addPoint(point0, False)
        self.rubberBandDisplacement.addPoint(point1, False)
        self.rubberBandDisplacement.addPoint(point2, True)  # true to update canvas
        self.rubberBandDisplacement.show()

    def showDisplacement(self, startPoint, endPoint):
        self.rubberBandOrigin.reset(QgsWkbTypes.PointGeometry)
        self.rubberBandOrigin.addPoint(endPoint, True)
        self.rubberBandOrigin.show()

        self.rubberBandDisplacement.reset(QgsWkbTypes.LineGeometry)
        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(endPoint.x(), endPoint.y())
        self.rubberBandDisplacement.addPoint(point1, False)
        self.rubberBandDisplacement.addPoint(point2, True)  # true to update canvas
        self.rubberBandDisplacement.show()

        self.rubberBandExtent.reset(QgsWkbTypes.LineGeometry)
        for point in self.originalCornerPoints:
            self._addDisplacementToPoint(self.rubberBandExtent, point, False)
        # for closing
        self._addDisplacementToPoint(
            self.rubberBandExtent, self.originalCornerPoints[0], True
        )
        self.rubberBandExtent.show()

        self.rasterShadow.reset(self.layer)
        self.rasterShadow.setDeltaDisplacement(
            self.endPoint.x() - self.startPoint.x(),
            self.endPoint.y() - self.startPoint.y(),
            True,
        )
        self.rasterShadow.show()

    def _addDisplacementToPoint(self, rubberBand, point, doUpdate):
        x = point.x() + self.endPoint.x() - self.startPoint.x()
        y = point.y() + self.endPoint.y() - self.startPoint.y()
        self.rubberBandExtent.addPoint(QgsPointXY(x, y), doUpdate)

class SelectNorthMapTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.rasterShadow = RasterShadowMapCanvasItem(self.canvas)

        self.firstPoint = None
        self.secondPoint = None

        # Marker for the starting point
        self.rubberBandOriginPoint = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.rubberBandOriginPoint.setColor(Qt.red)
        self.rubberBandOriginPoint.setIcon(QgsRubberBand.ICON_X)
        self.rubberBandOriginPoint.setIconSize(7)
        self.rubberBandOriginPoint.setWidth(2)

        # Line for the North Line
        self.rubberBandLine = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubberBandLine.setColor(Qt.red)
        self.rubberBandLine.setWidth(1)

        self.isLayerVisible = True

        self.reset()

    def setLayer(self, layer):
        self.layer = layer

    def reset(self):
        self.secondPoint = self.firstPoint = None
        self.isEmittingPoint = False
        self.rubberBandOriginPoint.reset(QgsWkbTypes.PointGeometry)
        self.rubberBandLine.reset(QgsWkbTypes.LineGeometry)
        self.layer = None

    def deactivate(self):
        QgsMapToolEmitPoint.deactivate(self)
        self.reset()

    def canvasPressEvent(self, e):
        self.firstPoint = self.toMapCoordinates(e.pos())
        self.isEmittingPoint = True

        # Set the starting point marker to the first position and show
        self.rubberBandOriginPoint.reset(QgsWkbTypes.PointGeometry)
        self.rubberBandOriginPoint.addPoint(self.firstPoint, True)
        self.rubberBandOriginPoint.show()

        self.layer.history.append(
        {
            "action": "rotation",
            "rotation": self.layer.rotation,
            "center": self.layer.center,
        })

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False
        self.secondPoint = self.toMapCoordinates(e.pos())

        azimuth = -self.firstPoint.azimuth(self.secondPoint)
        self.layer.setRotation(azimuth + self.layer.rotation)

        self.layer.repaint()

        self.layer.commitTransformParameters()

        self.rubberBandLine.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandOriginPoint.reset(QgsWkbTypes.PointGeometry)
        self.rasterShadow.reset()

        self.firstPoint = self.secondPoint = None

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.secondPoint = self.toMapCoordinates(e.pos())
        self.showDisplacement(self.firstPoint, self.secondPoint)

    def showDisplacement(self, startPoint, endPoint):
        self.rubberBandLine.reset(QgsWkbTypes.LineGeometry)
        self.rubberBandLine.addPoint(startPoint, False)
        self.rubberBandLine.addPoint(endPoint, True)  # true to update canvas
        self.rubberBandLine.show()

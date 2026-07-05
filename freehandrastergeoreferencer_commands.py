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
import os

from PyQt5.QtCore import qDebug, QPointF, QRectF, QSize
from PyQt5.QtGui import QColor, QImage, QImageWriter, QPainter
from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgsMessageBar

from . import utils


class ExportGeorefRasterCommand(object):
    def __init__(self, iface):
        self.iface = iface

    def exportGeorefRaster(
        self, layer, rasterPath, isPutRotationInWorldFile, isExportOnlyWorldFile
    ):
        baseRasterFilePath, _ = os.path.splitext(rasterPath)
        # suppose supported format already checked
        rasterFormat = utils.imageFormat(rasterPath)

        try:
            originalWidth = layer.image.width()
            originalHeight = layer.image.height()
            radRotation = layer.rotation * math.pi / 180

            if isPutRotationInWorldFile or isExportOnlyWorldFile:
                # keep the image as is and put all transformation params
                # in world file
                img = layer.image

                a = layer.xScale * math.cos(radRotation)
                # sin instead of -sin because angle in CW
                b = -layer.yScale * math.sin(radRotation)
                d = layer.xScale * -math.sin(radRotation)
                e = -layer.yScale * math.cos(radRotation)
                c = layer.center.x() - (
                    a * (originalWidth - 1) / 2 + b * (originalHeight - 1) / 2
                )
                f = layer.center.y() - (
                    d * (originalWidth - 1) / 2 + e * (originalHeight - 1) / 2
                )

            else:
                # transform the image with rotation and scaling between the
                # axes
                # maintain at least the original resolution of the raster
                ratio = layer.xScale / layer.yScale
                if ratio > 1:
                    # increase x
                    scaleX = ratio
                    scaleY = 1
                else:
                    # increase y
                    scaleX = 1
                    scaleY = 1.0 / ratio

                width = abs(scaleX * originalWidth * math.cos(radRotation)) + abs(
                    scaleY * originalHeight * math.sin(radRotation)
                )
                height = abs(scaleX * originalWidth * math.sin(radRotation)) + abs(
                    scaleY * originalHeight * math.cos(radRotation)
                )

                qDebug("wh %f,%f" % (width, height))

                img = QImage(
                    QSize(math.ceil(width), math.ceil(height)), QImage.Format_ARGB32
                )
                # transparent background
                img.fill(QColor(0, 0, 0, 0))

                painter = QPainter(img)
                painter.setRenderHint(QPainter.Antialiasing, True)
                # painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

                rect = QRectF(
                    QPointF(-layer.image.width() / 2.0, -layer.image.height() / 2.0),
                    QPointF(layer.image.width() / 2.0, layer.image.height() / 2.0),
                )

                painter.translate(QPointF(width / 2.0, height / 2.0))
                painter.rotate(layer.rotation)
                painter.scale(scaleX, scaleY)
                painter.drawImage(rect, layer.image)
                painter.end()

                extent = layer.extent()
                a = extent.width() / width
                e = -extent.height() / height
                # 2nd term because (0,0) of world file is on center of upper
                # left pixel instead of upper left corner of that pixel
                c = extent.xMinimum() + a / 2
                f = extent.yMaximum() + e / 2
                b = d = 0.0

            if not isExportOnlyWorldFile:
                # export image
                if rasterFormat == "tif":
                    writer = QImageWriter()
                    # use LZW compression for tiff
                    # useful for scanned documents (mostly white)
                    writer.setCompression(1)
                    writer.setFormat(b"TIFF")
                    writer.setFileName(rasterPath)
                    writer.write(img)
                else:
                    img.save(rasterPath, rasterFormat)

            worldFilePath = baseRasterFilePath + "."
            if rasterFormat == "jpg":
                worldFilePath += "jgw"
            elif rasterFormat == "png":
                worldFilePath += "pgw"
            elif rasterFormat == "bmp":
                worldFilePath += "bpw"
            elif rasterFormat == "tif":
                worldFilePath += "tfw"

            with open(worldFilePath, "w") as writer:
                # order is as described at
                # http://webhelp.esri.com/arcims/9.3/General/topics/author_world_files.htm
                writer.write(
                    "%.13f\n%.13f\n%.13f\n%.13f\n%.13f\n%.13f" % (a, d, b, e, c, f)
                )

            crsFilePath = rasterPath + ".aux.xml"
            with open(crsFilePath, "w") as writer:
                writer.write(
                    self.auxContent(
                        self.iface.mapCanvas().mapSettings().destinationCrs()
                    )
                )

            widget = QgsMessageBar.createMessage(
                "Raster Georeferencer", "Raster exported successfully."
            )
            self.iface.messageBar().pushWidget(widget, Qgis.Info, 2)
        except Exception as ex:
            QgsMessageLog.logMessage(repr(ex))
            widget = QgsMessageBar.createMessage(
                "Raster Georeferencer",
                "There was an error performing this command. "
                "See QGIS Message log for details.",
            )
            self.iface.messageBar().pushWidget(widget, Qgis.Critical, 5)

    def auxContent(self, crs):
        content = """<PAMDataset>
  <Metadata domain="xml:ESRI" format="xml">
    <GeodataXform xsi:type="typens:IdentityXform" 
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
      xmlns:xs="http://www.w3.org/2001/XMLSchema" 
      xmlns:typens="http://www.esri.com/schemas/ArcGIS/9.2">
      <SpatialReference xsi:type="typens:%sCoordinateSystem">
        <WKT>%s</WKT>
      </SpatialReference>
    </GeodataXform>
  </Metadata>
</PAMDataset>"""  # noqa
        geogOrProj = "Geographic" if crs.isGeographic() else "Projected"
        return content % (geogOrProj, crs.toWkt())

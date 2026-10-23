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

from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgsMessageBar
from qgis.PyQt.QtCore import QPointF, QRectF, QSize, qDebug
from qgis.PyQt.QtGui import QColor, QImage, QImageWriter, QPainter

from . import transform as transform_math, utils


class ExportGeorefRasterCommand:
    def __init__(self, iface):
        self.iface = iface

    def export_georef_raster(
        self,
        layer,
        raster_path,
        is_put_rotation_in_world_file,
        is_export_only_world_file,
    ):
        base_raster_file_path, _ = os.path.splitext(raster_path)
        # suppose supported format already checked
        raster_format = utils.image_format(raster_path)

        try:
            original_width = layer.image.width()
            original_height = layer.image.height()
            rad_rotation = layer.rotation * math.pi / 180

            if is_put_rotation_in_world_file or is_export_only_world_file:
                # keep the image as is and put all transformation params
                # in world file
                img = layer.image

                world_file_transform = transform_math.world_file_transform_for_image(
                    original_width,
                    original_height,
                    transform_math.Point(layer.center.x(), layer.center.y()),
                    layer.rotation,
                    layer.x_scale,
                    layer.y_scale,
                )

            else:
                # transform the image with rotation and scaling between the
                # axes
                # maintain at least the original resolution of the raster
                ratio = layer.x_scale / layer.y_scale
                if ratio > 1:
                    # increase x
                    scale_x = ratio
                    scale_y = 1
                else:
                    # increase y
                    scale_x = 1
                    scale_y = 1.0 / ratio

                width = abs(scale_x * original_width * math.cos(rad_rotation)) + abs(
                    scale_y * original_height * math.sin(rad_rotation)
                )
                height = abs(scale_x * original_width * math.sin(rad_rotation)) + abs(
                    scale_y * original_height * math.cos(rad_rotation)
                )

                qDebug(f"wh {width:f},{height:f}")

                img = QImage(
                    QSize(math.ceil(width), math.ceil(height)),
                    QImage.Format.Format_ARGB32,
                )
                # transparent background
                img.fill(QColor(0, 0, 0, 0))

                painter = QPainter(img)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                # painter.setRenderHint(
                #     QPainter.RenderHint.SmoothPixmapTransform, True
                # )

                rect = QRectF(
                    QPointF(-layer.image.width() / 2.0, -layer.image.height() / 2.0),
                    QPointF(layer.image.width() / 2.0, layer.image.height() / 2.0),
                )

                painter.translate(QPointF(width / 2.0, height / 2.0))
                painter.rotate(layer.rotation)
                painter.scale(scale_x, scale_y)
                painter.drawImage(rect, layer.image)
                painter.end()

                extent = layer.extent()
                world_file_transform = transform_math.world_file_transform_for_extent(
                    width,
                    height,
                    (
                        extent.xMinimum(),
                        extent.yMinimum(),
                        extent.xMaximum(),
                        extent.yMaximum(),
                    ),
                )

            if not is_export_only_world_file:
                # export image
                if raster_format == "tif":
                    writer = QImageWriter()
                    # use LZW compression for tiff
                    # useful for scanned documents (mostly white)
                    writer.setCompression(1)
                    writer.setFormat(b"TIFF")
                    writer.setFileName(raster_path)
                    writer.write(img)
                else:
                    img.save(raster_path, raster_format)

            world_file_path = base_raster_file_path + "."
            if raster_format == "jpg":
                world_file_path += "jgw"
            elif raster_format == "png":
                world_file_path += "pgw"
            elif raster_format == "bmp":
                world_file_path += "bpw"
            elif raster_format == "tif":
                world_file_path += "tfw"

            with open(world_file_path, "w") as writer:
                # order is as described at
                # http://webhelp.esri.com/arcims/9.3/General/topics/author_world_files.htm
                writer.write(
                    "\n".join(
                        f"{value:.13f}" for value in world_file_transform.as_lines()
                    )
                )

            crs_file_path = raster_path + ".aux.xml"
            with open(crs_file_path, "w") as writer:
                writer.write(
                    self.aux_content(
                        self.iface.mapCanvas().mapSettings().destinationCrs()
                    )
                )

            widget = QgsMessageBar.createMessage(
                "Freehand raster georeferencer", "Raster exported successfully."
            )
            self.iface.messageBar().pushWidget(widget, Qgis.MessageLevel.Info, 2)
        except Exception as ex:
            QgsMessageLog.logMessage(repr(ex))
            widget = QgsMessageBar.createMessage(
                "Freehand raster georeferencer",
                "There was an error performing this command. "
                "See QGIS Message log for details.",
            )
            self.iface.messageBar().pushWidget(widget, Qgis.MessageLevel.Critical, 5)

    def aux_content(self, crs):
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
        geog_or_proj = "Geographic" if crs.isGeographic() else "Projected"
        return content % (geog_or_proj, crs.toWkt())

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

from qgis.core import QgsProject
from qgis.PyQt.QtCore import qDebug

# constants for saving data inside QGS
SETTINGS_KEY = "FreehandRasterGeoreferencer"
SETTING_BROWSER_RASTER_DIR = "browseRasterDir"


def to_relative_to_qgs(image_path):
    qgs_path = QgsProject.instance().fileName()
    if qgs_path and os.path.isabs(image_path):
        # Make it relative to current project if image below QGS
        imageFolder, image_name = os.path.split(image_path)
        qgs_folder, _ = os.path.split(qgs_path)
        imageFolder = os.path.abspath(imageFolder)
        qgs_folder = os.path.abspath(qgs_folder)

        if imageFolder.startswith(qgs_folder):
            # relative
            imageFolderRelPath = os.path.relpath(imageFolder, qgs_folder)
            image_path = os.path.join(imageFolderRelPath, image_name)
            qDebug(image_path)

    return image_path


def tryfloat(strF):
    try:
        f = float(strF)
        return f
    except ValueError:
        return None


def image_format(path):
    _, extension = os.path.splitext(path)
    extension = extension.lstrip(".").lower()
    if extension == "tiff":
        extension = "tif"
    return extension

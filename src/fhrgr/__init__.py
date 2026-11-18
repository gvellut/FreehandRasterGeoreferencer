"""
/***************************************************************************
 FreehandRasterGeoreferencer
                                 A QGIS plugin
 Interactive georeferencing of rasters
                             -------------------
        copyright            : (C) 2018 by Guilhem Vellut
        email                : guilhem.vellut@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""


def classFactory(iface):
    from .freehandrastergeoreferencer import FreehandRasterGeoreferencer

    return FreehandRasterGeoreferencer(iface)

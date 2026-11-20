import numpy as np
from osgeo import gdal

from fhrgr.qt_image import qimage_from_display_array
from fhrgr.raster_io import probe_raster_size


def test_gdal_probes_raster_size(tmp_path):
    path = tmp_path / "tiny.tif"
    dataset = gdal.GetDriverByName("GTiff").Create(str(path), 3, 2, 1, gdal.GDT_Byte)
    dataset.GetRasterBand(1).WriteArray(np.ones((2, 3), dtype=np.uint8))
    dataset = None

    assert probe_raster_size(str(path)) == (3, 2)


def test_qt_image_uses_raster_buffer():
    image = qimage_from_display_array(np.zeros((2, 3, 4), dtype=np.uint8))

    assert image.width() == 3
    assert image.height() == 2
    assert image._fhrgr_buffer.shape == (2, 3, 4)

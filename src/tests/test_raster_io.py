import numpy as np
import pytest

from fhrgr.raster_display import (
    RasterBandData,
    compose_display_array,
    normalize_band_to_byte,
)


def test_byte_band_is_preserved():
    values = np.array([[0, 255]], dtype=np.uint8)

    result, was_rescaled, warnings = normalize_band_to_byte(values)

    assert result is values
    assert not was_rescaled
    assert warnings == []


def test_uint16_band_is_scaled_to_byte():
    values = np.array([[0, 500], [1000, 2000]], dtype=np.uint16)

    result, was_rescaled, warnings = normalize_band_to_byte(values, data_type="UInt16")

    assert result.tolist() == [[0, 64], [128, 255]]
    assert was_rescaled
    assert warnings == ["Band data was rescaled to 8-bit for display."]


def test_nodata_is_ignored_when_scaling():
    values = np.array([[-9999, 10], [20, 30]], dtype=np.float32)

    result, was_rescaled, warnings = normalize_band_to_byte(
        values, nodata=-9999, data_type="Float32"
    )

    assert result.tolist() == [[0, 0], [128, 255]]
    assert was_rescaled
    assert warnings == ["Band data was rescaled to 8-bit for display."]


def test_constant_non_byte_band_does_not_divide_by_zero():
    values = np.array([[42, 42]], dtype=np.uint16)

    result, was_rescaled, warnings = normalize_band_to_byte(values, data_type="UInt16")

    assert result.tolist() == [[0, 0]]
    assert was_rescaled
    assert warnings == [
        "Band has a constant value; displaying it as black to avoid division by zero."
    ]


def test_single_band_nodata_becomes_rgba():
    band = RasterBandData(
        np.array([[0, 1]], dtype=np.uint8), nodata=0, data_type="Byte"
    )

    result, was_rescaled, warnings = compose_display_array([band])

    assert result.shape == (1, 2, 4)
    assert result[0, 0].tolist() == [0, 0, 0, 0]
    assert result[0, 1].tolist() == [1, 1, 1, 255]
    assert not was_rescaled
    assert warnings == ["Applied nodata as transparency for display."]


def test_two_band_gray_alpha():
    gray = RasterBandData(np.array([[10, 20]], dtype=np.uint8), data_type="Byte")
    alpha = RasterBandData(
        np.array([[0, 255]], dtype=np.uint8),
        color_interpretation="Alpha",
        data_type="Byte",
    )

    result, was_rescaled, warnings = compose_display_array([gray, alpha])

    assert result.tolist() == [[[10, 10, 10, 0], [20, 20, 20, 255]]]
    assert not was_rescaled
    assert warnings == ["Interpreted the second raster band as alpha."]


def test_two_non_alpha_bands_warn_and_use_first():
    first = RasterBandData(np.array([[1, 2]], dtype=np.uint8), data_type="Byte")
    second = RasterBandData(np.array([[3, 4]], dtype=np.uint8), data_type="Byte")

    result, _was_rescaled, warnings = compose_display_array([first, second])

    assert result.tolist() == [[1, 2]]
    assert warnings == [
        "Raster has two non-alpha bands; only the first band is displayed."
    ]


def test_rgb_bands_are_selected_by_color_interpretation():
    blue = RasterBandData(np.array([[30]], dtype=np.uint8), "Blue", data_type="Byte")
    red = RasterBandData(np.array([[10]], dtype=np.uint8), "Red", data_type="Byte")
    green = RasterBandData(np.array([[20]], dtype=np.uint8), "Green", data_type="Byte")

    result, _was_rescaled, warnings = compose_display_array([blue, red, green])

    assert result.tolist() == [[[10, 20, 30]]]
    assert warnings == []


def test_rgba_uses_alpha_band_and_ignores_extra_band():
    bands = [
        RasterBandData(np.array([[10]], dtype=np.uint8), "Red", data_type="Byte"),
        RasterBandData(np.array([[20]], dtype=np.uint8), "Green", data_type="Byte"),
        RasterBandData(np.array([[30]], dtype=np.uint8), "Blue", data_type="Byte"),
        RasterBandData(np.array([[40]], dtype=np.uint8), "Alpha", data_type="Byte"),
        RasterBandData(np.array([[50]], dtype=np.uint8), data_type="Byte"),
    ]

    result, _was_rescaled, warnings = compose_display_array(bands)

    assert result.tolist() == [[[10, 20, 30, 40]]]
    assert warnings == [
        "Extra raster bands were ignored for display.",
        "Applied raster alpha band for display.",
    ]


def test_color_table_is_applied():
    band = RasterBandData(
        np.array([[0, 1]], dtype=np.uint8),
        color_interpretation="Palette",
        color_table=((1, 2, 3, 255), (4, 5, 6, 128)),
        data_type="Byte",
    )

    result, was_rescaled, warnings = compose_display_array([band])

    assert result.tolist() == [[[1, 2, 3, 255], [4, 5, 6, 128]]]
    assert not was_rescaled
    assert warnings == ["Applied raster color table for display."]


def test_optional_gdal_probe_skips_without_gdal(tmp_path):
    pytest.importorskip("osgeo.gdal")

    from osgeo import gdal

    from fhrgr.raster_io import probe_raster_size

    path = tmp_path / "tiny.tif"
    dataset = gdal.GetDriverByName("GTiff").Create(str(path), 3, 2, 1, gdal.GDT_Byte)
    dataset.GetRasterBand(1).WriteArray(np.ones((2, 3), dtype=np.uint8))
    dataset = None

    assert probe_raster_size(str(path)) == (3, 2)


def test_optional_qt_image_skips_without_qgis_pyqt():
    pytest.importorskip("qgis.PyQt.QtGui")

    from fhrgr.qt_image import qimage_from_display_array

    image = qimage_from_display_array(np.zeros((2, 3, 4), dtype=np.uint8))

    assert image.width() == 3
    assert image.height() == 2
    assert image._fhrgr_buffer.shape == (2, 3, 4)

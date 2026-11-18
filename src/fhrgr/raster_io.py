from dataclasses import dataclass
from typing import Any

from osgeo import gdal

from .raster_display import (
    RasterBandData,
    RasterDisplayError,
    compose_display_array,
)


class RasterLoadError(Exception):
    pass


@dataclass
class RasterDisplayImage:
    qimage: Any
    width: int
    height: int
    source_path: str
    was_rescaled: bool
    warnings: list[str]
    geotransform: tuple[float, float, float, float, float, float] | None
    crs_wkt: str | None
    buffer: Any


def _read_color_table(color_table):
    if color_table is None:
        return None
    return tuple(
        tuple(int(channel) for channel in color_table.GetColorEntry(index))
        for index in range(color_table.GetCount())
    )


def _read_bands(dataset):
    bands = []
    for index in range(1, dataset.RasterCount + 1):
        band = dataset.GetRasterBand(index)
        array = band.ReadAsArray()
        if array is None:
            raise RasterLoadError(f"Could not read raster band {index}.")
        bands.append(
            RasterBandData(
                array=array,
                color_interpretation=gdal.GetColorInterpretationName(
                    band.GetColorInterpretation()
                ),
                nodata=band.GetNoDataValue(),
                data_type=gdal.GetDataTypeName(band.DataType),
                color_table=_read_color_table(band.GetRasterColorTable()),
            )
        )
    return bands


def _dataset_geotransform(dataset):
    try:
        geotransform = dataset.GetGeoTransform(can_return_null=True)
    except TypeError:
        geotransform = dataset.GetGeoTransform()
    if geotransform is None:
        return None
    return tuple(float(value) for value in geotransform)


def _open_dataset(path):
    dataset = gdal.OpenEx(path, gdal.OF_RASTER)
    if dataset is None:
        message = gdal.GetLastErrorMsg() or f"GDAL could not open raster: {path}"
        raise RasterLoadError(message)
    return dataset


def load_raster_for_display(path):
    dataset = _open_dataset(path)
    if dataset.RasterCount == 0:
        raise RasterLoadError("Raster has no bands to display.")

    from .qt_image import qimage_from_display_array

    try:
        display_array, was_rescaled, warnings = compose_display_array(
            _read_bands(dataset)
        )
    except RasterDisplayError as ex:
        raise RasterLoadError(str(ex)) from ex

    qimage = qimage_from_display_array(display_array)
    return RasterDisplayImage(
        qimage=qimage,
        width=int(dataset.RasterXSize),
        height=int(dataset.RasterYSize),
        source_path=path,
        was_rescaled=was_rescaled,
        warnings=warnings,
        geotransform=_dataset_geotransform(dataset),
        crs_wkt=dataset.GetProjection() or None,
        buffer=qimage._fhrgr_buffer,
    )


def probe_raster_size(path):
    dataset = _open_dataset(path)
    return int(dataset.RasterXSize), int(dataset.RasterYSize)

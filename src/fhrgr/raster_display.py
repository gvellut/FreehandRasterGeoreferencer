from dataclasses import dataclass

import numpy as np


class RasterDisplayError(Exception):
    pass


@dataclass(frozen=True)
class RasterBandData:
    array: np.ndarray
    color_interpretation: str = "Undefined"
    nodata: float | None = None
    data_type: str = "Byte"
    color_table: tuple[tuple[int, int, int, int], ...] | None = None


def _valid_data_mask(array, nodata):
    mask = np.isfinite(array)
    if nodata is not None:
        mask &= array != nodata
    return mask


def normalize_band_to_byte(array, nodata=None, data_type="Byte"):
    values = np.asarray(array)
    warnings = []
    if values.dtype == np.uint8 and data_type == "Byte":
        return values.astype(np.uint8, copy=False), False, warnings

    valid = _valid_data_mask(values, nodata)
    if not np.any(valid):
        warnings.append("Band has no valid pixels; displaying it as black.")
        return np.zeros(values.shape, dtype=np.uint8), True, warnings

    minimum = float(np.min(values[valid]))
    maximum = float(np.max(values[valid]))
    if minimum == maximum:
        warnings.append(
            "Band has a constant value; displaying it as black to avoid "
            "division by zero."
        )
        return np.zeros(values.shape, dtype=np.uint8), True, warnings

    scaled = np.zeros(values.shape, dtype=np.float64)
    scaled[valid] = (
        (values[valid].astype(np.float64) - minimum) * 255.0 / (maximum - minimum)
    )
    result = np.clip(np.rint(scaled), 0, 255).astype(np.uint8)
    warnings.append("Band data was rescaled to 8-bit for display.")
    return result, True, warnings


def _alpha_from_nodata(bands):
    masks = [
        _valid_data_mask(np.asarray(band.array), band.nodata)
        for band in bands
        if band.nodata is not None
    ]
    if not masks:
        return None

    valid = masks[0]
    for mask in masks[1:]:
        valid &= mask
    return np.where(valid, 255, 0).astype(np.uint8)


def _normalize_selected_bands(bands):
    arrays = []
    warnings = []
    was_rescaled = False
    for band in bands:
        array, rescaled, band_warnings = normalize_band_to_byte(
            band.array, nodata=band.nodata, data_type=band.data_type
        )
        arrays.append(array)
        warnings.extend(band_warnings)
        was_rescaled = was_rescaled or rescaled
    return arrays, was_rescaled, warnings


def _color_name(band):
    return band.color_interpretation.lower()


def _is_alpha(band):
    return _color_name(band) == "alpha"


def _find_color_bands(bands):
    by_name = {_color_name(band): band for band in bands}
    if {"red", "green", "blue"} <= set(by_name):
        return [by_name["red"], by_name["green"], by_name["blue"]]
    return None


def _apply_color_table(band):
    if not band.color_table:
        raise RasterDisplayError("Raster color table is empty.")

    values = np.asarray(band.array)
    indices = np.clip(values.astype(np.int64), 0, len(band.color_table) - 1)
    table = np.asarray(band.color_table, dtype=np.uint8)
    rgba = table[indices]
    alpha = _alpha_from_nodata([band])
    if alpha is not None:
        rgba[..., 3] = alpha
    return rgba


def compose_display_array(bands):
    if not bands:
        raise RasterDisplayError("Raster has no bands to display.")

    warnings = []
    was_rescaled = False

    if bands[0].color_table is not None:
        warnings.append("Applied raster color table for display.")
        return _apply_color_table(bands[0]), was_rescaled, warnings

    if len(bands) == 1:
        arrays, was_rescaled, warnings = _normalize_selected_bands([bands[0]])
        alpha = _alpha_from_nodata([bands[0]])
        if alpha is None:
            return arrays[0], was_rescaled, warnings
        warnings.append("Applied nodata as transparency for display.")
        return (
            np.dstack((arrays[0], arrays[0], arrays[0], alpha)),
            was_rescaled,
            warnings,
        )

    if len(bands) == 2:
        arrays, was_rescaled, band_warnings = _normalize_selected_bands(bands)
        warnings.extend(band_warnings)
        if _is_alpha(bands[1]):
            warnings.append("Interpreted the second raster band as alpha.")
            return (
                np.dstack((arrays[0], arrays[0], arrays[0], arrays[1])),
                was_rescaled,
                warnings,
            )
        warnings.append(
            "Raster has two non-alpha bands; only the first band is displayed."
        )
        alpha = _alpha_from_nodata([bands[0]])
        if alpha is None:
            return arrays[0], was_rescaled, warnings
        warnings.append("Applied nodata as transparency for display.")
        return (
            np.dstack((arrays[0], arrays[0], arrays[0], alpha)),
            was_rescaled,
            warnings,
        )

    rgb_bands = _find_color_bands(bands)
    alpha_band = next((band for band in bands if _is_alpha(band)), None)
    if rgb_bands is None:
        non_alpha_bands = [band for band in bands if not _is_alpha(band)]
        rgb_bands = non_alpha_bands[:3]
        warnings.append(
            "Raster bands do not declare RGB color interpretation; using the "
            "first three displayable bands."
        )

    if len(rgb_bands) < 3:
        raise RasterDisplayError("Raster does not contain enough displayable bands.")

    selected = [*rgb_bands]
    if alpha_band is not None:
        selected.append(alpha_band)
    arrays, was_rescaled, band_warnings = _normalize_selected_bands(selected)
    warnings.extend(band_warnings)

    if len(bands) > len(selected):
        warnings.append("Extra raster bands were ignored for display.")

    if alpha_band is not None:
        warnings.append("Applied raster alpha band for display.")
        return np.dstack(arrays[:4]), was_rescaled, warnings

    alpha = _alpha_from_nodata(rgb_bands)
    if alpha is not None:
        warnings.append("Applied nodata as transparency for display.")
        return np.dstack((*arrays[:3], alpha)), was_rescaled, warnings
    return np.dstack(arrays[:3]), was_rescaled, warnings

import numpy as np
from qgis.PyQt.QtGui import QImage


def qimage_from_display_array(array):
    buffer = np.ascontiguousarray(array)
    if buffer.dtype != np.uint8:
        raise TypeError("Display image arrays must use uint8 pixels")

    if buffer.ndim == 2:
        height, width = buffer.shape
        bytes_per_line = width
        image_format = QImage.Format.Format_Grayscale8
    elif buffer.ndim == 3 and buffer.shape[2] == 3:
        height, width, _channels = buffer.shape
        bytes_per_line = 3 * width
        image_format = QImage.Format.Format_RGB888
    elif buffer.ndim == 3 and buffer.shape[2] == 4:
        height, width, _channels = buffer.shape
        bytes_per_line = 4 * width
        image_format = QImage.Format.Format_RGBA8888
    else:
        raise ValueError("Display image arrays must be grayscale, RGB, or RGBA")

    image = QImage(buffer.data, width, height, bytes_per_line, image_format)
    image._fhrgr_buffer = buffer
    return image

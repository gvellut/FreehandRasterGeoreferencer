from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class RasterGeoreference:
    center: Point
    rotation: float
    x_scale: float
    y_scale: float
    crs_wkt: str | None = None
    raw_geotransform: tuple[float, float, float, float, float, float] | None = None


@dataclass(frozen=True)
class WorldFileTransform:
    a: float
    d: float
    b: float
    e: float
    c: float
    f: float

    def as_lines(self):
        return (self.a, self.d, self.b, self.e, self.c, self.f)


def _rotate(point, cos_rotation, sin_rotation):
    return Point(
        point.x * cos_rotation - point.y * sin_rotation,
        point.x * sin_rotation + point.y * cos_rotation,
    )


def corner_coordinates(width, height, center, rotation, x_scale, y_scale):
    half_width = width / 2.0 * x_scale
    half_height = height / 2.0 * y_scale
    corners = (
        Point(-half_width, half_height),
        Point(half_width, half_height),
        Point(half_width, -half_height),
        Point(-half_width, -half_height),
    )

    rotation_radians = -rotation * math.pi / 180
    cos_rotation = math.cos(rotation_radians)
    sin_rotation = math.sin(rotation_radians)

    return tuple(
        Point(rotated.x + center.x, rotated.y + center.y)
        for rotated in (
            _rotate(corners[0], cos_rotation, sin_rotation),
            _rotate(corners[1], cos_rotation, sin_rotation),
            _rotate(corners[2], cos_rotation, sin_rotation),
            _rotate(corners[3], cos_rotation, sin_rotation),
        )
    )


def corner_coordinates_from_point(
    width,
    height,
    center,
    current_rotation,
    current_x_scale,
    current_y_scale,
    start_point,
    rotation,
    x_scale,
    y_scale,
):
    d_x = (center.x - start_point.x) * x_scale
    d_y = (center.y - start_point.y) * y_scale
    half_width = width / 2.0 * current_x_scale * x_scale
    half_height = height / 2.0 * current_y_scale * y_scale

    corners = (
        Point(-half_width, half_height),
        Point(half_width, half_height),
        Point(half_width, -half_height),
        Point(-half_width, -half_height),
    )

    current_rotation_radians = -current_rotation * math.pi / 180
    current_cos = math.cos(current_rotation_radians)
    current_sin = math.sin(current_rotation_radians)
    moved_corners = tuple(
        Point(rotated.x + d_x, rotated.y + d_y)
        for rotated in (
            _rotate(corners[0], current_cos, current_sin),
            _rotate(corners[1], current_cos, current_sin),
            _rotate(corners[2], current_cos, current_sin),
            _rotate(corners[3], current_cos, current_sin),
        )
    )

    rotation_radians = -rotation * math.pi / 180
    cos_rotation = math.cos(rotation_radians)
    sin_rotation = math.sin(rotation_radians)
    return tuple(
        Point(rotated.x + start_point.x, rotated.y + start_point.y)
        for rotated in (
            _rotate(moved_corners[0], cos_rotation, sin_rotation),
            _rotate(moved_corners[1], cos_rotation, sin_rotation),
            _rotate(moved_corners[2], cos_rotation, sin_rotation),
            _rotate(moved_corners[3], cos_rotation, sin_rotation),
        )
    )


def center_from_point_transform(
    width,
    height,
    center,
    current_rotation,
    current_x_scale,
    current_y_scale,
    start_point,
    rotation,
    x_scale,
    y_scale,
):
    corners = corner_coordinates_from_point(
        width,
        height,
        center,
        current_rotation,
        current_x_scale,
        current_y_scale,
        start_point,
        rotation,
        x_scale,
        y_scale,
    )
    return Point(
        (corners[0].x + corners[2].x) / 2,
        (corners[0].y + corners[2].y) / 2,
    )


def extent_from_corners(corners):
    left = min(point.x for point in corners)
    right = max(point.x for point in corners)
    top = max(point.y for point in corners)
    bottom = min(point.y for point in corners)
    return (left, bottom, right, top)


def is_default_geotransform(geotransform):
    return (
        geotransform[0] == 0
        and geotransform[3] == 0
        and geotransform[1] == 1
        and geotransform[5] == 1
    )


def georeference_from_geotransform(geotransform, width, height, crs_wkt=None):
    rotation = 180 / math.pi * -math.atan2(geotransform[4], geotransform[1])
    x_scale = math.sqrt(geotransform[1] ** 2 + geotransform[4] ** 2)
    y_scale = math.sqrt(geotransform[2] ** 2 + geotransform[5] ** 2)
    image_center_x = width / 2
    image_center_y = height / 2
    center = Point(
        geotransform[0]
        + geotransform[1] * image_center_x
        + geotransform[2] * image_center_y,
        geotransform[3]
        + geotransform[4] * image_center_x
        + geotransform[5] * image_center_y,
    )
    return RasterGeoreference(
        center=center,
        rotation=rotation,
        x_scale=x_scale,
        y_scale=y_scale,
        crs_wkt=crs_wkt,
        raw_geotransform=tuple(geotransform),
    )


def fit_scale_to_extent(image_width, image_height, extent_width, extent_height):
    width_ratio = extent_width / image_width
    height_ratio = extent_height / image_height
    if width_ratio > height_ratio:
        return (height_ratio, height_ratio)
    return (width_ratio, width_ratio)


def world_file_transform_for_image(width, height, center, rotation, x_scale, y_scale):
    rotation_radians = rotation * math.pi / 180
    a = x_scale * math.cos(rotation_radians)
    b = -y_scale * math.sin(rotation_radians)
    d = x_scale * -math.sin(rotation_radians)
    e = -y_scale * math.cos(rotation_radians)
    c = center.x - (a * (width - 1) / 2 + b * (height - 1) / 2)
    f = center.y - (d * (width - 1) / 2 + e * (height - 1) / 2)
    return WorldFileTransform(a=a, d=d, b=b, e=e, c=c, f=f)


def world_file_transform_for_extent(width, height, extent):
    left, bottom, right, top = extent
    a = (right - left) / width
    e = -(top - bottom) / height
    c = left + a / 2
    f = top + e / 2
    return WorldFileTransform(a=a, d=0.0, b=0.0, e=e, c=c, f=f)

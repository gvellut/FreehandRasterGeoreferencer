import math

import pytest

from fhrgr.transform import (
    Point,
    center_from_point_transform,
    corner_coordinates,
    extent_from_corners,
    fit_scale_to_extent,
    georeference_from_geotransform,
    is_default_geotransform,
    world_file_transform_for_extent,
    world_file_transform_for_image,
)


def assert_point(point, x, y):
    assert point.x == pytest.approx(x)
    assert point.y == pytest.approx(y)


def test_corner_coordinates_without_rotation():
    corners = corner_coordinates(10, 4, Point(100, 200), 0, 2, 3)

    assert_point(corners[0], 90, 206)
    assert_point(corners[1], 110, 206)
    assert_point(corners[2], 110, 194)
    assert_point(corners[3], 90, 194)
    assert extent_from_corners(corners) == pytest.approx((90, 194, 110, 206))


def test_corner_coordinates_use_clockwise_rotation():
    corners = corner_coordinates(2, 2, Point(0, 0), 90, 1, 1)

    assert_point(corners[0], 1, 1)
    assert_point(corners[1], 1, -1)
    assert_point(corners[2], -1, -1)
    assert_point(corners[3], -1, 1)


def test_center_from_point_transform_matches_corner_center():
    center = center_from_point_transform(
        10,
        4,
        Point(10, 0),
        0,
        1,
        1,
        Point(0, 0),
        90,
        2,
        2,
    )

    assert_point(center, 0, -20)


def test_default_geotransform_detection():
    assert is_default_geotransform((0, 1, 0, 0, 0, 1))
    assert not is_default_geotransform((100, 1, 0, 200, 0, -1))


def test_georeference_from_geotransform():
    georef = georeference_from_geotransform((10, 2, 0, 20, 0, -3), 8, 6, "wkt")

    assert georef.center == Point(18, 11)
    assert georef.rotation == pytest.approx(0)
    assert georef.x_scale == pytest.approx(2)
    assert georef.y_scale == pytest.approx(3)
    assert georef.crs_wkt == "wkt"
    assert georef.raw_geotransform == (10, 2, 0, 20, 0, -3)


def test_world_file_transform_for_rotated_image():
    transform = world_file_transform_for_image(101, 51, Point(1000, 2000), 30, 2, 3)

    assert transform.a == pytest.approx(2 * math.cos(math.radians(30)))
    assert transform.b == pytest.approx(-3 * math.sin(math.radians(30)))
    assert transform.d == pytest.approx(-2 * math.sin(math.radians(30)))
    assert transform.e == pytest.approx(-3 * math.cos(math.radians(30)))
    assert transform.c == pytest.approx(
        1000 - (transform.a * 100 / 2 + transform.b * 50 / 2)
    )
    assert transform.f == pytest.approx(
        2000 - (transform.d * 100 / 2 + transform.e * 50 / 2)
    )


def test_world_file_transform_for_extent():
    transform = world_file_transform_for_extent(100, 50, (10, 20, 110, 70))

    assert transform.as_lines() == pytest.approx((1, 0, 0, -1, 10.5, 69.5))


def test_fit_scale_to_extent():
    assert fit_scale_to_extent(100, 50, 1000, 200) == pytest.approx((4, 4))
    assert fit_scale_to_extent(100, 50, 200, 1000) == pytest.approx((2, 2))

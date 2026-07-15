import pytest

from dronetrack.geo import choose_zoom, haversine_metres, web_mercator_pixel


def test_haversine_known_short_distance() -> None:
    distance = haversine_metres(0.0, 0.0, 0.0, 0.001)
    assert distance == pytest.approx(111.195, abs=0.01)


def test_web_mercator_origin() -> None:
    assert web_mercator_pixel(0, 0, 0) == pytest.approx((128, 128))


def test_choose_zoom_fits_route() -> None:
    route = [(0.0, 0.0), (0.001, 0.002)]
    zoom = choose_zoom(route, width=800, height=500)
    pixels = [web_mercator_pixel(lat, lon, zoom) for lat, lon in route]
    assert abs(pixels[1][0] - pixels[0][0]) < 800
    assert abs(pixels[1][1] - pixels[0][1]) < 500

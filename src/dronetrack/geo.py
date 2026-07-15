from __future__ import annotations

import math
from collections.abc import Sequence

from dronetrack.models import TelemetrySample

EARTH_RADIUS_METRES = 6_371_008.8
TILE_SIZE = 256


def haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METRES * math.asin(math.sqrt(a))


def smooth_coordinates(
    samples: Sequence[TelemetrySample], window: int = 15
) -> list[tuple[float, float]]:
    if window < 1:
        raise ValueError("Smoothing window must be positive")
    if len(samples) < window:
        window = 1
    half_window = window // 2
    result: list[tuple[float, float]] = []
    latitude_prefix = [0.0]
    longitude_prefix = [0.0]
    for sample in samples:
        latitude_prefix.append(latitude_prefix[-1] + sample.latitude)
        longitude_prefix.append(longitude_prefix[-1] + sample.longitude)
    for index in range(len(samples)):
        start = max(0, index - half_window)
        end = min(len(samples), index + half_window + 1)
        count = end - start
        result.append(
            (
                (latitude_prefix[end] - latitude_prefix[start]) / count,
                (longitude_prefix[end] - longitude_prefix[start]) / count,
            )
        )
    return result


def route_distance_metres(coordinates: Sequence[tuple[float, float]], stride: int = 15) -> float:
    if len(coordinates) < 2:
        return 0.0
    selected = list(coordinates[::stride])
    if selected[-1] != coordinates[-1]:
        selected.append(coordinates[-1])
    return sum(
        haversine_metres(first[0], first[1], second[0], second[1])
        for first, second in zip(selected, selected[1:], strict=False)
    )


def web_mercator_pixel(latitude: float, longitude: float, zoom: int) -> tuple[float, float]:
    latitude = max(-85.05112878, min(85.05112878, latitude))
    scale = TILE_SIZE * (2**zoom)
    x = (longitude + 180.0) / 360.0 * scale
    sine = math.sin(math.radians(latitude))
    y = (0.5 - math.log((1 + sine) / (1 - sine)) / (4 * math.pi)) * scale
    return x, y


def choose_zoom(
    coordinates: Sequence[tuple[float, float]],
    width: int,
    height: int,
    padding_fraction: float = 0.12,
    max_zoom: int = 19,
) -> int:
    available_width = width * (1 - 2 * padding_fraction)
    available_height = height * (1 - 2 * padding_fraction)
    for zoom in range(max_zoom, -1, -1):
        pixels = [web_mercator_pixel(lat, lon, zoom) for lat, lon in coordinates]
        span_x = max(point[0] for point in pixels) - min(point[0] for point in pixels)
        span_y = max(point[1] for point in pixels) - min(point[1] for point in pixels)
        if span_x <= available_width and span_y <= available_height:
            return zoom
    return 0

from datetime import datetime
from pathlib import Path

from PIL import Image

from dronetrack.geo import web_mercator_pixel
from dronetrack.models import FlightTrack, TelemetrySample
from dronetrack.overlay import CornerMapRenderer
from dronetrack.tiles import MapViewport


def _sample(sequence: int, seconds: float, latitude: float, longitude: float) -> TelemetrySample:
    return TelemetrySample(
        sequence=sequence,
        start_seconds=seconds,
        end_seconds=seconds + 1,
        frame_count=sequence,
        captured_at=datetime(2030, 1, 1),
        latitude=latitude,
        longitude=longitude,
        relative_altitude=10 + sequence,
        absolute_altitude=100 + sequence,
    )


def test_corner_map_frame_has_clipping_route_and_trail() -> None:
    samples = (
        _sample(1, 0, 0.0010, 0.0010),
        _sample(2, 1, 0.0011, 0.0012),
        _sample(3, 2, 0.0012, 0.0014),
    )
    track = FlightTrack(source=Path("flight.SRT"), samples=samples)
    zoom = 17
    origin_x, origin_y = web_mercator_pixel(samples[0].latitude, samples[0].longitude, zoom)
    viewport = MapViewport(
        image=Image.new("RGBA", (400, 250), "#dce5e8"),
        zoom=zoom,
        left=origin_x - 100,
        top=origin_y - 125,
    )

    renderer = CornerMapRenderer(track, viewport, map_opacity=0.5)
    frame = renderer.frame(2)

    assert frame.size == (400, 250)
    assert frame.getpixel((0, 0))[3] == 0
    assert renderer.base.getpixel((350, 200))[3] == 128
    assert any(r < 20 and g > 180 and b > 200 for r, g, b, _alpha in frame.get_flattened_data())

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFont

from dronetrack.geo import haversine_metres, smooth_coordinates
from dronetrack.models import FlightTrack
from dronetrack.tiles import MapViewport


class CornerMapRenderer:
    def __init__(
        self,
        track: FlightTrack,
        viewport: MapViewport,
        map_opacity: float = 0.78,
    ) -> None:
        self.track = track
        self.viewport = viewport
        self.map_opacity = map_opacity
        self.coordinates = smooth_coordinates(track.samples)
        self.points = [viewport.project(lat, lon) for lat, lon in self.coordinates]
        self.width, self.height = viewport.image.size
        self.route_width = max(3, self.width // 120)
        self.base = self._build_base()
        self.trail = Image.new("RGBA", self.base.size, (0, 0, 0, 0))
        self.trail_draw = ImageDraw.Draw(self.trail, "RGBA")
        self.last_trail_index = 0
        self.font = ImageFont.load_default(size=max(13, self.width // 38))

    def _build_base(self) -> Image.Image:
        radius = max(12, self.width // 35)
        mask = Image.new("L", (self.width, self.height), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, self.width - 1, self.height - 1), radius=radius, fill=255
        )
        base = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        map_image = self.viewport.image.copy()
        map_image.putalpha(mask.point(lambda value: round(value * self.map_opacity)))
        base.alpha_composite(map_image)
        draw = ImageDraw.Draw(base, "RGBA")
        if len(self.points) > 1:
            draw.line(
                self.points,
                fill=(15, 25, 35, 155),
                width=self.route_width + 4,
                joint="curve",
            )
            draw.line(self.points, fill=(236, 241, 244, 220), width=self.route_width, joint="curve")
        draw.rounded_rectangle(
            (1, 1, self.width - 2, self.height - 2),
            radius=radius,
            outline=(255, 255, 255, 160),
            width=max(2, self.width // 250),
        )
        return base

    def _advance_trail(self, index: int) -> None:
        if index < self.last_trail_index:
            self.trail = Image.new("RGBA", self.base.size, (0, 0, 0, 0))
            self.trail_draw = ImageDraw.Draw(self.trail, "RGBA")
            self.last_trail_index = 0
        if index <= self.last_trail_index:
            return
        new_points = self.points[self.last_trail_index : index + 1]
        if len(new_points) > 1:
            self.trail_draw.line(
                new_points,
                fill=(4, 20, 28, 190),
                width=self.route_width + 5,
                joint="curve",
            )
            self.trail_draw.line(
                new_points,
                fill=(0, 224, 255, 255),
                width=self.route_width,
                joint="curve",
            )
        self.last_trail_index = index

    def _speed(self, index: int) -> float:
        before = max(0, index - 15)
        after = min(len(self.track.samples) - 1, index + 15)
        elapsed = self.track.samples[after].start_seconds - self.track.samples[before].start_seconds
        if elapsed <= 0:
            return 0.0
        first = self.coordinates[before]
        second = self.coordinates[after]
        return haversine_metres(first[0], first[1], second[0], second[1]) / elapsed

    def _heading(self, index: int) -> float:
        before = max(0, index - 12)
        after = min(len(self.points) - 1, index + 12)
        dx = self.points[after][0] - self.points[before][0]
        dy = self.points[after][1] - self.points[before][1]
        if math.hypot(dx, dy) < 0.5:
            return 0.0
        return math.atan2(dy, dx)

    def _draw_marker(self, draw: ImageDraw.ImageDraw, index: int) -> None:
        x, y = self.points[index]
        angle = self._heading(index)
        radius = max(8, self.width // 50)
        tip = (x + math.cos(angle) * radius * 1.45, y + math.sin(angle) * radius * 1.45)
        left = (
            x + math.cos(angle + 2.45) * radius,
            y + math.sin(angle + 2.45) * radius,
        )
        right = (
            x + math.cos(angle - 2.45) * radius,
            y + math.sin(angle - 2.45) * radius,
        )
        shadow = [(px + 2, py + 3) for px, py in (tip, left, right)]
        draw.polygon(shadow, fill=(0, 0, 0, 150))
        draw.polygon((tip, left, right), fill=(255, 244, 64, 255), outline=(15, 25, 30, 255))

    def frame(self, index: int) -> Image.Image:
        index = max(0, min(len(self.points) - 1, index))
        self._advance_trail(index)
        frame = Image.alpha_composite(self.base, self.trail)
        draw = ImageDraw.Draw(frame, "RGBA")
        self._draw_marker(draw, index)

        sample = self.track.samples[index]
        altitude = sample.relative_altitude
        altitude_text = f"ALT {altitude:.1f} m" if altitude is not None else "ALT --"
        label = f"{altitude_text}   {self._speed(index):.1f} m/s"
        bbox = draw.textbbox((0, 0), label, font=self.font)
        label_width = bbox[2] - bbox[0]
        label_height = bbox[3] - bbox[1]
        margin = max(7, self.width // 90)
        horizontal_padding = margin
        vertical_padding = max(4, round(margin * 0.6))
        box_left = margin
        box_top = margin
        box_right = box_left + label_width + horizontal_padding * 2
        box_bottom = box_top + label_height + vertical_padding * 2
        draw.rounded_rectangle(
            (box_left, box_top, box_right, box_bottom),
            radius=vertical_padding,
            fill=(8, 18, 25, 205),
        )
        draw.text(
            (
                box_left + horizontal_padding - bbox[0],
                box_top + vertical_padding - bbox[1],
            ),
            label,
            font=self.font,
            fill=(255, 255, 255, 245),
        )
        return frame

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    sequence: int
    start_seconds: float
    end_seconds: float
    frame_count: int | None
    captured_at: datetime | None
    latitude: float
    longitude: float
    relative_altitude: float | None
    absolute_altitude: float | None


@dataclass(frozen=True, slots=True)
class FlightTrack:
    source: Path
    samples: tuple[TelemetrySample, ...]

    @property
    def duration_seconds(self) -> float:
        return self.samples[-1].end_seconds

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        latitudes = [sample.latitude for sample in self.samples]
        longitudes = [sample.longitude for sample in self.samples]
        return min(latitudes), min(longitudes), max(latitudes), max(longitudes)


@dataclass(frozen=True, slots=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    duration_seconds: float
    codec: str | None = None

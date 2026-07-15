from __future__ import annotations

import bisect
import re
from datetime import datetime
from pathlib import Path

from dronetrack.models import FlightTrack, TelemetrySample

_BLOCK_RE = re.compile(
    r"(?ms)^\s*(?P<sequence>\d+)\s*\r?\n"
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2},\d{3})\s*\r?\n"
    r"(?P<body>.*?)(?=^\s*\d+\s*\r?\n\d{2}:\d{2}:\d{2},\d{3}\s*-->|\Z)"
)
_LATITUDE_RE = re.compile(r"\[latitude:\s*(-?\d+(?:\.\d+)?)\]")
_LONGITUDE_RE = re.compile(r"\[longitude:\s*(-?\d+(?:\.\d+)?)\]")
_ALTITUDE_RE = re.compile(r"\[rel_alt:\s*(-?\d+(?:\.\d+)?)\s+abs_alt:\s*(-?\d+(?:\.\d+)?)\]")
_FRAME_RE = re.compile(r"FrameCnt:\s*(\d+)")
_CAPTURED_RE = re.compile(r"(?m)^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\s*$")


class TelemetryError(ValueError):
    """Raised when a DJI subtitle file cannot produce a usable flight track."""


def _parse_srt_time(value: str) -> float:
    hours, minutes, remainder = value.split(":")
    seconds, milliseconds = remainder.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000


def parse_dji_srt(path: str | Path) -> FlightTrack:
    source = Path(path)
    text = source.read_text(encoding="utf-8-sig")
    samples: list[TelemetrySample] = []

    for match in _BLOCK_RE.finditer(text):
        body = match.group("body")
        latitude_match = _LATITUDE_RE.search(body)
        longitude_match = _LONGITUDE_RE.search(body)
        if not latitude_match or not longitude_match:
            continue

        altitude_match = _ALTITUDE_RE.search(body)
        frame_match = _FRAME_RE.search(body)
        captured_match = _CAPTURED_RE.search(body)
        captured_at = None
        if captured_match:
            captured_at = datetime.fromisoformat(captured_match.group(1))

        samples.append(
            TelemetrySample(
                sequence=int(match.group("sequence")),
                start_seconds=_parse_srt_time(match.group("start")),
                end_seconds=_parse_srt_time(match.group("end")),
                frame_count=int(frame_match.group(1)) if frame_match else None,
                captured_at=captured_at,
                latitude=float(latitude_match.group(1)),
                longitude=float(longitude_match.group(1)),
                relative_altitude=(float(altitude_match.group(1)) if altitude_match else None),
                absolute_altitude=(float(altitude_match.group(2)) if altitude_match else None),
            )
        )

    if not samples:
        raise TelemetryError(f"No coordinate-bearing DJI telemetry blocks found in {source}")

    starts = [sample.start_seconds for sample in samples]
    if starts != sorted(starts):
        raise TelemetryError(f"Telemetry timestamps are not monotonic in {source}")

    return FlightTrack(source=source, samples=tuple(samples))


def sample_index_at(track: FlightTrack, seconds: float) -> int:
    starts = [sample.start_seconds for sample in track.samples]
    return max(0, min(len(starts) - 1, bisect.bisect_right(starts, seconds) - 1))


def find_video_and_srt(path: str | Path) -> tuple[Path, Path]:
    candidate = Path(path)
    if candidate.is_dir():
        files = sorted(item for item in candidate.iterdir() if item.is_file())
        videos = [item for item in files if item.suffix.lower() == ".mp4"]
        subtitles = [item for item in files if item.suffix.lower() == ".srt"]
        if len(videos) != 1 or len(subtitles) != 1:
            raise TelemetryError(
                f"Expected exactly one MP4 and one SRT in {candidate}; "
                f"found {len(videos)} video(s) and {len(subtitles)} subtitle file(s)"
            )
        return videos[0], subtitles[0]

    suffix = candidate.suffix.lower()
    if suffix not in {".mp4", ".srt"}:
        raise TelemetryError(f"Expected a directory, MP4, or SRT path; got {candidate}")

    video = candidate if suffix == ".mp4" else candidate.with_suffix(".MP4")
    srt = candidate if suffix == ".srt" else candidate.with_suffix(".SRT")
    if not video.exists():
        alternate = video.with_suffix(".mp4")
        video = alternate if alternate.exists() else video
    if not srt.exists():
        alternate = srt.with_suffix(".srt")
        srt = alternate if alternate.exists() else srt
    if not video.exists() or not srt.exists():
        raise TelemetryError(f"Could not find matching MP4/SRT pair for {candidate}")
    return video, srt

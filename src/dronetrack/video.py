from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

from dronetrack.models import FlightTrack, VideoInfo
from dronetrack.overlay import CornerMapRenderer
from dronetrack.telemetry import sample_index_at
from dronetrack.tiles import TileCache, render_basemap


class VideoError(RuntimeError):
    """Raised when video inspection or rendering fails."""


def ffmpeg_executable() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_video(path: str | Path) -> VideoInfo:
    result = subprocess.run(
        [ffmpeg_executable(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    metadata = result.stderr
    duration_match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)", metadata)
    video_match = re.search(
        r"Video:\s*(?P<codec>[^,\s]+).*?"
        r"(?P<width>\d{2,5})x(?P<height>\d{2,5}).*?"
        r"(?P<fps>\d+(?:\.\d+)?)\s+fps",
        metadata,
    )
    if not video_match:
        raise VideoError(f"Could not read video dimensions/frame rate from {path}")
    duration = 0.0
    if duration_match:
        duration = (
            int(duration_match.group(1)) * 3600
            + int(duration_match.group(2)) * 60
            + float(duration_match.group(3))
        )
    return VideoInfo(
        width=int(video_match.group("width")),
        height=int(video_match.group("height")),
        fps=float(video_match.group("fps")),
        duration_seconds=duration,
        codec=video_match.group("codec"),
    )


def _overlay_expression(position: str, margin: int) -> tuple[str, str]:
    horizontal = "W-w-{margin}" if position.endswith("right") else "{margin}"
    vertical = "H-h-{margin}" if position.startswith("bottom") else "{margin}"
    return horizontal.format(margin=margin), vertical.format(margin=margin)


def render_video(
    video_path: Path,
    output_path: Path,
    track: FlightTrack,
    *,
    map_position: str = "bottom-right",
    map_width_fraction: float = 0.28,
    map_aspect: float = 1.6,
    overlay_fps: float = 15.0,
    preview_seconds: float | None = None,
    tile_url: str,
    map_attribution: str,
    map_theme: str = "dark",
    map_opacity: float = 0.78,
) -> None:
    info = probe_video(video_path)
    map_width = max(320, round(info.width * map_width_fraction))
    map_width -= map_width % 2
    map_height = max(200, round(map_width / map_aspect))
    map_height -= map_height % 2
    coordinates = [(sample.latitude, sample.longitude) for sample in track.samples]
    cache_dir = Path.home() / ".cache" / "dronetrack" / "tiles"
    tile_cache = TileCache(cache_dir=cache_dir, tile_url=tile_url)
    try:
        try:
            viewport = render_basemap(
                coordinates,
                map_width,
                map_height,
                tile_cache,
                attribution=map_attribution,
                theme=map_theme,
            )
        except (OSError, RuntimeError) as error:
            raise VideoError(f"Could not prepare corner map: {error}") from error
    finally:
        tile_cache.close()
    renderer = CornerMapRenderer(track, viewport, map_opacity=map_opacity)

    render_duration = min(
        track.duration_seconds,
        info.duration_seconds if info.duration_seconds > 0 else track.duration_seconds,
    )
    if preview_seconds is not None:
        render_duration = min(render_duration, preview_seconds)
    frame_count = math.ceil(render_duration * overlay_fps)
    margin = max(16, round(info.width * 0.018))
    x_expression, y_expression = _overlay_expression(map_position, margin)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        ffmpeg_executable(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgba",
        "-video_size",
        f"{map_width}x{map_height}",
        "-framerate",
        str(overlay_fps),
        "-i",
        "pipe:0",
        "-filter_complex",
        f"[0:v][1:v]overlay=x={x_expression}:y={y_expression}:eof_action=pass[v]",
        "-map",
        "[v]",
        "-map",
        "0:a?",
        "-t",
        f"{render_duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for overlay_frame in range(frame_count):
            seconds = overlay_frame / overlay_fps
            sample_index = sample_index_at(track, seconds)
            process.stdin.write(renderer.frame(sample_index).tobytes())
    except BrokenPipeError:
        pass
    finally:
        process.stdin.close()
    assert process.stderr is not None
    error_output = process.stderr.read().decode("utf-8", errors="replace")
    return_code = process.wait()
    if return_code != 0:
        output_path.unlink(missing_ok=True)
        raise VideoError(f"FFmpeg failed with exit code {return_code}:\n{error_output.strip()}")

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dronetrack.geo import route_distance_metres, smooth_coordinates
from dronetrack.telemetry import TelemetryError, find_video_and_srt, parse_dji_srt
from dronetrack.tiles import DEFAULT_ATTRIBUTION, DEFAULT_TILE_URL
from dronetrack.video import VideoError, probe_video, render_video


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dronetrack", description="Overlay a DJI GPS flight track on its video"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="inspect a matching MP4/SRT pair")
    inspect_parser.add_argument("input", type=Path)

    render_parser = subparsers.add_parser("render", help="render a video with a corner map")
    render_parser.add_argument("input", type=Path)
    render_parser.add_argument("--output", type=Path, required=True)
    render_parser.add_argument(
        "--map-position",
        choices=("top-left", "top-right", "bottom-left", "bottom-right"),
        default="bottom-right",
    )
    render_parser.add_argument("--map-width", type=float, default=0.28)
    render_parser.add_argument("--map-aspect", type=float, default=1.6)
    render_parser.add_argument("--overlay-fps", type=float, default=15.0)
    render_parser.add_argument("--preview-seconds", type=float)
    render_parser.add_argument("--tile-url", default=DEFAULT_TILE_URL)
    render_parser.add_argument("--map-attribution", default=DEFAULT_ATTRIBUTION)
    render_parser.add_argument("--map-theme", choices=("dark", "light"), default="dark")
    render_parser.add_argument("--map-opacity", type=float, default=0.78)
    return parser


def _inspect(input_path: Path) -> int:
    video_path, srt_path = find_video_and_srt(input_path)
    track = parse_dji_srt(srt_path)
    video = probe_video(video_path)
    coordinates = smooth_coordinates(track.samples)
    min_lat, min_lon, max_lat, max_lon = track.bounds
    relative_altitudes = [
        sample.relative_altitude for sample in track.samples if sample.relative_altitude is not None
    ]
    print(f"Video:       {video_path}")
    print(f"Subtitles:   {srt_path}")
    print(
        f"Video:       {video.width}x{video.height}, "
        f"{video.fps:.3f} fps, {video.codec or 'unknown'}"
    )
    print(f"Duration:    {track.duration_seconds:.3f} s")
    print(f"Samples:     {len(track.samples)}")
    print(f"Bounds:      {min_lat:.6f},{min_lon:.6f} to {max_lat:.6f},{max_lon:.6f}")
    print(f"Distance:    {route_distance_metres(coordinates):.1f} m")
    if relative_altitudes:
        print(f"Rel altitude:{min(relative_altitudes):9.1f} to {max(relative_altitudes):.1f} m")
    return 0


def _render(args: argparse.Namespace) -> int:
    if not 0.1 <= args.map_width <= 0.8:
        raise TelemetryError("--map-width must be between 0.1 and 0.8")
    if args.map_aspect <= 0 or args.overlay_fps <= 0:
        raise TelemetryError("--map-aspect and --overlay-fps must be positive")
    if args.preview_seconds is not None and args.preview_seconds <= 0:
        raise TelemetryError("--preview-seconds must be positive")
    if not 0.1 <= args.map_opacity <= 1.0:
        raise TelemetryError("--map-opacity must be between 0.1 and 1.0")
    video_path, srt_path = find_video_and_srt(args.input)
    track = parse_dji_srt(srt_path)
    print(f"Rendering {video_path.name} with {len(track.samples)} telemetry samples...")
    render_video(
        video_path,
        args.output,
        track,
        map_position=args.map_position,
        map_width_fraction=args.map_width,
        map_aspect=args.map_aspect,
        overlay_fps=args.overlay_fps,
        preview_seconds=args.preview_seconds,
        tile_url=args.tile_url,
        map_attribution=args.map_attribution,
        map_theme=args.map_theme,
        map_opacity=args.map_opacity,
    )
    print(f"Wrote {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            return _inspect(args.input)
        return _render(args)
    except (TelemetryError, VideoError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

# DroneTrack

DroneTrack turns the per-frame GPS telemetry in DJI `.SRT` subtitle files into an
animated corner map and composites it onto the matching video.

## Set up

The project uses [`uv`](https://docs.astral.sh/uv/) for Python and dependency management.

```powershell
uv sync
uv run dronetrack inspect path/to/flight
```

The input folder should contain exactly one DJI video and its matching `.SRT` file.

## Render a preview

```powershell
uv run dronetrack render path/to/flight --preview-seconds 12 --output output/preview.mp4
```

Render the complete video by omitting `--preview-seconds`:

```powershell
uv run dronetrack render path/to/flight --output output/tracked.mp4
```

The default map uses OpenStreetMap's standard raster tiles. DroneTrack requests only
the small fixed viewport needed for the current flight, identifies itself with a custom
user agent, caches tiles locally, shows attribution, and allows the tile URL to be
overridden with `--tile-url`. Production or high-volume use should use a suitable tile
provider or a self-hosted service.

Useful render options:

```text
--map-position {top-left,top-right,bottom-left,bottom-right}
--map-width 0.28
--map-aspect 1.6
--overlay-fps 15
--map-theme dark
--map-opacity 0.78
--tile-url "https://example.com/{z}/{x}/{y}.png"
--map-attribution "(c) Your map provider"
```

The dark theme is produced locally from the selected raster tiles, so it does not
require a separate dark-map provider. `--map-opacity` affects the map surface while
keeping the route, drone marker, telemetry, and attribution readable.

## Privacy and local media

Drone footage and DJI subtitle files are intentionally ignored by Git. DJI subtitles
contain precise coordinates and capture timestamps, so do not force-add them unless
they have been deliberately sanitized. Map rendering also requests tiles for the
flight area from the configured tile provider.

## Development

```powershell
uv run pytest
uv run ruff check .
```

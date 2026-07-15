from __future__ import annotations

import hashlib
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from dronetrack.geo import TILE_SIZE, choose_zoom, web_mercator_pixel

DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_ATTRIBUTION = "© OpenStreetMap contributors"


def apply_map_theme(image: Image.Image, theme: str) -> Image.Image:
    if theme == "light":
        return image.convert("RGBA")
    if theme != "dark":
        raise ValueError(f"Unknown map theme: {theme}")

    grayscale = ImageOps.grayscale(image)
    inverted = ImageOps.invert(grayscale)
    contrasted = ImageOps.autocontrast(inverted, cutoff=1)
    return ImageOps.colorize(
        contrasted,
        black="#09111a",
        mid="#263947",
        white="#9ab0bd",
    ).convert("RGBA")


@dataclass(frozen=True, slots=True)
class MapViewport:
    image: Image.Image
    zoom: int
    left: float
    top: float

    def project(self, latitude: float, longitude: float) -> tuple[float, float]:
        x, y = web_mercator_pixel(latitude, longitude, self.zoom)
        return x - self.left, y - self.top


class TileCache:
    def __init__(
        self,
        cache_dir: Path,
        tile_url: str = DEFAULT_TILE_URL,
        user_agent: str = "DroneTrack/0.1 (local video map renderer)",
    ) -> None:
        provider_key = hashlib.sha256(tile_url.encode()).hexdigest()[:12]
        self.cache_dir = cache_dir / provider_key
        self.tile_url = tile_url
        self.user_agent = user_agent
        self.curl = shutil.which("curl.exe") or shutil.which("curl")

    def close(self) -> None:
        pass

    def _download(self, url: str, destination: Path) -> None:
        if not self.curl:
            raise RuntimeError(
                "Downloading map tiles requires curl, but no curl executable was found"
            )
        temporary = destination.with_suffix(".part")
        temporary.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.curl,
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--retry",
            "2",
            "--user-agent",
            self.user_agent,
            "--output",
            str(temporary),
            url,
        ]
        if Path(self.curl).name.lower() == "curl.exe":
            command.insert(1, "--ssl-revoke-best-effort")
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            temporary.unlink(missing_ok=True)
            message = result.stderr.strip() or f"curl exited with code {result.returncode}"
            raise RuntimeError(f"Could not download map tile {url}: {message}")
        temporary.replace(destination)

    def get(self, zoom: int, x: int, y: int) -> Image.Image:
        world_tiles = 2**zoom
        x %= world_tiles
        if y < 0 or y >= world_tiles:
            return Image.new("RGB", (TILE_SIZE, TILE_SIZE), "#dce5e8")
        destination = self.cache_dir / str(zoom) / str(x) / f"{y}.png"
        if destination.exists():
            with Image.open(destination) as cached:
                return cached.convert("RGB")

        url = self.tile_url.format(z=zoom, x=x, y=y)
        self._download(url, destination)
        with Image.open(destination) as downloaded:
            tile = downloaded.convert("RGB")
        return tile


def render_basemap(
    coordinates: list[tuple[float, float]],
    width: int,
    height: int,
    tile_cache: TileCache,
    attribution: str = DEFAULT_ATTRIBUTION,
    theme: str = "dark",
) -> MapViewport:
    zoom = choose_zoom(coordinates, width, height)
    route_pixels = [web_mercator_pixel(lat, lon, zoom) for lat, lon in coordinates]
    x_values = [point[0] for point in route_pixels]
    y_values = [point[1] for point in route_pixels]
    centre_x = (min(x_values) + max(x_values)) / 2
    centre_y = (min(y_values) + max(y_values)) / 2
    left = centre_x - width / 2
    top = centre_y - height / 2

    first_tile_x = math.floor(left / TILE_SIZE)
    last_tile_x = math.floor((left + width - 1) / TILE_SIZE)
    first_tile_y = math.floor(top / TILE_SIZE)
    last_tile_y = math.floor((top + height - 1) / TILE_SIZE)
    canvas = Image.new("RGB", (width, height), "#dce5e8")
    for tile_y in range(first_tile_y, last_tile_y + 1):
        for tile_x in range(first_tile_x, last_tile_x + 1):
            tile = tile_cache.get(zoom, tile_x, tile_y)
            paste_x = round(tile_x * TILE_SIZE - left)
            paste_y = round(tile_y * TILE_SIZE - top)
            canvas.paste(tile, (paste_x, paste_y))

    rgba = apply_map_theme(canvas, theme)
    draw = ImageDraw.Draw(rgba, "RGBA")
    font = ImageFont.load_default(size=max(10, width // 55))
    bbox = draw.textbbox((0, 0), attribution, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = width - text_width - 7
    y = height - text_height - 6
    if theme == "dark":
        attribution_fill = (4, 10, 16, 205)
        attribution_text = (224, 235, 240, 235)
    else:
        attribution_fill = (255, 255, 255, 205)
        attribution_text = (20, 25, 30, 235)
    draw.rounded_rectangle((x - 4, y - 2, width - 3, height - 2), radius=3, fill=attribution_fill)
    draw.text((x, y), attribution, font=font, fill=attribution_text)
    return MapViewport(image=rgba, zoom=zoom, left=left, top=top)

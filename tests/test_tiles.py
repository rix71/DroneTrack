from PIL import Image, ImageStat

from dronetrack.tiles import apply_map_theme


def test_dark_theme_reduces_average_brightness() -> None:
    source = Image.new("RGB", (20, 20), "#e8eee8")
    dark = apply_map_theme(source, "dark")

    assert sum(ImageStat.Stat(dark.convert("RGB")).mean) < sum(ImageStat.Stat(source).mean)


def test_light_theme_preserves_pixels() -> None:
    source = Image.new("RGB", (2, 2), "#abc123")

    assert apply_map_theme(source, "light").getpixel((0, 0)) == (171, 193, 35, 255)

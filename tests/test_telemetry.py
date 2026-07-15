from pathlib import Path

import pytest

from dronetrack.telemetry import (
    TelemetryError,
    find_video_and_srt,
    parse_dji_srt,
    sample_index_at,
)

SRT = """1
00:00:00,000 --> 00:00:00,033
<font size="28">FrameCnt: 1, DiffTime: 33ms
2030-01-01 12:00:00.000
[latitude: 0.001000] [longitude: 0.001000] [rel_alt: 10.000 abs_alt: 110.000]</font>

2
00:00:00,033 --> 00:00:00,066
<font size="28">FrameCnt: 2, DiffTime: 33ms
2030-01-01 12:00:00.033
[latitude: 0.001100] [longitude: 0.001200] [rel_alt: 10.100 abs_alt: 110.100]</font>
"""


def test_parses_dji_srt(tmp_path: Path) -> None:
    path = tmp_path / "flight.SRT"
    path.write_text(SRT, encoding="utf-8")

    track = parse_dji_srt(path)

    assert len(track.samples) == 2
    assert track.duration_seconds == pytest.approx(0.066)
    assert track.samples[0].frame_count == 1
    assert track.samples[0].latitude == pytest.approx(0.001)
    assert track.samples[0].relative_altitude == pytest.approx(10.0)
    assert track.samples[0].captured_at is not None
    assert sample_index_at(track, 0.032) == 0
    assert sample_index_at(track, 0.033) == 1


def test_rejects_srt_without_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "empty.SRT"
    path.write_text("1\n00:00:00,000 --> 00:00:01,000\nNo telemetry\n", encoding="utf-8")

    with pytest.raises(TelemetryError):
        parse_dji_srt(path)


def test_finds_case_insensitive_pair_without_duplicates(tmp_path: Path) -> None:
    video = tmp_path / "flight.MP4"
    subtitles = tmp_path / "flight.SRT"
    video.touch()
    subtitles.write_text(SRT, encoding="utf-8")

    assert find_video_and_srt(tmp_path) == (video, subtitles)

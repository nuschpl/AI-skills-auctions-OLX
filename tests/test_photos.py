from datetime import datetime
from pathlib import Path

import piexif
from PIL import Image

from scripts.photos import (
    normalise_photo,
    read_taken_at,
    strip_gps,
)


def _write_jpeg(path: Path, size: tuple[int, int] = (800, 600)) -> None:
    img = Image.new("RGB", size, color=(128, 200, 90))
    img.save(path, format="JPEG", quality=95)


def _write_jpeg_with_exif(path: Path, taken_at: datetime, gps: dict | None) -> None:
    img = Image.new("RGB", (800, 600), (100, 100, 100))
    exif_dict: dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = taken_at.strftime(
        "%Y:%m:%d %H:%M:%S"
    ).encode()
    if gps:
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = gps["lat"]
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = gps["lon"]
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = b"N"
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = b"E"
    exif_bytes = piexif.dump(exif_dict)
    img.save(path, format="JPEG", quality=95, exif=exif_bytes)


def test_normalise_resizes_long_edge(tmp_path: Path):
    src = tmp_path / "big.jpg"
    _write_jpeg(src, size=(6000, 3000))
    out = normalise_photo(src, max_long_edge=4096, quality=88)
    with Image.open(out) as img:
        assert max(img.size) == 4096
        assert img.size == (4096, 2048)


def test_normalise_skips_when_already_small(tmp_path: Path):
    src = tmp_path / "small.jpg"
    _write_jpeg(src, size=(800, 600))
    out = normalise_photo(src, max_long_edge=4096, quality=88)
    with Image.open(out) as img:
        assert img.size == (800, 600)


def test_read_taken_at_returns_datetime(tmp_path: Path):
    src = tmp_path / "with_exif.jpg"
    dt = datetime(2026, 4, 18, 9, 30, 0)
    _write_jpeg_with_exif(src, taken_at=dt, gps=None)
    assert read_taken_at(src) == dt


def test_read_taken_at_falls_back_to_mtime(tmp_path: Path):
    src = tmp_path / "no_exif.jpg"
    _write_jpeg(src)
    assert read_taken_at(src) is not None


def test_strip_gps_removes_coordinates(tmp_path: Path):
    src = tmp_path / "geo.jpg"
    _write_jpeg_with_exif(
        src,
        taken_at=datetime(2026, 4, 18, 9, 30),
        gps={"lat": ((52, 1), (14, 1), (0, 1)), "lon": ((21, 1), (0, 1), (0, 1))},
    )
    out = strip_gps(src)
    with Image.open(out) as img:
        exif_bytes = img.info.get("exif", b"")
    assert exif_bytes, "output must still have some EXIF"
    parsed = piexif.load(exif_bytes)
    assert parsed["GPS"] == {}

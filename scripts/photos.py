"""Photo normalisation: resize, strip GPS, read EXIF."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image


def normalise_photo(
    path: Path,
    *,
    max_long_edge: int = 4096,
    quality: int = 88,
    out_dir: Path | None = None,
) -> Path:
    """Resize to fit *max_long_edge* and re-encode JPEG. Returns new path."""
    out_dir = out_dir or path.parent
    out_path = out_dir / f"{path.stem}.normalised.jpg"
    with Image.open(path) as img:
        img = img.convert("RGB") if img.mode != "RGB" else img
        long = max(img.size)
        if long > max_long_edge:
            scale = max_long_edge / long
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.LANCZOS)
        exif_bytes = img.info.get("exif", b"")
        img.save(out_path, format="JPEG", quality=quality, exif=exif_bytes)
    return out_path


def read_taken_at(path: Path) -> datetime | None:
    """Return DateTimeOriginal from EXIF, or file mtime as fallback."""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            raw = exif.get(36867) or exif.get(306)
            if raw is None:
                exif_ifd = exif.get_ifd(0x8769)
                raw = exif_ifd.get(36867)
            if raw:
                if isinstance(raw, bytes):
                    raw = raw.decode("ascii", errors="ignore").rstrip("\x00").strip()
                return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def strip_gps(path: Path, out_path: Path | None = None) -> Path:
    """Return a copy of *path* with GPS EXIF removed."""
    import piexif

    out_path = out_path or path.with_name(f"{path.stem}.nogps.jpg")
    with Image.open(path) as img:
        exif_bytes = img.info.get("exif")
        if exif_bytes:
            exif_dict = piexif.load(exif_bytes)
            exif_dict["GPS"] = {}
            new_exif = piexif.dump(exif_dict)
        else:
            new_exif = b""
        img.save(
            out_path,
            format="JPEG",
            quality=img.info.get("quality", 88),
            exif=new_exif,
        )
    return out_path

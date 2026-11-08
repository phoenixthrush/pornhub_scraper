import re
from pathlib import Path

LIBRARY_ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r'"([^"]+)"\s+(https?://\S+)')


def artist_folder(root: Path, name: str) -> Path:
    if Path(name).is_absolute():
        raise ValueError(f"Artist folder must be relative: {name}")
    try:
        folder = (root / name).resolve()
    except RuntimeError as error:
        raise ValueError(f"Could not resolve artist folder: {name}") from error
    if folder == root or not folder.is_relative_to(root):
        raise ValueError(f"Artist folder is outside the library: {name}")
    return folder


def cleanup_partial_downloads(folder: Path):
    """Remove leftover yt-dlp parts from a completed artist folder."""
    for pattern in ("*.part", "*.part-Frag*", "*.ytdl"):
        for path in folder.glob(pattern):
            if path.is_file():
                print(f"Removing partial download: {path}")
                path.unlink(missing_ok=True)

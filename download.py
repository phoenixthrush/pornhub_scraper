import re
import subprocess
from pathlib import Path

from common import cleanup_partial_downloads

# ======================
# Configuration
# ======================
MOUNTPOINT = Path("mountpoint")
LINKS_FILE = MOUNTPOINT / "_links.txt"


def upgrade_yt_dlp():
    """Upgrading yt-dlp"""
    subprocess.run(["pip", "install", "--upgrade", "yt-dlp"])


def sort_links():
    """Sorting links by artist name"""
    with LINKS_FILE.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    lines = sorted(
        lines,
        key=lambda x: (
            re.match(r'"([^"]+)"\s+', x).group(1)
            if re.match(r'"([^"]+)"\s+', x)
            else ""
        ),
    )

    with LINKS_FILE.open("w", encoding="utf-8") as file:
        file.writelines(lines)


def download_videos():
    """Downloading videos with per-artist archive"""
    with LINKS_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            match = re.match(r'"([^"]+)"\s+(https?://\S+)', stripped)

            if not match:
                continue

            artist_name = match.group(1)
            url = match.group(2)

            # Create artist folder
            folder_path = MOUNTPOINT / artist_name
            folder_path.mkdir(parents=True, exist_ok=True)

            print(f"Using folder: {folder_path}")

            archive_path = str((folder_path / "_downloaded.txt").resolve())

            subprocess.run(
                [
                    "yt-dlp",
                    "--download-archive",
                    archive_path,
                    "--ignore-errors",
                    "--no-warnings",
                    "--referer",
                    "https://www.pornhub.com/",
                    "-o",
                    "%(id)s.%(ext)s",
                    "--embed-metadata",
                    "--embed-thumbnail",
                    "--no-overwrites",
                    url,
                ],
                cwd=folder_path,
            )


def main():
    try:
        upgrade_yt_dlp()
        sort_links()
        download_videos()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_partial_downloads()

    print("Quitting...")


if __name__ == "__main__":
    main()

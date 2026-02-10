import re
import subprocess
from pathlib import Path

from common import cleanup_partial_downloads


def upgrade_yt_dlp():
    """Upgrading yt-dlp"""
    subprocess.run(["pip", "install", "--upgrade", "yt-dlp"])


def sort_links():
    """Sorting links"""
    with open("mountpoint/links.txt", "r") as file:
        lines = file.readlines()

        # Sort lines by artist name (first capture group)
        lines = sorted(
            lines,
            key=lambda x: (
                re.match(r'"([^"]+)"\s+', x).group(1)
                if re.match(r'"([^"]+)"\s+', x)
                else ""
            ),
        )

    with open("mountpoint/links.txt", "w") as file:
        file.writelines(lines)


def download_videos():
    """Downloading videos"""
    archive_path = str((Path("mountpoint") / "downloaded.txt").resolve())
    with open("mountpoint/links.txt", "r") as file:
        for line in file:
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            match = re.match(r'"([^"]+)"\s+(https?://\S+)', stripped)

            if match:
                artist_name = match.group(1)
                url = match.group(2)

                folder_path = Path("mountpoint") / artist_name
                folder_path.mkdir(parents=True, exist_ok=True)

                print(f"Created folder: {folder_path}")

                subprocess.run(
                    [
                        "yt-dlp",
                        "--download-archive",
                        archive_path,
                        "--ignore-errors",
                        "--no-warnings",
                        "--referer",  # currently needed #15827
                        "https://www.pornhub.com/",
                        "-o",
                        "%(id)s.%(ext)s",
                        # "--postprocessor-args",
                        # "ffmpeg:-c:v libx265 -preset veryslow",
                        "--embed-metadata",  # somehow does not work?
                        "--embed-thumbnail",
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

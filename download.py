import subprocess
import sys
from fcntl import LOCK_EX, LOCK_NB, flock

from common import LIBRARY_ROOT, LINK, artist_folder, cleanup_partial_downloads


def upgrade_yt_dlp():
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp", "curl-cffi"],
        check=False,
    )
    if result.returncode:
        print(
            "Could not upgrade yt-dlp. Trying the installed version.", file=sys.stderr
        )


def download_videos(links):
    failed = False
    for artist_name, url in links:
        try:
            folder = artist_folder(LIBRARY_ROOT, artist_name)
        except ValueError as error:
            print(error, file=sys.stderr)
            failed = True
            continue

        folder.mkdir(parents=True, exist_ok=True)
        print(f"Using folder: {folder}")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "--download-archive",
                "_downloaded.txt",
                "--no-abort-on-error",
                "-o",
                "%(id)s.%(ext)s",
                "--embed-metadata",
                "--embed-thumbnail",
                "--no-overwrites",
                url,
            ],
            cwd=folder,
            check=False,
        )
        if result.returncode:
            print(
                f"yt-dlp exited with status {result.returncode}: {folder}",
                file=sys.stderr,
            )
            failed = True
        else:
            cleanup_partial_downloads(folder)
    return int(failed)


def main():
    try:
        with (LIBRARY_ROOT / "_links.txt").open(encoding="utf-8") as links_file:
            try:
                flock(links_file, LOCK_EX | LOCK_NB)
            except BlockingIOError:
                print("Another download run is active.", file=sys.stderr)
                return 1

            links = [
                match.groups()
                for line in links_file
                if (match := LINK.match(line.strip()))
            ]
            links.sort(key=lambda link: link[0])
            if not links:
                print("No download links found.", file=sys.stderr)
                return 1

            upgrade_yt_dlp()
            return download_videos(links)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

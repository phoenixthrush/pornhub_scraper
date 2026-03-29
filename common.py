from pathlib import Path


def cleanup_partial_downloads():
    """Removing partial downloads"""
    patterns = [
        "**/*.part",
        "**/*.ytdl",
    ]

    for pattern in patterns:
        for file in Path("mountpoint").glob(pattern):
            if file.is_file():
                print(f"Removing partial download: {file}")
                file.unlink()

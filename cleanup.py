"""Audit the scraper's output directory without modifying it."""

import argparse
import json
import os
import re
import stat
import struct
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from common import LIBRARY_ROOT, LINK, artist_folder

VIDEO_SUFFIXES = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".flv",
    ".ts",
    ".mpg",
    ".mpeg",
    ".wmv",
    ".ogv",
    ".3gp",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
PARTIAL = re.compile(
    r"(?:\.part(?:[-.]|$)|\.ytdl$|\.temp(?:\.|$)|\.tmp$|\.f\d+\.[^.]+$)", re.IGNORECASE
)
VIDEO_ID = re.compile(r"(?:ph[0-9a-f]{13}|[0-9a-f]{13}|[0-9]+)", re.IGNORECASE)
ARCHIVE_RECORD = re.compile(r"pornhub\s+([A-Za-z0-9_-]+)", re.IGNORECASE)
SOURCE_ID = re.compile(rb"(?:viewkey=|/video/)([A-Za-z0-9_-]+)")
BOX = struct.Struct(">I4s")
MAX_SIDECAR_BYTES = 2_000_000
METADATA_CHILDREN = {
    b"moov": {b"udta", b"meta"},
    b"udta": {b"meta"},
    b"meta": {b"ilst"},
    b"ilst": {b"\xa9nam", b"\xa9cmt", b"purl"},
}


def canonical_id(value):
    if value.lower().startswith("ph") and VIDEO_ID.fullmatch(value):
        return value[2:]
    return value


def read_at(stream, offset, size):
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("unexpected end of file")
    return data


def mp4_boxes(stream, start, end):
    while start < end:
        if end - start < BOX.size:
            raise ValueError(f"incomplete MP4 box header at byte {start}")
        size, kind = BOX.unpack(read_at(stream, start, BOX.size))
        header = BOX.size
        if size == 1:
            if end - start < 16:
                raise ValueError(f"incomplete extended MP4 box header at byte {start}")
            size = struct.unpack(">Q", read_at(stream, start + header, 8))[0]
            header += 8
        elif size == 0:
            size = end - start
        if not header <= size <= end - start:
            raise ValueError(f"invalid MP4 box size at byte {start}")
        yield kind, start + header, start + size
        start += size


def mp4_tags(stream, kind, start, end, tags):
    if kind == b"meta":
        start += 4
        if start > end:
            raise ValueError("incomplete MP4 metadata header")
    if kind in METADATA_CHILDREN:
        child_kinds = set()
        for child, offset, limit in mp4_boxes(stream, start, end):
            child_kinds.add(child)
            if child in METADATA_CHILDREN[kind]:
                mp4_tags(stream, child, offset, limit, tags)
        if kind == b"moov" and not {b"mvhd", b"trak"} <= child_kinds:
            raise ValueError("movie box is missing a header or track")
    else:
        for child, offset, limit in mp4_boxes(stream, start, end):
            if child == b"data" and 8 < limit - offset <= 8192:
                tags[kind] = read_at(stream, offset + 8, limit - offset - 8)


def inspect_video(path, size):
    """Return embedded tags and whether the container format was checked."""
    with path.open("rb") as stream:
        suffix = path.suffix.lower()
        if suffix in {".mp4", ".m4v", ".mov", ".3gp"}:
            tags = {}
            movie = False
            media = False
            for kind, start, end in mp4_boxes(stream, 0, size):
                if kind == b"moov" and end > start:
                    movie = True
                    mp4_tags(stream, kind, start, end, tags)
                if kind == b"mdat" and end > start:
                    media = True
            if not movie or not media:
                raise ValueError("missing movie (moov) or media (mdat) box")
            return tags, True
        if suffix in {".mkv", ".webm"}:
            if stream.read(4) != b"\x1a\x45\xdf\xa3":
                raise ValueError("missing EBML signature")
        elif suffix == ".avi":
            header = stream.read(12)
            if header[:4] != b"RIFF" or header[8:] != b"AVI ":
                raise ValueError("missing AVI signature")
        elif suffix == ".flv":
            if stream.read(3) != b"FLV":
                raise ValueError("missing FLV signature")
        else:
            return {}, False
        return {}, True


def read_text(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_SIDECAR_BYTES + 1)
    if len(data) > MAX_SIDECAR_BYTES:
        raise ValueError("text file exceeds the audit size limit")
    return data.decode("utf-8-sig")


def audit_links(root, note, totals):
    path = root / "_links.txt"
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("links file is not a regular file")
        lines = read_text(path).splitlines()
    except (OSError, ValueError) as error:
        note("unreadable link list", path, str(error))
        return

    seen = set()
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = LINK.match(line)
        if not match:
            note("malformed link entry", path, f"line {number}")
            continue
        try:
            folder = artist_folder(root, match[1])
        except (OSError, ValueError):
            note("link folder outside library", path, f"line {number}")
            continue
        link = (folder, match[2])
        if link in seen:
            note("duplicate link entry", path, f"line {number}")
        seen.add(link)
        totals["download links"] += 1
        if not folder.is_dir():
            note("missing configured folder", folder)


def audit_ledger(path, note, totals):
    ids = set()
    try:
        lines = read_text(path).splitlines()
    except (OSError, ValueError) as error:
        note("unreadable archive", path, str(error))
        return None

    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        match = ARCHIVE_RECORD.fullmatch(line)
        if not match:
            note("malformed archive record", path, f"line {number}")
            continue
        totals["archive records"] += 1
        if not VIDEO_ID.fullmatch(match[1]):
            note("unexpected archive ID format", path, f"line {number}")
        identifier = canonical_id(match[1])
        if identifier in ids:
            note("duplicate archive ID", path, f"line {number}: {identifier}")
        ids.add(identifier)
    return ids


def audit_sidecar(path, identifier, note):
    try:
        content = read_text(path)
        if path.suffix.lower() == ".nfo":
            metadata_id = ET.fromstring(content).findtext("uniqueid")
        else:
            metadata = json.loads(content)
            if not isinstance(metadata, dict):
                raise ValueError("expected a JSON object")
            metadata_id = metadata.get("id")
    except (OSError, ValueError, ET.ParseError) as error:
        note("invalid metadata sidecar", path, str(error))
        return

    if not metadata_id:
        note("metadata sidecar missing an ID", path)
    elif canonical_id(str(metadata_id)) != identifier:
        note("metadata sidecar ID mismatch", path)


def audit(root):
    totals = Counter()
    issues = defaultdict(list)
    videos = defaultdict(lambda: defaultdict(list))
    archives = {}
    sidecars = []

    def note(kind, path, detail=""):
        issues[kind].append((path, detail))

    def walk_error(error):
        note("unreadable directory", Path(error.filename or root), str(error))

    audit_links(root, note, totals)
    checkout = Path(__file__).resolve().parent
    for directory, dirs, files in os.walk(root, onerror=walk_error):
        parent = Path(directory)
        dirs.sort()
        for name in dirs[:]:
            path = parent / name
            if (
                name == ".git"
                or path == checkout
                or (
                    parent == root
                    and name == checkout.name
                    and (path / "download.py").is_file()
                )
            ):
                dirs.remove(name)
            elif path.is_symlink():
                dirs.remove(name)
                note("symlink directory skipped", path)

        for name in sorted(files):
            path = parent / name
            try:
                attrs = path.lstat()
            except OSError as error:
                note("unreadable file", path, str(error))
                continue
            if not stat.S_ISREG(attrs.st_mode):
                note("non-regular file skipped", path)
                continue
            totals["files"] += 1
            suffix = path.suffix.lower()
            if attrs.st_size == 0:
                note("empty file", path)
            if PARTIAL.search(name):
                note("partial or temporary download", path)
            elif name == "_downloaded.txt":
                totals["archives"] += 1
                archives[parent] = audit_ledger(path, note, totals)
            elif suffix in VIDEO_SUFFIXES:
                totals["videos"] += 1
                identifier = canonical_id(path.stem)
                videos[parent][identifier].append(path)
                if not VIDEO_ID.fullmatch(path.stem):
                    note("unexpected video filename", path)
                if not attrs.st_size:
                    continue
                try:
                    tags, checked = inspect_video(path, attrs.st_size)
                except (OSError, ValueError) as error:
                    note("invalid or unreadable video header", path, str(error))
                    continue
                if not checked:
                    note("video format without a header check", path)
                else:
                    totals["headers checked"] += 1
                if tags.get(b"\xa9nam"):
                    totals["embedded titles"] += 1
                ids = {
                    canonical_id(match.decode("ascii"))
                    for field in (b"\xa9cmt", b"purl")
                    for match in SOURCE_ID.findall(tags.get(field, b""))
                }
                if ids:
                    totals["embedded source IDs"] += 1
                    if ids != {identifier}:
                        note("embedded source ID mismatch", path)
            elif suffix in IMAGE_SUFFIXES or suffix in {".json", ".nfo"}:
                sidecars.append(path)
            elif path != root / "_links.txt":
                note("unexpected file", path)

    all_ids = {identifier for folder in videos.values() for identifier in folder}
    for folder, ids in archives.items():
        if ids is None:
            continue
        archive = folder / "_downloaded.txt"
        for identifier in sorted(ids - videos.get(folder, {}).keys()):
            kind = (
                "archive ID found only in another folder"
                if identifier in all_ids
                else "archive ID missing video"
            )
            note(kind, archive, identifier)
    for folder, by_id in videos.items():
        if folder not in archives:
            note("folder missing an archive", folder)
        archived = archives.get(folder, set())
        for identifier, paths in by_id.items():
            if len(paths) > 1:
                for path in paths:
                    note("duplicate video ID in folder", path)
            if archived is not None and identifier not in archived:
                for path in paths:
                    note("unarchived video", path)

    for path in sidecars:
        suffix = path.suffix.lower()
        name = path.name
        stem = (
            name[: -len(".info.json")]
            if name.lower().endswith(".info.json")
            else path.stem
        )
        identifier = canonical_id(stem)
        paired = identifier in videos.get(path.parent, {})
        if suffix in IMAGE_SUFFIXES:
            totals["images"] += 1
            note("separate thumbnail" if paired else "standalone image", path)
        else:
            totals["metadata sidecars"] += 1
            if not paired:
                note("orphan metadata sidecar", path)
            audit_sidecar(path, identifier, note)

    return totals, issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path, nargs="?")
    parser.add_argument("--details", action="store_true", help="show paths and details")
    args = parser.parse_args()
    try:
        root = (args.library or LIBRARY_ROOT).resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(root)
        if args.library is None and not (root / "_links.txt").is_file():
            raise FileNotFoundError(
                f"{root / '_links.txt'} is missing. Pass the library path explicitly."
            )
        totals, issues = audit(root)
    except (OSError, RuntimeError) as error:
        print(f"Cannot audit library: {error}", file=sys.stderr)
        return 2

    print(f"Library: {root}")
    for label in (
        "files",
        "videos",
        "headers checked",
        "archives",
        "archive records",
        "download links",
        "embedded titles",
        "embedded source IDs",
        "images",
        "metadata sidecars",
    ):
        print(f"{label}: {totals[label]}")
    print(f"Findings: {sum(map(len, issues.values()))}")
    for kind, findings in sorted(issues.items()):
        print(f"  {kind}: {len(findings)}")
        if args.details:
            for path, detail in findings:
                display = path.relative_to(root) if path.is_relative_to(root) else path
                suffix = f" ({detail})" if detail else ""
                print(f"    {display}{suffix}")
    if "unreadable directory" in issues and not totals["files"]:
        return 2
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())

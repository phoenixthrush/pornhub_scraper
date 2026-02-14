# https://kodi.wiki/view/NFO_files/Templates

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from common import cleanup_partial_downloads

# ======================
# Configuration
# ======================
MOUNTPOINT = Path("mountpoint")
VIDEO_GLOB = "**/*.mp4"
JSON_GLOB = "**/*.json"


def download_metadata_json():
    """Downloading metadata in JSON format"""

    for file in MOUNTPOINT.glob(VIDEO_GLOB):
        if file.is_file():
            file_id = file.stem
            url = f"https://www.pornhub.com/view_video.php?viewkey={file_id}"

            subprocess.run(
                [
                    "yt-dlp",
                    "--write-info-json",
                    url,
                    "--referer",
                    "https://www.pornhub.com/",
                    "-o",
                    f"{file_id}.%(ext)s",
                ],
                cwd=file.parent,
            )

            info_json_path = file.parent / f"{file_id}.info.json"
            if info_json_path.is_file():
                with open(info_json_path, "r", encoding="utf-8") as info_file:
                    parsed_json = json.load(info_file)

                # write pretty id.json
                output_json_path = file.parent / f"{file_id}.json"
                with open(output_json_path, "w", encoding="utf-8") as output_file:
                    json.dump(parsed_json, output_file, indent=4, ensure_ascii=False)

                # delete temporary file
                info_json_path.unlink()


def convert_json_to_nfo():
    """Converting JSON metadata to NFO format"""

    def _text(value) -> str:
        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        if isinstance(value, (list, tuple)):
            return ", ".join(_text(v) for v in value if _text(v))
        if isinstance(value, dict):
            for key in ("name", "title", "id"):
                if key in value:
                    return _text(value.get(key))
            return ""
        return str(value)

    for json_file in MOUNTPOINT.glob(JSON_GLOB):
        if not json_file.is_file():
            continue

        with open(json_file, "r", encoding="utf-8") as file:
            data = json.load(file)

        title = _text(data.get("title", ""))
        originaltitle = title
        uniqueid = _text(data.get("id", ""))
        premiered = ""

        if "upload_date" in data and len(data["upload_date"]) == 8:
            premiered = f"{data['upload_date'][:4]}-{data['upload_date'][4:6]}-{data['upload_date'][6:]}"

        userrating = 0
        thumb = _text(data.get("thumbnail", ""))
        genres = data.get("categories") or []
        tags = data.get("tags") or []
        uploader = data.get("uploader")

        movie = ET.Element("movie")
        ET.SubElement(movie, "title").text = title
        ET.SubElement(movie, "originaltitle").text = originaltitle

        uniqueid_el = ET.SubElement(
            movie, "uniqueid", {"type": "home", "default": "true"}
        )
        uniqueid_el.text = uniqueid

        if premiered:
            ET.SubElement(movie, "premiered").text = premiered

        ET.SubElement(movie, "userrating").text = str(userrating)

        if thumb:
            ET.SubElement(movie, "thumb").text = thumb

        for genre in genres if isinstance(genres, (list, tuple)) else [genres]:
            g = _text(genre).strip()
            if g:
                ET.SubElement(movie, "genre").text = g

        for tag in tags if isinstance(tags, (list, tuple)) else [tags]:
            t = _text(tag).strip()
            if t:
                ET.SubElement(movie, "tag").text = t

        uploader_names = []
        if isinstance(uploader, (list, tuple)):
            uploader_names = [u for u in (_text(v).strip() for v in uploader) if u]
        else:
            u = _text(uploader).strip()
            if u:
                uploader_names = [u]

        for idx, name in enumerate(uploader_names, start=1):
            actor_el = ET.SubElement(movie, "actor")
            ET.SubElement(actor_el, "name").text = name
            ET.SubElement(actor_el, "order").text = str(idx)

        tree = ET.ElementTree(movie)
        try:
            ET.indent(tree, space="    ", level=0)
        except Exception:
            pass

        nfo_path = json_file.with_suffix(".nfo")
        with open(nfo_path, "w", encoding="utf-8") as nfo_file:
            tree.write(nfo_file, encoding="unicode", xml_declaration=True)

        json_file.unlink()


def main():
    try:
        download_metadata_json()
        convert_json_to_nfo()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_partial_downloads()

    print("Quitting...")


if __name__ == "__main__":
    main()

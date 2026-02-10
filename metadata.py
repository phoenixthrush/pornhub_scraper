# https://kodi.wiki/view/NFO_files/Templates
"""
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<movie>
    <title></title>
    <originaltitle></originaltitle>
    <userrating>0</userrating>
    <plot></plot>
    <mpaa></mpaa>
    <uniqueid type="" default="true"></uniqueid> <!-- add a value to type="" eg imdb, tmdb, home, sport, docu, see sample below -->
    <genre></genre>
    <tag></tag>
    <country></country>
    <set>
        <name></name>
        <overview></overview>
    </set>
    <credits></credits>
    <director></director>
    <premiered></premiered> <!-- yyyy-mm-dd -->
    <studio></studio>
    <actor>
        <name></name>
        <role></role>
        <order></order>
    </actor>
</movie>
"""

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from common import cleanup_partial_downloads


def download_metadata_json():
    """Downloading metadata in JSON format"""

    for file in Path("mountpoint").glob("**/*.mp4"):
        if file.is_file():
            file_id = file.stem
            url = f"https://www.pornhub.com/view_video.php?viewkey={file_id}"

            subprocess.run(
                [
                    "yt-dlp",
                    "--write-info-json",
                    url,
                    "--referer",  # currently needed #15827
                    "https://www.pornhub.com/",
                    "-o",
                    f"{file_id}.%(ext)s",
                ],
                cwd=file.parent,
            )

            info_json_path = file.parent / f"{file_id}.info.json"
            if info_json_path.is_file():
                with open(info_json_path, "r") as info_file:
                    info_data = info_file.read()

                parsed_json = json.loads(info_data)
                pretty_json = json.dumps(parsed_json, indent=4)

                # write to id.json
                output_json_path = file.parent / f"{file_id}.json"
                with open(output_json_path, "w") as output_file:
                    output_file.write(pretty_json)

                # delete the id.info.json
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

    for json_file in Path("mountpoint").glob("**/*.json"):
        if json_file.is_file():
            with open(json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            # Extract fields with fallbacks
            title = _text(data.get("title", ""))
            originaltitle = _text(data.get("title", ""))
            uniqueid = _text(data.get("id", ""))
            premiered = ""

            if "upload_date" in data and len(data["upload_date"]) == 8:
                premiered = f"{data['upload_date'][:4]}-{data['upload_date'][4:6]}-{data['upload_date'][6:]}"

            userrating = 0
            thumb = _text(data.get("thumbnail", ""))
            genres = data.get("categories") or []
            tags = data.get("tags") or []
            uploader = data.get("uploader")

            # Build XML safely (escapes &, <, > automatically)
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

            if isinstance(genres, (list, tuple)):
                for genre in genres:
                    g = _text(genre).strip()
                    if g:
                        ET.SubElement(movie, "genre").text = g
            else:
                g = _text(genres).strip()
                if g:
                    ET.SubElement(movie, "genre").text = g

            if isinstance(tags, (list, tuple)):
                for tag in tags:
                    t = _text(tag).strip()
                    if t:
                        ET.SubElement(movie, "tag").text = t
            else:
                t = _text(tags).strip()
                if t:
                    ET.SubElement(movie, "tag").text = t

            # Represent uploader as actor(s)
            uploader_names: list[str] = []
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
            # Pretty print when available (Python 3.9+)
            try:
                ET.indent(tree, space="    ", level=0)
            except Exception:
                pass

            nfo_path = json_file.with_suffix(".nfo")

            with open(nfo_path, "w", encoding="utf-8") as nfo_file:
                tree.write(nfo_file, encoding="unicode", xml_declaration=True)

            # remove the original JSON file
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

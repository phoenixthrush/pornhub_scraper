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

    for json_file in Path("mountpoint").glob("**/*.json"):
        if json_file.is_file():
            with open(json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            # Extract fields with fallbacks
            title = data.get("title", "")
            originaltitle = data.get("title", "")
            uniqueid = data.get("id", "")
            premiered = ""

            if "upload_date" in data and len(data["upload_date"]) == 8:
                premiered = f"{data['upload_date'][:4]}-{data['upload_date'][4:6]}-{data['upload_date'][6:]}"

            userrating = 0
            thumb = data.get("thumbnail", "")
            genres = data.get("categories", [])
            tags = data.get("tags", [])
            actors = data.get("uploader", "")

            # Build XML
            nfo = [
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                "<movie>",
                f"    <title>{title}</title>",
                f"    <originaltitle>{originaltitle}</originaltitle>",
                f'    <uniqueid type="home" default="true">{uniqueid}</uniqueid>',
                f"    <premiered>{premiered}</premiered>",
                f"    <userrating>{userrating}</userrating>",
                f"    <thumb>{thumb}</thumb>",
            ]

            for genre in genres:
                nfo.append(f"    <genre>{genre}</genre>")

            for tag in tags:
                nfo.append(f"    <tag>{tag}</tag>")

            # Actor block
            if actors:
                nfo.append("    <actor>")
                nfo.append(f"        <name>{actors}</name>")
                nfo.append("        <order>1</order>")
                nfo.append("    </actor>")
            nfo.append("</movie>")

            nfo_content = "\n".join(nfo)
            nfo_path = json_file.with_suffix(".nfo")

            with open(nfo_path, "w", encoding="utf-8") as nfo_file:
                nfo_file.write(nfo_content)

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

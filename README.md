# PornHub-Scraper

Download videos with yt-dlp and embed metadata and thumbnails. Put the scraper
checkout directly inside the library folder, alongside `_links.txt`. Each
entry in `_links.txt` has the form `"Artist folder" https://example.org/videos`.
Videos and each artist's `_downloaded.txt` archive go in that artist's folder.

Run the downloader with `python download.py`. It finds the library relative to
the script, so the current working directory can be anywhere.

Run `python cleanup.py` for a read-only library audit. Use `--details` to
show the paths behind the summary or pass a library directory to audit a
different copy. The audit reads container headers and metadata without decoding
the video streams. It exits with 1 for findings and 2 if it cannot read the
library.

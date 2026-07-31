"""
Download YouTube video as video or audio
Dependencies: `pip install yt-dlp`; also make sure ffmpeg is installed
Usage: `python ytdl.py [YOUTUBE_URL] --mode [mp3/mp4]
"""

import sys
import argparse
from pathlib import Path

import yt_dlp

def show_progress(data):
    if data.get("status") == "downloading":
        percent = data.get("_percent_str", "").strip()
        speed = data.get("_speed_str", "").strip()
        print(f"\r{percent} at {speed}", end="", flush=True)
    elif data.get("status") == "finished":
        print("\nDownload Complete")

"""
Download YouTube video from `url` as video (`mode`="mp4") or audio (`mode`="mp3") to `output_dir` (default to current dir)
"""
def download(url: str, mode: str="mp4", output_dir: Path=None):
    if output_dir is None:
        output_dir = Path.cwd()

    output_dir.mkdir(parents=True, exist_ok=True)

    options = {
        "outtmpl": str(output_dir / "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "progress_hooks": [show_progress],
    }

    if mode == "mp4":
        options = {
            **options,
            "format": "bv*[height<=1080]+ba/b[height<=1080]",
            "merge_output_format": "mp4",
        }
    else:
        options = {
            **options,
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.download([url])
    except yt_dlp.utils.DownloadError as error:
        print(f"Download failed: {error}", file=sys.stderr)
        return 1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("-m", "--m", "-mode", "--mode", choices=("mp4", "mp3"), default="mp4")
    parser.add_argument("-o", "--o", "-output", "--output", type=Path, default=None)
    args = parser.parse_args()

    download(args.url, args.m, args.o)


if __name__ == "__main__":
    main() 
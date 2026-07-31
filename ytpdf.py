"""
Convert a YouTube video into a PDF with many advanced options

Dependencies: `pip install yt-dlp opencv-python numpy pillow`; also make sure ffmpeg is installed

Usage:
    `python ytpdf.py [YOUTUBE_URL]`
    `python ytpdf.py [YOUTUBE_URL] --crop`
    `python ytpdf.py [YOUTUBE_URL] --interval 0.5 --threshold 0.06`
    `python ytpdf.py [YOUTUBE_URL] --margin 0.4 --gap 0.15`
"""

import argparse
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ytdl import download

A4W = 8.27
A4H = 11.69

def crop_frame(frame, bt, t, b, l, r, min_content_ratio=0.02):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = gray > bt

    rows = np.where(np.mean(mask, axis=1) > min_content_ratio)[0]
    cols = np.where(np.mean(mask, axis=0) > min_content_ratio)[0]

    if len(rows) == 0 or len(cols) == 0:
        return frame

    cropped = frame[
        rows[0] + t : rows[-1] - b,
        cols[0] + l : cols[-1] - r
    ]

    return cropped if cropped.size > 0 else frame

def create_fingerprint(frame, width=160, height=90):
    return cv2.resize(
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
        (width, height),
        interpolation=cv2.INTER_AREA
    ).astype(np.float32) / 255.0

def unique_frame(fingerprint, selected_fingerprints, threshold):
    for selected in selected_fingerprints:
        if float(np.mean(np.abs(fingerprint - selected))) < threshold:
            return False

    return True

def get_unique_frames(video_path, fdir, interval, threshold, crop, bt, t, b, l, r):
    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)

    if not fps or fps <= 0:
        fps = 30.0

    frame_cnt = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_step = max(1, round(fps * interval))

    fpaths = []
    fprints = []

    i = 0
    n = 0

    while True:
        success, frame = capture.read()

        if not success:
            break

        if i % frame_step != 0:
            i += 1
            continue

        if crop:
            frame = crop_frame(frame, bt, t, b, l, r)

        fprint = create_fingerprint(frame)

        if unique_frame(fprint, fprints, threshold):
            n += 1
            fpath = fdir / f"frame-{n:05d}.png"

            cv2.imwrite(str(fpath), frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])

            fpaths.append(fpath)
            fprints.append(fprint)

        i += 1

        if frame_cnt > 0:
            percent = min(100, i / frame_cnt * 100)
            print(f"\rProcessing video: {percent:5.1f}% "f"({n} unique frames)", end="", flush=True)

    capture.release()
    print()

    return fpaths

def resize_frame(image, max_width, max_height):
    width_scale = max_width / image.width
    height_scale = max_height / image.height
    scale = min(width_scale, height_scale)

    new_width = max(1, round(image.width * scale))
    new_height = max(1, round(image.height * scale))

    return image.resize((new_width, new_height), Image.Resampling.BOX)

def save_pdf(frame_paths, out_dir, margin, gap, dpi, page_width_inches=A4W, page_height_inches=A4H):
    pg_width = round(page_width_inches * dpi)
    pg_height = round(page_height_inches * dpi)
    margin = round(margin * dpi)
    gap = round(gap * dpi)

    content_width = pg_width - 2 * margin
    content_height = pg_height - 2 * margin

    pgs = []
    pg = Image.new("RGB", (pg_width, pg_height), "white")
    curr_y = margin

    for index, frame_path in enumerate(frame_paths):
        with Image.open(frame_path) as source:
            frame = source.convert("RGB")

        noborders = 2

        frame = resize_frame(frame, max_width=content_width, max_height=content_height)
        frame = frame.crop([
            noborders,
            noborders,
            frame.width - noborders,
            frame.height - noborders
        ])

        left_height = frame.height

        if curr_y > margin:
            left_height += gap

        page_bottom = pg_height - margin

        if curr_y + left_height > page_bottom:
            pgs.append(pg)
            pg = Image.new("RGB", (pg_width, pg_height), "white")
            curr_y = margin
        elif curr_y > margin:
            curr_y += gap

        x = margin + (content_width - frame.width) // 2
        pg.paste(frame, (x, curr_y))
        curr_y += frame.height

        print(f"\rCreating PDF: frame {index + 1}/{len(frame_paths)}", end="", flush=True)

    pgs.append(pg)
    print()

    out_dir.parent.mkdir(parents=True, exist_ok=True)

    pgs[0].save(out_dir, "PDF", save_all=True, append_images=pgs[1:], resolution=dpi)


def find_downloaded_video(dir: Path) -> Path:
    video_paths = sorted(dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)

    if not video_paths:
        raise RuntimeError("Could not find the downloaded video file")

    return max(video_paths, key=lambda path: path.stat().st_size)

parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("-o", "--o", "-output", "--output", type=Path, default=Path("output.pdf"))
parser.add_argument("-i", "--i", "-interval", "--interval", type=float, default=1.0)
parser.add_argument("-thresh", "--thresh", "-threshold", "--threshold", type=float, default=0.08)
parser.add_argument("-c", "--c", "-crop", "--crop", action="store_true")
parser.add_argument("--bt", "--black-threshold", type=int, default=16)
parser.add_argument("-m", "-margin", "--m", "--margin", type=float, default=0.25)
parser.add_argument("-g", "--g", "-gap", "--gap", type=float, default=0.12)
parser.add_argument("--dpi", type=int, default=150)
parser.add_argument("--t", "--top", type=int, default=0)
parser.add_argument("--b", "--bottom", type=int, default=0)
parser.add_argument("--l", "--left", type=int, default=0)
parser.add_argument("--r", "--right", type=int, default=0)

args = parser.parse_args()

with tempfile.TemporaryDirectory(prefix="ytpdf-") as temp_name:
    temp_dir = Path(temp_name)
    video_dir = temp_dir / "video"
    frames_dir = temp_dir / "frames"

    video_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading video...")

    result = download(args.url, output_dir=video_dir)

    if result != 0:
        raise RuntimeError("Video download failed")

    video_paths = list(video_dir.glob("*.mp4"))

    if not video_paths:
        raise RuntimeError("Could not find the downloaded video file")

    video_path = max(video_paths, key=lambda path: path.stat().st_size)

    print(f"Downloaded: {video_path.name}")
    print("Extracting unique frames...")

    frame_paths = get_unique_frames(video_path, frames_dir, args.i, args.thresh, args.c, args.bt, args.t, args.b, args.l, args.r)

    print(f"Selected {len(frame_paths)} unique frames")
    print("Building PDF...")

    save_pdf(frame_paths, args.o, args.m, args.g, args.dpi)

    print(f"PDF created at {args.o.resolve()}")

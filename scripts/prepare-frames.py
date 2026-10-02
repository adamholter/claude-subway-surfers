#!/usr/bin/env python3
"""Prepare compact JPEG-in-SVG frames for the Claude Desktop side pane."""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "frames"
NATIVE_SVG_LIMIT = 131_072
DEFAULT_FRAME_LIMIT = 100_000
PART_LIMIT = 4 * 1024 * 1024 - 1
FRAME_NAME = re.compile(r"^frame-(\d+)\.jpg$")


def run(command: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"Required executable is missing: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or error.stdout.strip() or str(error)
        raise RuntimeError(message) from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Timed out after {timeout}s: {command[0]}") from error


def ffmpeg_quality(quality: int) -> int:
    """Map JPEG quality 1..100 onto FFmpeg's inverse MJPEG qscale 1..31."""
    return max(1, min(31, round(1 + (100 - quality) * 0.20)))


def extract_frames(
    source: Path,
    target: Path,
    *,
    fps: int,
    seconds: float,
    width: int,
    quality: int,
) -> list[Path]:
    frame_limit = max(1, math.ceil(fps * seconds))
    qscale = ffmpeg_quality(quality)
    pattern = target / "frame-%06d.jpg"
    vf = f"fps={fps},scale={width}:-2:flags=lanczos,setsar=1"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-an",
            "-sn",
            "-dn",
            "-vf",
            vf,
            "-t",
            f"{seconds:.3f}",
            "-frames:v",
            str(frame_limit),
            "-fps_mode",
            "passthrough",
            "-q:v",
            str(qscale),
            "-start_number",
            "0",
            "-f",
            "image2",
            str(pattern),
        ]
    )
    frames: list[tuple[int, Path]] = []
    for path in target.iterdir():
        match = FRAME_NAME.match(path.name)
        if match:
            frames.append((int(match.group(1)), path))
    frames.sort(key=lambda item: item[0])
    if not frames:
        raise RuntimeError("FFmpeg produced no video frames")
    return [path for _, path in frames]


def image_dimensions(frame: Path) -> tuple[int, int]:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(frame),
        ]
    )
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise RuntimeError(f"Could not read dimensions from {frame.name}")
    return int(streams[0]["width"]), int(streams[0]["height"])


def svg_frame(frame: Path, width: int, height: int, limit: int) -> str:
    encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">'
        f'<image x="0" y="0" width="{width}" height="{height}" '
        f'preserveAspectRatio="none" '
        f'href="data:image/jpeg;base64,{encoded}"/></svg>'
    )
    if len(svg) > limit:
        raise RuntimeError(
            f"{frame.name} needs {len(svg):,} SVG characters, over the "
            f"{limit:,} character frame limit"
        )
    return svg


def flush_part(stage: Path, part_index: int, frames: list[str]) -> str:
    name = f"part-{part_index:03d}.json"
    payload = json.dumps(frames, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(payload) >= 4 * 1024 * 1024:
        raise RuntimeError(f"{name} is not below the 4 MiB part limit")
    (stage / name).write_bytes(payload)
    return name


def build_parts(
    frame_paths: list[Path],
    stage: Path,
    *,
    width: int,
    height: int,
    frame_limit: int,
) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    current_bytes = 2  # JSON brackets

    for path in frame_paths:
        svg = svg_frame(path, width, height, frame_limit)
        item_bytes = len(json.dumps(svg, ensure_ascii=True).encode("ascii"))
        added_bytes = item_bytes + (1 if current else 0)
        if current and current_bytes + added_bytes > PART_LIMIT:
            parts.append(flush_part(stage, len(parts), current))
            current = []
            current_bytes = 2
            added_bytes = item_bytes
        if current_bytes + added_bytes > PART_LIMIT:
            raise RuntimeError(f"A single frame in {path.name} exceeds the part limit")
        current.append(svg)
        current_bytes += added_bytes

    if current:
        parts.append(flush_part(stage, len(parts), current))
    return parts


def atomic_write(path: Path, data: bytes, staging: Path) -> None:
    staged = staging / path.name
    staged.write_bytes(data)
    os.replace(staged, path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="input gameplay video")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--width", type=int, default=240)
    parser.add_argument(
        "--quality",
        type=int,
        default=70,
        help="JPEG quality from 1 (small) to 100 (best); default 70",
    )
    parser.add_argument(
        "--max-frame-chars",
        type=int,
        default=DEFAULT_FRAME_LIMIT,
        help="maximum characters in one SVG source (default 100000; native cap 131072)",
    )
    args = parser.parse_args(argv)
    if args.fps < 1 or args.fps > 60:
        parser.error("--fps must be between 1 and 60")
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be a finite number greater than zero")
    if args.width < 16 or args.width > 2048:
        parser.error("--width must be between 16 and 2048 pixels")
    if not 1 <= args.quality <= 100:
        parser.error("--quality must be between 1 and 100")
    if not 512 <= args.max_frame_chars <= NATIVE_SVG_LIMIT:
        parser.error(f"--max-frame-chars must be between 512 and {NATIVE_SVG_LIMIT}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(f"Input video does not exist: {source}", file=sys.stderr)
        return 2
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ffmpeg and ffprobe must be available on PATH", file=sys.stderr)
        return 2

    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix="subway-jpegs-") as frame_tmp:
            frame_paths = extract_frames(
                source,
                Path(frame_tmp),
                fps=args.fps,
                seconds=args.seconds,
                width=args.width,
                quality=args.quality,
            )
            width, height = image_dimensions(frame_paths[0])
            with tempfile.TemporaryDirectory(prefix=".subway-stage-", dir=output) as stage_tmp:
                stage = Path(stage_tmp)
                parts = build_parts(
                    frame_paths,
                    stage,
                    width=width,
                    height=height,
                    frame_limit=args.max_frame_chars,
                )
                manifest = json.dumps(
                    {"fps": args.fps, "width": width, "height": height, "parts": parts},
                    separators=(",", ":"),
                ).encode("ascii")

                for name in parts:
                    os.replace(stage / name, output / name)
                atomic_write(output / "clip.json", manifest, stage)
    except (RuntimeError, OSError, json.JSONDecodeError) as error:
        print(f"Frame preparation failed: {error}", file=sys.stderr)
        return 1

    print(
        f"Prepared {len(frame_paths)} frames at {args.fps} fps, "
        f"{width}x{height}, max SVG {args.max_frame_chars:,} chars, "
        f"{len(parts)} JSON parts in {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

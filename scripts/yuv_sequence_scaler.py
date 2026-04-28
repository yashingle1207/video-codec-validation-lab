"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    yuv_sequence_scaler.py
Purpose: Resize raw YUV420p sequences while preserving frame rate and pixel format.

Description:
    This command-line helper wraps FFmpeg rawvideo input/output flags so test
    sequences can be rescaled for codec experiments. It accepts explicit source
    and destination geometry, optionally limits frame count, and writes another
    headerless YUV420p file compatible with the encoder validation pipeline.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the YUV scaler.

    Returns:
        argparse.Namespace: Validated CLI options including input/output paths,
        source and destination dimensions, frame rate, and optional frame limit.
    """
    parser = argparse.ArgumentParser(description="Rescale a raw YUV420p sequence.")
    parser.add_argument("--input", required=True, help="Source .yuv file")
    parser.add_argument("--output", required=True, help="Destination .yuv file")
    parser.add_argument("--src-width", type=int, required=True)
    parser.add_argument("--src-height", type=int, required=True)
    parser.add_argument("--dst-width", type=int, required=True)
    parser.add_argument("--dst-height", type=int, required=True)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument(
        "--frames", type=int, default=0, help="Number of frames to process (0 = all)"
    )
    return parser.parse_args()


def main() -> int:
    """Scale a headerless raw YUV420p sequence using FFmpeg.

    Returns:
        int: Process exit code. Zero means FFmpeg succeeded and wrote the output.
    """
    args = parse_args()

    src = Path(args.input)
    dst = Path(args.output)

    if not src.is_file():
        print(f"ERROR: input file not found: '{src}'", file=sys.stderr)
        return 1

    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "yuv420p",
        "-s:v", f"{args.src_width}x{args.src_height}",
        "-r", str(args.fps),
        "-i", str(src),
        # FFmpeg's scale filter resamples luma and chroma planes consistently.
        "-vf", f"scale={args.dst_width}:{args.dst_height}",
        "-pix_fmt", "yuv420p",
        "-f", "rawvideo",
    ]
    if args.frames > 0:
        cmd += ["-frames:v", str(args.frames)]
    cmd.append(str(dst))

    print(
        f"Scaling {args.src_width}x{args.src_height} -> "
        f"{args.dst_width}x{args.dst_height}"
    )
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("ERROR: ffmpeg scaling failed", file=sys.stderr)
        return result.returncode

    size_mb = dst.stat().st_size / 1_048_576
    print(f"Output: '{dst}'  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

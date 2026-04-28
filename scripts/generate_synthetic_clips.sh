#!/usr/bin/env bash
# =============================================================================
# Author:  Yash Daniel Ingle
# Email:   yashingle1207@gmail.com
# GitHub:  github.com/yashingle1207
# Project: Video Codec Validation Lab
# Script:  generate_synthetic_clips.sh
# Purpose: Generate deterministic raw YUV420p clips with FFmpeg lavfi sources.
# =============================================================================

set -euo pipefail

OUTDIR="data/raw_yuv"
mkdir -p "$OUTDIR"

check_ffmpeg() {
    if ! command -v ffmpeg &>/dev/null; then
        echo "ERROR: ffmpeg not found in PATH. Install FFmpeg with lavfi support." >&2
        exit 1
    fi
}

gen_clip() {
    local source="$1"
    local size="$2"
    local fps="$3"
    local frames="$4"
    local outfile="$5"

    if [[ -f "$outfile" && -s "$outfile" ]]; then
        echo "  [SKIP] $outfile already exists"
        return
    fi

    echo "  [GEN]  $outfile  (${size} ${fps}fps ${frames}f)"
    ffmpeg -y \
        -f lavfi \
        -i "${source}=size=${size}:rate=${fps}" \
        -frames:v "$frames" \
        -pix_fmt yuv420p \
        -f rawvideo \
        "$outfile"
}

check_ffmpeg

echo "==> Generating test YUV clips into $OUTDIR"

# testsrc2: synthetic colorful test pattern, good for codec stress testing.
gen_clip "testsrc2" "352x288" 30 150 "$OUTDIR/test_352x288_30fps_150f.yuv"
gen_clip "testsrc2" "1280x720" 30 150 "$OUTDIR/test_1280x720_30fps_150f.yuv"

# mandelbrot: complex fractal; exercises motion estimation and rate control.
gen_clip "mandelbrot" "1920x1080" 30 100 "$OUTDIR/test_1920x1080_30fps_100f.yuv"

# Solid black: used for black-frame and frozen-frame detection tests.
gen_clip "color=c=black" "352x288" 30 60 "$OUTDIR/black_352x288_30fps_60f.yuv"

# Solid white: useful for clipped-frame detection.
gen_clip "color=c=white" "352x288" 30 60 "$OUTDIR/white_352x288_30fps_60f.yuv"

echo "==> Done. Files in $OUTDIR:"
ls -lh "$OUTDIR"/*.yuv 2>/dev/null || echo "  (no .yuv files found)"

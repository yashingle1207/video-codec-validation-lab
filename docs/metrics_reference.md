# Author: Yash Daniel Ingle
# Email: yashingle1207@gmail.com
# GitHub: github.com/yashingle1207
# Project: Video Codec Validation Lab
# File: metrics_reference.md
# Purpose: Define the objective metrics used by the validation pipeline.

# Metrics Reference

This file explains the metrics used by the project. It does not contain measured
experiment results.

## PSNR

PSNR measures pixel-level error between a reference sequence and a distorted
sequence.

Formula:

```text
PSNR = 20 * log10(MAX / RMSE)
```

For 8-bit video, `MAX = 255`.

Project use:

- Used as a fast full-reference quality metric.
- Reported primarily for the luma plane as `PSNR-Y`.
- Used in validation thresholds when configured.

## SSIM

SSIM measures structural similarity between a reference and distorted sequence.
It is bounded between `0.0` and `1.0`, where `1.0` indicates identical structure.

Project use:

- Used as a perceptual proxy alongside PSNR.
- Parsed from FFmpeg SSIM output.
- Included in JSON/CSV reports when available.

## VMAF

VMAF is a perceptual quality metric commonly used for video streaming analysis.
It requires FFmpeg to be built with `libvmaf`.

Project use:

- Treated as optional because not every FFmpeg build includes libvmaf.
- If unavailable, the quality evaluator returns NaN placeholders instead of
  crashing the validation flow.
- Included in reports and thresholds when available.

## Bits Per Pixel

BPP normalizes encoded size by resolution and frame count.

Formula:

```text
BPP = (file_size_bytes * 8) / (width * height * frame_count)
```

Project use:

- Used for rate-distortion comparisons.
- Helps compare codec efficiency independent of clip duration and resolution.

## BD-Rate

BD-rate estimates average bitrate difference between two rate-distortion curves
over their overlapping quality range.

Project use:

- Implemented in `rd_curve_analyzer.py`.
- Intended for comparing codec efficiency after enough RD points are generated.
- Not reported unless the user runs experiments with sufficient points per curve.

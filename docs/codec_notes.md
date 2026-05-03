# Author: Yash Daniel Ingle
# Email: yashingle1207@gmail.com
# GitHub: github.com/yashingle1207
# Project: Video Codec Validation Lab
# File: codec_notes.md
# Purpose: Summarize codec properties that influence validation coverage.

# Codec Notes

These notes describe why each codec is useful in the validation lab. They are
technical background, not measured project results.

## H.264 / AVC

H.264/AVC is used as the compatibility baseline. It is widely supported, fast to
encode with software tools, and useful for validating the basic encode, decode,
quality, and bitstream-analysis flow.

Validation relevance:

- Common reference point for codec comparisons.
- Useful for checking GOP behavior, frame count, bitrate, PSNR, and SSIM.
- Fast enough for repeated local regression tests.

## HEVC / H.265

HEVC/H.265 is included because it improves compression efficiency over H.264 while
adding more encoder complexity. That makes it useful for validating rate-control
behavior, GOP structure, and quality tradeoffs at lower bitrates.

Validation relevance:

- More complex compression structure than H.264.
- Useful for comparing BPP and quality at similar visual targets.
- Important codec family for modern video pipelines.

## AV1

AV1 is included as a modern open video codec with stronger compression tools and
higher software-encoding cost. In this project it is useful for validating that the
pipeline can handle slower codecs, wider CRF ranges, and optional VMAF-based
quality checks.

Validation relevance:

- Modern codec coverage beyond H.264/HEVC.
- Useful for RD-curve and quality-efficiency comparisons.
- Good stress case for encode-time and quality-metric reporting.

## VP9

VP9 is supported by the encoder wrapper for additional web-video codec coverage.
It is not the primary focus of the default config set, but the wrapper includes it
so the validation flow can be extended without changing the core encoder API.

Validation relevance:

- Additional open codec family.
- Useful for testing two-pass CBR behavior.
- Helpful for broadening codec-wrapper coverage.

## Summary

| Codec | Role in this project | Primary validation use |
|---|---|---|
| H.264/AVC | Baseline codec | Fast regression and compatibility checks |
| HEVC/H.265 | Higher-efficiency codec | Compression-efficiency and complexity comparison |
| AV1 | Modern open codec | RD behavior, quality metrics, encode-time stress |
| VP9 | Optional wrapper support | Additional web-codec and two-pass coverage |

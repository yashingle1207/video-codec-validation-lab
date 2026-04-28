# Video Codec Validation Lab


## Overview

A C++/Python validation lab for testing video codec behavior across **H.264/AVC, HEVC/H.265, and AV1**.

I built this project to practice a practical codec validation workflow: generate test inputs, encode them with different codec settings, verify decoded output, inspect bitstream metadata, measure quality, apply pass/fail thresholds, and generate repeatable reports.

The goal is to show a clean validation system for video compression and silicon-validation-style software work, with reproducible configs, measurable outputs, and clear failure reasons.

## What I Built

- Codec validation pipeline for **H.264/AVC, HEVC/H.265, VP9, and AV1**.
- Python automation for encoding, decode verification, bitstream analysis, quality metrics, and reporting.
- C++ YUV420p validator for frame count, frame statistics, SHA-256 fingerprints, black/frozen frame checks, clipping checks, and truncation detection.
- ffprobe-based metadata analysis for codec, profile, pixel format, resolution, bitrate, duration, frame count, keyframes, and GOP behavior.
- PSNR, SSIM, and optional VMAF quality evaluation.
- YAML-based validation thresholds for pass/fail checks.
- JSON/CSV report generation for regression-style validation.
- Lightweight pytest suite with mocked FFmpeg/ffprobe calls for fast local testing.

## Why This Project

Video codec validation is more than checking whether an encoded file plays. A useful validation flow should answer:

- Did the encoder produce a valid and decodable bitstream?
- Does the decoded output preserve the expected frame count?
- Are codec metadata, bitrate, BPP, and GOP structure sane?
- How do PSNR, SSIM, and VMAF change across codec settings?
- Did a regression break quality, timing, decode behavior, or output consistency?

This project is built around those checks.

## Architecture

```text
RAW YUV
  -> Encoder
  -> Bitstream
  -> Decoder / Verifier
  -> Bitstream Analyzer
  -> Quality Evaluator
  -> Validation Rules
  -> RD Analyzer
  -> Report

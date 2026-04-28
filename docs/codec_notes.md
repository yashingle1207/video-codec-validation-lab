# Author: Yash Daniel Ingle
# Email: yashingle1207@gmail.com
# GitHub: github.com/yashingle1207
# Project: Video Codec Validation Lab
# File: codec_notes.md
# Purpose: Summarize codec tradeoffs relevant to encoder validation.

# Codec Design Notes: H.264, HEVC, and AV1

## H.264 / AVC (libx264)

H.264 (ISO/IEC 14496-10) is the most widely deployed video codec in the world.
Its compression toolbox includes CABAC/CAVLC entropy coding, quarter-pixel motion
compensation, 4x4 and 8x8 integer DCT transforms, and in-loop deblocking.
The reference encoder `libx264` is highly optimised: a single-pass CRF encode at
`medium` preset runs near real-time even on embedded hardware.  H.264 remains the
baseline for compatibility testing because it is supported by every hardware decoder
produced since ~2010.

**Strengths:** negligible decode complexity, universal hardware support, mature tooling.
**Weaknesses:** ~40-50 % higher bitrate than HEVC at equivalent perceptual quality;
no 10-bit support in the baseline profile used by most devices.

---

## HEVC / H.265 (libx265)

HEVC (ISO/IEC 23008-2) roughly halves the bitrate of H.264 at the same perceptual
quality by doubling the maximum coding unit (CU) size to 64x64 and introducing
flexible partitioning, improved intra-prediction with 35 angular modes, and
asymmetric motion partitioning.  The complexity increase is significant: hardware
encoders require approximately 10x the gates of H.264.

`libx265` defaults to a rate-distortion optimised B-frame hierarchy and CABAC
entropy coding.  The CRF scale shifts relative to H.264: CRF 28 in HEVC is
perceptually comparable to CRF 23 in H.264.

**Strengths:** ~40-50 % bitrate savings over H.264; native 10-bit and HDR support.
**Weaknesses:** encode is 5-20x slower than H.264 at the same preset; patent pool
complexity has historically slowed adoption; software decode is heavier.

---

## AV1 (libaom-av1)

AV1 (Alliance for Open Media, 2018) is a royalty-free codec designed to succeed VP9
and compete with HEVC.  It introduces superblocks up to 128x128, a large set of
intra prediction modes (directional, recursive filter, palette, CfL), compound
inter-prediction, film grain synthesis, and CDEF/loop restoration filters.

`libaom-av1` at `cpu-used 0`-`2` is exhaustive and extremely slow (hours per minute
of 1080p); in practice `cpu-used 6`-`8` trades ~1-2 dB PSNR for real-time-class
speed.  AV1 achieves roughly 30 % bitrate reduction over HEVC at equivalent quality
in many content classes.

**Strengths:** royalty-free; best-in-class coding efficiency; native 12-bit support.
**Weaknesses:** encode speed is the primary bottleneck in production workflows; hardware
decode support is still ramping (Apple A17/M3+, ARM Mali-G715+).

---

## VP9 (libvpx-vp9)

VP9 (Google, 2013) preceded AV1 and is widely deployed in web streaming (YouTube).
It shares many concepts with AV1 but uses simpler partition structures and fewer
prediction modes, making it significantly faster to encode.  At comparable quality
VP9 is roughly on par with HEVC.

`libvpx-vp9` in CRF mode requires `-b:v 0` to fully enable constant-quality mode.
Two-pass encoding is strongly recommended for CBR targets.

---

## Summary Table

| Codec    | Typical CRF | Relative Bitrate | Encode Speed | HW Decode |
|----------|-------------|-----------------|--------------|-----------|
| H.264    | 23          | 1.0x (baseline) | Very fast    | Universal |
| HEVC     | 28          | ~0.55x          | Slow         | Widespread|
| VP9      | 33          | ~0.55x          | Moderate     | Common    |
| AV1      | 35          | ~0.40x          | Very slow    | Ramping   |

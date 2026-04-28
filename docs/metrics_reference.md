# Author: Yash Daniel Ingle
# Email: yashingle1207@gmail.com
# GitHub: github.com/yashingle1207
# Project: Video Codec Validation Lab
# File: metrics_reference.md
# Purpose: Define objective quality and rate-distortion metrics used by the lab.

# Metrics Reference

## PSNR (Peak Signal-to-Noise Ratio)

**Formula:** `PSNR = 20 * log10(MAX / RMSE)` where MAX = 255 for 8-bit content.

PSNR measures pixel-level fidelity between reference and distorted sequences.
It is computed per plane (Y, U, V) and averaged over frames.

**Interpretation:**
- > 40 dB: transparent quality (indistinguishable from reference on most displays)
- 36-40 dB: high quality, minor artefacts visible under close inspection
- 30-36 dB: acceptable quality, visible compression noise on texture areas
- < 30 dB: noticeable degradation, blocking, and ringing artefacts

**Limitations:** PSNR correlates poorly with subjective quality on complex content
(high motion, film grain, synthetic graphics).  Use VMAF for perceptual evaluation.

---

## SSIM (Structural Similarity Index)

**Range:** 0.0 (worst) - 1.0 (identical).

SSIM measures luminance, contrast, and structural similarity using local statistics
in an 11x11 Gaussian window.  It is a better proxy for human perception than PSNR
but still struggles with blocking artefacts on complex textures.

**Typical values:**
- > 0.98: excellent
- 0.95-0.98: good
- 0.90-0.95: fair
- < 0.90: poor

---

## VMAF (Video Multi-Method Assessment Fusion)

VMAF is a machine-learning perceptual quality metric developed by Netflix.
It combines three elementary features (VIF, DLM, motion) using a support vector
machine trained on subjective quality scores.

**Range:** 0 - 100 (higher is better).

**Typical streaming targets:**
- 95+: premium (transparent)
- 85-95: high quality (HD streaming)
- 70-85: acceptable (mobile, constrained bitrate)
- < 70: noticeable degradation

VMAF requires FFmpeg compiled with `--enable-libvmaf` (version >= 2.x JSON schema).

---

## Bits Per Pixel (BPP)

`BPP = (file_size_bytes x 8) / (width x height x frame_count)`

BPP normalises encoded file size for resolution and duration, enabling fair
comparison between sequences of different lengths and resolutions.  Used as the
X-axis of RD plots in this project.

---

## BD-Rate (Bjontegaard Delta Rate)

BD-rate measures the average bitrate difference between two RD curves over their
overlapping quality range, expressed as a percentage.

**Interpretation:**
- BD-rate of -30 % means codec B achieves the same quality as codec A at 30 % fewer bits.
- BD-rate of +10 % means codec B is 10 % less efficient than codec A.

**Implementation:** log-domain polynomial fitting (degree 3 by default) with
numerical integration, as described in ITU-T SG16 VCEG-M33.

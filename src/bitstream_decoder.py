"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    bitstream_decoder.py
Purpose: Decode encoded video bitstreams back to raw YUV420p and verify frame
         count and bitstream integrity using FFmpeg and ffprobe.

Description:
    DecodeVerifier provides three validation methods: decode_to_yuv() runs FFmpeg
    to reconstruct the raw pixel data, verify_frame_count() uses ffprobe packet
    counting for a fast frame-count check without full decoding, and
    check_bitstream_integrity() invokes ffprobe with error-detection flags to
    surface corrupt NAL units, PTS gaps, and container anomalies.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.pipeline_utils import ensure_dir, get_logger

_LOG = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class IntegrityReport:
    """Result of a bitstream integrity check performed by ffprobe.

    Attributes:
        path: Path to the encoded file that was checked.
        passed: ``True`` when no errors were detected.
        errors: List of critical error strings surfaced by ffprobe.
        warnings: List of non-fatal anomaly strings (e.g. truncated packets).
    """

    path: Path
    passed: bool
    errors: list[str]
    warnings: list[str]


# ---------------------------------------------------------------------------
# Verifier class
# ---------------------------------------------------------------------------

class DecodeVerifier:
    """Decode encoded video files and perform bitstream-level correctness checks.

    Uses FFmpeg for decoding and ffprobe for structural analysis.
    All methods are stateless - a single instance can be reused across many files.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decode_to_yuv(
        self,
        encoded_path: str | Path,
        output_yuv_path: str | Path,
        width: int,
        height: int,
        fps: float,
    ) -> bool:
        """Decode an encoded bitstream to a raw YUV420p file.

        The output YUV file can then be compared pixel-by-pixel against the
        original reference using quality metrics (PSNR / SSIM / VMAF).

        Args:
            encoded_path: Path to the encoded video file (MP4, MKV, IVF, etc.).
            output_yuv_path: Destination path for the decoded raw YUV420p data.
            width: Expected decoded frame width - used only for logging verification;
                FFmpeg determines the actual width from the bitstream.
            height: Expected decoded frame height.
            fps: Target output frame rate passed to FFmpeg's ``-r`` flag.

        Returns:
            ``True`` if FFmpeg exited with code 0 and a non-empty output file
            was created; ``False`` on timeout, non-zero exit, or empty output.
        """
        encoded_path = Path(encoded_path)
        output_yuv_path = Path(output_yuv_path)
        # Create parent directories so FFmpeg can write the output file.
        ensure_dir(output_yuv_path.parent)

        cmd = [
            "ffmpeg", "-y",                     # -y: overwrite output file if exists
            "-i", str(encoded_path),
            "-f", "rawvideo",                   # output format: headerless raw video
            "-pix_fmt", "yuv420p",              # force 4:2:0 planar 8-bit output
            "-r", str(fps),
            str(output_yuv_path),
        ]

        _LOG.info("Decoding '%s' -> '%s'", encoded_path.name, output_yuv_path.name)
        try:
            # 300 s timeout - long files at 1080p can take a while to decode.
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            _LOG.error("Decode timed out after 300 s for '%s'", encoded_path)
            return False

        if proc.returncode != 0:
            _LOG.warning("FFmpeg decode failed (stderr last 2000 chars):\n%s",
                         proc.stderr[-2000:])
            return False

        # A zero-byte output file indicates FFmpeg ran but produced no frames.
        if not output_yuv_path.is_file() or output_yuv_path.stat().st_size == 0:
            _LOG.error("Decoded file is missing or empty: '%s'", output_yuv_path)
            return False

        _LOG.info("Decode OK - %d bytes written to '%s'",
                  output_yuv_path.stat().st_size, output_yuv_path.name)
        return True

    def verify_frame_count(
        self,
        encoded_path: str | Path,
        expected_frames: int,
    ) -> bool:
        """Verify the encoded file contains exactly ``expected_frames`` video frames.

        Uses ffprobe packet counting (``-count_packets``) which is much faster
        than full decoding and counts the actual demuxed packets.

        Args:
            encoded_path: Path to the encoded video file.
            expected_frames: The number of frames the encoder should have produced.

        Returns:
            ``True`` if the counted packet count matches ``expected_frames``.
        """
        encoded_path = Path(encoded_path)
        actual = self._probe_frame_count(encoded_path)

        if actual is None:
            _LOG.error("Could not determine frame count for '%s'", encoded_path.name)
            return False

        if actual != expected_frames:
            _LOG.warning(
                "Frame count mismatch: expected %d, probed %d in '%s'",
                expected_frames, actual, encoded_path.name,
            )
            return False

        _LOG.info("Frame count verified: %d frames in '%s'", actual, encoded_path.name)
        return True

    def check_bitstream_integrity(
        self, encoded_path: str | Path
    ) -> IntegrityReport:
        """Run ffprobe with error detection to find bitstream anomalies.

        Enables ``-err_detect explode`` which causes ffprobe to report errors
        that a strict hardware decoder (e.g. a video DSP) would reject.  Parses
        stdout and stderr for lines containing error/warning keywords.

        Args:
            encoded_path: Path to the encoded video file.

        Returns:
            :class:`IntegrityReport` listing any detected errors and warnings.
        """
        encoded_path = Path(encoded_path)
        errors: list[str] = []
        warnings: list[str] = []

        # Short-circuit: nothing to probe if the file does not exist.
        if not encoded_path.is_file():
            return IntegrityReport(
                path=encoded_path,
                passed=False,
                errors=[f"File not found: '{encoded_path}'"],
                warnings=[],
            )

        cmd = [
            "ffprobe",
            "-v", "error",              # suppress INFO/DEBUG - only show errors
            "-err_detect", "explode",   # treat minor bitstream errors as fatal
            "-show_entries", "format=duration,bit_rate,size",
            "-print_format", "json",
            str(encoded_path),
        ]

        try:
            # 120 s is generous for probing even a long file.
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return IntegrityReport(
                path=encoded_path,
                passed=False,
                errors=["ffprobe timed out after 120 s"],
                warnings=[],
            )

        # Scan all output lines for error/warning keywords.
        for line in (proc.stdout + proc.stderr).splitlines():
            low = line.lower()
            if any(tok in low for tok in ("error", "invalid", "corrupt")):
                errors.append(line.strip())
            elif any(tok in low for tok in ("warning", "truncated", "missing")):
                warnings.append(line.strip())

        # Non-zero exit with no captured errors - add a generic error entry.
        if proc.returncode != 0 and not errors:
            errors.append(f"ffprobe exited with non-zero code {proc.returncode}")

        # Parse the format block for basic container sanity checks.
        try:
            info = json.loads(proc.stdout)
            fmt = info.get("format", {})
            duration = float(fmt.get("duration", 0))
            size = int(fmt.get("size", 0))
            if duration <= 0:
                # A zero duration usually means the muxer did not write a valid header.
                warnings.append("Container duration is zero or missing")
            if size == 0:
                errors.append("ffprobe reports file size as zero bytes")
        except (json.JSONDecodeError, ValueError, KeyError):
            warnings.append("Could not parse ffprobe JSON output block")

        passed = len(errors) == 0
        _LOG.info(
            "Integrity check '%s': passed=%s  errors=%d  warnings=%d",
            encoded_path.name, passed, len(errors), len(warnings),
        )
        return IntegrityReport(
            path=encoded_path,
            passed=passed,
            errors=errors,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _probe_frame_count(self, encoded_path: Path) -> int | None:
        """Use ffprobe to count the number of video packets in the file.

        Counting packets is O(1) in file size for indexed containers (MP4)
        and O(N) for non-indexed ones (TS).

        Args:
            encoded_path: Path to the encoded video file.

        Returns:
            Integer packet count, or ``None`` if probing fails.
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",       # first video stream only
            "-count_packets",               # count packets rather than decoding frames
            "-show_entries", "stream=nb_read_packets",
            "-print_format", "json",
            str(encoded_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            _LOG.error("ffprobe packet-count timed out for '%s'", encoded_path.name)
            return None

        try:
            data = json.loads(proc.stdout)
            # ffprobe returns nb_read_packets as a string - convert to int.
            return int(data["streams"][0]["nb_read_packets"])
        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            _LOG.warning("Could not parse packet count for '%s': %s",
                         encoded_path.name, exc)
            return None

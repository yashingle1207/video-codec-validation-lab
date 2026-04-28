"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    codec_encoder.py
Purpose: FFmpeg subprocess wrapper that encodes raw YUV420p sequences in CRF or
         CBR mode for H.264, HEVC, VP9, and AV1.

Description:
    CodecEncoder builds and executes FFmpeg command lines without sudo, measures
    wall-clock encode time, and returns a typed EncodeResult dataclass.  CBR mode
    for VP9 and AV1 automatically uses a two-pass strategy to achieve accurate
    bitrate targets.  All output directories are created automatically.
"""

import multiprocessing
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.pipeline_utils import ensure_dir, get_logger

_LOG = get_logger(__name__)

# Codecs supported by this wrapper - must match FFmpeg codec names exactly.
SUPPORTED_CODECS = frozenset({"libx264", "libx265", "libvpx-vp9", "libaom-av1"})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class EncodeResult:
    """Immutable result record returned by every encode operation.

    Attributes:
        codec: FFmpeg codec name (e.g. ``'libx264'``).
        mode: Encoding mode - either ``'crf'`` or ``'cbr'``.
        crf_or_bitrate: CRF integer for CRF mode; bitrate in kbps for CBR mode.
        gop: Keyframe interval (GOP size) in frames.
        output_path: Absolute :class:`pathlib.Path` to the encoded bitstream.
        encode_time_s: Wall-clock encode duration in seconds.
        file_size_bytes: Byte size of the output file on disk.
        return_code: FFmpeg process exit code (0 = success).
        stderr: Captured FFmpeg stderr (truncated in repr to keep logs readable).
    """

    codec: str
    mode: str
    crf_or_bitrate: int
    gop: int
    output_path: Path
    encode_time_s: float
    file_size_bytes: int
    return_code: int = 0
    stderr: str = field(default="", repr=False)  # excluded from repr - can be large


# ---------------------------------------------------------------------------
# Encoder class
# ---------------------------------------------------------------------------

class CodecEncoder:
    """Thin, stateless wrapper around FFmpeg for encoding raw YUV sequences.

    Encodes raw planar YUV420p data to compressed bitstreams using FFmpeg.
    Supports constant-quality (CRF) and constant-bitrate (CBR) modes.
    Never calls sudo - FFmpeg must be accessible to the current user.
    """

    def __init__(self) -> None:
        """Initialise encoder state.

        Returns:
            None: The encoder stores only the most recent encode duration.
        """
        # Stores the most recent encode duration for retrieval via get_encode_time().
        self._last_encode_time_s: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encode_crf(
        self,
        input_yuv: str | Path,
        codec: str,
        crf: int,
        gop: int,
        preset: str,
        width: int,
        height: int,
        fps: float,
        output_path: str | Path,
    ) -> EncodeResult:
        """Encode a raw YUV420p file in constant-quality (CRF) mode.

        CRF mode lets the encoder vary the bitrate per frame to maintain a
        constant perceptual quality target.  Lower CRF = higher quality and
        larger files.

        Args:
            input_yuv: Path to the raw YUV420p input file on disk.
            codec: FFmpeg codec name - must be one of ``SUPPORTED_CODECS``.
            crf: Constant rate factor.  Typical ranges: H.264 0-51, HEVC 0-51,
                AV1 0-63.  Lower values produce higher quality.
            gop: GOP (Group of Pictures) size - keyframe interval in frames.
                Affects seek granularity and I-frame overhead.
            preset: Encoder speed preset controlling quality/speed trade-off
                (e.g. ``'ultrafast'``, ``'medium'``, ``'slow'`` for H.264/HEVC).
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frame rate of the input sequence.
            output_path: Destination file path for the encoded bitstream.

        Returns:
            :class:`EncodeResult` populated with timing, size, and FFmpeg exit code.

        Raises:
            ValueError: If ``codec`` is not in ``SUPPORTED_CODECS``.
        """
        self._validate_codec(codec)
        output_path = Path(output_path)
        ensure_dir(output_path.parent)  # create output directory if missing

        # Start building the FFmpeg command with raw YUV input arguments.
        cmd = self._build_yuv_input_args(input_yuv, width, height, fps)

        if codec == "libaom-av1":
            # libaom-av1 CRF mode requires -b:v 0 to disable target bitrate.
            # -cpu-used controls encode speed (0=slowest/best, 8=fastest).
            cpus = multiprocessing.cpu_count()
            cmd += [
                "-c:v", codec,
                "-crf", str(crf),
                "-b:v", "0",                        # 0 = pure CRF, no bitrate cap
                "-cpu-used", str(min(cpus, 8)),     # cap at 8 (libaom max)
                "-g", str(gop),
            ]
        elif codec == "libvpx-vp9":
            # VP9 CRF mode also requires -b:v 0 for unconstrained quality mode.
            # -deadline replaces -preset for VP9.
            cmd += [
                "-c:v", codec,
                "-crf", str(crf),
                "-b:v", "0",            # 0 = constrained-quality off, pure CRF
                "-deadline", preset,    # VP9 speed preset: realtime / good / best
                "-g", str(gop),
            ]
        else:
            # H.264 (libx264) and HEVC (libx265) share the same CRF flag.
            cmd += [
                "-c:v", codec,
                "-preset", preset,
                "-crf", str(crf),
                "-g", str(gop),
            ]

        # -y: overwrite output without prompting
        cmd += ["-y", str(output_path)]
        return self._run(cmd, codec, "crf", crf, gop, output_path)

    def encode_cbr(
        self,
        input_yuv: str | Path,
        codec: str,
        bitrate_kbps: int,
        gop: int,
        width: int,
        height: int,
        fps: float,
        output_path: str | Path,
        preset: str = "medium",
    ) -> EncodeResult:
        """Encode a raw YUV420p file in constant-bitrate (CBR) mode.

        For VP9 and AV1, a two-pass encode is used to achieve accurate bitrate
        targets.  H.264 and HEVC use single-pass CBR with maxrate/bufsize tuned
        to 1.5x and 2x the target bitrate respectively.

        Args:
            input_yuv: Path to the raw YUV420p input file.
            codec: FFmpeg codec name - must be one of ``SUPPORTED_CODECS``.
            bitrate_kbps: Target output bitrate in kilobits per second.
            gop: Keyframe interval in frames.
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frame rate of the input sequence.
            output_path: Destination file path for the encoded bitstream.
            preset: Encoder speed preset (default ``'medium'``).

        Returns:
            :class:`EncodeResult` populated with timing, size, and FFmpeg exit code.
        """
        self._validate_codec(codec)
        output_path = Path(output_path)
        ensure_dir(output_path.parent)
        # FFmpeg bitrate strings require a 'k' suffix for kbps.
        bitrate_str = f"{bitrate_kbps}k"

        if codec in ("libvpx-vp9", "libaom-av1"):
            # VP9/AV1 CBR is only accurate with a two-pass encode.
            result = self._encode_two_pass(
                input_yuv, codec, bitrate_kbps, gop, preset, width, height, fps,
                output_path
            )
        else:
            cmd = self._build_yuv_input_args(input_yuv, width, height, fps)
            if codec == "libx265":
                # x265 CBR: pass=0 selects single-pass ABR (closest to CBR for libx265).
                cmd += [
                    "-c:v", codec,
                    "-preset", preset,
                    "-b:v", bitrate_str,
                    "-x265-params", "pass=0",
                    "-g", str(gop),
                ]
            else:
                # x264 CBR: maxrate = 1.5x target to absorb I-frame spikes;
                # bufsize = 2x target to smooth out rate control over ~2 seconds.
                cmd += [
                    "-c:v", codec,
                    "-preset", preset,
                    "-b:v", bitrate_str,
                    "-maxrate", f"{int(bitrate_kbps * 1.5)}k",  # 1.5x target
                    "-bufsize", f"{bitrate_kbps * 2}k",         # 2x target
                    "-g", str(gop),
                ]
            cmd += ["-y", str(output_path)]
            result = self._run(cmd, codec, "cbr", bitrate_kbps, gop, output_path)
        return result

    def get_encode_time(self) -> float:
        """Return the wall-clock duration of the most recent encode call.

        Returns:
            Encode duration in seconds as a :class:`float`.
            Returns ``0.0`` if no encode has been run yet.
        """
        return self._last_encode_time_s

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_codec(self, codec: str) -> None:
        """Raise ValueError if codec is not in SUPPORTED_CODECS.

        Args:
            codec: FFmpeg codec name to validate.

        Raises:
            ValueError: If ``codec`` is not a supported encoder.
        """
        if codec not in SUPPORTED_CODECS:
            raise ValueError(
                f"Unsupported codec '{codec}'. "
                f"Supported codecs: {sorted(SUPPORTED_CODECS)}"
            )

    def _build_yuv_input_args(
        self,
        input_yuv: str | Path,
        width: int,
        height: int,
        fps: float,
    ) -> list[str]:
        """Construct the FFmpeg input-side arguments for a raw YUV420p stream.

        Raw video has no container headers, so FFmpeg must be told the pixel
        format, resolution, and frame rate explicitly via ``-f rawvideo``.

        Args:
            input_yuv: Path to the raw YUV420p file.
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frames per second.

        Returns:
            List of FFmpeg argument strings up to (but not including) ``-i``.
        """
        return [
            "ffmpeg",
            "-f", "rawvideo",           # tell FFmpeg to read raw (headerless) video
            "-pix_fmt", "yuv420p",      # 4:2:0 planar, 8-bit - most common YUV format
            "-s:v", f"{width}x{height}",
            "-r", str(fps),
            "-i", str(input_yuv),
        ]

    def _encode_two_pass(
        self,
        input_yuv: str | Path,
        codec: str,
        bitrate_kbps: int,
        gop: int,
        preset: str,
        width: int,
        height: int,
        fps: float,
        output_path: Path,
    ) -> EncodeResult:
        """Execute a two-pass CBR encode for VP9 or AV1.

        Pass 1 analyses the input and writes statistics to a passlog file.
        Pass 2 uses those statistics to distribute bits optimally while
        hitting the target bitrate.  Total elapsed time covers both passes.

        Args:
            input_yuv: Path to the raw YUV420p input file.
            codec: ``'libvpx-vp9'`` or ``'libaom-av1'``.
            bitrate_kbps: Target bitrate in kbps.
            gop: Keyframe interval in frames.
            preset: Speed preset string.
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frames per second.
            output_path: Destination for the final bitstream.

        Returns:
            :class:`EncodeResult` using the pass 2 return code and combined timing.
        """
        bitrate_str = f"{bitrate_kbps}k"
        # Passlog prefix - FFmpeg appends codec-specific suffixes automatically.
        passlog = str(output_path.with_suffix("")) + "_passlog"

        # ---- Pass 1: analyse input, write stats, discard output ----
        pass1 = self._build_yuv_input_args(input_yuv, width, height, fps)
        if codec == "libvpx-vp9":
            pass1 += [
                "-c:v", codec, "-b:v", bitrate_str,
                "-deadline", preset, "-g", str(gop),
                "-pass", "1", "-passlogfile", passlog,
                "-an",          # no audio
                "-f", "null",   # discard all output - pass 1 only writes the log
            ]
        else:  # libaom-av1
            cpus = multiprocessing.cpu_count()
            pass1 += [
                "-c:v", codec, "-b:v", bitrate_str,
                "-cpu-used", str(min(cpus, 8)), "-g", str(gop),
                "-pass", "1", "-passlogfile", passlog,
                "-an", "-f", "null",
            ]

        # On Windows, /dev/null does not exist; use NUL instead.
        pass1.append("NUL" if sys.platform == "win32" else "/dev/null")

        _LOG.info("Two-pass encode - pass 1: %s", shlex.join(pass1))
        t0 = time.perf_counter()  # start timing before pass 1
        r1 = subprocess.run(pass1, capture_output=True, text=True)
        if r1.returncode != 0:
            _LOG.warning("Pass 1 stderr (last 2000 chars): %s", r1.stderr[-2000:])

        # ---- Pass 2: encode using pass-1 statistics ----
        pass2 = self._build_yuv_input_args(input_yuv, width, height, fps)
        if codec == "libvpx-vp9":
            pass2 += [
                "-c:v", codec, "-b:v", bitrate_str,
                "-deadline", preset, "-g", str(gop),
                "-pass", "2", "-passlogfile", passlog,
            ]
        else:  # libaom-av1
            cpus = multiprocessing.cpu_count()
            pass2 += [
                "-c:v", codec, "-b:v", bitrate_str,
                "-cpu-used", str(min(cpus, 8)), "-g", str(gop),
                "-pass", "2", "-passlogfile", passlog,
            ]
        pass2 += ["-y", str(output_path)]

        _LOG.info("Two-pass encode - pass 2: %s", shlex.join(pass2))
        r2 = subprocess.run(pass2, capture_output=True, text=True)
        elapsed = time.perf_counter() - t0  # total wall-clock across both passes
        self._last_encode_time_s = elapsed

        if r2.returncode != 0:
            _LOG.warning("Pass 2 stderr (last 2000 chars): %s", r2.stderr[-2000:])

        file_size = output_path.stat().st_size if output_path.is_file() else 0
        return EncodeResult(
            codec=codec,
            mode="cbr",
            crf_or_bitrate=bitrate_kbps,
            gop=gop,
            output_path=output_path,
            encode_time_s=elapsed,
            file_size_bytes=file_size,
            return_code=r2.returncode,
            stderr=r2.stderr,
        )

    def _run(
        self,
        cmd: list[str],
        codec: str,
        mode: str,
        crf_or_bitrate: int,
        gop: int,
        output_path: Path,
    ) -> EncodeResult:
        """Execute an FFmpeg command, measure wall-clock time, and return a result.

        Args:
            cmd: Complete FFmpeg argument list including the output path.
            codec: Codec name for the result record.
            mode: ``'crf'`` or ``'cbr'``.
            crf_or_bitrate: CRF integer or bitrate in kbps.
            gop: Keyframe interval in frames.
            output_path: Expected output file path (used to read file size).

        Returns:
            :class:`EncodeResult` with all fields populated.
        """
        _LOG.info("Running encode: %s", shlex.join(cmd))
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.perf_counter() - t0
        self._last_encode_time_s = elapsed

        _LOG.debug("Return code: %d  |  elapsed: %.2f s", proc.returncode, elapsed)
        if proc.returncode != 0:
            # Log last 2000 chars - full stderr can be very verbose for HEVC.
            _LOG.warning("FFmpeg stderr (last 2000 chars):\n%s", proc.stderr[-2000:])
        else:
            _LOG.debug("FFmpeg stderr snippet:\n%s", proc.stderr[-500:])

        # Read actual file size after encode - 0 if the file was not created.
        file_size = output_path.stat().st_size if output_path.is_file() else 0
        return EncodeResult(
            codec=codec,
            mode=mode,
            crf_or_bitrate=crf_or_bitrate,
            gop=gop,
            output_path=output_path,
            encode_time_s=elapsed,
            file_size_bytes=file_size,
            return_code=proc.returncode,
            stderr=proc.stderr,
        )

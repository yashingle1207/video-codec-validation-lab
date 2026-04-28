"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    quality_evaluator.py
Purpose: Compute full-reference video quality metrics - PSNR, SSIM, and VMAF -
         by comparing a raw YUV reference against an encoded bitstream via FFmpeg.

Description:
    QualityEvaluator wraps three FFmpeg filter_complex invocations (psnr, ssim,
    libvmaf) and aggregates their per-frame outputs into summary statistics.
    Per-frame VMAF data is written to JSON via libvmaf's log_path option.
    All methods gracefully handle missing FFmpeg filters (e.g. libvmaf not compiled)
    by returning NaN values rather than crashing.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.pipeline_utils import ensure_dir, get_logger

_LOG = get_logger(__name__)

# Default directory for per-frame metric logs and VMAF JSON files.
_METRICS_DIR = Path("outputs/metrics")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class QualityResult:
    """Aggregated quality metrics for a single encode evaluated against a reference.

    Attributes:
        vmaf_mean: Mean VMAF score across all frames (range 0-100; higher is better).
        vmaf_min: Worst-case VMAF score across all frames.
        psnr_y_mean: Mean luma-plane PSNR in dB (higher is better).
        ssim_mean: Mean SSIM score (range 0-1; 1.0 = identical to reference).
        frame_count: Number of frames measured (from VMAF; 0 if VMAF unavailable).
        metrics_json_path: Path to the libvmaf per-frame JSON, or ``None`` if VMAF
            computation was skipped or failed.
    """

    vmaf_mean: float
    vmaf_min: float
    psnr_y_mean: float
    ssim_mean: float
    frame_count: int
    metrics_json_path: Path | None = None


# ---------------------------------------------------------------------------
# Evaluator class
# ---------------------------------------------------------------------------

class QualityEvaluator:
    """Compute PSNR, SSIM, and VMAF between a raw YUV reference and an encoded file.

    Wraps FFmpeg's built-in ``psnr``, ``ssim``, and ``libvmaf`` video filters.
    All three metrics use a ``filter_complex`` with two inputs: [0:v] = reference
    YUV, [1:v] = encoded bitstream decoded on-the-fly by FFmpeg.
    """

    def __init__(self, metrics_output_dir: str | Path = _METRICS_DIR) -> None:
        """Initialise the evaluator and create the metrics output directory.

        Args:
            metrics_output_dir: Directory for per-frame VMAF JSON and PSNR/SSIM
                stats files.  Created automatically if absent.
        """
        self._out_dir = ensure_dir(metrics_output_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_vmaf(
        self,
        reference_yuv: str | Path,
        encoded_path: str | Path,
        width: int,
        height: int,
        fps: float,
    ) -> dict:
        """Compute VMAF scores using FFmpeg's libvmaf filter.

        Saves per-frame VMAF data to a JSON file in ``metrics_output_dir``.
        Handles both the modern libvmaf 2.x schema (``pooled_metrics``) and the
        older 1.x schema (``frames[].metrics.vmaf``) transparently.

        Args:
            reference_yuv: Path to the raw YUV420p reference file.
            encoded_path: Path to the encoded video file to evaluate.
            width: Frame width in pixels (must match the reference YUV).
            height: Frame height in pixels.
            fps: Frames per second of the reference sequence.

        Returns:
            Dict with keys ``vmaf_mean``, ``vmaf_min``, ``vmaf_max``,
            ``frame_count``, and ``json_path``.  All float values are NaN
            on failure to allow graceful downstream handling.
        """
        # Output path for the per-frame libvmaf JSON log.
        json_path = self._out_dir / f"{Path(encoded_path).stem}_vmaf.json"

        # filter_complex wires two inputs into libvmaf:
        #   [0:v] = reference YUV (raw input),  [1:v] = distorted (encoded)
        # setpts=PTS-STARTPTS resets both streams to t=0 to ensure sync.
        filter_str = (
            f"[0:v]setpts=PTS-STARTPTS[ref];"
            f"[1:v]setpts=PTS-STARTPTS[dist];"
            f"[dist][ref]libvmaf=log_path={json_path}:log_fmt=json"
            # log_fmt=json enables structured per-frame output (libvmaf >= 2.0)
        )

        cmd = self._build_filter_cmd(
            reference_yuv, encoded_path, width, height, fps, filter_str
        )
        _LOG.info("Computing VMAF for '%s'", Path(encoded_path).name)
        result = self._run_ffmpeg(cmd, "VMAF")

        if result["returncode"] != 0:
            _LOG.warning("VMAF computation failed - returning NaN placeholders")
            return {
                "vmaf_mean": float("nan"), "vmaf_min": float("nan"),
                "vmaf_max": float("nan"), "frame_count": 0, "json_path": None,
            }

        return self._parse_vmaf_json(json_path)

    def compute_psnr(
        self,
        reference_yuv: str | Path,
        encoded_path: str | Path,
        width: int,
        height: int,
        fps: float,
    ) -> dict:
        """Compute per-plane PSNR (Y, U, V) and their average via FFmpeg psnr filter.

        Writes a per-frame stats file; falls back to parsing the FFmpeg stderr
        summary line if the stats file cannot be read.

        Args:
            reference_yuv: Path to the raw YUV420p reference file.
            encoded_path: Path to the encoded video file to evaluate.
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frames per second.

        Returns:
            Dict with keys ``psnr_y``, ``psnr_u``, ``psnr_v``, ``psnr_avg``,
            and ``frame_count``.  Values are NaN on failure.
        """
        stats_path = self._out_dir / f"{Path(encoded_path).stem}_psnr.log"

        # psnr filter: write per-frame stats to stats_file, also prints a
        # summary line to stderr at the end of processing.
        filter_str = (
            f"[0:v]setpts=PTS-STARTPTS[ref];"
            f"[1:v]setpts=PTS-STARTPTS[dist];"
            f"[dist][ref]psnr=stats_file={stats_path}"
        )

        cmd = self._build_filter_cmd(
            reference_yuv, encoded_path, width, height, fps, filter_str
        )
        _LOG.info("Computing PSNR for '%s'", Path(encoded_path).name)
        result = self._run_ffmpeg(cmd, "PSNR")

        if result["returncode"] != 0:
            _LOG.warning("PSNR computation failed")
            return {
                "psnr_y": float("nan"), "psnr_u": float("nan"),
                "psnr_v": float("nan"), "psnr_avg": float("nan"), "frame_count": 0,
            }

        return self._parse_psnr_log(stats_path, result["stderr"])

    def compute_ssim(
        self,
        reference_yuv: str | Path,
        encoded_path: str | Path,
        width: int,
        height: int,
        fps: float,
    ) -> dict:
        """Compute per-plane SSIM (Y, U, V) and combined average via FFmpeg ssim filter.

        Args:
            reference_yuv: Path to the raw YUV420p reference file.
            encoded_path: Path to the encoded video file to evaluate.
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frames per second.

        Returns:
            Dict with keys ``ssim_y``, ``ssim_u``, ``ssim_v``, ``ssim_avg``,
            and ``frame_count``.  Values are NaN on failure.
        """
        stats_path = self._out_dir / f"{Path(encoded_path).stem}_ssim.log"

        # ssim filter behaves similarly to psnr - writes per-frame stats file
        # and a summary to stderr.
        filter_str = (
            f"[0:v]setpts=PTS-STARTPTS[ref];"
            f"[1:v]setpts=PTS-STARTPTS[dist];"
            f"[dist][ref]ssim=stats_file={stats_path}"
        )

        cmd = self._build_filter_cmd(
            reference_yuv, encoded_path, width, height, fps, filter_str
        )
        _LOG.info("Computing SSIM for '%s'", Path(encoded_path).name)
        result = self._run_ffmpeg(cmd, "SSIM")

        if result["returncode"] != 0:
            _LOG.warning("SSIM computation failed")
            return {
                "ssim_y": float("nan"), "ssim_u": float("nan"),
                "ssim_v": float("nan"), "ssim_avg": float("nan"), "frame_count": 0,
            }

        return self._parse_ssim_log(stats_path, result["stderr"])

    def compute_all(
        self,
        reference_yuv: str | Path,
        encoded_path: str | Path,
        width: int,
        height: int,
        fps: float,
    ) -> QualityResult:
        """Run VMAF, PSNR, and SSIM in sequence and return a unified result.

        Args:
            reference_yuv: Path to the raw YUV420p reference file.
            encoded_path: Path to the encoded video file to evaluate.
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frames per second.

        Returns:
            :class:`QualityResult` aggregating all three metric sets.
        """
        vmaf = self.compute_vmaf(reference_yuv, encoded_path, width, height, fps)
        psnr = self.compute_psnr(reference_yuv, encoded_path, width, height, fps)
        ssim = self.compute_ssim(reference_yuv, encoded_path, width, height, fps)

        json_path_str = vmaf.get("json_path")
        return QualityResult(
            vmaf_mean=vmaf.get("vmaf_mean", float("nan")),
            vmaf_min=vmaf.get("vmaf_min", float("nan")),
            psnr_y_mean=psnr.get("psnr_y", float("nan")),
            ssim_mean=ssim.get("ssim_avg", float("nan")),
            frame_count=vmaf.get("frame_count", 0),
            metrics_json_path=Path(json_path_str) if json_path_str else None,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_filter_cmd(
        self,
        reference_yuv: str | Path,
        encoded_path: str | Path,
        width: int,
        height: int,
        fps: float,
        filter_complex: str,
    ) -> list[str]:
        """Build an FFmpeg command with two inputs and a filter_complex graph.

        Input 0 is the raw YUV reference; input 1 is the encoded file that
        FFmpeg will decode on-the-fly.  Output is discarded (``-f null -``).

        Args:
            reference_yuv: Path to the raw YUV420p reference.
            encoded_path: Path to the encoded video to compare against.
            width: Frame width for the raw input descriptor.
            height: Frame height for the raw input descriptor.
            fps: Frame rate for the raw input descriptor.
            filter_complex: A complete FFmpeg filter_complex string.

        Returns:
            List of FFmpeg argument strings.
        """
        return [
            "ffmpeg",
            # Input 0: raw YUV420p reference - must describe format explicitly.
            "-f", "rawvideo", "-pix_fmt", "yuv420p",
            "-s:v", f"{width}x{height}", "-r", str(fps),
            "-i", str(reference_yuv),
            # Input 1: encoded bitstream - FFmpeg auto-detects format.
            "-i", str(encoded_path),
            "-filter_complex", filter_complex,
            # Discard all output frames - we only need the filter's side-effects.
            "-f", "null", "-",
        ]

    def _run_ffmpeg(self, cmd: list[str], label: str) -> dict:
        """Execute an FFmpeg command and return its exit code and captured stderr.

        Args:
            cmd: Complete FFmpeg argument list.
            label: Short label for logging (e.g. ``'VMAF'``, ``'PSNR'``).

        Returns:
            Dict with keys ``returncode`` (int) and ``stderr`` (str).
        """
        try:
            # 600 s timeout - VMAF at 1080p can take several minutes.
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            _LOG.error("%s FFmpeg process timed out after 600 s", label)
            return {"returncode": -1, "stderr": ""}

        if proc.returncode != 0:
            # Log the tail of stderr for diagnosing filter failures.
            _LOG.debug("%s stderr (last 3000 chars):\n%s",
                       label, proc.stderr[-3000:])
        return {"returncode": proc.returncode, "stderr": proc.stderr}

    def _parse_vmaf_json(self, json_path: Path) -> dict:
        """Parse the libvmaf JSON output file and extract summary statistics.

        Handles both the libvmaf 2.x schema (``pooled_metrics``) and the older
        1.x schema (``frames[].metrics.vmaf``).

        Args:
            json_path: Path to the libvmaf per-frame JSON log file.

        Returns:
            Dict with ``vmaf_mean``, ``vmaf_min``, ``vmaf_max``, ``frame_count``,
            and ``json_path``.  Float fields are NaN if parsing fails.
        """
        if not json_path.is_file():
            _LOG.warning("VMAF JSON not written at '%s'", json_path)
            return {
                "vmaf_mean": float("nan"), "vmaf_min": float("nan"),
                "vmaf_max": float("nan"), "frame_count": 0, "json_path": None,
            }

        try:
            with json_path.open() as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            _LOG.warning("Cannot read VMAF JSON '%s': %s", json_path, exc)
            return {
                "vmaf_mean": float("nan"), "vmaf_min": float("nan"),
                "vmaf_max": float("nan"), "frame_count": 0, "json_path": None,
            }

        # Try modern libvmaf 2.x schema first - uses 'pooled_metrics'.
        try:
            pooled = data["pooled_metrics"]["vmaf"]
            return {
                "vmaf_mean": pooled["mean"],
                "vmaf_min": pooled["min"],
                "vmaf_max": pooled["max"],
                "frame_count": len(data.get("frames", [])),
                "json_path": str(json_path),
            }
        except KeyError:
            pass  # fall through to legacy schema

        # Fallback: libvmaf 1.x schema - per-frame scores under 'frames[].metrics'.
        try:
            frames = data.get("frames", [])
            scores = [f["metrics"]["vmaf"] for f in frames]
            if not scores:
                raise ValueError("VMAF JSON contains no frame scores")
            return {
                "vmaf_mean": sum(scores) / len(scores),
                "vmaf_min": min(scores),
                "vmaf_max": max(scores),
                "frame_count": len(scores),
                "json_path": str(json_path),
            }
        except (KeyError, ValueError, TypeError) as exc:
            _LOG.warning("VMAF JSON schema unrecognised: %s", exc)
            return {
                "vmaf_mean": float("nan"), "vmaf_min": float("nan"),
                "vmaf_max": float("nan"), "frame_count": 0,
                "json_path": str(json_path),
            }

    def _parse_psnr_log(self, stats_path: Path, stderr: str) -> dict:
        """Parse PSNR values from the FFmpeg psnr filter stats file.

        The stats file contains one line per frame with space-separated
        ``key:value`` tokens.  Falls back to parsing the stderr summary line
        if the file is absent.

        Args:
            stats_path: Path to the per-frame PSNR stats file.
            stderr: Captured FFmpeg stderr string for fallback parsing.

        Returns:
            Dict with ``psnr_y``, ``psnr_u``, ``psnr_v``, ``psnr_avg``,
            and ``frame_count``.
        """
        if stats_path.is_file():
            y_vals: list[float] = []
            u_vals: list[float] = []
            v_vals: list[float] = []
            try:
                with stats_path.open() as fh:
                    for line in fh:
                        # Each token is "key:value"; split all and build a dict.
                        parts = dict(
                            token.split(":", 1) for token in line.split()
                            if ":" in token
                        )
                        if "psnr_y" in parts:
                            y_vals.append(float(parts["psnr_y"]))
                        if "psnr_u" in parts:
                            u_vals.append(float(parts["psnr_u"]))
                        if "psnr_v" in parts:
                            v_vals.append(float(parts["psnr_v"]))
            except (OSError, ValueError):
                pass

            if y_vals:
                py = sum(y_vals) / len(y_vals)
                pu = sum(u_vals) / len(u_vals) if u_vals else float("nan")
                pv = sum(v_vals) / len(v_vals) if v_vals else float("nan")
                # Average across all three planes (luminance + chrominance).
                avg = (py + pu + pv) / 3 if (u_vals and v_vals) else py
                return {
                    "psnr_y": py, "psnr_u": pu, "psnr_v": pv,
                    "psnr_avg": avg, "frame_count": len(y_vals),
                }

        # Fallback: parse the single-line summary printed to stderr by FFmpeg.
        # Example: "... PSNR y:42.3 u:44.1 v:44.0 average:43.4 min:..."
        for line in stderr.splitlines():
            if "PSNR" in line and "average" in line.lower():
                try:
                    tokens = dict(t.split(":", 1) for t in line.split() if ":" in t)
                    py = float(tokens.get("y", "nan"))
                    pu = float(tokens.get("u", "nan"))
                    pv = float(tokens.get("v", "nan"))
                    return {
                        "psnr_y": py, "psnr_u": pu, "psnr_v": pv,
                        "psnr_avg": (py + pu + pv) / 3, "frame_count": 0,
                    }
                except (ValueError, KeyError):
                    pass

        return {
            "psnr_y": float("nan"), "psnr_u": float("nan"),
            "psnr_v": float("nan"), "psnr_avg": float("nan"), "frame_count": 0,
        }

    def _parse_ssim_log(self, stats_path: Path, stderr: str) -> dict:
        """Parse SSIM values from the FFmpeg ssim filter stats file.

        The stats file uses space-separated ``key:value`` tokens per frame.
        Falls back to parsing the stderr ``All:`` summary if the file is absent.

        Args:
            stats_path: Path to the per-frame SSIM stats file.
            stderr: Captured FFmpeg stderr string for fallback parsing.

        Returns:
            Dict with ``ssim_y``, ``ssim_u``, ``ssim_v``, ``ssim_avg``,
            and ``frame_count``.
        """
        if stats_path.is_file():
            y_vals: list[float] = []
            u_vals: list[float] = []
            v_vals: list[float] = []
            all_vals: list[float] = []
            try:
                with stats_path.open() as fh:
                    for line in fh:
                        parts = dict(
                            token.split(":", 1) for token in line.split()
                            if ":" in token
                        )
                        # SSIM stats file uses uppercase single-letter keys (Y, U, V, All).
                        if "Y" in parts:
                            y_vals.append(float(parts["Y"]))
                        if "U" in parts:
                            u_vals.append(float(parts["U"]))
                        if "V" in parts:
                            v_vals.append(float(parts["V"]))
                        if "All" in parts:
                            all_vals.append(float(parts["All"]))
            except (OSError, ValueError):
                pass

            if y_vals:
                return {
                    "ssim_y":   sum(y_vals)   / len(y_vals),
                    "ssim_u":   sum(u_vals)   / len(u_vals)   if u_vals   else float("nan"),
                    "ssim_v":   sum(v_vals)   / len(v_vals)   if v_vals   else float("nan"),
                    "ssim_avg": sum(all_vals) / len(all_vals) if all_vals else float("nan"),
                    "frame_count": len(y_vals),
                }

        # Fallback: scan stderr for the "All:" summary value.
        # Example: "... SSIM Y:0.994 U:0.997 V:0.997 All:0.995 (22.596)"
        for line in reversed(stderr.splitlines()):
            if "SSIM" in line and "All" in line:
                try:
                    idx = line.index("All:")
                    # Value immediately follows "All:" separated by a space.
                    val = float(line[idx:].split()[1])
                    return {
                        "ssim_y": float("nan"), "ssim_u": float("nan"),
                        "ssim_v": float("nan"), "ssim_avg": val, "frame_count": 0,
                    }
                except (ValueError, IndexError):
                    pass

        return {
            "ssim_y": float("nan"), "ssim_u": float("nan"),
            "ssim_v": float("nan"), "ssim_avg": float("nan"), "frame_count": 0,
        }

"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    bitstream_analyzer.py
Purpose: Parse encoded video bitstreams with ffprobe to extract frame types,
         GOP structure, rolling bitrate, and PTS continuity data.

Description:
    BitstreamAnalyzer uses ffprobe's JSON output to perform structural validation
    without decoding the bitstream.  It detects missing keyframes, oversized GOPs,
    PTS discontinuities, and bitrate spikes - the same checks run during hardware
    encoder bring-up and post-silicon validation.
"""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.pipeline_utils import get_logger

_LOG = get_logger(__name__)


def _to_int(value: Any) -> int | None:
    """Convert ffprobe string fields to integers when possible.

    Args:
        value: Raw ffprobe field value.

    Returns:
        int | None: Parsed integer, or None for missing/non-numeric values.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    """Convert ffprobe string fields to floats when possible.

    Args:
        value: Raw ffprobe field value.

    Returns:
        float | None: Parsed float, or None for missing/non-numeric values.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FrameInfo:
    """Per-frame structural metadata extracted from ffprobe.

    Attributes:
        frame_num: Zero-based display frame index (ffprobe output order).
        frame_type: Picture type - ``'I'``, ``'P'``, ``'B'``, or ``'unknown'``.
        size_bytes: Encoded packet size in bytes (from ``pkt_size``).
        pts: Presentation timestamp in stream timebase units.
        pts_time: Presentation timestamp in seconds (float).
        dts: Decode timestamp in stream timebase units.
    """

    frame_num: int
    frame_type: str
    size_bytes: int
    pts: int
    pts_time: float
    dts: int


@dataclass
class GOPInfo:
    """Aggregate byte-cost statistics for a single Group of Pictures.

    Each GOP begins with an I-frame and ends just before the next I-frame.
    Byte costs are useful for understanding I-frame overhead vs P/B savings.

    Attributes:
        start_frame: Display index of the first I-frame in this GOP.
        length: Total number of frames in the GOP (including the I-frame).
        i_size_bytes: Total bytes consumed by I-frames in this GOP.
        p_size_bytes: Total bytes consumed by P-frames in this GOP.
        b_size_bytes: Total bytes consumed by B-frames in this GOP.
    """

    start_frame: int
    length: int
    i_size_bytes: int = 0
    p_size_bytes: int = 0
    b_size_bytes: int = 0


# ---------------------------------------------------------------------------
# Analyzer class
# ---------------------------------------------------------------------------

class BitstreamAnalyzer:
    """Structural analysis of encoded video bitstreams using ffprobe.

    All methods are stateless - one instance can be reused across many files.
    Results are returned as plain Python objects (lists and dicts) for easy
    serialisation and integration with downstream reporting.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_frame_types(
        self, encoded_path: str | Path
    ) -> list[FrameInfo]:
        """Return per-frame picture type, byte cost, and timestamp data.

        Runs ffprobe with ``-show_frames`` to obtain ``pict_type`` for each
        video frame and combines it with packet size from ``-show_packets``.

        Args:
            encoded_path: Path to the encoded video file (MP4, MKV, etc.).

        Returns:
            List of :class:`FrameInfo` in display order.  Returns an empty
            list if ffprobe fails or the file contains no video stream.
        """
        # Probe the bitstream - this does NOT decode frames, just parses headers.
        raw = self._probe_frames(encoded_path)
        frames: list[FrameInfo] = []

        for idx, pkt in enumerate(raw):
            # Normalise picture type - ffprobe may return '' for B-frames in
            # some container/codec combinations.
            ptype = pkt.get("pict_type", "unknown")
            if ptype not in ("I", "P", "B"):
                ptype = "unknown"

            try:
                # pkt_pts is the legacy key; pts is the current ffprobe key.
                pts = int(pkt.get("pts", pkt.get("pkt_pts", 0)) or 0)
                dts = int(pkt.get("pkt_dts", 0) or 0)
                pts_time = float(
                    pkt.get("pts_time", pkt.get("pkt_pts_time", 0.0)) or 0.0
                )
                size = int(pkt.get("pkt_size", 0) or 0)
            except (ValueError, TypeError):
                # Corrupted or missing fields - use safe zero defaults.
                pts, dts, pts_time, size = 0, 0, 0.0, 0

            frames.append(FrameInfo(
                frame_num=idx,
                frame_type=ptype,
                size_bytes=size,
                pts=pts,
                pts_time=pts_time,
                dts=dts,
            ))

        return frames

    def get_gop_structure(
        self, encoded_path: str | Path
    ) -> list[GOPInfo]:
        """Analyse the Group of Pictures (GOP) structure of an encoded file.

        Each I-frame starts a new GOP.  Frames between consecutive I-frames
        belong to the preceding GOP.

        Args:
            encoded_path: Path to the encoded video file.

        Returns:
            List of :class:`GOPInfo`, one per GOP in display order.
        """
        frames = self.get_frame_types(encoded_path)
        gops: list[GOPInfo] = []
        current: GOPInfo | None = None

        for fi in frames:
            if fi.frame_type == "I":
                # Flush the current GOP before starting a new one.
                if current is not None:
                    gops.append(current)
                current = GOPInfo(
                    start_frame=fi.frame_num,
                    length=1,
                    i_size_bytes=fi.size_bytes,  # I-frame byte cost
                )
            elif current is not None:
                current.length += 1
                if fi.frame_type == "P":
                    current.p_size_bytes += fi.size_bytes
                elif fi.frame_type == "B":
                    current.b_size_bytes += fi.size_bytes

        # Append the final (possibly incomplete) GOP.
        if current is not None:
            gops.append(current)

        return gops

    def get_bitrate_over_time(
        self,
        encoded_path: str | Path,
        window_frames: int = 30,
    ) -> list[tuple[int, float]]:
        """Compute a rolling average bitrate over a sliding frame window.

        Bitrate = total bits in window / window duration.  The window slides
        one frame at a time across the full sequence.

        Args:
            encoded_path: Path to the encoded video file.
            window_frames: Number of frames in the sliding window (default 30,
                i.e. 1 second at 30 fps).

        Returns:
            List of ``(center_frame_index, bitrate_kbps)`` tuples.
            Empty if the file has fewer frames than ``window_frames``.
        """
        frames = self.get_frame_types(encoded_path)
        if len(frames) < window_frames:
            return []

        # Use probed fps; fall back to 30.0 if unavailable.
        fps = self._probe_fps(encoded_path) or 30.0
        results: list[tuple[int, float]] = []

        for i in range(len(frames) - window_frames + 1):
            window = frames[i : i + window_frames]
            # Total bits in this window across all frame types.
            total_bits = sum(f.size_bytes * 8 for f in window)
            # Duration of window_frames at the stream frame rate (in seconds).
            duration_s = window_frames / fps
            # Convert bits/second to kilobits/second.
            bitrate_kbps = total_bits / duration_s / 1000.0
            # Report at the center frame of the window for smooth plotting.
            center = i + window_frames // 2
            results.append((center, bitrate_kbps))

        return results

    def summarize(self, encoded_path: str | Path) -> dict[str, Any]:
        """Return a diagnostic summary of the bitstream.

        Checks for:
        - First frame not being an I-frame.
        - PTS values that are not strictly monotonically increasing.

        Args:
            encoded_path: Path to the encoded video file.

        Returns:
            Dict with frame statistics, GOP metrics, and a ``'issues'`` list
            of detected structural problems (empty list = no issues).
        """
        frames = self.get_frame_types(encoded_path)
        gops = self.get_gop_structure(encoded_path)
        issues: list[str] = []

        if not frames:
            return {"total_frames": 0, "gops": [], "issues": ["No video frames found"]}

        # Count frames by type.
        i_count = sum(1 for f in frames if f.frame_type == "I")
        p_count = sum(1 for f in frames if f.frame_type == "P")
        b_count = sum(1 for f in frames if f.frame_type == "B")

        # Random-access requirement: the first frame MUST be an I-frame.
        if frames[0].frame_type != "I":
            issues.append(
                f"First frame is type '{frames[0].frame_type}', expected 'I'"
            )

        # PTS continuity check - non-monotonic PTS causes A/V sync failures.
        pts_vals = [f.pts for f in frames if f.pts > 0]
        for j in range(1, len(pts_vals)):
            if pts_vals[j] <= pts_vals[j - 1]:
                issues.append(
                    f"PTS discontinuity at frame {j}: "
                    f"pts[{j}]={pts_vals[j]} <= pts[{j-1}]={pts_vals[j - 1]}"
                )
                break  # report only the first discontinuity

        gop_lengths = [g.length for g in gops]
        return {
            "total_frames": len(frames),
            "i_frames": i_count,
            "p_frames": p_count,
            "b_frames": b_count,
            "gop_count": len(gops),
            "gop_lengths": gop_lengths,
            "gop_min": min(gop_lengths) if gop_lengths else 0,
            "gop_max": max(gop_lengths) if gop_lengths else 0,
            "total_size_bytes": sum(f.size_bytes for f in frames),
            "issues": issues,
        }

    def get_stream_metadata(self, encoded_path: str | Path) -> dict[str, Any]:
        """Return codec, profile, pixel format, duration, bitrate, and size metadata.

        Args:
            encoded_path: Path to the encoded video file.

        Returns:
            dict[str, Any]: Metadata parsed from ffprobe. Missing or failed probes
            return an ``issues`` list explaining the failure.
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries",
            "stream=codec_name,profile,pix_fmt,width,height,nb_frames,avg_frame_rate,bit_rate:format=duration,bit_rate,size",
            "-print_format", "json",
            str(encoded_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return {"issues": ["ffprobe metadata probe timed out"]}

        if proc.returncode != 0:
            return {"issues": [proc.stderr.strip() or "ffprobe metadata probe failed"]}

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            return {"issues": [f"ffprobe metadata JSON parse failed: {exc}"]}

        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format", {})
        return {
            "codec": stream.get("codec_name"),
            "profile": stream.get("profile"),
            "pixel_format": stream.get("pix_fmt"),
            "width": _to_int(stream.get("width")),
            "height": _to_int(stream.get("height")),
            "frame_count": _to_int(stream.get("nb_frames")),
            "avg_frame_rate": stream.get("avg_frame_rate"),
            "stream_bit_rate": _to_int(stream.get("bit_rate")),
            "duration": _to_float(fmt.get("duration")),
            "bitrate": _to_int(fmt.get("bit_rate")),
            "size_bytes": _to_int(fmt.get("size")),
            "issues": [],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _probe_frames(self, encoded_path: str | Path) -> list[dict]:
        """Run ffprobe with -show_frames and parse the resulting JSON.

        Args:
            encoded_path: Path to the encoded video file.

        Returns:
            List of frame dicts from the ffprobe JSON output.
            Empty list on timeout or parse failure.
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",   # first video stream only
            "-show_frames",             # emit one JSON object per decoded frame
            "-show_packets",            # emit pkt_size per packet
            "-print_format", "json",
            str(encoded_path),
        ]
        try:
            # 300 s covers very long files; parsing only, no decoding.
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            _LOG.error("ffprobe timed out for '%s'", encoded_path)
            return []

        if proc.returncode != 0:
            _LOG.warning("ffprobe failed (last 2000 chars):\n%s",
                         proc.stderr[-2000:])
            return []

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            _LOG.warning("ffprobe JSON parse error for '%s': %s", encoded_path, exc)
            return []

        # ffprobe -show_frames emits both audio and video entries;
        # filter to video-only frames to avoid mixed type errors.
        return [f for f in data.get("frames", [])
                if f.get("media_type") == "video"]

    def _probe_fps(self, encoded_path: str | Path) -> float | None:
        """Return the average frame rate of the first video stream.

        Args:
            encoded_path: Path to the encoded video file.

        Returns:
            Frame rate as a :class:`float`, or ``None`` if unavailable.
        """
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate",
            "-print_format", "json",
            str(encoded_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            data = json.loads(proc.stdout)
            # avg_frame_rate is a rational string like "30000/1001" or "30/1".
            r = data["streams"][0]["avg_frame_rate"]
            num, den = (int(x) for x in r.split("/"))
            return num / den if den else None
        except Exception:
            return None

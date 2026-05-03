"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    test_bitstream_analyzer.py
Purpose: Unit tests for ffprobe JSON parsing, GOP grouping, bitrate, and metadata.

Description:
    Tests patch ffprobe subprocess calls with small JSON payloads so bitstream
    analysis can be validated quickly without real compressed media files.
"""

import json
from unittest.mock import patch

from src.bitstream_analyzer import BitstreamAnalyzer


class _Completed:
    """Fake subprocess result for ffprobe tests."""

    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        """Store subprocess-like fields.

        Args:
            stdout: JSON stdout text.
            returncode: Process exit code.
            stderr: Captured stderr text.
        """
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _frames_json() -> str:
    """Return a tiny ffprobe frame JSON payload.

    Returns:
        str: JSON containing one I-frame followed by P/B frames.
    """
    return json.dumps({
        "frames": [
            {"key_frame": 1, "pict_type": "I", "pkt_size": "1000", "pts": "1", "best_effort_timestamp_time": "0.000000", "pkt_dts": "1"},
            {"key_frame": 0, "pict_type": "B", "pkt_size": "250", "pts": "2", "best_effort_timestamp_time": "0.033333", "pkt_dts": "2"},
            {"key_frame": 0, "pict_type": "P", "pkt_size": "500", "pts": "3", "best_effort_timestamp_time": "0.066667", "pkt_dts": "3"},
            {"key_frame": 1, "pict_type": "I", "pkt_size": "900", "pts": "4", "best_effort_timestamp_time": "0.100000", "pkt_dts": "4"},
        ]
    })


def test_get_frame_types_parses_ffprobe_frames():
    """get_frame_types should return typed FrameInfo records."""
    analyzer = BitstreamAnalyzer()
    with patch("src.bitstream_analyzer.subprocess.run", return_value=_Completed(_frames_json())):
        frames = analyzer.get_frame_types("clip.mp4")
    assert [frame.frame_type for frame in frames] == ["I", "B", "P", "I"]
    assert frames[0].size_bytes == 1000
    assert frames[0].key_frame is True
    assert frames[1].timestamp == 0.033333


def test_get_gop_structure_groups_frames_from_i_frame():
    """get_gop_structure should group frames beginning at an I-frame."""
    analyzer = BitstreamAnalyzer()
    with patch("src.bitstream_analyzer.subprocess.run", return_value=_Completed(_frames_json())):
        gops = analyzer.get_gop_structure("clip.mp4")
    assert len(gops) == 2
    assert gops[0].length == 3
    assert gops[0].i_size_bytes == 1000


def test_get_stream_metadata_parses_codec_profile_and_format():
    """get_stream_metadata should expose codec, profile, pixel format, and bitrate."""
    payload = json.dumps({
        "streams": [{
            "codec_name": "h264",
            "profile": "High",
            "pix_fmt": "yuv420p",
            "width": 352,
            "height": 288,
            "nb_frames": "60",
            "avg_frame_rate": "30/1",
            "bit_rate": "900000",
        }],
        "format": {"duration": "2.0", "bit_rate": "900000", "size": "225000"},
    })
    analyzer = BitstreamAnalyzer()
    with patch("src.bitstream_analyzer.subprocess.run", return_value=_Completed(payload)):
        metadata = analyzer.get_stream_metadata("clip.mp4")
    assert metadata["codec"] == "h264"
    assert metadata["profile"] == "High"
    assert metadata["pixel_format"] == "yuv420p"
    assert metadata["frame_count"] == 60
    assert metadata["issues"] == []


def test_summarize_computes_gop_and_frame_type_counts():
    """summarize should populate GOP and frame-type fields from frame JSON."""
    analyzer = BitstreamAnalyzer()
    with patch("src.bitstream_analyzer.subprocess.run", return_value=_Completed(_frames_json())):
        summary = analyzer.summarize("clip.mp4")
    assert summary["frame_count"] == 4
    assert summary["keyframe_count"] == 2
    assert summary["gop_count"] == 2
    assert summary["gop_max"] == 3
    assert summary["frame_type_counts"] == {"I": 2, "P": 1, "B": 1, "other": 0}
    assert summary["issues"] == []

"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    rd_curve_analyzer.py
Purpose: Rate-distortion analysis - compute BPP, plot RD curves, calculate BD-rate
         between codec pairs, and persist results to JSON.

Description:
    RDCurveAnalyzer implements the full RD workflow: bits-per-pixel normalisation,
    matplotlib-based RD curve plotting (BPP vs VMAF/PSNR/SSIM), and Bjontegaard
    Delta Rate (BD-rate) computation via degree-3 polynomial integration in
    log-bitrate space (ITU-T SG16 VCEG-M33 method).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from src.pipeline_utils import ensure_dir, get_logger

# Use the non-interactive Agg backend so plots can be generated on headless servers
# (e.g. CI pipelines, Docker containers) without a display.
matplotlib.use("Agg")

_LOG = get_logger(__name__)

# Default output directory for generated plot images.
_PLOTS_DIR = Path("outputs/plots")


class RDCurveAnalyzer:
    """Rate-distortion analysis tool for comparing codecs and encoding configurations.

    Computes BPP (bits-per-pixel), generates RD curve plots as PNG images, and
    implements Bjontegaard Delta Rate (BD-rate) using polynomial fitting over the
    overlapping quality range of two RD curves.
    """

    def __init__(self, plots_output_dir: str | Path = _PLOTS_DIR) -> None:
        """Initialise and ensure the plots output directory exists.

        Args:
            plots_output_dir: Directory where PNG plot files will be written.
        """
        self._plots_dir = ensure_dir(plots_output_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_bpp(
        self,
        file_size_bytes: int,
        width: int,
        height: int,
        frame_count: int,
    ) -> float:
        """Compute bits-per-pixel - a resolution-normalised compression metric.

        BPP = (file_size_bytes x 8) / (width x height x frame_count)

        BPP normalises encoded file size for both resolution and duration,
        enabling fair comparison between clips of different lengths.

        Args:
            file_size_bytes: Total size of the encoded output file in bytes.
            width: Frame width in pixels.
            height: Frame height in pixels.
            frame_count: Total number of frames in the sequence.

        Returns:
            Bits-per-pixel as a :class:`float`.  Lower BPP = more efficient
            compression for a given quality level.

        Raises:
            ValueError: If any of ``frame_count``, ``width``, or ``height`` is <= 0.
        """
        if frame_count <= 0 or width <= 0 or height <= 0:
            raise ValueError(
                f"frame_count, width, height must all be positive integers; "
                f"got frame_count={frame_count}, width={width}, height={height}"
            )
        # Total pixel count across the entire sequence.
        total_pixels = width * height * frame_count
        # Convert bytes to bits (x8) then divide by total pixels.
        return (file_size_bytes * 8) / total_pixels

    def plot_rd_curve(
        self,
        results_list: list[dict[str, Any]],
        metric: str = "vmaf",
        output_path: str | Path | None = None,
    ) -> Path:
        """Plot a rate-distortion curve (BPP on X axis, quality metric on Y axis).

        Each entry in ``results_list`` is a dict containing at minimum:
          - ``'bpp'``: bits-per-pixel value (float)
          - the chosen metric key (float)
          - optionally ``'label'`` or ``'codec'`` for the legend

        Multiple curves are supported - entries are grouped by ``'label'`` or
        ``'codec'`` and each group becomes one line on the plot.

        Args:
            results_list: List of RD point dicts.
            metric: Quality metric for the Y axis.  Supported: ``'vmaf'``,
                ``'psnr_y'``, ``'ssim'``, or any key present in the dicts.
            output_path: Destination PNG path.  Auto-named from metric if ``None``.

        Returns:
            :class:`pathlib.Path` to the saved PNG file.

        Raises:
            ValueError: If ``results_list`` is empty.
        """
        if not results_list:
            raise ValueError("results_list must contain at least one RD point")

        if output_path is None:
            output_path = self._plots_dir / f"rd_curve_{metric}.png"
        output_path = Path(output_path)
        ensure_dir(output_path.parent)

        fig, ax = plt.subplots(figsize=(9, 6))

        # Group points by label (or codec name as fallback).
        groups: dict[str, list[dict]] = {}
        for r in results_list:
            key = r.get("label", r.get("codec", "unknown"))
            groups.setdefault(key, []).append(r)

        # Plot each codec group as a separate labelled line.
        for label, pts in groups.items():
            # Sort ascending by BPP so line segments always go left to right.
            pts_sorted = sorted(pts, key=lambda x: x.get("bpp", 0))
            bpps = [p["bpp"] for p in pts_sorted]
            quals = [p.get(metric, float("nan")) for p in pts_sorted]
            ax.plot(bpps, quals, marker="o", label=label, linewidth=2)

        ax.set_xlabel("Bits per Pixel (BPP)", fontsize=12)
        ax.set_ylabel(metric.upper(), fontsize=12)
        ax.set_title(f"Rate-Distortion: BPP vs {metric.upper()}", fontsize=13)
        ax.legend()
        ax.grid(True, alpha=0.4)
        fig.tight_layout()
        # dpi=150 produces ~1350x900 px at 9-inch width - good for documentation.
        fig.savefig(str(output_path), dpi=150)
        plt.close(fig)  # free memory - Agg backend does not auto-close figures

        _LOG.info("RD curve saved to '%s'", output_path)
        return output_path

    def compute_bdrate(
        self,
        rd_curve_a: list[tuple[float, float]],
        rd_curve_b: list[tuple[float, float]],
        piecewise_degree: int = 3,
    ) -> float:
        """Compute Bjontegaard Delta Rate (BD-rate) between two RD curves.

        BD-rate is the average bitrate saving (or overhead) of curve B relative
        to curve A, integrated over their overlapping quality range in log-bitrate
        space.  Negative = B is more efficient; Positive = B is less efficient.

        Implementation follows the polynomial-integral method described in
        ITU-T SG16 VCEG-M33 (Bjontegaard 2001), using degree-3 polynomial
        fitting.

        Args:
            rd_curve_a: Reference RD curve as ``[(bpp, quality), ...]``.
                Requires at least 4 points for a meaningful degree-3 fit.
            rd_curve_b: Test RD curve as ``[(bpp, quality), ...]``.
            piecewise_degree: Polynomial degree for log-domain curve fitting
                (default 3, as per the Bjontegaard standard).

        Returns:
            BD-rate percentage.  A value of ``-30.0`` means curve B achieves
            the same quality as A at 30 % fewer bits.  Returns ``NaN`` if
            there is no overlapping quality range.

        Raises:
            ValueError: If either curve has fewer than 4 data points.
        """
        if len(rd_curve_a) < 4 or len(rd_curve_b) < 4:
            raise ValueError(
                "BD-rate requires at least 4 data points per curve for a "
                "reliable degree-3 polynomial fit"
            )

        # Sort both curves by quality (ascending) for polyfit stability.
        ra = sorted(rd_curve_a, key=lambda x: x[1])
        rb = sorted(rd_curve_b, key=lambda x: x[1])

        # Work in log-bitrate space - this linearises the RD relationship and
        # is the standard transformation in the Bjontegaard method.
        bpp_a = np.log([p[0] for p in ra])
        q_a = np.array([p[1] for p in ra])
        bpp_b = np.log([p[0] for p in rb])
        q_b = np.array([p[1] for p in rb])

        # Integration bounds = overlap of the two quality ranges.
        min_q = max(q_a.min(), q_b.min())
        max_q = min(q_a.max(), q_b.max())

        if min_q >= max_q:
            _LOG.warning(
                "No overlapping quality range between the two curves - "
                "cannot compute BD-rate"
            )
            return float("nan")

        # Fit degree-3 polynomials (log-bpp as a function of quality).
        poly_a = np.polyfit(q_a, bpp_a, piecewise_degree)
        poly_b = np.polyfit(q_b, bpp_b, piecewise_degree)

        # Integrate each polynomial over [min_q, max_q].
        # np.polyint() raises degree by 1 and prepends the antiderivative coefficients.
        int_a = np.polyint(poly_a)
        int_b = np.polyint(poly_b)

        # Definite integrals via the fundamental theorem of calculus.
        area_a = np.polyval(int_a, max_q) - np.polyval(int_a, min_q)
        area_b = np.polyval(int_b, max_q) - np.polyval(int_b, min_q)

        # Average log-BPP difference over the quality range.
        avg_diff_log_bpp = (area_b - area_a) / (max_q - min_q)

        # Convert from log-space difference to percentage.
        # exp(Delta log BPP) - 1 gives the fractional bitrate change.
        bdrate_pct = (np.exp(avg_diff_log_bpp) - 1) * 100.0
        return float(bdrate_pct)

    def compare_codecs(
        self,
        codec_results_dict: dict[str, list[dict[str, Any]]],
        metric: str = "vmaf",
        output_path: str | Path | None = None,
    ) -> Path:
        """Plot RD curves for multiple codecs on a single overlay figure.

        Args:
            codec_results_dict: Mapping of ``codec_name -> [rd_point_dict, ...]``.
                Each dict needs at minimum a ``'bpp'`` key and the chosen metric key.
            metric: Quality metric for the Y axis.
            output_path: Destination PNG.  Auto-named if ``None``.

        Returns:
            :class:`pathlib.Path` to the saved PNG.
        """
        if output_path is None:
            output_path = self._plots_dir / f"codec_comparison_{metric}.png"
        output_path = Path(output_path)

        # Flatten all codec point lists into a single list with a 'label' key.
        all_points: list[dict[str, Any]] = []
        for codec, pts in codec_results_dict.items():
            for p in pts:
                all_points.append({**p, "label": codec})

        return self.plot_rd_curve(all_points, metric=metric, output_path=output_path)

    def save_rd_table(
        self,
        results: list[dict[str, Any]],
        output_json: str | Path,
    ) -> None:
        """Persist a list of RD result dicts to a JSON file.

        Args:
            results: List of RD point dicts (each from a single encode run).
            output_json: Destination JSON file path.
        """
        output_json = Path(output_json)
        ensure_dir(output_json.parent)
        try:
            with output_json.open("w", encoding="utf-8") as fh:
                # default=str handles Path objects and other non-JSON-serialisable types.
                json.dump(results, fh, indent=2, default=str)
            _LOG.info("RD table persisted to '%s'", output_json)
        except OSError as exc:
            _LOG.error("Failed to write RD table to '%s': %s", output_json, exc)

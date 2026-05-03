"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    generate_rd_analysis.py
Purpose: Generate RD curves and BD-rate style codec comparison tables.

Description:
    Reads the validation summary CSV, plots BPP-vs-quality curves, and computes
    pairwise average bitrate savings over overlapping quality ranges. The PSNR
    path is always attempted; SSIM and VMAF are generated only when data exists.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPORT_CSV = Path("outputs/reports/validation_summary.csv")
PLOTS_DIR = Path("outputs/plots")
DOCS_IMAGES_DIR = Path("docs/images")

_COLUMN_ALIASES = {
    "codec": ["codec", "Codec"],
    "bpp": ["bpp", "BPP"],
    "psnr_y": ["psnr_y", "PSNR-Y", "PSNR_Y", "PSNR"],
    "ssim": ["ssim", "SSIM"],
    "vmaf": ["vmaf", "VMAF"],
}


def _ensure_dirs() -> None:
    """Create output directories for plots and README images."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common report column aliases.

    Args:
        df: Raw DataFrame loaded from CSV.

    Returns:
        DataFrame with canonical codec, bpp, psnr_y, ssim, and vmaf columns when present.
    """
    out = df.copy()
    for canonical, aliases in _COLUMN_ALIASES.items():
        if canonical in out.columns:
            continue
        for alias in aliases:
            if alias in out.columns:
                out[canonical] = out[alias]
                break
    return out


def _metric_available(df: pd.DataFrame, metric: str) -> bool:
    """Return True when metric values exist in the report."""
    return metric in df.columns and pd.to_numeric(df[metric], errors="coerce").notna().any()


def _codec_curve(df: pd.DataFrame, codec: str, metric: str) -> list[tuple[float, float]]:
    """Extract a clean BPP/metric curve for one codec.

    Args:
        df: Normalized validation summary rows.
        codec: Codec name to filter.
        metric: Quality metric column.

    Returns:
        Sorted list of (bpp, quality) points.
    """
    subset = df[df["codec"] == codec].copy()
    subset["bpp"] = pd.to_numeric(subset["bpp"], errors="coerce")
    subset[metric] = pd.to_numeric(subset[metric], errors="coerce")
    subset = subset.dropna(subset=["bpp", metric])
    subset = subset[(subset["bpp"] > 0)]
    points = [(float(row["bpp"]), float(row[metric])) for _, row in subset.iterrows()]
    return sorted(points, key=lambda item: item[1])


def average_bitrate_saving(test_curve: list[tuple[float, float]], ref_curve: list[tuple[float, float]]) -> float | None:
    """Compute average bitrate saving over the overlapping quality range.

    Args:
        test_curve: Test codec RD points as (bpp, quality).
        ref_curve: Reference codec RD points as (bpp, quality).

    Returns:
        Percent bitrate difference, or None when comparison is not meaningful.
        Negative means the test codec needs less BPP than the reference codec.
    """
    if len(test_curve) < 2 or len(ref_curve) < 2:
        return None

    test = np.array(sorted(test_curve, key=lambda item: item[1]), dtype=float)
    ref = np.array(sorted(ref_curve, key=lambda item: item[1]), dtype=float)
    q_min = max(float(test[:, 1].min()), float(ref[:, 1].min()))
    q_max = min(float(test[:, 1].max()), float(ref[:, 1].max()))
    if not math.isfinite(q_min) or not math.isfinite(q_max) or q_min >= q_max:
        return None

    quality_grid = np.linspace(q_min, q_max, 50)
    test_log_bpp = np.interp(quality_grid, test[:, 1], np.log(test[:, 0]))
    ref_log_bpp = np.interp(quality_grid, ref[:, 1], np.log(ref[:, 0]))
    avg_delta = float(np.mean(test_log_bpp - ref_log_bpp))
    return (math.exp(avg_delta) - 1.0) * 100.0


def _metric_slug(metric: str) -> str:
    """Return filename-friendly metric name."""
    return "psnr" if metric == "psnr_y" else metric


def _plot_rd_curve(df: pd.DataFrame, metric: str) -> Path | None:
    """Plot one BPP-vs-quality RD curve grouped by codec."""
    if not _metric_available(df, metric):
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    for codec in sorted(df["codec"].dropna().unique()):
        points = _codec_curve(df, codec, metric)
        if points:
            bpps, values = zip(*points)
            ax.plot(bpps, values, marker="o", label=codec)

    ax.set_title(f"Rate-Distortion: BPP vs {metric.upper()}")
    ax.set_xlabel("BPP")
    ax.set_ylabel(metric.upper())
    ax.grid(True, alpha=0.35)
    ax.legend()
    fig.tight_layout()
    path = PLOTS_DIR / f"rd_curve_{_metric_slug(metric)}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    shutil.copy2(path, DOCS_IMAGES_DIR / path.name)
    return path


def _write_bdrate_matrix(df: pd.DataFrame, metric: str) -> tuple[Path, Path] | None:
    """Write a pairwise BD-rate style matrix as CSV and PNG heatmap."""
    if not _metric_available(df, metric):
        return None

    codecs = sorted(df["codec"].dropna().unique())
    matrix: list[list[float | None]] = []
    for test_codec in codecs:
        row: list[float | None] = []
        for ref_codec in codecs:
            if test_codec == ref_codec:
                row.append(0.0)
            else:
                row.append(average_bitrate_saving(
                    _codec_curve(df, test_codec, metric),
                    _codec_curve(df, ref_codec, metric),
                ))
        matrix.append(row)

    csv_path = PLOTS_DIR / f"bd_rate_matrix_{_metric_slug(metric)}.csv"
    pd.DataFrame(matrix, index=codecs, columns=codecs).to_csv(csv_path, na_rep="NA")

    values = np.array([[np.nan if value is None else value for value in row] for row in matrix], dtype=float)
    fig, ax = plt.subplots(figsize=(max(6, len(codecs) * 1.3), max(4, len(codecs) * 1.0)))
    image = ax.imshow(values, cmap="RdYlGn_r", vmin=-50, vmax=50)
    ax.set_xticks(range(len(codecs)))
    ax.set_yticks(range(len(codecs)))
    ax.set_xticklabels(codecs, rotation=30, ha="right")
    ax.set_yticklabels(codecs)
    ax.set_title(f"BD-rate Style Matrix ({metric.upper()})")
    ax.set_xlabel("Reference codec")
    ax.set_ylabel("Test codec")
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            label = "NA" if value is None else f"{value:.1f}%"
            ax.text(j, i, label, ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=ax, label="Bitrate difference (%)")
    fig.tight_layout()
    png_path = PLOTS_DIR / f"bd_rate_matrix_{_metric_slug(metric)}.png"
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    shutil.copy2(png_path, DOCS_IMAGES_DIR / png_path.name)
    return csv_path, png_path


def generate_rd_analysis(report_csv: Path = REPORT_CSV) -> list[Path]:
    """Generate RD curves and BD-rate matrices from a validation CSV.

    Args:
        report_csv: Path to validation_summary.csv.

    Returns:
        List of generated output paths.
    """
    _ensure_dirs()
    if not report_csv.is_file():
        raise FileNotFoundError(f"Report CSV not found: {report_csv}")

    df = _resolve_columns(pd.read_csv(report_csv))
    outputs: list[Path] = []
    for metric in ["psnr_y", "ssim", "vmaf"]:
        curve = _plot_rd_curve(df, metric)
        if curve:
            outputs.append(curve)
        matrix = _write_bdrate_matrix(df, metric)
        if matrix:
            outputs.extend(matrix)
    return outputs


def main() -> None:
    """CLI entry point for RD and BD-rate style analysis."""
    for path in generate_rd_analysis():
        print(path)


if __name__ == "__main__":
    main()

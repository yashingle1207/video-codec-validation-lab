"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    generate_validation_plots.py
Purpose: Generate documentation-ready validation plots from the pipeline CSV report.

Description:
    Reads outputs/reports/validation_summary.csv and turns codec validation rows
    into compact PNG plots for GitHub documentation. The script avoids media-file
    dependencies and copies small README-ready images into docs/images.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


REPORT_CSV = Path("outputs/reports/validation_summary.csv")
PLOTS_DIR = Path("outputs/plots")
DOCS_IMAGES_DIR = Path("docs/images")


def _ensure_dirs() -> None:
    """Create plot output directories if they do not already exist."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _numeric(series: pd.Series) -> pd.Series:
    """Convert a report column to numeric values with invalid cells as NaN."""
    return pd.to_numeric(series, errors="coerce")


def _has_metric(df: pd.DataFrame, metric: str) -> bool:
    """Return True when the metric column exists and has at least one value."""
    return metric in df.columns and _numeric(df[metric]).notna().any()


def _copy_to_docs(path: Path) -> None:
    """Copy one generated PNG into docs/images for GitHub README use."""
    shutil.copy2(path, DOCS_IMAGES_DIR / path.name)


def _plot_metric_by_codec(df: pd.DataFrame, x_col: str, y_col: str, filename: str, title: str) -> Path | None:
    """Plot one numeric metric grouped by codec.

    Args:
        df: Validation summary rows.
        x_col: X-axis column name.
        y_col: Y-axis column name.
        filename: PNG filename to write under outputs/plots.
        title: Plot title.

    Returns:
        Path to the generated PNG, or None if the required data is missing.
    """
    if x_col not in df.columns or not _has_metric(df, y_col):
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    for codec, group in df.groupby("codec"):
        x = _numeric(group[x_col])
        y = _numeric(group[y_col])
        keep = x.notna() & y.notna()
        if keep.any():
            order = x[keep].argsort()
            ax.plot(x[keep].iloc[order], y[keep].iloc[order], marker="o", label=codec)

    ax.set_title(title)
    ax.set_xlabel(x_col.replace("_", " ").upper())
    ax.set_ylabel(y_col.replace("_", " ").upper())
    ax.grid(True, alpha=0.35)
    ax.legend()
    fig.tight_layout()
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=150)
    plt.close(fig)
    _copy_to_docs(path)
    return path


def _plot_bar_by_row(df: pd.DataFrame, value_col: str, filename: str, title: str) -> Path | None:
    """Plot a compact per-encode bar chart.

    Args:
        df: Validation summary rows.
        value_col: Numeric column to plot.
        filename: PNG filename to write.
        title: Plot title.

    Returns:
        Path to the generated PNG, or None when no values are available.
    """
    if not _has_metric(df, value_col):
        return None

    labels = df["codec"].astype(str) + " CRF " + df["crf_or_bitrate"].astype(str)
    values = _numeric(df[value_col])
    keep = values.notna()
    if not keep.any():
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(range(keep.sum()), values[keep])
    ax.set_xticks(range(keep.sum()))
    ax.set_xticklabels(labels[keep], rotation=45, ha="right")
    ax.set_title(title)
    ax.set_ylabel(value_col.replace("_", " ").upper())
    ax.grid(True, axis="y", alpha=0.35)
    fig.tight_layout()
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=150)
    plt.close(fig)
    _copy_to_docs(path)
    return path


def _plot_pass_fail(df: pd.DataFrame) -> Path:
    """Plot pass/fail counts from the validation report."""
    passed = df["pass"].astype(str).str.lower().isin(["true", "1", "yes"]).sum()
    failed = len(df) - passed
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["Pass", "Fail"], [passed, failed])
    ax.set_title("Validation Pass/Fail Summary")
    ax.set_ylabel("Rows")
    ax.grid(True, axis="y", alpha=0.35)
    fig.tight_layout()
    path = PLOTS_DIR / "validation_pass_fail_summary.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    _copy_to_docs(path)
    return path


def generate_plots(report_csv: Path = REPORT_CSV) -> list[Path]:
    """Generate all available validation plots from a summary CSV.

    Args:
        report_csv: Path to validation_summary.csv.

    Returns:
        List of PNG paths generated under outputs/plots.
    """
    _ensure_dirs()
    if not report_csv.is_file():
        raise FileNotFoundError(f"Report CSV not found: {report_csv}")

    df = pd.read_csv(report_csv)
    generated: list[Path] = []
    plot_specs = [
        ("bpp", "psnr_y", "rd_curve_psnr.png", "Rate-Distortion: BPP vs PSNR-Y"),
        ("crf_or_bitrate", "psnr_y", "crf_vs_psnr.png", "CRF vs PSNR-Y"),
        ("crf_or_bitrate", "bpp", "crf_vs_bpp.png", "CRF vs BPP"),
        ("bpp", "ssim", "rd_curve_ssim.png", "Rate-Distortion: BPP vs SSIM"),
        ("bpp", "vmaf", "rd_curve_vmaf.png", "Rate-Distortion: BPP vs VMAF"),
    ]
    for x_col, y_col, filename, title in plot_specs:
        path = _plot_metric_by_codec(df, x_col, y_col, filename, title)
        if path:
            generated.append(path)

    for value_col, filename, title in [
        ("encode_time_s", "encode_time_comparison.png", "Encode Time by Codec Setting"),
        ("file_size_mb", "file_size_comparison.png", "Encoded File Size by Codec Setting"),
    ]:
        path = _plot_bar_by_row(df, value_col, filename, title)
        if path:
            generated.append(path)

    generated.append(_plot_pass_fail(df))
    return generated


def main() -> None:
    """CLI entry point for plot generation."""
    generated = generate_plots()
    for path in generated:
        print(path)


if __name__ == "__main__":
    main()

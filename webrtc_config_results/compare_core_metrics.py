#!/usr/bin/env python3
"""
Compare key WebRTC QoE metrics between two receiver runs.

The script focuses on the metrics called out in the Gain2 vs GoogleCC2 debug
charts (QP, FPS, freeze count, undecodable frames). It parses receiver log
files, aggregates the metrics, prints a textual summary with percentage
improvements, and optionally writes a bar chart for easier visual comparison.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import matplotlib

matplotlib.use("Agg")  # Always render off-screen.
import matplotlib.pyplot as plt
import pandas as pd


PATTERNS = {
    "framerate": re.compile(
        r"\[VideoQuality-FrameRate\] MonoTime: (\d+), SSRC: (\d+), "
        r"Frames Received: (\d+), Frames Decoded: (\d+), Frames Dropped: (\d+), "
        r"Decoded FPS: (\d+), Frame Size: (\d+)x(\d+)"
    ),
    "freeze": re.compile(
        r"\[VideoQuality-FreezeRate\] MonoTime: (\d+), SSRC: (\d+), Freeze Count: (\d+)"
    ),
    "qp": re.compile(
        r"\[VideoQuality-QP\] MonoTime: (\d+), SSRC: (\d+), QP Sum: (\d+), Average QP: (\d+\.?\d*)"
    ),
}


@dataclass(frozen=True)
class MetricSnapshot:
    """Container for the metrics we report."""

    avg_fps: float
    avg_qp: float
    total_freezes: float
    total_undecodable: float


def parse_receiver_log(path: Path) -> pd.DataFrame:
    """Parse a receiver log exported by WebRTC."""
    aggregated: Dict[int, Dict[str, float]] = {}

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            match = PATTERNS["framerate"].search(line)
            if match:
                timestamp = int(match.group(1))
                frames_dropped = int(match.group(5))
                aggregated.setdefault(timestamp, {})
                aggregated[timestamp]["decoded_fps"] = int(match.group(6))
                aggregated[timestamp]["undecodable_frames"] = frames_dropped
                continue

            match = PATTERNS["freeze"].search(line)
            if match:
                timestamp = int(match.group(1))
                aggregated.setdefault(timestamp, {})
                aggregated[timestamp]["freeze_count"] = int(match.group(3))
                continue

            match = PATTERNS["qp"].search(line)
            if match:
                timestamp = int(match.group(1))
                aggregated.setdefault(timestamp, {})
                aggregated[timestamp]["avg_qp"] = float(match.group(4))
                continue

    df = pd.DataFrame.from_dict(aggregated, orient="index")
    df.index.name = "timestamp"
    df.sort_index(inplace=True)
    return df


def compute_summary(df: pd.DataFrame) -> MetricSnapshot:
    """Compute key statistics from the parsed dataframe."""
    if df.empty:
        return MetricSnapshot(avg_fps=0.0, avg_qp=0.0, total_freezes=0.0, total_undecodable=0.0)

    qp_mask = df["avg_qp"] > 0 if "avg_qp" in df.columns else pd.Series(dtype=bool)
    avg_qp = df.loc[qp_mask, "avg_qp"].mean() if qp_mask.any() else 0.0

    return MetricSnapshot(
        avg_fps=df["decoded_fps"].mean() if "decoded_fps" in df.columns else 0.0,
        avg_qp=avg_qp,
        total_freezes=df["freeze_count"].max() if "freeze_count" in df.columns else 0.0,
        total_undecodable=(
            df["undecodable_frames"].max() if "undecodable_frames" in df.columns else 0.0
        ),
    )


def compute_improvement(base: MetricSnapshot, challenger: MetricSnapshot) -> Dict[str, float]:
    """Compute percentage improvements from base -> challenger."""
    improvements: Dict[str, float] = {}

    def pct_improvement(val_base: float, val_new: float, higher_better: bool) -> float:
        if val_base == 0:
            return 0.0
        delta = val_new - val_base if higher_better else val_base - val_new
        return (delta / val_base) * 100.0

    improvements["avg_fps"] = pct_improvement(base.avg_fps, challenger.avg_fps, higher_better=True)
    improvements["avg_qp"] = pct_improvement(base.avg_qp, challenger.avg_qp, higher_better=False)
    improvements["total_freezes"] = pct_improvement(
        base.total_freezes, challenger.total_freezes, higher_better=False
    )
    improvements["total_undecodable"] = pct_improvement(
        base.total_undecodable, challenger.total_undecodable, higher_better=False
    )

    return improvements


def print_summary_table(
    base_label: str,
    challenger_label: str,
    base_metrics: MetricSnapshot,
    challenger_metrics: MetricSnapshot,
    improvements: Dict[str, float],
) -> None:
    """Emit a textual comparison table."""
    rows: Iterable[Tuple[str, str, bool]] = (
        ("Average FPS (higher is better)", "avg_fps", True),
        ("Average QP (lower is better)", "avg_qp", False),
        ("Total Freezes (lower is better)", "total_freezes", False),
        ("Total Undecodable Frames (lower)", "total_undecodable", False),
    )

    print("\n" + "=" * 86)
    print(f"{'QoE Metrics Comparison':^86}")
    print("=" * 86)
    print(f"{'Metric':<40}{base_label:>16}{challenger_label:>16}{'Improvement':>14}")
    print("-" * 86)

    for title, key, higher_better in rows:
        base_value = getattr(base_metrics, key)
        challenger_value = getattr(challenger_metrics, key)
        improvement = improvements[key]
        direction = "↑" if (improvement > 0 and higher_better) or (improvement >= 0 and not higher_better) else "↓"
        print(
            f"{title:<40}"
            f"{base_value:>16.2f}"
            f"{challenger_value:>16.2f}"
            f"{direction} {abs(improvement):>9.2f}%"
        )

    print("=" * 86 + "\n")


def plot_bar_chart(
    base_label: str,
    challenger_label: str,
    base_metrics: MetricSnapshot,
    challenger_metrics: MetricSnapshot,
    output_path: Path,
) -> None:
    """Create a bar chart comparing the four metrics."""
    labels = [
        ("Average FPS", "avg_fps", True),
        ("Average QP", "avg_qp", False),
        ("Total Freezes", "total_freezes", False),
        ("Undecodable Frames", "total_undecodable", False),
    ]

    base_values = [getattr(base_metrics, key) for _, key, _ in labels]
    challenger_values = [getattr(challenger_metrics, key) for _, key, _ in labels]

    x = range(len(labels))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x, base_values, width=0.35, label=base_label, color="#E69F00", edgecolor="black")
    ax.bar(
        [i + 0.35 for i in x],
        challenger_values,
        width=0.35,
        label=challenger_label,
        color="#009E73",
        edgecolor="black",
    )

    ax.set_xticks([i + 0.175 for i in x])
    ax.set_xticklabels([title for title, _, _ in labels])
    ax.set_ylabel("Value")
    ax.set_title("Key QoE Metrics")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend()

    for idx, (base_val, new_val) in enumerate(zip(base_values, challenger_values)):
        ax.text(idx, base_val, f"{base_val:.1f}", ha="center", va="bottom", fontsize=9)
        ax.text(
            idx + 0.35,
            new_val,
            f"{new_val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare QP/FPS/Freeze/Undecodable metrics between two WebRTC runs."
    )
    parser.add_argument("--base-log", required=True, type=Path, help="Receiver log for the baseline (e.g. GoogleCC2).")
    parser.add_argument(
        "--challenger-log", required=True, type=Path, help="Receiver log for the challenger (e.g. Gain2)."
    )
    parser.add_argument("--base-label", default="Baseline", help="Name to show for the baseline configuration.")
    parser.add_argument(
        "--challenger-label", default="Challenger", help="Name to show for the challenger configuration."
    )
    parser.add_argument(
        "--plot",
        type=Path,
        help="Optional path to write a PNG/PDF bar chart highlighting the four metrics.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    base_df = parse_receiver_log(args.base_log)
    challenger_df = parse_receiver_log(args.challenger_log)

    base_metrics = compute_summary(base_df)
    challenger_metrics = compute_summary(challenger_df)
    improvements = compute_improvement(base_metrics, challenger_metrics)

    print_summary_table(
        args.base_label,
        args.challenger_label,
        base_metrics,
        challenger_metrics,
        improvements,
    )

    if args.plot:
        plot_bar_chart(
            args.base_label,
            args.challenger_label,
            base_metrics,
            challenger_metrics,
            args.plot,
        )
        print(f"[*] Bar chart written to {args.plot}")


if __name__ == "__main__":
    main()

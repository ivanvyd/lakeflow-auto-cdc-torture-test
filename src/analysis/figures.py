"""
Generate matplotlib figures from the normalized results.

Run after `make results` (which itself depends on `make test`).
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from src.analysis.branding import brand_image_file
from src.scenario_specs import DISPLAY_NAME_BY_SCENARIO

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
NORM_DIR = RESULTS_DIR / "normalized"
RAW_DIR = RESULTS_DIR / "raw"
FIG_DIR = RESULTS_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

STYLE_PATH = PROJECT_ROOT / "article" / "media" / "visual-system.json"
VISUAL_STYLE = json.loads(STYLE_PATH.read_text(encoding="utf-8"))
PALETTE = {name: entry["hex"] for name, entry in VISUAL_STYLE["palette"].items()}

INK = PALETTE["ink"]
BONE = PALETTE["bone"]
PAPER = PALETTE["paper"]
TEAL = PALETTE["teal"]
VERMILION = PALETTE["vermilion"]
VIOLET = PALETTE["violet"]
OCHRE = PALETTE["ochre"]
MUTED = PALETTE["muted"]
GRID = PALETTE["grid"]

CLASSIFICATION_COLORS = {
    outcome: PALETTE[color_name] for outcome, color_name in VISUAL_STYLE["outcome_mapping"].items()
}

matplotlib.rcParams.update(
    {
        "font.family": [
            VISUAL_STYLE["typography"]["primary"],
            VISUAL_STYLE["typography"]["fallback"],
        ],
        "font.size": 11,
        "axes.titleweight": "bold",
        "axes.titlesize": 20,
        "axes.labelcolor": INK,
        "text.color": INK,
        "figure.facecolor": BONE,
        "axes.facecolor": BONE,
        "savefig.facecolor": BONE,
    }
)


def _load_matrix():
    p = NORM_DIR / "summary_matrix.json"
    if not p.exists():
        print(f"missing {p}; run `make test` first", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def _save(fig: plt.Figure, filename: str) -> Path:
    out = FIG_DIR / filename
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return brand_image_file(out, out)


def _remove_frame(ax: plt.Axes) -> None:
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)


def _target_rows(target_name: str) -> list[dict[str, str | None]]:
    state_path = RAW_DIR / "target_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"missing {state_path}; run `make test` first")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    target = state["after_late_phase"][target_name]
    return [dict(zip(target["columns"], row)) for row in target["rows"]]


def figure_summary_matrix(matrix) -> Path:
    fig, ax = plt.subplots(figsize=(13.5, 7.2))
    fig.subplots_adjust(top=0.78, left=0.035, right=0.98, bottom=0.08)
    _remove_frame(ax)
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 3)
    ax.set_xticks([])
    ax.set_yticks([])

    counts = {
        classification: sum(item["classification"] == classification for item in matrix)
        for classification in CLASSIFICATION_COLORS
    }
    fig.text(
        0.04, 0.94, "18 green runs. Five production interventions.", fontsize=25, weight="bold"
    )
    fig.text(
        0.04,
        0.895,
        "Each tile is one measured AUTO CDC configuration, in scenario order.",
        fontsize=12,
        color=MUTED,
    )

    legend_x = 0.04
    for classification, color in CLASSIFICATION_COLORS.items():
        label = classification.replace("_", " ").title()
        fig.text(
            legend_x,
            0.83,
            f"●  {counts[classification]} {label}",
            color=color,
            fontsize=11,
            weight="bold",
        )
        legend_x += {
            "HANDLED": 0.145,
            "CONFIGURATION_DEPENDENT": 0.235,
            "BUSINESS_SEMANTICS": 0.205,
        }.get(classification, 0.18)

    for index, item in enumerate(matrix):
        row, col = divmod(index, 6)
        x = col + 0.08
        y = 2.02 - row
        display_name = DISPLAY_NAME_BY_SCENARIO[item["scenario"]]
        code, _, label = display_name.partition(" ")
        color = CLASSIFICATION_COLORS[item["classification"]]
        tile = FancyBboxPatch(
            (x, y),
            0.84,
            0.72,
            boxstyle="round,pad=0.02,rounding_size=0.055",
            linewidth=1.4,
            edgecolor=color,
            facecolor=PAPER,
        )
        ax.add_patch(tile)
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                0.11,
                0.72,
                boxstyle="round,pad=0.02,rounding_size=0.055",
                linewidth=0,
                facecolor=color,
            )
        )
        ax.text(x + 0.19, y + 0.46, code, fontsize=15, weight="bold", va="center")
        ax.text(
            x + 0.19,
            y + 0.23,
            textwrap.fill(label, width=20),
            fontsize=7.8,
            color=MUTED,
            va="center",
            linespacing=1.1,
        )

    return _save(fig, "summary_matrix.png")


def figure_scd2_noise(matrix) -> Path | None:
    rows = [m for m in matrix if m["scenario"].startswith("08_")]
    if not rows:
        return None
    counts = [int(r["target_rows"]) for r in rows]
    fig, ax = plt.subplots(figsize=(12.5, 5.8))
    fig.subplots_adjust(top=0.76, left=0.05, right=0.97, bottom=0.12)
    _remove_frame(ax)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])

    fig.text(
        0.055,
        0.92,
        "AUTO CDC recorded 51 versions when SCD2 tracked\nthe sync timestamp",
        fontsize=22,
        weight="bold",
    )
    fig.text(
        0.055,
        0.81,
        "Same source events. One history-tracking decision.",
        fontsize=12,
        color=MUTED,
    )

    left_count, right_count = counts
    left_x = [0.45 + i * 4.25 / max(left_count - 1, 1) for i in range(left_count)]
    ax.vlines(left_x, 0.22, 0.78, color=VERMILION, linewidth=2.1, alpha=0.88)
    ax.vlines([7.5], 0.22, 0.78, color=TEAL, linewidth=8)
    ax.text(2.58, 0.88, str(left_count), ha="center", fontsize=36, weight="bold", color=VERMILION)
    ax.text(7.5, 0.88, str(right_count), ha="center", fontsize=36, weight="bold", color=TEAL)
    ax.text(2.58, 0.08, "TRACK EVERY COLUMN", ha="center", fontsize=12, weight="bold")
    ax.text(
        2.58,
        0.015,
        "operational noise becomes business history",
        ha="center",
        fontsize=10,
        color=MUTED,
    )
    ax.text(7.5, 0.08, "EXCLUDE last_synced_at", ha="center", fontsize=12, weight="bold")
    ax.text(7.5, 0.015, "one business version remains", ha="center", fontsize=10, color=MUTED)

    return _save(fig, "scd2_history_noise.png")


def _bitemporal_rows() -> list[dict[str, str | None]]:
    return _target_rows("s09_bitemporal_tgt")


def _seconds(value: str, origin: datetime) -> float:
    return (datetime.fromisoformat(value.replace("Z", "+00:00")) - origin).total_seconds()


def figure_bitemporal_timeline(matrix) -> Path | None:
    """Draw a system-time timeline for the bitemporal target.

    Each bar comes from a measured target row and shows its system-time
    interval. Hatching marks a corrected belief: its system start differs
    from the source event's ingestion time.
    """
    row = next((m for m in matrix if m["scenario"] == "09_bitemporal"), None)
    if row is None:
        return None
    measured_rows = int(row["target_rows"])
    rows = _bitemporal_rows()
    if len(rows) != measured_rows:
        raise ValueError(
            f"captured bitemporal rows ({len(rows)}) do not match matrix ({measured_rows})"
        )

    valid_starts = [
        datetime.fromisoformat(row["__START_AT"].replace("Z", "+00:00")) for row in rows
    ]
    origin = min(valid_starts)
    starts = [_seconds(row["__SYSTEM_START_AT"], origin) for row in rows]
    open_end = max(starts) + 60

    fig, ax = plt.subplots(figsize=(13, 6.2))
    fig.subplots_adjust(top=0.78, left=0.22, right=0.96, bottom=0.17)
    _remove_frame(ax)
    palette = {"PENDING": OCHRE, "ACTIVE": TEAL, "SUSPENDED": VERMILION}
    ordered = sorted(
        rows,
        key=lambda item: (
            item["__SYSTEM_START_AT"],
            item["__SYSTEM_END_AT"] is None,
            item["status"],
        ),
    )
    for i, r in enumerate(ordered):
        start = _seconds(r["__SYSTEM_START_AT"], origin)
        end = (
            _seconds(r["__SYSTEM_END_AT"], origin) if r["__SYSTEM_END_AT"] is not None else open_end
        )
        color = palette.get(r["status"], "#999")
        is_correction = r["__SYSTEM_START_AT"] != r["ingested_at"]
        ax.barh(
            i,
            end - start,
            left=start,
            color=PAPER if is_correction else color,
            edgecolor=color,
            linewidth=2.8 if is_correction else 0,
            height=0.62,
        )
        label = f"{r['status']}{'  ·  corrected belief' if is_correction else ''}"
        ax.text(
            -8,
            i,
            label,
            va="center",
            ha="right",
            fontsize=10.5,
            weight="bold" if is_correction else "normal",
        )

    for x in (60, 180, 300):
        ax.axvline(x, color=GRID, linewidth=1.2, zorder=0)

    ax.set_yticks([])
    ax.set_xlim(0, 390)
    ax.set_xticks([60, 180, 300])
    ax.set_xticklabels(["arrival 1\n60s", "arrival 2\n180s", "arrival 3\n300s"], color=MUTED)
    ax.set_xlabel("SYSTEM TIME  ·  ingested_at", fontsize=10, weight="bold", labelpad=18)
    ax.invert_yaxis()
    fig.text(
        0.055,
        0.92,
        f"AUTO CDC recorded {measured_rows} beliefs from three source events",
        fontsize=24,
        weight="bold",
    )
    fig.text(
        0.055,
        0.855,
        "Filled bars show original beliefs. Outlined bars preserve later corrections.",
        fontsize=12,
        color=MUTED,
    )
    return _save(fig, "bitemporal_timeline.png")


def figure_wrong_clock(matrix) -> Path | None:
    rows = [m for m in matrix if m["scenario"].startswith("04_")]
    if not rows:
        return None
    statuses = []
    for row in rows:
        target_rows = _target_rows(row["configuration"])
        statuses.append(target_rows[0]["status"] if target_rows else "<empty>")

    fig, ax = plt.subplots(figsize=(12.5, 5.8))
    fig.subplots_adjust(top=0.76, left=0.05, right=0.97, bottom=0.1)
    _remove_frame(ax)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])

    fig.text(
        0.055,
        0.92,
        "Two green pipelines returned different business states",
        fontsize=24,
        weight="bold",
    )
    fig.text(
        0.055,
        0.855,
        "The sequence column defines what ‘latest’ means.",
        fontsize=12,
        color=MUTED,
    )

    cards = [
        (0.35, VERMILION, "ORDER BY ingested_at", statuses[0], "business state missed"),
        (5.25, TEAL, "ORDER BY source_updated_at", statuses[1], "business state matched"),
    ]
    for x, color, heading, status, verdict in cards:
        card = FancyBboxPatch(
            (x, 0.16),
            4.35,
            0.67,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            linewidth=1.4,
            edgecolor=color,
            facecolor=PAPER,
        )
        ax.add_patch(card)
        ax.add_patch(
            FancyBboxPatch(
                (x, 0.16),
                0.12,
                0.67,
                boxstyle="round,pad=0.02,rounding_size=0.06",
                linewidth=0,
                facecolor=color,
            )
        )
        ax.text(x + 0.34, 0.7, heading, fontsize=11, weight="bold")
        ax.text(x + 0.34, 0.42, status, fontsize=28, weight="bold", color=color)
        ax.text(
            x + 0.34,
            0.25,
            f"GREEN PIPELINE  ·  {verdict}",
            fontsize=9.5,
            color=MUTED,
            weight="bold",
        )

    return _save(fig, "wrong_clock.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()  # accept and ignore --profile/--catalog for symmetry with other steps
    matrix = _load_matrix()
    out1 = figure_summary_matrix(matrix)
    out2 = figure_scd2_noise(matrix)
    out3 = figure_wrong_clock(matrix)
    out4 = figure_bitemporal_timeline(matrix)
    written = ", ".join(str(p) for p in (out1, out2, out3, out4) if p is not None)
    print(f"wrote {written}")


if __name__ == "__main__":
    main()

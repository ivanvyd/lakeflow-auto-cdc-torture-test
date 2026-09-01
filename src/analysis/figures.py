"""
Generate matplotlib figures from the normalized results.

Run after `make results` (which itself depends on `make test`).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"
NORM_DIR = RESULTS_DIR / "normalized"
RAW_DIR = RESULTS_DIR / "raw"
FIG_DIR = RESULTS_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_matrix():
    p = NORM_DIR / "summary_matrix.json"
    if not p.exists():
        print(f"missing {p}; run `make test` first", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def figure_summary_matrix(matrix) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6))
    scenarios = [m["scenario"] for m in matrix]
    classifications = [m["classification"] for m in matrix]
    palette = {
        "HANDLED": "#2a9d8f",
        "CONFIGURATION_DEPENDENT": "#e9c46a",
        "BUSINESS_SEMANTICS": "#f4a261",
        "AMBIGUOUS_ORDER": "#8d7fb8",
    }
    colors = [palette.get(c, "#999") for c in classifications]
    ax.barh(scenarios, [1] * len(scenarios), color=colors, edgecolor="black")
    for i, c in enumerate(classifications):
        ax.text(0.01, i, c, va="center", color="black", fontsize=8)
    ax.set_xlabel("Classified outcome")
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Nine AUTO CDC scenario families: 18 measured configurations")
    ax.invert_yaxis()
    plt.tight_layout()
    out = FIG_DIR / "summary_matrix.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def figure_scd2_noise(matrix) -> Path | None:
    rows = [m for m in matrix if m["scenario"].startswith("08_")]
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(7, 4))
    names = [r["configuration"].replace("s08_", "").replace("_scd2_tgt", "") for r in rows]
    counts = [int(r["target_rows"]) for r in rows]
    ax.bar(names, counts, color=["#e76f51", "#2a9d8f"], edgecolor="black")
    for i, c in enumerate(counts):
        ax.text(i, c, str(c), ha="center", va="bottom")
    ax.set_ylabel("SCD2 history rows")
    ax.set_title("Scenario 8: TRACK HISTORY ON * EXCEPT (last_synced_at) suppresses noise")
    plt.tight_layout()
    out = FIG_DIR / "scd2_history_noise.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def _bitemporal_rows() -> list[dict[str, str | None]]:
    state_path = RAW_DIR / "target_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"missing {state_path}; run `make test` first")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    target = state["after_late_phase"]["s09_bitemporal_tgt"]
    return [dict(zip(target["columns"], row)) for row in target["rows"]]


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

    fig, ax = plt.subplots(figsize=(10, 4.8))
    palette = {"PENDING": "#8ecae6", "ACTIVE": "#2a9d8f", "SUSPENDED": "#e76f51"}
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
        hatch = "///" if is_correction else ""
        ax.barh(
            i,
            end - start,
            left=start,
            color=color,
            edgecolor="black",
            linewidth=1,
            hatch=hatch,
        )
        label = f"{r['status']}{' (corrected)' if is_correction else ''}"
        ax.text(end + 6, i, label, va="center", fontsize=9)

    for x in (60, 180, 300):
        ax.axvline(x, color="grey", linestyle=":", linewidth=0.8)

    ax.set_yticks([])
    ax.set_xlim(0, 480)
    ax.set_xticks([60, 180, 300])
    ax.set_xticklabels(["t=60s", "t=180s", "t=300s"])
    ax.set_xlabel("System time (ingested_at)")
    ax.set_title(f"Scenario 9: bitemporal system-time history, {measured_rows} rows from 3 events")
    ax.invert_yaxis()
    plt.tight_layout()
    out = FIG_DIR / "bitemporal_timeline.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def figure_wrong_clock(matrix) -> Path | None:
    rows = [m for m in matrix if m["scenario"].startswith("04_")]
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(7, 4))
    names = ["ingested_at", "source_updated_at"]
    ax.bar(names, [1, 1], color=["#f4a261", "#2a9d8f"], edgecolor="black")
    # Annotate business semantics
    for i, r in enumerate(rows):
        ax.text(
            i,
            0.5,
            r["correct_state"],
            ha="center",
            va="center",
            color="white",
            fontsize=12,
            fontweight="bold",
        )
    ax.set_ylim(0, 1.2)
    ax.set_yticks([])
    ax.set_ylabel("Matches business expectation?")
    ax.set_title("Scenario 4: the wrong clock")
    plt.tight_layout()
    out = FIG_DIR / "wrong_clock.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


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

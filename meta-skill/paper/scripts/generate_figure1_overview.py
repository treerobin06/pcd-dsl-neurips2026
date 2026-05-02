#!/usr/bin/env python3
"""Generate Figure 1: compile-once pipeline overview.

This script intentionally avoids stochastic image generation because Figure 1
contains precise paper claims and must remain editable/reproducible.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.patches import FancyArrowPatch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "figure1_overview.png"


COLORS = {
    "ink": "#17212B",
    "muted": "#5B6673",
    "blue": "#DCEEFF",
    "blue_edge": "#4C84B5",
    "cream": "#FFF4CF",
    "cream_edge": "#BFA45D",
    "green": "#DFF3E6",
    "green_edge": "#4E9B62",
    "purple": "#EEE7FF",
    "purple_edge": "#7F6AC8",
    "gray": "#EEF1F4",
    "gray_edge": "#8A96A3",
    "orange": "#FBE7CC",
    "orange_edge": "#C47B2D",
}


def add_box(
    ax,
    x,
    y,
    w,
    h,
    title,
    body,
    fill,
    edge,
    title_size=18,
    body_size=12,
    lw=2.0,
):
    box = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.035",
        linewidth=lw,
        edgecolor=edge,
        facecolor=fill,
        zorder=2,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h * 0.66,
        title,
        ha="center",
        va="center",
        fontsize=title_size,
        fontweight="bold",
        color=COLORS["ink"],
        zorder=3,
    )
    ax.text(
        x + w / 2,
        y + h * 0.34,
        body,
        ha="center",
        va="center",
        fontsize=body_size,
        color=COLORS["muted"],
        linespacing=1.25,
        zorder=3,
    )
    return box


def arrow(ax, x1, y1, x2, y2, color="#53606E", lw=2.4, style="solid", rad=0.0):
    arr = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="-|>",
        mutation_scale=18,
        linewidth=lw,
        color=color,
        linestyle=style,
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=6,
        shrinkB=6,
        zorder=1,
    )
    ax.add_patch(arr)
    return arr


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "figure.dpi": 220,
            "savefig.dpi": 320,
        }
    )

    fig, ax = plt.subplots(figsize=(15.6, 5.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(
        0.5,
        0.93,
        "Compile-Once Probabilistic Reasoning",
        ha="center",
        va="center",
        fontsize=27,
        fontweight="bold",
        color=COLORS["ink"],
    )
    ax.text(
        0.5,
        0.875,
        "One LLM induction call emits a typed specification; deterministic solvers handle subsequent inference.",
        ha="center",
        va="center",
        fontsize=13.5,
        color=COLORS["muted"],
    )

    y = 0.46
    h = 0.24
    boxes = [
        (0.045, 0.125, "Task Examples", "3-5 labeled\nfamily examples", COLORS["gray"], COLORS["gray_edge"]),
        (0.205, 0.135, "LLM Inductor", "recognize family\nemit schema", COLORS["blue"], COLORS["blue_edge"]),
        (0.375, 0.125, "TaskSpec", "family, state\nobservation, decision", COLORS["cream"], COLORS["cream_edge"]),
        (0.540, 0.135, "Compiler", "typed ops\nmacros/routes", COLORS["blue"], COLORS["blue_edge"]),
        (0.705, 0.135, "Two-Gate Check", "1 code sanity\n2 validation samples", COLORS["purple"], COLORS["purple_edge"]),
        (0.870, 0.110, "Solver", "validated backend\nzero LLM calls", COLORS["green"], COLORS["green_edge"]),
    ]

    for x, w, title, body, fill, edge in boxes:
        add_box(ax, x, y, w, h, title, body, fill, edge)

    centers = [(x + w, y + h / 2, boxes[i + 1][0], y + h / 2) for i, (x, w, *_rest) in enumerate(boxes[:-1])]
    for x1, y1, x2, y2 in centers:
        arrow(ax, x1, y1, x2, y2)

    # Registry/feedback lane.
    add_box(
        ax,
        0.34,
        0.15,
        0.32,
        0.115,
        "Reusable Registry",
        "verified solvers and macros can be reused by later tasks",
        COLORS["orange"],
        COLORS["orange_edge"],
        title_size=15,
        body_size=10.5,
        lw=1.7,
    )
    arrow(ax, 0.88, 0.44, 0.64, 0.265, color=COLORS["orange_edge"], lw=2.0, style="dashed", rad=-0.18)
    arrow(ax, 0.36, 0.265, 0.27, 0.44, color=COLORS["orange_edge"], lw=2.0, style="dashed", rad=-0.20)
    ax.text(
        0.735,
        0.285,
        "persist after verification",
        ha="center",
        va="center",
        fontsize=10.5,
        color=COLORS["orange_edge"],
        fontweight="bold",
    )

    # Scope note.
    note = patches.FancyBboxPatch(
        (0.07, 0.045),
        0.86,
        0.06,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        linewidth=1.1,
        edgecolor="#D1D8E0",
        facecolor="#F7F9FB",
        zorder=0,
    )
    ax.add_patch(note)
    ax.text(
        0.5,
        0.075,
        "Backend exactness is conditional on a valid TaskSpec; natural-language E2E is reported separately.",
        ha="center",
        va="center",
        fontsize=11.2,
        color=COLORS["muted"],
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

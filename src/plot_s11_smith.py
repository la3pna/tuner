#!/usr/bin/env python3
"""
Plot S11 points on a Smith chart from a CSV file.

Input CSV format (as in your file):
  f_hz, x_steps, y_steps, s11_re, s11_im, s21_re, s21_im, s12_re, s12_im, s22_re, s22_im

Behavior:
- Uses S11 from the file (complex reflection coefficient).
- "Hold S22 at 50 ohm" => assumes port 2 is perfectly matched (Γ_L = 0), i.e. S22 is set to 0.
  For plotting S11 itself this doesn't change the points, but it's reflected in the network assumption.

Dependencies: numpy, pandas, matplotlib
Optional: scikit-rf (skrf). If installed, you can switch to skrf plotting (see notes in code).
"""

from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def draw_smith_grid(ax, r_list=None, x_list=None, grid_alpha=0.25, lw=0.8):
    """
    Draw a lightweight impedance Smith chart grid in the Γ-plane.
    This is the classic Z-Smith (normalized impedance) grid.

    Constant resistance circles:
      center = (r/(r+1), 0), radius = 1/(r+1)

    Constant reactance circles:
      center = (1, 1/x), radius = 1/|x|
      (for x != 0)
    """
    if r_list is None:
        r_list = [0, 0.2, 0.5, 1, 2, 5, 10]
    if x_list is None:
        x_list = [-10, -5, -2, -1, -0.5, -0.2, 0.2, 0.5, 1, 2, 5, 10]

    # Unit circle (|Γ|=1)
    t = np.linspace(0, 2*np.pi, 1200)
    ax.plot(np.cos(t), np.sin(t), linewidth=1.2)

    # Horizontal axis
    ax.axhline(0, linewidth=0.8, alpha=0.8)

    # Resistance circles
    for r in r_list:
        c = r / (r + 1.0)
        rad = 1.0 / (r + 1.0)
        x = c + rad * np.cos(t)
        y = 0 + rad * np.sin(t)
        # Only keep parts inside unit circle numerically
        mask = (x*x + y*y) <= 1.0000001
        ax.plot(x[mask], y[mask], alpha=grid_alpha, linewidth=lw)

    # Reactance circles (upper and lower halves via sign of x)
    for xval in x_list:
        if xval == 0:
            continue
        cy = 1.0 / xval
        cx = 1.0
        rad = 1.0 / abs(xval)
        x = cx + rad * np.cos(t)
        y = cy + rad * np.sin(t)
        mask = (x*x + y*y) <= 1.0000001
        ax.plot(x[mask], y[mask], alpha=grid_alpha, linewidth=lw)

    ax.set_aspect('equal', adjustable='box')
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("Re(Γ)")
    ax.set_ylabel("Im(Γ)")
    ax.set_title("Smith chart (Γ-plane)")

    # Hide box spines for a cleaner look
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([-1, -0.5, 0, 0.5, 1])
    ax.set_yticks([-1, -0.5, 0, 0.5, 1])


def main():
    ap = argparse.ArgumentParser(description="Plot S11 points on a Smith chart from CSV.")
    ap.add_argument("csv", type=Path, help="Input CSV file (e.g. f_1000MHz.csv)")
    ap.add_argument("--out", type=Path, default=None, help="Optional output image (PNG/SVG/PDF)")
    ap.add_argument("--show", action="store_true", help="Show interactive window")
    ap.add_argument("--color-by", choices=["none", "x_steps", "y_steps"], default="y_steps",
                    help="Color points by a column (default: y_steps)")
    ap.add_argument("--title", default=None, help="Plot title override")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)

    required = {"s11_re", "s11_im"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing required columns: {sorted(missing)}")

    gamma = df["s11_re"].to_numpy(dtype=float) + 1j * df["s11_im"].to_numpy(dtype=float)

    # "Hold S22 at 50 ohm" => matched port 2 => Γ = 0 at port 2.
    # If you later compute loaded input reflection, that assumption matters.
    # For this plot we simply plot measured/recorded S11 points.
    s22_assumed = 0.0 + 0.0j  # noqa: F841

    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    draw_smith_grid(ax)

    # Color mapping
    if args.color_by == "none":
        c = None
    else:
        if args.color_by not in df.columns:
            raise SystemExit(f"--color-by {args.color_by} requested, but column not present in CSV.")
        c = df[args.color_by].to_numpy()

    sc = ax.scatter(np.real(gamma), np.imag(gamma), s=45, c=c)

    if c is not None:
        cb = fig.colorbar(sc, ax=ax, shrink=0.85)
        cb.set_label(args.color_by)

    # Title
    if args.title:
        ax.set_title(args.title)
    else:
        # If the file contains a single frequency, include it
        if "f_hz" in df.columns and df["f_hz"].nunique() == 1:
            f = float(df["f_hz"].iloc[0])
            ax.set_title(f"S11 on Smith chart (f = {f/1e6:.3f} MHz)")
        else:
            ax.set_title("S11 on Smith chart")

    fig.tight_layout()

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.out, dpi=200)

    if args.show or not args.out:
        plt.show()


if __name__ == "__main__":
    main()

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def gamma_to_z(gamma: np.ndarray, z0: float = 50.0) -> np.ndarray:
    return z0 * (1 + gamma) / (1 - gamma)


def monotonic_chain(points):
    """Convex hull for 2D points. Returns hull vertices in order."""
    pts = sorted(set(points))
    if len(pts) <= 1:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


def draw_smith_grid(ax):
    """Simple Smith chart grid drawn in the Γ-plane."""
    theta = np.linspace(0, 2 * np.pi, 1000)
    ax.plot(np.cos(theta), np.sin(theta), linewidth=1.2)

    # Real axis
    ax.axhline(0, linewidth=0.8)
    ax.axvline(0, linewidth=0.8)

    # Constant resistance circles
    r_list = [0, 0.2, 0.5, 1, 2, 5]
    x_sweep = np.linspace(-20, 20, 3000)
    for r in r_list:
        z = r + 1j * x_sweep
        g = (z - 1) / (z + 1)
        mask = np.abs(g) <= 1.001
        ax.plot(g.real[mask], g.imag[mask], linewidth=0.5)

    # Constant reactance arcs
    x_list = [0.2, 0.5, 1, 2, 5]
    r_sweep = np.linspace(0, 20, 3000)
    for x in x_list:
        for sign in (+1, -1):
            z = r_sweep + 1j * sign * x
            g = (z - 1) / (z + 1)
            mask = np.abs(g) <= 1.001
            ax.plot(g.real[mask], g.imag[mask], linewidth=0.5)

    ax.set_aspect("equal", "box")
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("Re(Γ)")
    ax.set_ylabel("Im(Γ)")


def s_complex(df: pd.DataFrame, prefix: str) -> np.ndarray:
    return df[f"{prefix}_re"].to_numpy() + 1j * df[f"{prefix}_im"].to_numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="Calibration CSV, e.g. f_1000MHz.csv")
    ap.add_argument("--sparam", default="s22", choices=["s11", "s22"],
                    help="Which reflection coefficient to plot. Use s22 for tuner output plane, s11 for port-1 view.")
    ap.add_argument("--z0", type=float, default=50.0, help="Reference impedance")
    ap.add_argument("--out", default="", help="Optional output PNG")
    ap.add_argument("--annotate-extremes", action="store_true",
                    help="Annotate min/max |Γ| points")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    df = pd.read_csv(csv_path)

    gamma = s_complex(df, args.sparam.lower())
    s21 = s_complex(df, "s21")
    s21_db = 20 * np.log10(np.maximum(np.abs(s21), 1e-15))

    # Convert Γ to impedance
    z = gamma_to_z(gamma, z0=args.z0)
    r = np.real(z)
    x = np.imag(z)
    mag = np.abs(gamma)

    # Convex hull of points in Γ-plane
    pts = list(zip(np.real(gamma), np.imag(gamma)))
    hull = monotonic_chain(pts)

    # Stats
    idx_min_mag = int(np.argmin(mag))
    idx_max_mag = int(np.argmax(mag))
    idx_min_r = int(np.argmin(r))
    idx_max_r = int(np.argmax(r))
    idx_min_x = int(np.argmin(x))
    idx_max_x = int(np.argmax(x))

    print(f"CSV file: {csv_path}")
    print(f"Number of points: {len(df)}")
    print(f"Using reflection coefficient: {args.sparam.upper()}")
    print()
    print(f"Min |Γ| = {mag[idx_min_mag]:.4f} at x={int(df.iloc[idx_min_mag]['x_steps'])}, y={int(df.iloc[idx_min_mag]['y_steps'])}")
    print(f"Max |Γ| = {mag[idx_max_mag]:.4f} at x={int(df.iloc[idx_max_mag]['x_steps'])}, y={int(df.iloc[idx_max_mag]['y_steps'])}")
    print()
    print(f"Min R = {r[idx_min_r]:.3f} Ω at x={int(df.iloc[idx_min_r]['x_steps'])}, y={int(df.iloc[idx_min_r]['y_steps'])}")
    print(f"Max R = {r[idx_max_r]:.3f} Ω at x={int(df.iloc[idx_max_r]['x_steps'])}, y={int(df.iloc[idx_max_r]['y_steps'])}")
    print(f"Min X = {x[idx_min_x]:.3f} Ω at x={int(df.iloc[idx_min_x]['x_steps'])}, y={int(df.iloc[idx_min_x]['y_steps'])}")
    print(f"Max X = {x[idx_max_x]:.3f} Ω at x={int(df.iloc[idx_max_x]['x_steps'])}, y={int(df.iloc[idx_max_x]['y_steps'])}")

    # Plot 1: Smith chart with points and hull
    fig, ax = plt.subplots(figsize=(8, 8))
    draw_smith_grid(ax)

    sc = ax.scatter(
        np.real(gamma),
        np.imag(gamma),
        c=s21_db,
        s=18
    )
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("S21 (dB)")

    if len(hull) >= 2:
        hull_xy = np.array(hull + [hull[0]])
        ax.plot(hull_xy[:, 0], hull_xy[:, 1], linewidth=1.5)

    if args.annotate_extremes:
        for idx, label in [
            (idx_min_mag, "min |Γ|"),
            (idx_max_mag, "max |Γ|"),
            (idx_min_r, "min R"),
            (idx_max_r, "max R"),
        ]:
            ax.plot(np.real(gamma[idx]), np.imag(gamma[idx]), "o")
            ax.text(np.real(gamma[idx]), np.imag(gamma[idx]), f" {label}", fontsize=8)

    ax.set_title(f"Tuner coverage from {csv_path.name} using {args.sparam.upper()}")

    # Plot 2: X/Y coverage colored by |Γ|
    fig2, ax2 = plt.subplots(figsize=(8, 6))
    sc2 = ax2.scatter(df["x_steps"], df["y_steps"], c=mag, s=18)
    cbar2 = plt.colorbar(sc2, ax=ax2)
    cbar2.set_label("|Γ|")
    ax2.set_xlabel("x_steps")
    ax2.set_ylabel("y_steps")
    ax2.set_title(f"State coverage from {csv_path.name}")

    plt.tight_layout()

    if args.out:
        out = Path(args.out)
        fig.savefig(out, dpi=200, bbox_inches="tight")
        fig2.savefig(out.with_stem(out.stem + "_xy"), dpi=200, bbox_inches="tight")
        print()
        print(f"Saved Smith plot to: {out}")
        print(f"Saved XY plot to:    {out.with_stem(out.stem + '_xy')}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
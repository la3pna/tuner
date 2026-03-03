#!/usr/bin/env python3
# gen_calstates.py
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import List, Tuple

def linspace_int(a: int, b: int, n: int) -> List[int]:
    if n <= 1:
        return [int(round((a + b) / 2))]
    out = []
    for i in range(n):
        t = i / (n - 1)
        out.append(int(round(a + (b - a) * t)))
    seen = set()
    uniq = []
    for v in out:
        if v not in seen:
            uniq.append(v)
            seen.add(v)
    return uniq

def y_schedule_symmetric_edges(y_min: int, y_max: int, ny: int, edge_power: float) -> List[int]:
    if ny <= 1:
        return [int(round((y_min + y_max) / 2))]
    ys = []
    for i in range(ny):
        u = i / (ny - 1)
        base = 0.5 * (1.0 - math.cos(math.pi * u))
        base = base ** float(edge_power)
        y = y_min + (y_max - y_min) * base
        ys.append(int(round(y)))
    seen = set()
    uniq = []
    for v in ys:
        if v not in seen:
            uniq.append(v)
            seen.add(v)
    return uniq

def build_states(xs: List[int], ys: List[int], serpentine: bool) -> List[Tuple[int, int]]:
    states: List[Tuple[int, int]] = []
    if not serpentine:
        for x in xs:
            for y in ys:
                states.append((x, y))
        return states
    for idx, x in enumerate(xs):
        if idx % 2 == 0:
            for y in ys:
                states.append((x, y))
        else:
            for y in reversed(ys):
                states.append((x, y))
    return states

def add_sanity_points(states: List[Tuple[int, int]], x_min: int, x_max: int, y_min: int, y_max: int) -> List[Tuple[int, int]]:
    sanity = [
        (x_min, y_min),
        (x_min, y_max),
        (x_max, y_min),
        (x_max, y_max),
        (int(round((x_min + x_max) / 2)), int(round((y_min + y_max) / 2))),
    ]
    out = []
    seen = set()
    for p in sanity + states:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out

def write_states_csv(path: Path, states: List[Tuple[int,int]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x_steps", "y_steps"])
        w.writerows(states)

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate tuner calibration states CSV (X,Y absolute steps).")
    ap.add_argument("--xmax", type=int, required=True)
    ap.add_argument("--ymax", type=int, required=True)
    ap.add_argument("--xmin", type=int, default=0)
    ap.add_argument("--ymin", type=int, default=0)
    ap.add_argument("--nx", type=int, default=80)
    ap.add_argument("--ny", type=int, default=14)
    ap.add_argument("--x-margin", type=int, default=0)
    ap.add_argument("--y-margin", type=int, default=0)
    ap.add_argument("--y-edge-power", type=float, default=1.6)
    ap.add_argument("--serpentine", action="store_true")
    ap.add_argument("--sanity", action="store_true")
    ap.add_argument("--out", default="states.csv")
    args = ap.parse_args()

    x_min = int(args.xmin) + int(args.x_margin)
    x_max = int(args.xmax) - int(args.x_margin)
    y_min = int(args.ymin) + int(args.y_margin)
    y_max = int(args.ymax) - int(args.y_margin)

    if x_max <= x_min:
        raise SystemExit("X range invalid after margins.")
    if y_max <= y_min:
        raise SystemExit("Y range invalid after margins.")

    xs = linspace_int(x_min, x_max, int(args.nx))
    ys = y_schedule_symmetric_edges(y_min, y_max, int(args.ny), float(args.y_edge_power))

    states = build_states(xs, ys, serpentine=bool(args.serpentine))
    if args.sanity:
        states = add_sanity_points(states, x_min, x_max, y_min, y_max)

    out_path = Path(args.out)
    write_states_csv(out_path, states)
    print(f"Wrote {out_path} with {len(states)} states (nx={len(xs)}, ny={len(ys)}).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

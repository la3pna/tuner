from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
import math


@dataclass
class PickResult:
    x: int
    y: int
    gamma: complex
    err: float
    il_db: float


def z_to_gamma(z: complex, z0: float = 50.0) -> complex:
    return (z - z0) / (z + z0)


def il_db_from_s21(s21: complex) -> float:
    mag = abs(s21)
    if mag <= 0.0:
        return float("-inf")
    return 20.0 * math.log10(mag)


def _row_gamma(row) -> complex:
    return complex(float(row.s22.real), float(row.s22.imag)) if hasattr(row, "s22") else complex(float(row.s22_re), float(row.s22_im))


def _row_s21(row) -> complex:
    return complex(float(row.s21.real), float(row.s21.imag)) if hasattr(row, "s21") else complex(float(row.s21_re), float(row.s21_im))


def pick_state(
    rows: Iterable,
    gamma_target: complex,
    select: str = "topn_min_il",
    top_n: int = 30,
    alpha: float = 0.02,
    current_x: Optional[int] = None,
    current_y: Optional[int] = None,
    x_move_weight: float = 0.0,
    y_move_weight: float = 0.0,
) -> PickResult:
    """Pick the best tuner state.

    Base metric:
      gamma_err = |gamma - gamma_target|

    Optional motion bias:
      cost = gamma_err + x_move_weight*|dx| + y_move_weight*|dy|

    Notes:
    - x_move_weight/y_move_weight are in "gamma error per step".
    - Set x_move_weight > y_move_weight when X is slower than Y.
    - If current_x/current_y are omitted, motion bias is disabled.
    """
    scored = []

    for row in rows:
        gamma = _row_gamma(row)
        s21 = _row_s21(row)
        gamma_err = abs(gamma - gamma_target)

        motion_cost = 0.0
        if current_x is not None:
            motion_cost += float(x_move_weight) * abs(int(row.x) - int(current_x) if hasattr(row, "x") else int(row.x_steps) - int(current_x))
        if current_y is not None:
            motion_cost += float(y_move_weight) * abs(int(row.y) - int(current_y) if hasattr(row, "y") else int(row.y_steps) - int(current_y))

        cost = gamma_err + motion_cost
        il_db = il_db_from_s21(s21)

        x = int(row.x) if hasattr(row, "x") else int(row.x_steps)
        y = int(row.y) if hasattr(row, "y") else int(row.y_steps)

        scored.append((cost, gamma_err, il_db, x, y, gamma))

    if not scored:
        raise ValueError("No calibration rows available")

    select = (select or "topn_min_il").lower()

    if select == "nearest":
        scored.sort(key=lambda t: t[0])
        cost, gamma_err, il_db, x, y, gamma = scored[0]
        return PickResult(x=x, y=y, gamma=gamma, err=gamma_err, il_db=il_db)

    # Default: take top-N by cost, then prefer best IL among near-equals.
    scored.sort(key=lambda t: t[0])
    n = max(1, min(int(top_n), len(scored)))
    pool = scored[:n]

    best_cost = pool[0][0]
    threshold = best_cost + float(alpha)

    near = [t for t in pool if t[0] <= threshold]
    # il_db is S21 in dB; larger is better (less loss).
    near.sort(key=lambda t: (-t[2], t[0]))

    cost, gamma_err, il_db, x, y, gamma = near[0]
    return PickResult(x=x, y=y, gamma=gamma, err=gamma_err, il_db=il_db)

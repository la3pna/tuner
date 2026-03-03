from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple
from calibration_store import CalRow

def z_to_gamma(z: complex, z0: float = 50.0) -> complex:
    return (z - z0) / (z + z0)

def il_db_from_s21(s21: complex) -> float:
    mag = abs(s21)
    if mag <= 1e-15:
        return 300.0
    return -20.0 * math.log10(mag)

@dataclass
class PickResult:
    x: int
    y: int
    gamma: complex
    il_db: float
    err: float

def pick_state(rows: List[CalRow], gamma_target: complex,
              select: str = "topn_min_il", top_n: int = 30, alpha: float = 0.02) -> PickResult:
    scored: List[Tuple[float, float, CalRow]] = []
    for r in rows:
        gamma = r.s22
        err = abs(gamma - gamma_target)
        il_db = il_db_from_s21(r.s21)
        scored.append((err, il_db, r))

    scored.sort(key=lambda t: t[0])

    if select == "topn_min_il":
        subset = scored[:max(1, int(top_n))]
        subset.sort(key=lambda t: t[1])
        err, il_db, r = subset[0]
        return PickResult(r.x, r.y, r.s22, il_db, err)

    best: Optional[Tuple[float, float, float, CalRow]] = None
    for err, il_db, r in scored:
        J = err + alpha * il_db
        if best is None or J < best[0]:
            best = (J, err, il_db, r)
    assert best is not None
    _, err, il_db, r = best
    return PickResult(r.x, r.y, r.s22, il_db, err)

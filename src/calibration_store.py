from __future__ import annotations
import csv, os
from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass(frozen=True)
class CalRow:
    x: int
    y: int
    s11: complex
    s21: complex
    s12: complex
    s22: complex

class CalibrationStore:
    def __init__(self, cal_dir: str = "cal"):
        self.cal_dir = cal_dir
        os.makedirs(self.cal_dir, exist_ok=True)
        self._cache: Dict[int, List[CalRow]] = {}

    def _path_for_freq(self, f_hz: float) -> str:
        mhz = int(round(f_hz / 1e6))
        return os.path.join(self.cal_dir, f"f_{mhz:04d}MHz.csv")

    def load_freq(self, f_hz: float) -> Tuple[str, List[CalRow]]:
        mhz = int(round(f_hz / 1e6))
        if mhz in self._cache:
            return self._path_for_freq(f_hz), self._cache[mhz]

        path = self._path_for_freq(f_hz)
        if not os.path.exists(path):
            raise FileNotFoundError(path)

        rows: List[CalRow] = []
        with open(path, "r", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                rows.append(CalRow(
                    x=int(row["x_steps"]),
                    y=int(row["y_steps"]),
                    s11=complex(float(row["s11_re"]), float(row["s11_im"])),
                    s21=complex(float(row["s21_re"]), float(row["s21_im"])),
                    s12=complex(float(row["s12_re"]), float(row["s12_im"])),
                    s22=complex(float(row["s22_re"]), float(row["s22_im"]))
                ))

        self._cache[mhz] = rows
        return path, rows

    def save_freq(self, f_hz: float, rows: List[CalRow]) -> str:
        path = self._path_for_freq(f_hz)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "f_hz","x_steps","y_steps",
                "s11_re","s11_im","s21_re","s21_im",
                "s12_re","s12_im","s22_re","s22_im"
            ])
            for r in rows:
                w.writerow([
                    float(f_hz), r.x, r.y,
                    r.s11.real, r.s11.imag,
                    r.s21.real, r.s21.imag,
                    r.s12.real, r.s12.imag,
                    r.s22.real, r.s22.imag
                ])
        mhz = int(round(f_hz / 1e6))
        self._cache[mhz] = rows
        return path

    def clear_cache(self):
        self._cache.clear()

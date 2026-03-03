from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
from libreVNA import libreVNA

from measure_one_point_via_scpi_trace_v4 import (
    _scpi_cmd, _scpi_query, _require_calibration_active, _wait_sweep_done, _get_point_near
)

@dataclass
class VnaConfig:
    host: str = "127.0.0.1"
    port: int = 19542
    power_dbm: float = -10.0
    ifbw_hz: float = 10_000.0
    avg: int = 1
    span_hz: float = 400_000.0
    points: int = 2
    sweep_timeout_s: float = 8.0

class VnaBackend:
    def __init__(self, cfg: VnaConfig):
        self.cfg = cfg
        self.vna = libreVNA(cfg.host, cfg.port, check_cmds=False, timeout=1)

    def idn(self) -> str:
        return _scpi_query(self.vna, "*IDN?", timeout=1.0) or ""

    def measure_s2p_near(self, freq_hz: float) -> Tuple[float, complex, complex, complex, complex]:
        target = float(freq_hz)
        span = max(0.0, float(self.cfg.span_hz))
        start_hz = max(0.0, target - span / 2.0)
        stop_hz = target + span / 2.0

        _scpi_cmd(self.vna, ":DEV:MODE VNA")
        _scpi_cmd(self.vna, ":VNA:SWEEP FREQUENCY")
        _scpi_cmd(self.vna, f":VNA:STIM:LVL {self.cfg.power_dbm}")
        _scpi_cmd(self.vna, f":VNA:ACQ:IFBW {self.cfg.ifbw_hz}")
        _scpi_cmd(self.vna, f":VNA:ACQ:AVG {int(self.cfg.avg)}")
        _scpi_cmd(self.vna, f":VNA:ACQ:POINTS {int(self.cfg.points)}")
        _scpi_cmd(self.vna, f":VNA:FREQuency:START {start_hz}")
        _scpi_cmd(self.vna, f":VNA:FREQuency:STOP {stop_hz}")

        _require_calibration_active(self.vna)
        _wait_sweep_done(self.vna, timeout_s=float(self.cfg.sweep_timeout_s))

        f11, s11, _ = _get_point_near(self.vna, "S11", target, start_hz, stop_hz)
        f21, s21, _ = _get_point_near(self.vna, "S21", target, start_hz, stop_hz)
        f12, s12, _ = _get_point_near(self.vna, "S12", target, start_hz, stop_hz)
        f22, s22, _ = _get_point_near(self.vna, "S22", target, start_hz, stop_hz)
        return float(f11), complex(s11), complex(s21), complex(s12), complex(s22)

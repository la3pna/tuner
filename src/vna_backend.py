# vna_backend.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from vna_scpi import ScpiClient, ScpiConfig, wait_opc


@dataclass
class VnaConfig:
    host: str = "127.0.0.1"
    port: int = 19542
    timeout_s: float = 2.0

    power_dbm: float = -10.0
    ifbw_hz: float = 10000.0
    avg: int = 1

    single_point: bool = True
    span_hz: float = 200000.0
    points: int = 2

    sweep_timeout_s: float = 8.0


class VnaBackend:
    def __init__(self, cfg: VnaConfig):
        self.cfg = cfg
        self.scpi = ScpiClient(ScpiConfig(cfg.host, cfg.port, cfg.timeout_s))

    def idn(self) -> str:
        try:
            return self.scpi.idn()
        except Exception:
            return ""

    def close(self):
        self.scpi.close()

    def _setup_sweep(self, f_hz: float):
        c = self.scpi
        c.write(":DEV:MODE VNA")
        c.write(":VNA:SWEEP FREQUENCY")
        c.write(f":VNA:STIM:LVL {self.cfg.power_dbm}")
        c.write(f":VNA:ACQ:IFBW {self.cfg.ifbw_hz}")
        c.write(f":VNA:ACQ:AVG {int(self.cfg.avg)}")

        if self.cfg.single_point:
            c.write(":VNA:ACQ:POINTS 1")
            c.write(f":VNA:FREQuency:START {float(f_hz)}")
            c.write(f":VNA:FREQuency:STOP {float(f_hz)}")
        else:
            span = float(self.cfg.span_hz)
            start = max(0.0, float(f_hz) - span / 2.0)
            stop = float(f_hz) + span / 2.0
            pts = max(2, int(self.cfg.points))
            c.write(f":VNA:ACQ:POINTS {pts}")
            c.write(f":VNA:FREQuency:START {start}")
            c.write(f":VNA:FREQuency:STOP {stop}")

    def _trigger_and_wait(self):
        wait_opc(self.scpi, timeout_s=float(self.cfg.sweep_timeout_s))

    def _read_trace(self, name: str) -> complex:
        resp = self.scpi.query(f":VNA:TRACE:DATA? {name}")
        pts = ScpiClient.parse_complex_pairs(resp)
        if not pts:
            raise RuntimeError(f"No trace data returned for {name}: '{resp[:120]}'")
        return pts[0]

    def measure_s2p(self, f_hz: float) -> Tuple[float, complex, complex, complex, complex]:
        self._setup_sweep(float(f_hz))
        self._trigger_and_wait()

        s11 = self._read_trace("S11")
        s21 = self._read_trace("S21")
        s12 = self._read_trace("S12")
        s22 = self._read_trace("S22")

        return float(f_hz), s11, s21, s12, s22

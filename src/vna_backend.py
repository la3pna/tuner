
from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from vna_scpi import ScpiClient, ScpiConfig, wait_opc


@dataclass
class VnaConfig:
    host: str = "127.0.0.1"
    port: int = 19542
    timeout_s: float = 2.0

    trace_port: int = 19001
    trace_timeout_s: float = 3.0

    power_dbm: float = -10.0
    ifbw_hz: float = 10000.0
    avg: int = 1

    single_point: bool = False
    span_hz: float = 400000.0
    points: int = 2

    sweep_timeout_s: float = 8.0


class _TraceStream:
    """Reads LibreVNA JSON trace lines from port 19001/19002."""

    def __init__(self, host: str, port: int, timeout_s: float):
        self.host = host
        self.port = int(port)
        self.timeout_s = float(timeout_s)
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
        self.sock.settimeout(self.timeout_s)
        self.buf = b""

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

    def _readline(self) -> Optional[str]:
        while b"\n" not in self.buf:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                return None
            if not chunk:
                return None
            self.buf += chunk

        line, self.buf = self.buf.split(b"\n", 1)
        return line.decode("utf-8", errors="ignore").strip()

    def read_json(self, timeout_s: float) -> Optional[dict]:
        end = time.time() + timeout_s
        while time.time() < end:
            line = self._readline()
            if not line:
                continue
            try:
                return json.loads(line)
            except Exception:
                continue
        return None

    def drain(self, seconds: float = 0.2):
        end = time.time() + seconds
        while time.time() < end:
            try:
                self.sock.settimeout(0.05)
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self.buf += chunk
                while b"\n" in self.buf:
                    _, self.buf = self.buf.split(b"\n", 1)
            except Exception:
                break
        self.sock.settimeout(self.timeout_s)


class VnaBackend:
    """LibreVNA backend using SCPI + JSON trace stream."""

    def __init__(self, cfg: VnaConfig):
        self.cfg = cfg
        self.scpi = ScpiClient(ScpiConfig(cfg.host, cfg.port, cfg.timeout_s))

    def close(self):
        self.scpi.close()

    def idn(self) -> str:
        try:
            return self.scpi.idn()
        except Exception:
            return ""

    def _setup(self, f_hz: float):
        c = self.scpi
        c.write(":DEV:MODE VNA")
        c.write(":VNA:SWEEP FREQUENCY")
        c.write(f":VNA:STIM:LVL {self.cfg.power_dbm}")
        c.write(f":VNA:ACQ:IFBW {self.cfg.ifbw_hz}")
        c.write(f":VNA:ACQ:AVG {self.cfg.avg}")

        if self.cfg.single_point:
            c.write(":VNA:ACQ:POINTS 1")
            c.write(f":VNA:FREQ:START {f_hz}")
            c.write(f":VNA:FREQ:STOP {f_hz}")
        else:
            span = self.cfg.span_hz
            start = f_hz - span / 2
            stop = f_hz + span / 2
            c.write(f":VNA:ACQ:POINTS {self.cfg.points}")
            c.write(f":VNA:FREQ:START {start}")
            c.write(f":VNA:FREQ:STOP {stop}")

    @staticmethod
    def _extract_complex(j: dict, key: str) -> complex:
        m = j["measurements"]
        return complex(m[f"{key}_real"], m[f"{key}_imag"])

    def measure_s2p(self, f_hz: float) -> Tuple[float, complex, complex, complex, complex]:
        self._setup(f_hz)

        wait_opc(self.scpi, timeout_s=self.cfg.sweep_timeout_s)

        pts = 1 if self.cfg.single_point else max(2, self.cfg.points)

        ts = _TraceStream(self.cfg.host, self.cfg.trace_port, self.cfg.trace_timeout_s)
        try:
            ts.drain(0.3)

            got: Dict[int, dict] = {}
            deadline = time.time() + self.cfg.sweep_timeout_s + 2

            while time.time() < deadline:
                j = ts.read_json(0.5)
                if not j:
                    continue

                pn = j.get("pointNum")
                if pn is None:
                    continue

                pn = int(pn)
                if pn == 0:
                    got = {}

                got[pn] = j

                if len(got) >= pts:
                    break

            if len(got) < pts:
                raise RuntimeError(f"Trace stream incomplete ({len(got)}/{pts})")

            best = None
            best_df = None

            for j in got.values():
                f = float(j["frequency"])
                df = abs(f - f_hz)

                if best_df is None or df < best_df:
                    best_df = df
                    best = j

            picked_f = float(best["frequency"])

            s11 = self._extract_complex(best, "S11")
            s21 = self._extract_complex(best, "S21")
            s12 = self._extract_complex(best, "S12")
            s22 = self._extract_complex(best, "S22")

            return picked_f, s11, s21, s12, s22

        finally:
            ts.close()

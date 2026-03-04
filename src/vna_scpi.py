# vna_scpi.py
from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import List


@dataclass
class ScpiConfig:
    host: str = "127.0.0.1"
    port: int = 19542
    timeout_s: float = 2.0


class ScpiClient:
    """Minimal SCPI-over-TCP client (LF terminated)."""

    def __init__(self, cfg: ScpiConfig):
        self.cfg = cfg
        self.sock = socket.create_connection((cfg.host, cfg.port), timeout=cfg.timeout_s)
        self.sock.settimeout(cfg.timeout_s)
        self._rx = b""

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

    def write(self, cmd: str) -> None:
        self.sock.sendall((cmd.strip() + "\n").encode("utf-8", errors="ignore"))

    def _readline(self) -> str:
        while b"\n" not in self._rx:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            self._rx += chunk
        if b"\n" in self._rx:
            line, self._rx = self._rx.split(b"\n", 1)
        else:
            line, self._rx = self._rx, b""
        return line.decode("utf-8", errors="ignore").strip()

    def query(self, cmd: str) -> str:
        self.write(cmd)
        return self._readline()

    def idn(self) -> str:
        return self.query("*IDN?")

    @staticmethod
    def parse_float_list(s: str) -> List[float]:
        s = s.replace(";", ",").replace("\t", ",").replace(" ", ",")
        parts = [p for p in s.split(",") if p.strip() != ""]
        out: List[float] = []
        for p in parts:
            try:
                out.append(float(p))
            except ValueError:
                pass
        return out

    @staticmethod
    def parse_complex_pairs(s: str) -> List[complex]:
        vals = ScpiClient.parse_float_list(s)
        out: List[complex] = []
        for i in range(0, len(vals) - 1, 2):
            out.append(complex(vals[i], vals[i + 1]))
        return out


def wait_opc(scpi: ScpiClient, timeout_s: float = 8.0, poll_s: float = 0.05) -> None:
    t0 = time.time()
    while True:
        if time.time() - t0 > timeout_s:
            raise TimeoutError("Timeout waiting for *OPC?")
        try:
            ans = scpi.query("*OPC?")
            if ans.strip() == "1":
                return
        except Exception:
            pass
        time.sleep(poll_s)

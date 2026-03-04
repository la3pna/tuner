from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Optional

try:
    import serial  # pyserial
except ImportError:
    serial = None


@dataclass
class TunerConfig:
    mode: str                 # "tcp" or "serial"
    host: str = "127.0.0.1"
    port: int = 12001
    com: str = "COM6"
    baud: int = 115200

    # You confirmed LF works in your serial terminal.
    eol: str = "\n"

    # Per-read timeout (each readline call).
    io_timeout_s: float = 0.25

    # How long to wait for "OK" for motion commands (home/goto).
    motion_ok_timeout_s: float = 180.0  # long enough for full travel + homing

    # How long to wait for replies for queries (POS?/STAT?/IDN).
    query_timeout_s: float = 2.0


class TunerBackend:
    """
    Behavior (per your latest confirmation):
      - For :MOT:HOME:* and :MOT:*:GOTO, firmware returns 'OK' ONLY when motion is finished.
      - Therefore we must wait long enough for the OK line.

    We implement:
      - cmd_ok_motion(): wait up to motion_ok_timeout_s for OK
      - query(): wait up to query_timeout_s for a non-empty line
      - Verified GOTO: after OK, read POS? and retry once if mismatch
    """

    def __init__(self, cfg: TunerConfig):
        self.cfg = cfg
        self._sock: Optional[socket.socket] = None
        self._fh = None
        self._ser = None
        self.connect()

    def connect(self):
        self.close()
        if self.cfg.mode == "tcp":
            self._sock = socket.create_connection((self.cfg.host, self.cfg.port), timeout=self.cfg.query_timeout_s)
            self._sock.settimeout(self.cfg.io_timeout_s)
            self._fh = self._sock.makefile("rwb", buffering=0)
        elif self.cfg.mode == "serial":
            if serial is None:
                raise RuntimeError("pyserial not installed (pip install pyserial)")
            self._ser = serial.Serial(self.cfg.com, baudrate=self.cfg.baud, timeout=self.cfg.io_timeout_s)
        else:
            raise ValueError("mode must be tcp or serial")

        self.flush_input()

    def close(self):
        try:
            if self._fh:
                self._fh.close()
        except Exception:
            pass
        self._fh = None
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        self._sock = None
        try:
            if self._ser:
                self._ser.close()
        except Exception:
            pass
        self._ser = None

    # ---------- IO helpers ----------
    def flush_input(self):
        try:
            if self._ser:
                self._ser.reset_input_buffer()
        except Exception:
            pass

    def _write_line(self, line: str):
        data = (line.strip() + self.cfg.eol).encode("ascii", errors="ignore")
        if self._fh:
            self._fh.write(data)
        elif self._ser:
            self._ser.write(data)
        else:
            raise RuntimeError("Transport not open")

    def _read_line_once(self) -> str:
        if self._fh:
            return self._fh.readline().decode(errors="ignore").strip()
        if self._ser:
            return self._ser.readline().decode(errors="ignore").strip()
        raise RuntimeError("Transport not open")

    def _read_nonempty_until(self, timeout_s: float) -> str:
        deadline = time.time() + float(timeout_s)
        while time.time() < deadline:
            line = self._read_line_once()
            if line != "":
                return line
        return ""

    # ---------- commands ----------
    def query(self, cmd: str, timeout_s: Optional[float] = None) -> str:
        self.flush_input()
        self._write_line(cmd)
        t = self.cfg.query_timeout_s if timeout_s is None else float(timeout_s)
        return self._read_nonempty_until(t)

    def cmd_ok_motion(self, cmd: str) -> None:
        """
        Send a motion command and wait long enough for OK (which is sent after motion completes).
        """
        self.flush_input()
        self._write_line(cmd)
        ans = self._read_nonempty_until(self.cfg.motion_ok_timeout_s)
        if ans.upper() != "OK":
            raise RuntimeError(f"Expected OK, got '{ans}' for cmd '{cmd}'")

    # ---------- parsing ----------
    @staticmethod
    def _parse_int(s: str) -> int:
        s = (s or "").strip()
        try:
            return int(s)
        except ValueError:
            for tok in s.replace(";", ",").replace(" ", ",").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    return int(tok)
                except ValueError:
                    continue
        raise ValueError(f"Invalid integer response: '{s}'")

    # ---------- SCPI-ish API ----------
    def idn(self) -> str:
        return self.query("*IDN?")

    def enable(self, enable: bool = True) -> None:
        # Not in firmware command set; keep no-op for compatibility.
        return

    def home_all(self) -> None: self.cmd_ok_motion(":MOT:HOME:ALL")
    def home_x(self) -> None:   self.cmd_ok_motion(":MOT:HOME:X")
    def home_y(self) -> None:   self.cmd_ok_motion(":MOT:HOME:Y")

    def pos_x(self) -> int:
        return self._parse_int(self.query(":MOT:X:POS?"))

    def pos_y(self) -> int:
        return self._parse_int(self.query(":MOT:Y:POS?"))

    def goto_x(self, x_steps: int, retry_once: bool = True) -> int:
        target = int(x_steps)
        self.cmd_ok_motion(f":MOT:X:GOTO {target}")
        pos = self.pos_x()
        if pos != target and retry_once:
            self.cmd_ok_motion(f":MOT:X:GOTO {target}")
            pos = self.pos_x()
        if pos != target:
            raise RuntimeError(f"X verify failed: target={target}, pos={pos}")
        return pos

    def goto_y(self, y_steps: int, retry_once: bool = True) -> int:
        target = int(y_steps)
        self.cmd_ok_motion(f":MOT:Y:GOTO {target}")
        pos = self.pos_y()
        if pos != target and retry_once:
            self.cmd_ok_motion(f":MOT:Y:GOTO {target}")
            pos = self.pos_y()
        if pos != target:
            raise RuntimeError(f"Y verify failed: target={target}, pos={pos}")
        return pos

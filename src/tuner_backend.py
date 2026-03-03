from __future__ import annotations
import socket, time
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
    timeout_s: float = 1.0

class TunerBackend:
    def __init__(self, cfg: TunerConfig):
        self.cfg = cfg
        self._sock: Optional[socket.socket] = None
        self._fh = None
        self._ser = None
        self.connect()

    def connect(self):
        self.close()
        if self.cfg.mode == "tcp":
            self._sock = socket.create_connection((self.cfg.host, self.cfg.port), timeout=self.cfg.timeout_s)
            self._sock.settimeout(self.cfg.timeout_s)
            self._fh = self._sock.makefile("rwb", buffering=0)
        elif self.cfg.mode == "serial":
            if serial is None:
                raise RuntimeError("pyserial not installed (pip install pyserial)")
            self._ser = serial.Serial(self.cfg.com, baudrate=self.cfg.baud, timeout=self.cfg.timeout_s)
        else:
            raise ValueError("mode must be tcp or serial")

    def close(self):
        try:
            if self._fh: self._fh.close()
        except Exception: pass
        self._fh = None
        try:
            if self._sock: self._sock.close()
        except Exception: pass
        self._sock = None
        try:
            if self._ser: self._ser.close()
        except Exception: pass
        self._ser = None

    def _write(self, line: str):
        data = (line.strip() + "\n").encode("ascii", errors="ignore")
        if self._fh: self._fh.write(data)
        elif self._ser: self._ser.write(data)
        else: raise RuntimeError("Tuner transport not open")

    def _read(self) -> str:
        if self._fh: return self._fh.readline().decode(errors="ignore").strip()
        if self._ser: return self._ser.readline().decode(errors="ignore").strip()
        raise RuntimeError("Tuner transport not open")

    def write(self, cmd: str):
        self._write(cmd)

    def query(self, cmd: str) -> str:
        self._write(cmd)
        return self._read()

    def idn(self) -> str:
        return self.query("*IDN?")

    def enable(self, enable: bool = True):
        self.write(f":MOT:ENAB {1 if enable else 0}")

    def home_all(self): self.write(":MOT:HOME:ALL")
    def home_x(self):   self.write(":MOT:HOME:X")
    def home_y(self):   self.write(":MOT:HOME:Y")

    def goto_x(self, x_steps: int): self.write(f":MOT:X:GOTO {int(x_steps)}")
    def goto_y(self, y_steps: int): self.write(f":MOT:Y:GOTO {int(y_steps)}")

    def pos_x(self) -> int: return int(self.query(":MOT:X:POS?"))
    def pos_y(self) -> int: return int(self.query(":MOT:Y:POS?"))

    def stat_x(self) -> str: return self.query(":MOT:X:STAT?")
    def stat_y(self) -> str: return self.query(":MOT:Y:STAT?")

    def wait_stop(self, axis: str = "both", timeout_s: float = 30.0, poll_s: float = 0.05):
        t0 = time.time()
        while True:
            if time.time() - t0 > timeout_s:
                raise TimeoutError(f"Timeout waiting STOP axis={axis}")
            sx = self.stat_x().upper() if axis in ("x","both") else "STOP"
            sy = self.stat_y().upper() if axis in ("y","both") else "STOP"
            if "STOP" in sx and "STOP" in sy:
                return
            time.sleep(poll_s)

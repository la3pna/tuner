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
    mode: str                 # 'tcp' or 'serial'
    host: str = '127.0.0.1'
    port: int = 12001
    com: str = 'COM6'
    baud: int = 115200

    # You verified LF works.
    eol: str = '\n'

    # Per-read timeout (each readline call).
    io_timeout_s: float = 0.25

    # Wait for OK for motion commands (home/goto).
    motion_ok_timeout_s: float = 300.0

    # Wait for replies for queries (POS?/STAT?/IDN).
    query_timeout_s: float = 2.0

    # Some units sometimes ignore the *first* move right after HOME.
    # We mitigate by verifying POS after OK and retrying.
    move_verify_retries: int = 2
    retry_delay_s: float = 0.2
    post_home_delay_s: float = 0.1


class TunerBackend:
    """
    Observed behavior:
      - HOME returns OK after motion complete.
      - Immediately after HOME, a first GOTO may sometimes return OK but not actually move (POS stays 0).
        Sending the same GOTO again then moves.

    Fix:
      - After any GOTO OK, read POS? and if mismatch, retry sending GOTO (default 2 attempts total).
      - After HOME OK, wait a small settle delay.
    """

    def __init__(self, cfg: TunerConfig):
        self.cfg = cfg
        self._sock: Optional[socket.socket] = None
        self._fh = None
        self._ser = None
        self.connect()

    def connect(self):
        self.close()
        if self.cfg.mode == 'tcp':
            self._sock = socket.create_connection((self.cfg.host, self.cfg.port), timeout=self.cfg.query_timeout_s)
            self._sock.settimeout(self.cfg.io_timeout_s)
            self._fh = self._sock.makefile('rwb', buffering=0)
        elif self.cfg.mode == 'serial':
            if serial is None:
                raise RuntimeError('pyserial not installed (pip install pyserial)')
            self._ser = serial.Serial(self.cfg.com, baudrate=self.cfg.baud, timeout=self.cfg.io_timeout_s)
        else:
            raise ValueError('mode must be tcp or serial')
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

    def flush_input(self):
        try:
            if self._ser:
                self._ser.reset_input_buffer()
        except Exception:
            pass

    def _write_line(self, line: str):
        data = (line.strip() + self.cfg.eol).encode('ascii', errors='ignore')
        if self._fh:
            self._fh.write(data)
        elif self._ser:
            self._ser.write(data)
        else:
            raise RuntimeError('Transport not open')

    def _read_line_once(self) -> str:
        if self._fh:
            return self._fh.readline().decode(errors='ignore').strip()
        if self._ser:
            return self._ser.readline().decode(errors='ignore').strip()
        raise RuntimeError('Transport not open')

    def _read_nonempty_until(self, timeout_s: float) -> str:
        deadline = time.time() + float(timeout_s)
        while time.time() < deadline:
            line = self._read_line_once()
            if line != '':
                return line
        return ''

    def query(self, cmd: str, timeout_s: Optional[float] = None) -> str:
        self.flush_input()
        self._write_line(cmd)
        t = self.cfg.query_timeout_s if timeout_s is None else float(timeout_s)
        return self._read_nonempty_until(t)

    def cmd_ok_motion(self, cmd: str) -> None:
        """Send a motion command and wait for OK (sent after motion completes)."""
        self.flush_input()
        self._write_line(cmd)
        ans = self._read_nonempty_until(self.cfg.motion_ok_timeout_s)
        if ans.upper() != 'OK':
            raise RuntimeError(f"Expected OK, got '{ans}' for cmd '{cmd}'")

    @staticmethod
    def _parse_int(s: str) -> int:
        s = (s or '').strip()
        try:
            return int(s)
        except ValueError:
            for tok in s.replace(';', ',').replace(' ', ',').split(','):
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    return int(tok)
                except ValueError:
                    continue
        raise ValueError(f"Invalid integer response: '{s}'")

    @staticmethod
    def _stat_flags(stat: str) -> set[str]:
        parts = [p.strip().upper() for p in (stat or '').split(',') if p.strip()]
        return set(parts)

    def idn(self) -> str:
        return self.query('*IDN?')

    def stat_x(self) -> str:
        return self.query(':MOT:X:STAT?')

    def stat_y(self) -> str:
        return self.query(':MOT:Y:STAT?')

    def is_homed(self) -> bool:
        sx = self.stat_x()
        sy = self.stat_y()
        return ('HOMED' in self._stat_flags(sx)) and ('HOMED' in self._stat_flags(sy))

    def home_all(self) -> None:
        self.cmd_ok_motion(':MOT:HOME:ALL')
        if self.cfg.post_home_delay_s > 0:
            time.sleep(self.cfg.post_home_delay_s)

    def home_x(self) -> None:
        self.cmd_ok_motion(':MOT:HOME:X')
        if self.cfg.post_home_delay_s > 0:
            time.sleep(self.cfg.post_home_delay_s)

    def home_y(self) -> None:
        self.cmd_ok_motion(':MOT:HOME:Y')
        if self.cfg.post_home_delay_s > 0:
            time.sleep(self.cfg.post_home_delay_s)

    def pos_x(self) -> int:
        return self._parse_int(self.query(':MOT:X:POS?'))

    def pos_y(self) -> int:
        return self._parse_int(self.query(':MOT:Y:POS?'))

    def goto_x(self, x_steps: int) -> int:
        target = int(x_steps)
        attempts = max(1, int(self.cfg.move_verify_retries))
        last_pos = None
        for k in range(attempts):
            self.cmd_ok_motion(f':MOT:X:GOTO {target}')
            pos = self.pos_x()
            last_pos = pos
            if pos == target:
                return pos
            if k < attempts - 1:
                time.sleep(self.cfg.retry_delay_s)
        raise RuntimeError(f'X verify failed: target={target}, pos={last_pos} (attempts={attempts})')

    def goto_y(self, y_steps: int) -> int:
        target = int(y_steps)
        attempts = max(1, int(self.cfg.move_verify_retries))
        last_pos = None
        for k in range(attempts):
            self.cmd_ok_motion(f':MOT:Y:GOTO {target}')
            pos = self.pos_y()
            last_pos = pos
            if pos == target:
                return pos
            if k < attempts - 1:
                time.sleep(self.cfg.retry_delay_s)
        raise RuntimeError(f'Y verify failed: target={target}, pos={last_pos} (attempts={attempts})')

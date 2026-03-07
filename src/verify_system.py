from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

from client import ServiceClient


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ok(msg: str):
    print(f"[{now()}] PASS  {msg}")


def info(msg: str):
    print(f"[{now()}] INFO  {msg}")


def warn(msg: str):
    print(f"[{now()}] WARN  {msg}")


def fail(msg: str):
    print(f"[{now()}] FAIL  {msg}")


def require(res: dict, label: str):
    if not isinstance(res, dict):
        raise RuntimeError(f"{label}: response is not a dict: {res!r}")
    if not res.get("ok", False):
        raise RuntimeError(f"{label}: {res.get('error', 'unknown error')}")
    return res


def main():
    ap = argparse.ArgumentParser(
        description="Test and verify the tuner + service + VNA system."
    )
    ap.add_argument("--config", default="config.json", help="Path to config.json")
    ap.add_argument("--tuner", default="tuner2", help="Tuner name in config")
    ap.add_argument("--freq-mhz", type=int, default=1000, help="Test frequency in MHz")
    ap.add_argument("--home", action="store_true", help="Run HOME ALL")
    ap.add_argument("--setxy", action="store_true", help="Run a simple XY move test")
    ap.add_argument("--measure", action="store_true", help="Run a VNA measurement test")
    ap.add_argument("--setz", action="store_true", help="Run a SETZ lookup/move test")
    ap.add_argument("--target-r", type=float, default=50.0, help="Target resistance for SETZ")
    ap.add_argument("--target-x", type=float, default=0.0, help="Target reactance for SETZ")
    ap.add_argument("--states-csv", default="", help="Optional states CSV to verify existence")
    ap.add_argument("--expect-cal", default="", help="Optional calibration CSV to verify existence")
    ap.add_argument("--timeout-s", type=float, default=300.0, help="Per-call timeout")
    ap.add_argument("--move-x", type=int, default=800, help="X for setxy test")
    ap.add_argument("--move-y", type=int, default=400, help="Y for setxy test")
    args = ap.parse_args()

    freq_hz = float(args.freq_mhz) * 1e6
    overall_pass = True

    info(f"Using config={args.config} tuner={args.tuner} freq={args.freq_mhz} MHz")
    c = ServiceClient.from_config(args.config, args.tuner)
    info(f"Client endpoint {c.host}:{c.port}, client timeout={c.timeout_s}s")

    try:
        res = require(c.call({"cmd": "ping"}, timeout_s=args.timeout_s), "PING")
        if res.get("tuner") != args.tuner:
            warn(f"PING returned tuner={res.get('tuner')}, expected {args.tuner}")
        ok("Service ping")
    except Exception as e:
        overall_pass = False
        fail(str(e))

    try:
        res = require(c.call({"cmd": "idn"}, timeout_s=args.timeout_s), "IDN")
        info(f"VNA IDN: {res.get('vna', '')}")
        info(f"Tuner IDN: {res.get('tuner', '')}")
        ok("IDN query")
    except Exception as e:
        overall_pass = False
        fail(str(e))

    if args.expect_cal:
        p = Path(args.expect_cal)
        if p.exists():
            ok(f"Calibration file exists: {p}")
        else:
            overall_pass = False
            fail(f"Calibration file not found: {p}")

    if args.states_csv:
        p = Path(args.states_csv)
        if p.exists():
            ok(f"States CSV exists: {p}")
        else:
            overall_pass = False
            fail(f"States CSV not found: {p}")

    if args.home:
        try:
            res = require(c.call({"cmd": "home", "axis": "all"}, timeout_s=args.timeout_s), "HOME")
            x = int(res["x"])
            y = int(res["y"])
            if x != 0 or y != 0:
                warn(f"HOME returned x={x}, y={y}, expected 0,0")
            ok(f"HOME ALL completed, final position x={x}, y={y}")
        except Exception as e:
            overall_pass = False
            fail(str(e))

    if args.setxy:
        try:
            req = {"cmd": "setxy", "x_steps": int(args.move_x), "y_steps": int(args.move_y)}
            res = require(c.call(req, timeout_s=args.timeout_s), "SETXY")
            x = int(res["x"])
            y = int(res["y"])
            if x != int(args.move_x) or y != int(args.move_y):
                raise RuntimeError(f"SETXY verify failed: returned x={x}, y={y}")
            ok(f"SETXY moved to x={x}, y={y}")
        except Exception as e:
            overall_pass = False
            fail(str(e))

    if args.measure:
        try:
            res = require(c.call({"cmd": "measure", "f_hz": freq_hz}, timeout_s=args.timeout_s), "MEASURE")
            f = float(res["f_hz"])
            s11 = res.get("s11")
            s21 = res.get("s21")
            s12 = res.get("s12")
            s22 = res.get("s22")
            for name, val in [("s11", s11), ("s21", s21), ("s12", s12), ("s22", s22)]:
                if not (isinstance(val, list) and len(val) == 2):
                    raise RuntimeError(f"MEASURE invalid {name}: {val!r}")
            info(f"Measured center frequency: {f} Hz")
            info(f"S21 dB field: {res.get('il_db')}")
            ok("VNA measurement")
        except Exception as e:
            overall_pass = False
            fail(str(e))

    if args.expect_cal:
        try:
            res = require(c.call({"cmd": "load_cal", "f_hz": freq_hz}, timeout_s=args.timeout_s), "LOAD_CAL")
            info(f"Loaded calibration: {res.get('cal_file')} states={res.get('states')}")
            ok("Calibration lookup")
        except Exception as e:
            overall_pass = False
            fail(str(e))

    if args.setz:
        try:
            req = {
                "cmd": "setz",
                "f_hz": freq_hz,
                "R": float(args.target_r),
                "X": float(args.target_x),
            }
            res = require(c.call(req, timeout_s=args.timeout_s), "SETZ")
            x = int(res["x_steps"])
            y = int(res["y_steps"])
            err = float(res["err"])
            gamma_target = res.get("gamma_target")
            gamma = res.get("gamma")
            info(f"SETZ selected x={x}, y={y}, err={err:.6f}")
            info(f"gamma_target={gamma_target}")
            info(f"gamma={gamma}")
            ok("SETZ lookup and move")
        except Exception as e:
            overall_pass = False
            fail(str(e))

    print()
    if overall_pass:
        print("OVERALL RESULT: PASS")
        sys.exit(0)
    else:
        print("OVERALL RESULT: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        print()
        print("OVERALL RESULT: FAIL")
        sys.exit(1)

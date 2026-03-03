#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from client import ServiceClient

def main() -> int:
    ap = argparse.ArgumentParser(description="Measure one frequency point (S2P) via tuner_service.")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--tuner", default="tuner1")
    ap.add_argument("--freq", type=float, required=True)
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args()

    c = ServiceClient.from_config(args.config, tuner=args.tuner, timeout_s=float(args.timeout))
    res = c.call({"cmd":"measure","f_hz":float(args.freq)})
    print(json.dumps(res, indent=2 if args.pretty else None))
    return 0 if res.get("ok") else 1

if __name__ == "__main__":
    raise SystemExit(main())

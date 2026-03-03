#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from client import ServiceClient

def main() -> int:
    ap = argparse.ArgumentParser(description="Set tuner to target Z (R+jX) or Gamma.")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--tuner", default="tuner1")
    ap.add_argument("--freq", type=float, required=True)
    ap.add_argument("--R", type=float, default=None)
    ap.add_argument("--X", type=float, default=None)
    ap.add_argument("--gamma-re", type=float, default=None)
    ap.add_argument("--gamma-im", type=float, default=None)
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args()

    c = ServiceClient.from_config(args.config, tuner=args.tuner, timeout_s=float(args.timeout))

    if args.gamma_re is not None or args.gamma_im is not None:
        if args.gamma_re is None or args.gamma_im is None:
            print("Need both --gamma-re and --gamma-im", file=sys.stderr)
            return 2
        req = {"cmd":"setgamma","f_hz":float(args.freq),"gamma_re":float(args.gamma_re),"gamma_im":float(args.gamma_im)}
    else:
        if args.R is None or args.X is None:
            print("Need --R and --X (or --gamma-re/--gamma-im)", file=sys.stderr)
            return 2
        req = {"cmd":"setz","f_hz":float(args.freq),"R":float(args.R),"X":float(args.X)}

    res = c.call(req)
    print(json.dumps(res, indent=2 if args.pretty else None))
    return 0 if res.get("ok") else 1

if __name__ == "__main__":
    raise SystemExit(main())

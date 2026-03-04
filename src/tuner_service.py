from __future__ import annotations

import asyncio
import csv
from typing import Any, Dict, List, Tuple

from service_protocol import jdump, jloads
from tuner_backend import TunerBackend, TunerConfig
from vna_backend import VnaBackend, VnaConfig
from calibration_store import CalibrationStore, CalRow
from lookup_engine import z_to_gamma, pick_state, il_db_from_s21

from config_loader import (
    load_config,
    get_tuner_cfg,
    get_paths_cfg,
    get_vna_cfg,
    get_lookup_cfg,
    get_tuner_service_endpoint,
)


def cplx_to_list(z: complex):
    return [float(z.real), float(z.imag)]


class TunerService:
    def __init__(self, cfg_path: str, tuner_name: str):
        self.cfg = load_config(cfg_path)
        self.tuner_name = tuner_name

        paths = get_paths_cfg(self.cfg)
        self.store = CalibrationStore(cal_dir=paths.get("cal_dir", "cal"))

        tcfg = get_tuner_cfg(self.cfg, tuner_name)
        transport = (tcfg.get("transport") or "tcp").lower()
        motion = (tcfg.get("motion", {}) or {})

        def _decode_eol(v: str, default: str) -> str:
            s = str(v) if v is not None else default
            return s.encode("utf-8").decode("unicode_escape")

        motion_ok_timeout_s = float(motion.get("motion_ok_timeout_s", 300.0))
        move_verify_retries = int(motion.get("move_verify_retries", 2))
        retry_delay_s = float(motion.get("retry_delay_s", 0.2))
        post_home_delay_s = float(motion.get("post_home_delay_s", 0.1))

        if transport == "tcp":
            tcp = tcfg.get("tcp", {}) or {}
            self.tuner = TunerBackend(TunerConfig(
                mode="tcp",
                host=tcp.get("host", "127.0.0.1"),
                port=int(tcp.get("port", 12001)),
                baud=0,
                eol=_decode_eol(tcp.get("eol", "\n"), "\n"),
                io_timeout_s=float(tcp.get("io_timeout_s", 0.25)),
                query_timeout_s=float(tcp.get("query_timeout_s", 2.0)),
                motion_ok_timeout_s=motion_ok_timeout_s,
                move_verify_retries=move_verify_retries,
                retry_delay_s=retry_delay_s,
                post_home_delay_s=post_home_delay_s,
            ))
        elif transport == "serial":
            ser = tcfg.get("serial", {}) or {}
            self.tuner = TunerBackend(TunerConfig(
                mode="serial",
                com=ser.get("port", "COM6"),
                baud=int(ser.get("baud", 115200)),
                eol=_decode_eol(ser.get("eol", "\n"), "\n"),
                io_timeout_s=float(ser.get("io_timeout_s", 0.25)),
                query_timeout_s=float(ser.get("query_timeout_s", 2.0)),
                motion_ok_timeout_s=motion_ok_timeout_s,
                move_verify_retries=move_verify_retries,
                retry_delay_s=retry_delay_s,
                post_home_delay_s=post_home_delay_s,
            ))
        else:
            raise ValueError(f"Unsupported tuner transport: {transport}")

        vcfg = get_vna_cfg(self.cfg)
        scpi = vcfg.get("scpi", {}) or {}
        m = vcfg.get("measure_one_point", {}) or {}
        self.vna = VnaBackend(VnaConfig(
            host=scpi.get("host", "127.0.0.1"),
            port=int(scpi.get("port", 19542)),
            power_dbm=float(m.get("power_dbm", -10.0)),
            ifbw_hz=float(m.get("ifbw_hz", 10_000.0)),
            avg=int(m.get("avg", 1)),
            span_hz=float(m.get("span_hz", 400_000.0)),
            points=int(m.get("points", 2)),
            sweep_timeout_s=float(m.get("sweep_timeout_s", 8.0)),
        ))

        lk = get_lookup_cfg(self.cfg)
        self.z0 = float(lk.get("z0_ohm", 50.0))
        self.default_select = lk.get("default_select", "topn_min_il")
        self.default_top_n = int(lk.get("top_n", 30))
        self.default_alpha = float(lk.get("alpha", 0.02))

        self.lock = asyncio.Lock()

    def _ensure_homed(self):
        try:
            if not self.tuner.is_homed():
                self.tuner.home_all()
        except Exception:
            pass

    async def handle(self, req: Dict[str, Any]) -> Dict[str, Any]:
        cmd = (req.get("cmd") or "").lower().strip()

        if cmd == "ping":
            return {"ok": True, "pong": True, "tuner": self.tuner_name}

        async with self.lock:
            try:
                if cmd == "idn":
                    return {"ok": True, "tuner": self.tuner.idn(), "vna": self.vna.idn(), "tuner_name": self.tuner_name}

                if cmd == "home":
                    axis = (req.get("axis") or "all").lower()
                    if axis in ("all", "both"):
                        self.tuner.home_all()
                    elif axis == "x":
                        self.tuner.home_x()
                    elif axis == "y":
                        self.tuner.home_y()
                    else:
                        return {"ok": False, "error": f"invalid axis {axis}"}
                    return {"ok": True, "x": self.tuner.pos_x(), "y": self.tuner.pos_y()}

                if cmd == "setxy":
                    x = int(req["x_steps"])
                    y = int(req["y_steps"])

                    self._ensure_homed()

                    xf = self.tuner.goto_x(x)
                    yf = self.tuner.goto_y(y)
                    return {"ok": True, "x": xf, "y": yf}

                if cmd == "measure":
                    f_hz = float(req["f_hz"])
                    picked_f, s11, s21, s12, s22 = self.vna.measure_s2p(f_hz)
                    return {
                        "ok": True,
                        "f_hz": float(picked_f),
                        "s11": cplx_to_list(s11),
                        "s21": cplx_to_list(s21),
                        "s12": cplx_to_list(s12),
                        "s22": cplx_to_list(s22),
                        "il_db": float(il_db_from_s21(s21)),
                        "gamma_out": cplx_to_list(s22),
                    }

                if cmd == "load_cal":
                    f_hz = float(req["f_hz"])
                    path, rows = self.store.load_freq(f_hz)
                    return {"ok": True, "cal_file": path, "states": len(rows)}

                if cmd == "setz":
                    f_hz = float(req["f_hz"])
                    z0 = float(req.get("z0", self.z0))
                    R = float(req["R"])
                    X = float(req["X"])
                    gamma_target = z_to_gamma(complex(R, X), z0=z0)

                    select = req.get("select", self.default_select)
                    top_n = int(req.get("top_n", self.default_top_n))
                    alpha = float(req.get("alpha", self.default_alpha))

                    cal_file, rows = self.store.load_freq(f_hz)
                    pick = pick_state(rows, gamma_target, select=select, top_n=top_n, alpha=alpha)

                    self._ensure_homed()
                    xf = self.tuner.goto_x(pick.x)
                    yf = self.tuner.goto_y(pick.y)

                    return {
                        "ok": True,
                        "tuner_name": self.tuner_name,
                        "cal_file": cal_file,
                        "x_steps": int(xf),
                        "y_steps": int(yf),
                        "gamma_target": cplx_to_list(gamma_target),
                        "gamma": cplx_to_list(pick.gamma),
                        "err": float(pick.err),
                        "il_db": float(pick.il_db),
                    }

                if cmd == "cal_add_freq":
                    f_hz = float(req["f_hz"])

                    states: List[Tuple[int, int]] = []
                    if "states" in req:
                        for xy in req["states"]:
                            states.append((int(xy[0]), int(xy[1])))
                    else:
                        states_csv = req.get("states_csv", "states.csv")
                        with open(states_csv, "r", newline="") as f:
                            r = csv.DictReader(f)
                            for row in r:
                                states.append((int(row["x_steps"]), int(row["y_steps"])))

                    if not states:
                        return {"ok": False, "error": "no states provided"}

                    if req.get("home_first", True):
                        self.tuner.home_all()

                    out_rows: List[CalRow] = []
                    self._ensure_homed()
                    for (x, y) in states:
                        self.tuner.goto_x(x)
                        self.tuner.goto_y(y)

                        picked_f, s11, s21, s12, s22 = self.vna.measure_s2p(f_hz)
                        out_rows.append(CalRow(x=x, y=y, s11=s11, s21=s21, s12=s12, s22=s22))

                    path = self.store.save_freq(f_hz, out_rows)
                    return {"ok": True, "cal_file": path, "states": len(out_rows), "tuner_name": self.tuner_name}

                return {"ok": False, "error": f"unknown cmd '{cmd}'"}

            except Exception as e:
                return {"ok": False, "error": str(e)}


async def client_task(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, svc: TunerService):
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                req = jloads(line)
                res = await svc.handle(req)
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            writer.write(jdump(res))
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--tuner", required=True)
    ap.add_argument("--listen-host", default=None)
    ap.add_argument("--listen-port", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    svc_global = (cfg.get("service", {}) or {})
    host = svc_global.get("bind_host", svc_global.get("listen_host", "0.0.0.0"))
    _, port = get_tuner_service_endpoint(cfg, args.tuner)

    if args.listen_host:
        host = args.listen_host
    if args.listen_port:
        port = args.listen_port

    svc = TunerService(cfg_path=args.config, tuner_name=args.tuner)

    server = await asyncio.start_server(lambda r, w: client_task(r, w, svc), host=host, port=port)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"Tuner service ({args.tuner}) listening on {addrs}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())

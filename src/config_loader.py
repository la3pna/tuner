from __future__ import annotations

import json
import os
from typing import Any, Dict, Tuple


def load_config(path: str = "config.json") -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if cfg.get("version") != 1:
        raise ValueError(f"Unsupported config version: {cfg.get('version')}")
    return cfg


def get_tuner_cfg(cfg: Dict[str, Any], name: str) -> Dict[str, Any]:
    for t in cfg.get("tuners", []):
        if t.get("name") == name:
            if not t.get("enabled", True):
                raise ValueError(f"Tuner '{name}' is disabled in config")
            return t
    raise KeyError(f"Tuner '{name}' not found in config")


def get_paths_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg.get("paths", {})


def get_vna_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    v = cfg.get("vna", {})
    if not v.get("enabled", True):
        raise ValueError("VNA is disabled in config")
    return v


def get_lookup_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg.get("lookup", {})


def get_tuner_service_endpoint(cfg: Dict[str, Any], tuner_name: str) -> Tuple[str, int]:
    """Return (host, port) that the *client* should connect to."""
    t = get_tuner_cfg(cfg, tuner_name)
    svc_global = (cfg.get("service", {}) or {})

    # Your config uses client_host (preferred), but we keep backward compatibility:
    base_host = (
        svc_global.get("client_host")
        or svc_global.get("listen_host")
        or svc_global.get("bind_host")
        or "127.0.0.1"
    )

    svc = t.get("service", {}) or {}
    host = svc.get("host", base_host)
    port = int(svc.get("port", 53190))
    return host, port


def get_client_timeout_s(cfg: Dict[str, Any], tuner_name: str, default: float = 10.0) -> float:
    """Client socket timeout. Supports per-tuner override."""
    svc_global = (cfg.get("service", {}) or {})
    t = get_tuner_cfg(cfg, tuner_name)
    svc_t = t.get("service", {}) or {}

    # Priority: per-tuner -> global -> default
    v = svc_t.get("client_timeout_s", None)
    if v is None:
        v = svc_global.get("client_timeout_s", None)
    if v is None:
        return float(default)
    return float(v)

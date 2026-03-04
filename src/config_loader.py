from __future__ import annotations
import json, os
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

def get_tuner_service_endpoint(cfg, tuner_name):
    t = get_tuner_cfg(cfg, tuner_name)

    svc_global = (cfg.get("service", {}) or {})
    # client_host is for connecting, bind_host is for listening
    client_host = svc_global.get("client_host", "127.0.0.1")

    svc = t.get("service", {}) or {}
    host = svc.get("host", client_host)  # per-tuner override if present
    port = int(svc.get("port", 53190))
    return host, port

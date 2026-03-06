from __future__ import annotations

import json
import socket
from typing import Any, Dict, Optional

from config_loader import load_config, get_tuner_service_endpoint, get_client_timeout_s


class ServiceClient:
    def __init__(self, host: str, port: int, timeout_s: float = 10.0):
        self.host = host
        self.port = int(port)
        self.timeout_s = float(timeout_s)

    @classmethod
    def from_config(
        cls,
        config_path: str = "config.json",
        tuner: str = "tuner1",
        timeout_s: Optional[float] = None,
    ) -> "ServiceClient":
        cfg = load_config(config_path)
        host, port = get_tuner_service_endpoint(cfg, tuner)
        # Prefer config-driven client timeout (supports global + per-tuner override)
        if timeout_s is None:
            timeout_s = get_client_timeout_s(cfg, tuner, default=10.0)
        return cls(host, port, float(timeout_s))

    def call(self, req: Dict[str, Any], timeout_s: Optional[float] = None) -> Dict[str, Any]:
        """Send one JSON request and wait for one JSON line response."""
        t = float(self.timeout_s if timeout_s is None else timeout_s)
        data = (json.dumps(req) + "\n").encode("utf-8")

        with socket.create_connection((self.host, self.port), timeout=t) as s:
            s.settimeout(t)
            s.sendall(data)

            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk

        if not buf:
            return {"ok": False, "error": "empty response"}
        return json.loads(buf.decode("utf-8", errors="replace"))

from __future__ import annotations
import json, socket
from typing import Any, Dict
from config_loader import load_config, get_tuner_service_endpoint

class ServiceClient:
    def __init__(self, host: str, port: int, timeout_s: float = 10.0):
        self.host = host
        self.port = port
        self.timeout_s = timeout_s

    @classmethod
    def from_config(cls, config_path: str = "config.json", tuner: str = "tuner1", timeout_s: float = 10.0):
        cfg = load_config(config_path)
        host, port = get_tuner_service_endpoint(cfg, tuner)
        return cls(host, port, timeout_s)

    def call(self, req: Dict[str, Any]) -> Dict[str, Any]:
        data = (json.dumps(req) + "\n").encode("utf-8")
        with socket.create_connection((self.host, self.port), timeout=self.timeout_s) as s:
            s.sendall(data)
            s.settimeout(self.timeout_s)
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf.decode("utf-8"))

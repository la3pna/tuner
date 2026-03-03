from __future__ import annotations
import json, time
from dataclasses import dataclass
from typing import Any, Dict, Optional

def jdump(obj: Dict[str, Any]) -> bytes:
    return (json.dumps(obj, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')

def jloads(line: bytes) -> Dict[str, Any]:
    return json.loads(line.decode('utf-8'))

def now_ms() -> int:
    return int(time.time() * 1000)

@dataclass
class ServiceError(Exception):
    message: str
    code: str = "error"
    details: Optional[Dict[str, Any]] = None

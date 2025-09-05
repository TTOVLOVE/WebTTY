import json
from dataclasses import dataclass
from typing import Any, Optional

TERMINATOR = "\n".encode()

@dataclass
class Command:
    action: str
    arg: Optional[str] = None
    # 可选：nonce、ts、mac 用于HMAC鉴权


def dumps(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode() + TERMINATOR


def loads_line(line: bytes) -> dict:
    return json.loads(line.decode('utf-8'))
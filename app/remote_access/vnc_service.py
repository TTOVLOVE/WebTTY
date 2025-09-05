import os
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from ..config import BaseConfig

@dataclass
class VNCSession:
    session_id: str
    target_host: str
    target_port: int
    ws_host: str
    ws_port: int
    proc: subprocess.Popen = field(repr=False)
    start_time: float = field(default_factory=time.time)

class VNCService:
    def __init__(self):
        self._sessions: Dict[str, VNCSession] = {}
        self._lock = threading.Lock()
        self._next_port = BaseConfig.VNC_WEBSOCKIFY_BASE_PORT

    def _alloc_port(self) -> int:
        with self._lock:
            port = self._next_port
            self._next_port += 1
            return port

    def _port_free(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            return s.connect_ex(("127.0.0.1", port)) != 0

    def start(self, session_id: str, target_host: str, target_port: Optional[int] = None) -> VNCSession:
        """
        启动 websockify: ws_host:ws_port  ->  target_host:target_port
        返回用于 noVNC 连接的 WebSocket 信息。
        """
        target_port = int(target_port or BaseConfig.VNC_TARGET_DEFAULT_PORT)

        ws_port = None
        # 分配空闲端口
        for _ in range(50):
            candidate = self._alloc_port()
            if self._port_free(candidate):
                ws_port = candidate
                break
        if ws_port is None:
            raise RuntimeError("没有可用的本地端口用于 websockify")

        # 启动 websockify 子进程
        cmd = [
            BaseConfig.VNC_WEBSOCKIFY_BIN,
            f"{BaseConfig.VNC_WEBSOCKIFY_HOST}:{ws_port}",
            f"{target_host}:{target_port}",
            "--timeout", "30"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        sess = VNCSession(
            session_id=session_id,
            target_host=target_host,
            target_port=target_port,
            ws_host=BaseConfig.VNC_WEBSOCKIFY_HOST,
            ws_port=ws_port,
            proc=proc
        )
        with self._lock:
            self._sessions[session_id] = sess
        return sess

    def stop(self, session_id: str) -> bool:
        with self._lock:
            sess = self._sessions.pop(session_id, None)
        if not sess:
            return False
        try:
            sess.proc.terminate()
            try:
                sess.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                sess.proc.kill()
        except Exception:
            pass
        return True

    def get(self, session_id: str) -> Optional[VNCSession]:
        with self._lock:
            return self._sessions.get(session_id)

vnc_service = VNCService()

import requests
from typing import Dict, Optional
from ..config import BaseConfig

class GuacamoleClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    def login(self) -> Optional[str]:
        # POST /api/tokens
        url = f"{self.base_url}/api/tokens"
        resp = requests.post(url, data={"username": self.username, "password": self.password}, timeout=5)
        if resp.ok:
            data = resp.json()
            return data.get("authToken")
        return None

    def build_rdp_view_url(self, hostname: str, username: str, password: str, port: int = 3389, domain: str = "") -> Optional[str]:
        """
        简单方式：前端直接用 token 访问 Guacamole 默认主页，用户在 UI 内创建连接。
        进阶方式：调用 /api/session/data/{dataSource}/... 创建临时连接，再生成 share 链接。
        这里为了简单，直接把 RDP 连接参数放入 #query，实际生产建议用连接 API 创建临时连接。
        """
        token = self.login()
        if not token:
            return None

        # Guacamole 官方 UI 支持 URL hash 参数（取决于版本）：我们附带 RDP 参数，或让用户在 UI 里填。
        # 这里返回最简单的入口：只负责把用户带到带 token 的控制台，减少后端复杂度。
        return f"{self.base_url}/#/client/?token={token}&protocol=rdp&hostname={hostname}&port={port}&username={username}&password={password}&domain={domain}"

guac = GuacamoleClient(
    base_url=BaseConfig.GUACAMOLE_BASE_URL,
    username=BaseConfig.GUAC_USERNAME,
    password=BaseConfig.GUAC_PASSWORD
)

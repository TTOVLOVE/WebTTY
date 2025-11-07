import os
from datetime import timedelta

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "ratauthmoonbeaut")
    DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "downloads")
    UPLOAD_TEMP_DIR = os.getenv("UPLOAD_TEMP_DIR", "uploads_temp")
    RAT_PORT = int(os.getenv("RAT_PORT", 2383))
    SOCKETIO_PORT = int(os.getenv("SOCKETIO_PORT", 5000))

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATABASE_PATH = os.getenv("DATABASE_PATH", "app.db")
    
    # 会话配置
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # 安全配置
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.getenv("WTF_CSRF_SECRET_KEY", "csrf_secret_key")

    VNC_WEBSOCKIFY_BIN = os.getenv("VNC_WEBSOCKIFY_BIN", "websockify")   # 系统可执行：pip install websockify 后为 'websockify'
    VNC_WEBSOCKIFY_HOST = os.getenv("VNC_WEBSOCKIFY_HOST", "0.0.0.0")
    VNC_WEBSOCKIFY_BASE_PORT = int(os.getenv("VNC_WEBSOCKIFY_BASE_PORT", 6080))  # 会为不同会话自增分配
    VNC_TARGET_DEFAULT_PORT = int(os.getenv("VNC_TARGET_DEFAULT_PORT", 5900))    # 目标 VNC 默认端口（可被请求覆盖）

    # RDP / Guacamole
    GUACAMOLE_BASE_URL = os.getenv("GUACAMOLE_BASE_URL", "http://127.0.0.1:8080/guacamole")
    GUAC_USERNAME = os.getenv("GUAC_USERNAME", "guacadmin")
    GUAC_PASSWORD = os.getenv("GUAC_PASSWORD", "guacadmin")

    # Vulnerability scanning
    FSCAN_WINDOWS_PATH = os.getenv("FSCAN_WINDOWS_PATH", "fscan/fscan.exe")
    FSCAN_LINUX_PATH = os.getenv("FSCAN_LINUX_PATH", "fscan/fscan")
    FSCAN_DEFAULT_PATH = os.getenv("FSCAN_DEFAULT_PATH")
    FSCAN_OUTPUT_DIR = os.getenv("FSCAN_OUTPUT_DIR", "downloads/scan_reports")

class DevConfig(BaseConfig):
    DEBUG = True

class ProdConfig(BaseConfig):
    DEBUG = False

class TestConfig(BaseConfig):
    TESTING = True

def get_config(name):
    mapping = {
        "dev": DevConfig,
        "prod": ProdConfig,
        "test": TestConfig
    }
    return mapping.get(name.lower(), DevConfig)

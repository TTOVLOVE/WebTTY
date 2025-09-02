import os

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "ratauthmoonbeaut")
    DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "downloads")
    UPLOAD_TEMP_DIR = os.getenv("UPLOAD_TEMP_DIR", "uploads_temp")
    RAT_PORT = int(os.getenv("RAT_PORT", 2383))
    SOCKETIO_PORT = int(os.getenv("SOCKETIO_PORT", 5000))

    VNC_WEBSOCKIFY_BIN = os.getenv("VNC_WEBSOCKIFY_BIN", "websockify")   # 系统可执行：pip install websockify 后为 'websockify'
    VNC_WEBSOCKIFY_HOST = os.getenv("VNC_WEBSOCKIFY_HOST", "0.0.0.0")
    VNC_WEBSOCKIFY_BASE_PORT = int(os.getenv("VNC_WEBSOCKIFY_BASE_PORT", 6080))  # 会为不同会话自增分配
    VNC_TARGET_DEFAULT_PORT = int(os.getenv("VNC_TARGET_DEFAULT_PORT", 5900))    # 目标 VNC 默认端口（可被请求覆盖）

    # RDP / Guacamole
    GUACAMOLE_BASE_URL = os.getenv("GUACAMOLE_BASE_URL", "http://127.0.0.1:8080/guacamole")
    GUAC_USERNAME = os.getenv("GUAC_USERNAME", "guacadmin")  # 演示用，生产请用最小权限
    GUAC_PASSWORD = os.getenv("GUAC_PASSWORD", "guacadmin")

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

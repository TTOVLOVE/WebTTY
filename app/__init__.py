import os
import threading
from flask import Flask
from flask_login import LoginManager
from .config import get_config
from .extensions import socketio
from .web.sockets import init_socketio
from .remote_access import ssh_service, sftp_service
from .connect_func.tcp_server import start_tcp_server

# 导入新的蓝图
from .web.routes.dashboard import dashboard_bp
from .web.routes.assets import assets_bp
from .web.routes.toolbox import toolbox_bp
from .web.routes.vnc_api import vnc_api_bp
from .web.routes.rdp_api import rdp_api_bp
from .web.routes.auth import auth_bp
from .web.routes.ssh import ssh_bp
from .web.routes.sftp import sftp_bp
from .web.routes.admin_panel import admin_panel_bp
from .web.routes.admin import admin_bp

# 创建登录管理器
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    """用户加载函数"""
    from .models import User
    return User.get(user_id)

def create_app(config_name=None):
    app = Flask(__name__)
    config_class = get_config(config_name or os.getenv("FLASK_ENV", "dev"))
    app.config.from_object(config_class)

    # 初始化Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录以访问此页面'

    # 注册蓝图
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(toolbox_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(ssh_bp)
    app.register_blueprint(sftp_bp)
    app.register_blueprint(admin_panel_bp)
    app.register_blueprint(admin_bp)
    
    # 注册带前缀的蓝图
    app.register_blueprint(vnc_api_bp)
    app.register_blueprint(rdp_api_bp)

    # 初始化扩展
    socketio.init_app(app, async_mode='threading')

    # 注册 SocketIO 事件
    init_socketio(socketio)
    ssh_service.init_app(socketio)
    sftp_service.init_app(socketio)

    # 启动 TCP RAT 服务线程
    threading.Thread(target=start_tcp_server, daemon=True).start()

    return app

import os
import sys
import threading
from flask import Flask
from flask_login import LoginManager
from .config import get_config
from .extensions import socketio, db, migrate
from .web.sockets import init_socketio
from .remote_access import ssh_service, sftp_service
from .connect_func.tcp_server import start_tcp_server
from sqlalchemy import text

# 兼容历史绝对导入路径（如 utils、services、models 等）
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
from .web.routes.user_management import user_management_bp
from .web.routes.vulnerability_scan import vulnerability_scan_bp
from .web.routes.profile import profile_bp

# 创建登录管理器
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    """用户加载函数"""
    from .models import User
    return User.get(user_id)

# 确保默认角色存在
def ensure_default_roles(app):
    with app.app_context():
        try:
            from .models import Role
            default_roles = {
                'admin': '超级管理员',
                'user': '普通用户',
                'guest': '访客'
            }
            changed = False
            for name, desc in default_roles.items():
                if not Role.query.filter_by(name=name).first():
                    db.session.add(Role(name=name, description=desc))
                    changed = True
            if changed:
                db.session.commit()
        except Exception:
            # 若表尚未创建或其他异常，忽略，避免影响应用启动
            pass

def ensure_client_columns(app):
    """确保 clients 表包含必要的列，缺失则自动添加"""
    needed_columns = {
        'hardware_id': 'TEXT',
        'mac_address': 'TEXT',
        'device_fingerprint': 'TEXT'
    }
    with app.app_context():
        try:
            # 仅对 SQLite 进行轻量修复
            engine = db.get_engine()
            if 'sqlite' not in str(engine.url):
                return
            # 查询现有列
            conn = engine.raw_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(clients)")
            cols = {row[1] for row in cursor.fetchall()}
            to_add = [c for c in needed_columns.keys() if c not in cols]
            for col in to_add:
                cursor.execute(f"ALTER TABLE clients ADD COLUMN {col} {needed_columns[col]}")
            if to_add:
                conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            # 记录但不阻断应用启动
            print(f"[DB] 轻量结构修复失败: {e}")

def create_app(config_name=None):
    app = Flask(__name__)
    config_class = get_config(config_name or os.getenv("FLASK_ENV", "dev"))
    app.config.from_object(config_class)

    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)

    # 在应用启动时确保默认角色存在
    ensure_default_roles(app)
    # 确保 clients 表必要列存在
    ensure_client_columns(app)
    
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
    app.register_blueprint(user_management_bp)
    app.register_blueprint(vulnerability_scan_bp)
    app.register_blueprint(profile_bp)
    
    # 注册命令
    from .commands import register_commands
    register_commands(app)
    
    # 注册带前缀的蓝图
    app.register_blueprint(vnc_api_bp)
    app.register_blueprint(rdp_api_bp)

    # 初始化扩展
    socketio.init_app(app, async_mode='threading')

    # 注册 SocketIO 事件
    init_socketio(socketio)
    ssh_service.init_app(socketio)
    sftp_service.init_app(socketio)

    # 启动 TCP RAT 服务线程（传入 app 实例）
    threading.Thread(target=start_tcp_server, args=(app,), daemon=True).start()

    return app

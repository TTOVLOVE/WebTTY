import os
import sys
import threading
from datetime import datetime
from flask import Flask
from flask_login import LoginManager
from .config import get_config
from .extensions import socketio, db, migrate
from .web.sockets import init_socketio
from .remote_access import ssh_service, sftp_service
from .connect_func.tcp_server import start_tcp_server
from sqlalchemy import text
from .web.routes.connect_code import connect_code_bp
from .tasks.cleanup_worker import start_guest_cleanup

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
from .web.routes.recovery_api import recovery_api_bp
from .web.routes.security_groups import security_groups_bp

# 创建登录管理器
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    """用户加载函数"""
    from .models import User
    return User.query.get(int(user_id))

# 确保默认角色存在
def ensure_default_roles(app):
    with app.app_context():
        try:
            from .models import Role
            default_roles = {
                'admin': '超级管理员',
                'manager': '管理员',
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
    """确保 clients 表包含必要的列，缺失则自动添加（仅SQLite轻量修复）。"""
    needed_columns = {
        'hardware_id': 'TEXT',
        'mac_address': 'TEXT',
        'device_fingerprint': 'TEXT',
        'connect_code_id': 'INTEGER'
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


def ensure_connect_code_table(app):
    """确保 connect_codes 表存在（缺失则创建）。"""
    with app.app_context():
        try:
            from .models import ConnectCode
            engine = db.get_engine()
            # 仅在SQLite情况下检查并创建（其他数据库建议用迁移）
            if 'sqlite' in str(engine.url):
                ConnectCode.__table__.create(bind=engine, checkfirst=True)
        except Exception as e:
            print(f"[DB] ConnectCode 表检查/创建失败: {e}")




def ensure_vulnerability_scan_table(app):
    """确保漏洞扫描记录表存在"""
    with app.app_context():
        try:
            from .models import VulnerabilityScanRecord
            engine = db.get_engine()
            if 'sqlite' in str(engine.url):
                VulnerabilityScanRecord.__table__.create(bind=engine, checkfirst=True)
        except Exception as e:
            print(f"[DB] VulnerabilityScanRecord 表检查/创建失败: {e}")

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
    # 确保 connect_codes 表存在
    ensure_connect_code_table(app)
    # 确保漏洞扫描记录表存在
    ensure_vulnerability_scan_table(app)
    
    # 初始化Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录以访问此页面'

    @login_manager.unauthorized_handler
    def _unauthorized_handler():
        from flask import request, jsonify, redirect, url_for
        # 对 API 或期望 JSON 的请求返回 401 JSON，避免浏览器跟随重定向后得到 200 HTML
        accept = request.headers.get('Accept', '')
        xrw = request.headers.get('X-Requested-With', '')
        if request.path.startswith('/api/') or 'application/json' in accept or xrw == 'XMLHttpRequest':
            return jsonify({'error': 'unauthorized', 'message': '请先登录'}), 401
        return redirect(url_for('auth.login', next=request.url))

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
    app.register_blueprint(recovery_api_bp)
    app.register_blueprint(connect_code_bp)
    app.register_blueprint(security_groups_bp)

    
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

    # 启动客户端状态恢复检查（延迟5秒以确保TCP服务器已启动）
    def delayed_recovery_check():
        import time
        time.sleep(5)  # 等待TCP服务器完全启动
        with app.app_context():
            from .services.client_recovery import check_recovery_needed, recover_client_manager_state
            if check_recovery_needed():
                print("[启动] 检测到需要恢复客户端管理器状态")
                recover_client_manager_state()
            else:
                print("[启动] 客户端管理器状态正常，无需恢复")
    
    threading.Thread(target=delayed_recovery_check, daemon=True).start()

    # 启动游客清理线程（从模块启动）
    start_guest_cleanup(app)

    return app

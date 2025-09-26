"""
系统管理面板路由
提供系统管理相关的API接口
"""

from flask import Blueprint, jsonify, request, current_app, abort
from flask_login import login_required, current_user
import psutil
import os
import time
import json
from datetime import datetime, timedelta
from ...models import User, Role, InvitationCode, SystemLog, Client
from ...extensions import db

# 创建管理员蓝图
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# 检查用户权限装饰器
def admin_required(f):
    """检查用户是否为管理员"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': '未登录'}), 401
        if not hasattr(current_user, 'role') or not current_user.is_administrator():
            return jsonify({'error': '权限不足'}), 403
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/system-info')
@login_required
@admin_required
def get_system_info():
    """获取系统信息"""
    try:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存使用率
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # 磁盘使用率
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        
        # 系统运行时间
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        uptime_days = int(uptime_seconds // 86400)
        
        return jsonify({
            'cpu_usage': round(cpu_percent, 1),
            'memory_usage': round(memory_percent, 1),
            'disk_usage': round(disk_percent, 1),
            'uptime': uptime_days,
            'boot_time': datetime.fromtimestamp(boot_time).isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"获取系统信息失败: {e}")
        return jsonify({'error': '获取系统信息失败'}), 500

@admin_bp.route('/clients')
@login_required
@admin_required
def get_clients():
    """获取客户端信息"""
    try:
        # 从数据库获取客户端信息
        clients = Client.query.all()
        clients_data = []
        
        for client in clients:
            client_data = {
                'id': client.id,
                'name': client.hostname or client.client_id,  # 使用hostname作为name
                'ip': client.ip_address,
                'status': client.status or 'offline',
                'last_seen': client.last_seen.strftime('%Y-%m-%d %H:%M:%S') if client.last_seen else '从未连接',
                'os_type': client.os_type,
                'os_version': client.os_version,
                'owner': client.owner.username if client.owner else '未知'
            }
            clients_data.append(client_data)
        
        # 统计在线客户端数量
        online_count = sum(1 for client in clients_data if client['status'] == 'online')
        
        return jsonify({
            'clients': clients_data,
            'total': len(clients_data),
            'online': online_count,
            'max': 100  # 假设最大连接数为100
        })
    except Exception as e:
        current_app.logger.error(f"获取客户端信息失败: {e}")
        return jsonify({'error': '获取客户端信息失败'}), 500

@admin_bp.route('/database')
@login_required
@admin_required
def get_database_info():
    """获取数据库信息"""
    try:
        # 检查数据库连接
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        db_type = db_uri.split(':')[0] if db_uri else 'sqlite'
        
        # 默认值
        db_status = 'disconnected'
        db_size_mb = 0
        table_count = 0
        user_count = 0
        client_count = 0
        connection_count = 0
        log_count = 0
        response_time = 0
        db_path = ''
        
        try:
            # 测量数据库响应时间
            start_time = time.time()
            
            # 对于SQLite数据库，获取实际文件路径
            if db_type == 'sqlite':
                # 从URI中提取文件路径
                if ':///' in db_uri:
                    db_path = db_uri.split(':///', 1)[1]
                    # 如果是相对路径，需要结合Flask实例路径
                    if not os.path.isabs(db_path):
                        db_path = os.path.join(current_app.instance_path, db_path)
                else:
                    db_path = current_app.config.get('DATABASE_PATH', 'app.db')
                    if not os.path.isabs(db_path):
                        db_path = os.path.join(current_app.instance_path, db_path)
                
                # 检查数据库文件是否存在
                if os.path.exists(db_path):
                    db_status = 'connected'
                    db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
                else:
                    db_status = 'not_found'
            else:
                # 对于其他数据库类型，尝试连接测试
                db_status = 'connected'
            
            # 使用SQLAlchemy获取表信息
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            table_count = len(table_names)
            
            # 获取各表记录数
            user_count = User.query.count()
            client_count = Client.query.count()
            log_count = SystemLog.query.count()
            
            # 如果能执行到这里，说明数据库连接正常
            if db_status != 'not_found':
                db_status = 'connected'
            
            # 计算响应时间
            response_time = round((time.time() - start_time) * 1000, 2)
            
        except Exception as db_error:
            current_app.logger.error(f"数据库连接失败: {db_error}")
            db_status = 'error'
        
        # 获取连接池信息
        try:
            pool = db.engine.pool
            pool_size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            active_connections = checked_out
        except:
            pool_size = 5  # 默认值
            checked_in = 0
            checked_out = 0
            active_connections = 0
        
        return jsonify({
            'status': db_status,
            'type': db_type or 'sqlite',
            'pool_size': pool_size,
            'response_time': response_time,
            'active_connections': active_connections,
            'database': {
                'type': db_type or 'sqlite',
                'status': db_status,
                'path': db_path,
                'size_mb': db_size_mb,
                'table_count': table_count
            },
            'statistics': {
                'user_count': user_count,
                'client_count': client_count,
                'connection_count': connection_count,
                'log_count': log_count
            }
        })
    except Exception as e:
        current_app.logger.error(f"获取数据库信息失败: {e}")
        return jsonify({'error': '获取数据库信息失败'}), 500
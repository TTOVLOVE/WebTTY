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
import sqlite3
import uuid
from ...models import User, Role, InvitationCode, SystemLog
from ...extensions import db

# 创建管理面板蓝图
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
            'uptime': uptime_days
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
        from ...models import Client
        from datetime import datetime
        
        # 获取所有客户端
        clients = Client.query.all()
        
        # 计算在线客户端数量
        online_clients = Client.query.filter_by(status='online').count()
        
        # 准备客户端列表数据
        client_list = []
        for client in clients:
            # 计算最后在线时间的显示格式
            last_seen_str = '未知'
            if client.last_seen:
                time_diff = datetime.utcnow() - client.last_seen
                if time_diff.days > 0:
                    last_seen_str = f'{time_diff.days}天前'
                elif time_diff.seconds >= 3600:
                    last_seen_str = f'{time_diff.seconds // 3600}小时前'
                elif time_diff.seconds >= 60:
                    last_seen_str = f'{time_diff.seconds // 60}分钟前'
                else:
                    last_seen_str = f'{time_diff.seconds}秒前'
            
            client_list.append({
                'id': client.id,
                'name': f'Client-{client.client_id[:8]}',  # 使用客户端ID的前8位作为显示名称
                'status': client.status,
                'ip': client.ip_address or '未知',
                'last_seen': last_seen_str if client.status != 'online' else '在线'
            })
        
        clients_data = {
            'total': len(clients),
            'online': online_clients,
            'max': 100,  # 最大客户端数量限制
            'clients': client_list
        }
        
        return jsonify(clients_data)
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
        db_path = current_app.config.get('DATABASE_PATH', 'app.db')
        db_type = current_app.config.get('SQLALCHEMY_DATABASE_URI', '').split(':')[0]
        
        # 默认值
        db_status = 'not_found'
        db_size_mb = 0
        table_count = 0
        user_count = 0
        client_count = 0
        connection_count = 0
        log_count = 0
        response_time = 0
        
        # 测量数据库响应时间
        start_time = time.time()
        
        try:
            # 使用SQLAlchemy获取表信息
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            table_count = len(tables)
            
            # 获取各表记录数
            from ...models import User, Client, Connection, SystemLog
            user_count = User.query.count()
            client_count = Client.query.count()
            connection_count = Connection.query.count()
            log_count = SystemLog.query.count()
            
            # 计算响应时间
            response_time = round((time.time() - start_time) * 1000, 2)  # 毫秒
            
            # 获取数据库文件大小（如果是SQLite）
            if db_type == 'sqlite' and os.path.exists(db_path):
                db_size = os.path.getsize(db_path)
                db_size_mb = round(db_size / (1024 * 1024), 2)
            
            db_status = 'connected'
            
        except Exception as e:
            current_app.logger.error(f"数据库连接失败: {e}")
            db_status = 'error'
        
        # 获取活跃连接数
        active_connections = 1  # 至少有当前连接
        try:
            if hasattr(db.engine, 'pool'):
                active_connections = db.engine.pool.checkedout()
        except:
            pass
        
        # 获取连接池大小
        pool_size = 5  # 默认值
        try:
            if hasattr(db.engine, 'pool'):
                pool_size = db.engine.pool.size()
        except:
            pass
        
        return jsonify({
            'status': db_status,
            'type': db_type.upper() if db_type else 'SQLite',
            'pool_size': pool_size,
            'response_time': response_time,
            'active_connections': active_connections,
            'file_size_mb': db_size_mb,
            'table_count': table_count,
            'user_count': user_count,
            'client_count': client_count,
            'connection_count': connection_count,
            'log_count': log_count
        })
    except Exception as e:
        current_app.logger.error(f"获取数据库信息失败: {e}")
        return jsonify({'error': '获取数据库信息失败'}), 500

@admin_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    """获取用户列表"""
    try:
        # 从数据库获取用户列表
        from ...models import User
        
        # 查询所有用户
        db_users = User.query.all()
        
        users = []
        for user in db_users:
            # 格式化最后登录时间
            last_login = '未登录'
            if user.last_login:
                last_login = user.last_login.strftime('%Y-%m-%d %H:%M:%S')
            
            # 获取用户状态
            status = 'active' if user.is_active else 'inactive'
            
            # 获取角色名称
            role_name = '用户'
            if user.role:
                role_name = user.role.name
            
            users.append({
                'id': user.id,
                'username': user.username,
                'role': role_name,
                'status': status,
                'last_login': last_login
            })
        
        return jsonify({'users': users})
    except Exception as e:
        current_app.logger.error(f"获取用户列表失败: {e}")
        return jsonify({'error': '获取用户列表失败'}), 500

@admin_bp.route('/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    """创建新用户"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['username', 'email', 'password', 'role']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'缺少必需字段: {field}'}), 400
        
        # 验证角色
        valid_roles = ['admin', 'user', 'guest']
        if data['role'] not in valid_roles:
            return jsonify({'error': '无效的用户角色'}), 400
        
        # 检查用户名和邮箱是否已存在
        from ...models import User, Role, SystemLog
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': '用户名已存在'}), 400
            
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': '邮箱已存在'}), 400
        
        # 获取对应的角色对象
        role = Role.query.filter_by(name=data['role']).first()
        if not role:
            return jsonify({'error': '角色不存在'}), 400
        
        # 创建新用户
        new_user = User(
            username=data['username'],
            email=data['email'],
            role=role,
            is_active=True
        )
        
        # 设置密码
        new_user.password = data['password']
        
        # 保存到数据库
        db.session.add(new_user)
        db.session.commit()
        
        # 记录操作日志
        SystemLog.log_action(
            user_id=current_user.id,
            action='create_user',
            resource_type='user',
            resource_id=str(new_user.id),
            ip_address=request.remote_addr,
            details=f"创建新用户: {new_user.username}",
            status='success'
        )
        
        current_app.logger.info(f"创建新用户: {data['username']}")
        
        return jsonify({
            'message': '用户创建成功',
            'user_id': new_user.id
        })
    except Exception as e:
        current_app.logger.error(f"创建用户失败: {e}")
        # 记录失败日志
        if current_user and current_user.is_authenticated:
            SystemLog.log_action(
                user_id=current_user.id,
                action='create_user',
                resource_type='user',
                ip_address=request.remote_addr,
                details=f"创建用户失败: {str(e)}",
                status='failed'
            )
        return jsonify({'error': '创建用户失败'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def get_user_detail(user_id):
    """获取用户详情"""
    try:
        # 从数据库获取用户信息
        from ...models import User
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # 获取角色名称
        role_name = '用户'
        if user.role:
            role_name = user.role.name
        
        # 格式化最后登录时间
        last_login = '未登录'
        if user.last_login:
            last_login = user.last_login.strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建用户详情数据
        user_detail = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': role_name,
            'status': 'active' if user.is_active else 'inactive',
            'last_login': last_login,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return jsonify({'user': user_detail})
    except Exception as e:
        current_app.logger.error(f"获取用户详情失败: {e}")
        return jsonify({'error': '获取用户详情失败'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """更新用户信息"""
    try:
        data = request.get_json()
        
        # 从数据库获取用户信息
        from ...models import User, Role, SystemLog
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # 验证必需字段
        required_fields = ['username', 'email', 'role', 'status']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必需字段: {field}'}), 400
        
        # 验证角色
        valid_roles = ['admin', 'user', 'guest']
        if data['role'] not in valid_roles:
            return jsonify({'error': '无效的用户角色'}), 400
        
        # 验证状态
        valid_status = ['active', 'inactive']
        if data['status'] not in valid_status:
            return jsonify({'error': '无效的用户状态'}), 400
        
        # 更新用户信息
        user.username = data['username']
        user.email = data['email']
        
        # 更新角色
        role = Role.query.filter_by(name=data['role']).first()
        if role:
            user.role = role
        
        # 更新状态
        user.is_active = (data['status'] == 'active')
        
        # 如果提供了新密码，则更新密码
        if data.get('password') and data['password'].strip():
            user.set_password(data['password'])
        
        # 记录操作日志
        SystemLog.log_action(
            user_id=current_user.id,
            action='update_user',
            resource_type='user',
            resource_id=str(user_id),
            ip_address=request.remote_addr,
            details=f"更新用户信息: {user.username}",
            status='success'
        )
        
        # 保存更新
        db.session.commit()
        
        current_app.logger.info(f"更新用户信息: {user_id}")
        
        return jsonify({'message': '用户信息更新成功'})
    except Exception as e:
        current_app.logger.error(f"更新用户信息失败: {e}")
        return jsonify({'error': '更新用户信息失败'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户"""
    try:
        # 从数据库删除用户
        from ...models import User, SystemLog
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # 不允许删除自己
        if user.id == current_user.id:
            return jsonify({'error': '不能删除当前登录的用户'}), 400
        
        # 记录操作日志
        SystemLog.log_action(
            user_id=current_user.id,
            action='delete_user',
            resource_type='user',
            resource_id=str(user_id),
            ip_address=request.remote_addr,
            details=f"删除用户: {user.username}",
            status='success'
        )
        
        # 删除用户
        db.session.delete(user)
        db.session.commit()
        
        current_app.logger.info(f"删除用户: {user_id}")
        
        return jsonify({'message': '用户删除成功'})
    except Exception as e:
        current_app.logger.error(f"删除用户失败: {e}")
        return jsonify({'error': '删除用户失败'}), 500

@admin_bp.route('/ports', methods=['PUT'])
@login_required
@admin_required
def update_port():
    """更新端口设置"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        if not data.get('service') or not data.get('port'):
            return jsonify({'error': '缺少必需字段'}), 400
        
        service = data['service']
        port = data['port']
        
        # 验证端口号
        if not isinstance(port, int) or port < 1 or port > 65535:
            return jsonify({'error': '无效的端口号'}), 400
        
        # 这里应该更新配置文件或数据库中的端口设置
        # 目前只是记录日志
        
        current_app.logger.info(f"更新端口设置: {service} -> {port}")
        
        return jsonify({'message': '端口设置更新成功'})
    except Exception as e:
        current_app.logger.error(f"更新端口设置失败: {e}")
        return jsonify({'error': '更新端口设置失败'}), 500

@admin_bp.route('/domains', methods=['PUT'])
@login_required
@admin_required
def update_domain():
    """更新域名设置"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        if not data.get('type') or not data.get('domain'):
            return jsonify({'error': '缺少必需字段'}), 400
        
        domain_type = data['type']
        domain = data['domain']
        
        # 这里应该更新配置文件或数据库中的域名设置
        # 目前只是记录日志
        
        current_app.logger.info(f"更新域名设置: {domain_type} -> {domain}")
        
        return jsonify({'message': '域名设置更新成功'})
    except Exception as e:
        current_app.logger.error(f"更新域名设置失败: {e}")
        return jsonify({'error': '更新域名设置失败'}), 500

@admin_bp.route('/ssl/upload', methods=['POST'])
@login_required
@admin_required
def upload_ssl():
    """上传SSL证书"""
    try:
        # 这里应该处理SSL证书文件上传
        # 目前只是返回成功响应
        
        current_app.logger.info("SSL证书上传")
        
        return jsonify({'message': 'SSL证书上传成功'})
    except Exception as e:
        current_app.logger.error(f"SSL证书上传失败: {e}")
        return jsonify({'error': 'SSL证书上传失败'}), 500

@admin_bp.route('/keys/<key_type>', methods=['GET'])
@login_required
@admin_required
def get_key(key_type):
    """获取密钥信息"""
    try:
        # 这里应该从安全存储中获取密钥信息
        # 目前返回模拟数据
        
        if key_type not in ['rsa', 'ed25519']:
            return jsonify({'error': '无效的密钥类型'}), 400
        
        # 模拟密钥信息（实际应用中不应该返回完整密钥）
        key_info = {
            'type': key_type,
            'fingerprint': f'{key_type.upper()}_FINGERPRINT_HERE',
            'created': '2024-01-01 00:00:00',
            'status': 'active'
        }
        
        return jsonify(key_info)
    except Exception as e:
        current_app.logger.error(f"获取密钥信息失败: {e}")
        return jsonify({'error': '获取密钥信息失败'}), 500

@admin_bp.route('/keys/<key_type>/regenerate', methods=['POST'])
@login_required
@admin_required
def regenerate_key(key_type):
    """重新生成密钥"""
    try:
        if key_type not in ['rsa', 'ed25519']:
            return jsonify({'error': '无效的密钥类型'}), 400
        
        # 这里应该重新生成密钥
        # 目前只是记录日志
        
        current_app.logger.info(f"重新生成密钥: {key_type}")
        
        return jsonify({'message': f'{key_type.upper()}密钥重新生成成功'})
    except Exception as e:
        current_app.logger.error(f"重新生成密钥失败: {e}")
        return jsonify({'error': '重新生成密钥失败'}), 500

@admin_bp.route('/tokens/<token_type>', methods=['GET'])
@login_required
@admin_required
def get_token(token_type):
    """获取令牌信息"""
    try:
        if token_type not in ['api', 'websocket']:
            return jsonify({'error': '无效的令牌类型'}), 400
        
        # 从配置或数据库获取令牌信息
        token_key = f'{token_type.upper()}_TOKEN'
        token_value = current_app.config.get(token_key, '')
        
        # 如果配置中没有令牌，尝试从数据库获取
        if not token_value:
            # 这里可以添加从数据库获取令牌的代码
            # 例如：从系统设置表中获取
            pass
        
        # 获取令牌创建和过期时间
        from datetime import datetime, timedelta
        created_at = current_app.config.get(f'{token_key}_CREATED', datetime.utcnow() - timedelta(days=30))
        expires_at = current_app.config.get(f'{token_key}_EXPIRES', datetime.utcnow() + timedelta(days=365))
        
        # 如果是日期对象，格式化为字符串
        if isinstance(created_at, datetime):
            created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(expires_at, datetime):
            expires_at = expires_at.strftime('%Y-%m-%d %H:%M:%S')
        
        # 确定令牌状态
        status = 'active'
        if not token_value:
            status = 'not_generated'
        elif isinstance(expires_at, str):
            try:
                expires_datetime = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
                if expires_datetime < datetime.utcnow():
                    status = 'expired'
            except:
                pass
        
        # 为安全起见，只显示令牌的一部分
        masked_token = ''
        if token_value:
            if len(token_value) > 8:
                masked_token = token_value[:4] + '*' * (len(token_value) - 8) + token_value[-4:]
            else:
                masked_token = '*' * len(token_value)
        
        token_info = {
            'type': token_type,
            'token': masked_token,
            'created': created_at,
            'expires': expires_at,
            'status': status
        }
        
        return jsonify(token_info)
    except Exception as e:
        current_app.logger.error(f"获取令牌信息失败: {e}")
        return jsonify({'error': '获取令牌信息失败'}), 500

@admin_bp.route('/tokens/<token_type>/regenerate', methods=['POST'])
@login_required
@admin_required
def regenerate_token(token_type):
    """重新生成令牌"""
    try:
        if token_type not in ['api', 'websocket']:
            return jsonify({'error': '无效的令牌类型'}), 400
        
        # 生成新的令牌
        import secrets
        import string
        from datetime import datetime, timedelta
        
        # 生成32位随机字符串作为令牌
        alphabet = string.ascii_letters + string.digits
        new_token = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        # 设置令牌的创建时间和过期时间
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(days=365)  # 默认有效期一年
        
        # 保存令牌到应用配置
        token_key = f'{token_type.upper()}_TOKEN'
        current_app.config[token_key] = new_token
        current_app.config[f'{token_key}_CREATED'] = created_at
        current_app.config[f'{token_key}_EXPIRES'] = expires_at
        
        # 这里可以添加将令牌保存到数据库的代码
        # 例如：更新系统设置表中的令牌
        
        # 记录日志
        from ...models import SystemLog
        SystemLog.create(
            user_id=current_user.id,
            action=f'重新生成{token_type}令牌',
            resource_type='token',
            resource_id=token_type,
            status='success',
            ip_address=request.remote_addr
        )
        
        current_app.logger.info(f"重新生成令牌: {token_type}")
        
        # 为安全起见，只返回令牌的一部分
        masked_token = new_token[:4] + '*' * (len(new_token) - 8) + new_token[-4:]
        
        return jsonify({
            'message': f'{token_type.upper()}令牌重新生成成功',
            'token': masked_token,
            'created': created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'expires': expires_at.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'active'
        })
    except Exception as e:
        current_app.logger.error(f"重新生成令牌失败: {e}")
        return jsonify({'error': '重新生成令牌失败'}), 500

@admin_bp.route('/export/users')
@login_required
@admin_required
def export_users():
    """导出用户数据"""
    try:
        import csv
        import os
        import io
        from datetime import datetime
        from flask import send_file
        from ...models import User, Role
        
        # 从数据库获取所有用户
        users = User.query.all()
        
        # 创建CSV文件
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f'users_export_{timestamp}.csv'
        downloads_dir = os.path.join(current_app.root_path, 'static', 'downloads')
        
        # 确保下载目录存在
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
        
        filepath = os.path.join(downloads_dir, filename)
        
        # 写入CSV文件
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['用户ID', '用户名', '邮箱', '角色', '状态', '创建时间', '最后登录时间']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for user in users:
                # 获取角色名称
                role_name = '用户'
                if user.role and hasattr(user.role, 'name'):
                    role_name = user.role.name
                
                # 获取用户状态
                status = '活跃' if user.is_active else '禁用'
                
                # 格式化时间
                created_at = user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else ''
                last_login = user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else ''
                
                writer.writerow({
                    '用户ID': user.id,
                    '用户名': user.username,
                    '邮箱': user.email,
                    '角色': role_name,
                    '状态': status,
                    '创建时间': created_at,
                    '最后登录时间': last_login
                })
        
        # 记录日志
        from ...models import SystemLog
        SystemLog.log_action(
            user_id=current_user.id,
            action='导出用户数据',
            resource_type='user',
            resource_id='all',
            status='success',
            ip_address=request.remote_addr,
            details='导出所有用户数据'
        )
        
        current_app.logger.info("导出用户数据")
        
        # 返回下载链接
        download_url = f'/static/downloads/{filename}'
        return jsonify({
            'message': '用户数据导出成功',
            'download_url': download_url
        })
    except Exception as e:
        current_app.logger.error(f"导出用户数据失败: {e}")
        return jsonify({'error': '导出用户数据失败'}), 500

@admin_bp.route('/logs')
@login_required
@admin_required
def get_logs():
    """获取系统日志"""
    try:
        # 从数据库获取系统日志
        from ...models import SystemLog, User
        
        # 获取最近的50条日志记录，按时间倒序排列
        db_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(50).all()
        
        logs = []
        for log in db_logs:
            # 获取用户名
            username = '系统'
            if log.user_id:
                user = User.query.get(log.user_id)
                if user:
                    username = user.username
            
            # 确定日志级别
            level = 'INFO'
            if log.status == 'failed':
                level = 'ERROR'
            elif 'warning' in log.action.lower() or 'warn' in log.action.lower():
                level = 'WARNING'
            
            # 构建日志消息
            message = f'{log.action}'
            if log.resource_type and log.resource_id:
                message += f' - {log.resource_type}:{log.resource_id}'
            if log.details:
                message += f' - {log.details}'
            
            logs.append({
                'timestamp': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'level': level,
                'message': message,
                'user': username,
                'ip': log.ip_address or '未知'
            })
        
        return jsonify({'logs': logs})
    except Exception as e:
        current_app.logger.error(f"获取系统日志失败: {e}")
        return jsonify({'error': '获取系统日志失败'}), 500

@admin_bp.route('/stats')
@login_required
@admin_required
def get_stats():
    """获取系统统计信息"""
    try:
        # 从数据库获取真实的系统统计信息
        # 获取用户统计信息
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        
        # 获取连接统计信息（假设有一个Connection模型）
        # 如果没有Connection模型，可以从其他地方获取或保留默认值
        total_connections = 0
        active_connections = 0
        try:
            # 尝试从数据库或其他来源获取连接信息
            # 这里可以根据实际情况调整
            conn = sqlite3.connect(current_app.config.get('DATABASE_URI', 'app.db'))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM connections")
            total_connections = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM connections WHERE status='active'")
            active_connections = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            current_app.logger.warning(f"获取连接统计信息失败: {e}")
            # 如果获取失败，使用默认值
            total_connections = 0
            active_connections = 0
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'total_connections': total_connections,
            'active_connections': active_connections,
            'system_uptime': int(time.time() - psutil.boot_time()),
            'disk_usage': psutil.disk_usage('/').percent,
            'memory_usage': psutil.virtual_memory().percent,
            'cpu_usage': psutil.cpu_percent(interval=1)
        }
        
        return jsonify(stats)
    except Exception as e:
        current_app.logger.error(f"获取系统统计信息失败: {e}")
        return jsonify({'error': '获取系统统计信息失败'}), 500

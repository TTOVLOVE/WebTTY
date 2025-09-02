#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统管理面板路由
提供系统管理相关的API接口
"""

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
import psutil
import os
import time
import json
from datetime import datetime
import sqlite3

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
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
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
        # 这里可以从数据库或内存中获取客户端信息
        # 目前返回模拟数据
        clients_data = {
            'total': 15,
            'online': 8,
            'max': 100,
            'clients': [
                {
                    'id': 1,
                    'name': 'Client-001',
                    'status': 'online',
                    'ip': '192.168.1.100',
                    'last_seen': '2分钟前'
                },
                {
                    'id': 2,
                    'name': 'Client-002',
                    'status': 'offline',
                    'ip': '192.168.1.101',
                    'last_seen': '1小时前'
                },
                {
                    'id': 3,
                    'name': 'Client-003',
                    'status': 'connecting',
                    'ip': '192.168.1.102',
                    'last_seen': '正在连接'
                }
            ]
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
        
        if os.path.exists(db_path):
            # 获取数据库文件大小
            db_size = os.path.getsize(db_path)
            db_size_mb = round(db_size / (1024 * 1024), 2)
            
            # 尝试连接数据库
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # 获取表数量
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                table_count = len(tables)
                
                # 获取用户表记录数
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                
                conn.close()
                
                db_status = 'connected'
            except Exception as e:
                current_app.logger.error(f"数据库连接失败: {e}")
                db_status = 'error'
                table_count = 0
                user_count = 0
        else:
            db_status = 'not_found'
            db_size_mb = 0
            table_count = 0
            user_count = 0
        
        return jsonify({
            'status': db_status,
            'type': 'SQLite',
            'pool_size': 10,
            'response_time': 5,
            'active_connections': 3,
            'file_size_mb': db_size_mb,
            'table_count': table_count,
            'user_count': user_count
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
        # 这里应该从数据库获取用户列表
        # 目前返回模拟数据
        users = [
            {
                'id': 1,
                'username': 'admin',
                'role': 'admin',
                'status': 'active',
                'last_login': '2024-01-15 10:30:00'
            },
            {
                'id': 2,
                'username': 'user1',
                'role': 'user',
                'status': 'active',
                'last_login': '2024-01-15 09:15:00'
            },
            {
                'id': 3,
                'username': 'guest1',
                'role': 'guest',
                'status': 'inactive',
                'last_login': '2024-01-14 16:45:00'
            }
        ]
        
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
        
        # 这里应该将用户信息保存到数据库
        # 目前只是返回成功响应
        
        current_app.logger.info(f"创建新用户: {data['username']}")
        
        return jsonify({
            'message': '用户创建成功',
            'user_id': 999  # 模拟的用户ID
        })
    except Exception as e:
        current_app.logger.error(f"创建用户失败: {e}")
        return jsonify({'error': '创建用户失败'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户"""
    try:
        # 这里应该从数据库删除用户
        # 目前只是返回成功响应
        
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
        
        # 模拟令牌信息
        token_info = {
            'type': token_type,
            'token': f'{token_type.upper()}_TOKEN_HERE',
            'created': '2024-01-01 00:00:00',
            'expires': '2025-01-01 00:00:00',
            'status': 'active'
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
        
        # 这里应该重新生成令牌
        # 目前只是记录日志
        
        current_app.logger.info(f"重新生成令牌: {token_type}")
        
        return jsonify({'message': f'{token_type.upper()}令牌重新生成成功'})
    except Exception as e:
        current_app.logger.error(f"重新生成令牌失败: {e}")
        return jsonify({'error': '重新生成令牌失败'}), 500

@admin_bp.route('/export/users')
@login_required
@admin_required
def export_users():
    """导出用户数据"""
    try:
        # 这里应该生成用户数据导出文件
        # 目前只是返回成功响应
        
        current_app.logger.info("导出用户数据")
        
        return jsonify({
            'message': '用户数据导出成功',
            'download_url': '/downloads/users_export.csv'
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
        # 这里应该从日志文件或数据库中获取日志
        # 目前返回模拟数据
        
        logs = [
            {
                'timestamp': '2024-01-15 10:30:00',
                'level': 'INFO',
                'message': '系统启动成功'
            },
            {
                'timestamp': '2024-01-15 10:29:00',
                'level': 'INFO',
                'message': '数据库连接建立'
            },
            {
                'timestamp': '2024-01-15 10:28:00',
                'level': 'WARNING',
                'message': '检测到异常登录尝试'
            }
        ]
        
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
        # 获取系统统计信息
        stats = {
            'total_users': 15,
            'active_users': 8,
            'total_connections': 25,
            'active_connections': 12,
            'system_uptime': int(time.time() - psutil.boot_time()),
            'disk_usage': psutil.disk_usage('/').percent,
            'memory_usage': psutil.virtual_memory().percent,
            'cpu_usage': psutil.cpu_percent(interval=1)
        }
        
        return jsonify(stats)
    except Exception as e:
        current_app.logger.error(f"获取系统统计信息失败: {e}")
        return jsonify({'error': '获取系统统计信息失败'}), 500

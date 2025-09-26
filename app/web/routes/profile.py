from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import os
import json

# 创建个人信息蓝图
profile_bp = Blueprint('profile', __name__, url_prefix='/profile')

# 模拟用户数据存储（实际项目中应使用数据库）
USERS_FILE = 'data/users.json'

def load_users():
    """加载用户数据"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_users(users):
    """保存用户数据"""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_current_user():
    """获取当前用户信息"""
    # 使用Flask-Login的current_user
    if current_user.is_authenticated:
        # 从数据库用户转换为JSON格式用户数据
        users = load_users()
        user_id = current_user.username  # 使用用户名作为ID
        
        if user_id in users:
            user = users[user_id].copy()
            # 不返回密码
            user.pop('password', None)
            return user
        else:
            # 如果JSON文件中没有该用户，创建基本信息
            return {
                'user_id': current_user.username,
                'username': current_user.username,
                'email': getattr(current_user, 'email', ''),
                'phone': '',
                'department': '',
                'position': '',
                'description': '',
                'avatar': '/static/images/default-avatar.png',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'two_factor_enabled': False,
                'login_notifications': True,
                'session_timeout': 30,
                'password_last_changed': datetime.now().isoformat(),
                'failed_login_attempts': 0
            }
    return None

@profile_bp.route('/')
@login_required
def index():
    """个人信息页面"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    
    return render_template('dashboard/profile.html', user=user)

@profile_bp.route('/api/info')
def get_profile_info():
    """获取个人信息API"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': '用户未登录'})
    
    return jsonify({
        'success': True,
        'user': user
    })

@profile_bp.route('/api/update', methods=['POST'])
def update_profile():
    """更新个人信息API"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': '用户未登录'})
    
    try:
        data = request.get_json()
        users = load_users()
        user_id = current_user.username
        
        # 更新用户信息
        if user_id not in users:
            # 如果用户不存在，创建新用户记录
            users[user_id] = {
                'user_id': user_id,
                'username': user_id,
                'email': getattr(current_user, 'email', ''),
                'phone': '',
                'department': '',
                'position': '',
                'description': '',
                'avatar': '/static/images/default-avatar.png',
                'password': '',  # 密码由数据库管理，这里不存储
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'two_factor_enabled': False,
                'login_notifications': True,
                'session_timeout': 30,
                'password_last_changed': datetime.now().isoformat(),
                'failed_login_attempts': 0
            }
        
        # 更新允许修改的字段
        allowed_fields = ['username', 'email', 'phone', 'department', 'position', 'description']
        
        for field in allowed_fields:
            if field in data:
                users[user_id][field] = data[field]
        
        # 更新最后修改时间
        users[user_id]['updated_at'] = datetime.now().isoformat()
        
        save_users(users)
        
        return jsonify({
            'success': True,
            'message': '个人信息更新成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'更新失败: {str(e)}'
        })

@profile_bp.route('/api/change-password', methods=['POST'])
def change_password():
    """修改密码API"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': '用户未登录'})
    
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            return jsonify({'success': False, 'message': '请填写所有密码字段'})
        
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': '新密码和确认密码不匹配'})
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': '新密码长度至少6位'})
        
        users = load_users()
        user_id = current_user.username
        
        # 验证当前密码
        if not check_password_hash(users[user_id]['password'], current_password):
            return jsonify({'success': False, 'message': '当前密码错误'})
        
        # 更新密码
        users[user_id]['password'] = generate_password_hash(new_password)
        users[user_id]['updated_at'] = datetime.now().isoformat()
        
        save_users(users)
        
        return jsonify({
            'success': True,
            'message': '密码修改成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'密码修改失败: {str(e)}'
        })

@profile_bp.route('/api/upload-avatar', methods=['POST'])
def upload_avatar():
    """上传头像API"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': '用户未登录'})
    
    try:
        # 这里简化处理，实际项目中需要处理文件上传
        # 目前返回一个默认头像URL
        avatar_url = '/static/images/default-avatar.png'
        
        users = load_users()
        user_id = current_user.username
        users[user_id]['avatar'] = avatar_url
        users[user_id]['updated_at'] = datetime.now().isoformat()
        
        save_users(users)
        
        return jsonify({
            'success': True,
            'message': '头像上传成功',
            'avatar_url': avatar_url
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'头像上传失败: {str(e)}'
        })

@profile_bp.route('/api/activity-log')
def get_activity_log():
    """获取活动日志API"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': '用户未登录'})
    
    # 模拟活动日志数据
    activity_log = [
        {
            'id': 1,
            'action': '登录系统',
            'timestamp': '2024-01-15 09:30:00',
            'ip_address': '192.168.1.100',
            'user_agent': 'Chrome/120.0.0.0'
        },
        {
            'id': 2,
            'action': '修改个人信息',
            'timestamp': '2024-01-15 10:15:00',
            'ip_address': '192.168.1.100',
            'user_agent': 'Chrome/120.0.0.0'
        },
        {
            'id': 3,
            'action': '查看连接列表',
            'timestamp': '2024-01-15 11:00:00',
            'ip_address': '192.168.1.100',
            'user_agent': 'Chrome/120.0.0.0'
        },
        {
            'id': 4,
            'action': '创建新连接',
            'timestamp': '2024-01-15 14:20:00',
            'ip_address': '192.168.1.100',
            'user_agent': 'Chrome/120.0.0.0'
        },
        {
            'id': 5,
            'action': '执行漏洞扫描',
            'timestamp': '2024-01-15 15:45:00',
            'ip_address': '192.168.1.100',
            'user_agent': 'Chrome/120.0.0.0'
        }
    ]
    
    return jsonify({
        'success': True,
        'activity_log': activity_log
    })

@profile_bp.route('/api/security-settings')
def get_security_settings():
    """获取安全设置API"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': '用户未登录'})
    
    users = load_users()
    user_id = current_user.username
    user_data = users.get(user_id, {})
    
    security_settings = {
        'two_factor_enabled': user_data.get('two_factor_enabled', False),
        'login_notifications': user_data.get('login_notifications', True),
        'session_timeout': user_data.get('session_timeout', 30),
        'password_last_changed': user_data.get('password_last_changed', '2024-01-01'),
        'failed_login_attempts': user_data.get('failed_login_attempts', 0)
    }
    
    return jsonify({
        'success': True,
        'security_settings': security_settings
    })

@profile_bp.route('/api/update-security', methods=['POST'])
def update_security_settings():
    """更新安全设置API"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': '用户未登录'})
    
    try:
        data = request.get_json()
        users = load_users()
        user_id = current_user.username
        
        # 更新安全设置
        allowed_settings = ['two_factor_enabled', 'login_notifications', 'session_timeout']
        
        for setting in allowed_settings:
            if setting in data:
                users[user_id][setting] = data[setting]
        
        users[user_id]['updated_at'] = datetime.now().isoformat()
        save_users(users)
        
        return jsonify({
            'success': True,
            'message': '安全设置更新成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'安全设置更新失败: {str(e)}'
        })

# 初始化默认用户数据（如果不存在）
def init_default_user():
    """初始化默认用户数据"""
    users = load_users()
    
    if not users:
        default_user = {
            'admin': {
                'user_id': 'admin',
                'username': 'admin',
                'email': 'admin@example.com',
                'phone': '13800138000',
                'department': 'IT部门',
                'position': '系统管理员',
                'description': '系统管理员账户',
                'avatar': '/static/images/default-avatar.png',
                'password': generate_password_hash('admin123'),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'two_factor_enabled': False,
                'login_notifications': True,
                'session_timeout': 30,
                'password_last_changed': datetime.now().isoformat(),
                'failed_login_attempts': 0
            }
        }
        save_users(default_user)

# 在蓝图注册时初始化默认用户
init_default_user()
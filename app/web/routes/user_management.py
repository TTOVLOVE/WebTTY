"""
用户管理页面路由
"""

from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from ...models import User, Role, SystemLog
from ...extensions import db

user_management_bp = Blueprint('user_management', __name__, url_prefix='/user-management')

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

@user_management_bp.route('/')
@login_required
def user_management():
    """用户管理页面"""
    if not hasattr(current_user, 'role') or not current_user.is_administrator():
        return render_template('dashboard/error.html',
                             error_message='权限不足，需要管理员权限才能访问此页面')

    page_data = {
        'current_user': current_user,
        'page_title': '用户管理',
        'breadcrumb': [
            {'name': '首页', 'url': '/'},
            {'name': '系统管理', 'url': '/admin'},
            {'name': '用户管理', 'url': None}
        ]
    }

    return render_template('dashboard/user_management.html', **page_data)

@user_management_bp.route('/api/users')
@login_required
@admin_required
def get_users():
    """获取用户列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # 分页查询用户
        users_pagination = User.query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        users_data = []
        for user in users_pagination.items:
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role.name if user.role else 'user',
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
            users_data.append(user_data)

        return jsonify({
            'users': users_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': users_pagination.total,
                'pages': users_pagination.pages,
                'has_prev': users_pagination.has_prev,
                'has_next': users_pagination.has_next
            }
        })
    except Exception as e:
        current_app.logger.error(f"获取用户列表失败: {e}")
        return jsonify({'error': '获取用户列表失败'}), 500

@user_management_bp.route('/api/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    """创建新用户"""
    try:
        data = request.get_json()
        print(f"接收到的用户数据: {data}")  # 打印接收到的数据，便于调试

        # 验证必需字段
        required_fields = ['username', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'缺少必需字段: {field}'}), 400

        # 检查用户名是否已存在
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': '用户名已存在'}), 400

        # 检查邮箱是否已存在
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': '邮箱已存在'}), 400

        # 创建新用户
        user = User(
            username=data['username'],
            email=data['email'],
            is_active=data.get('is_active', True)
        )
        user.password = data['password']

        # 设置角色
        role_name = data.get('role', 'user')
        # 确保 role_type 字段有值，即使是字符串形式
        if hasattr(user, 'role_type'):
            user.role_type = role_name
        
        # 查找或创建角色
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            # 如果角色不存在，创建一个新角色
            role = Role(name=role_name, description=f"{role_name} role")
            db.session.add(role)
            db.session.flush()  # 刷新会话，获取新角色的ID
        
        user.role = role
        user.role_id = role.id

        db.session.add(user)
        db.session.commit()

        # 记录操作日志
        log = SystemLog(
            user_id=current_user.id,
            action='create_user',
            details=f"创建用户: {user.username}",
            ip_address=request.remote_addr,
            status='success'  # 确保状态字段有值
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({'message': '用户创建成功', 'user_id': user.id}), 201
    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"创建用户失败，详细错误: {error_details}")  # 打印详细错误堆栈
        
        # 记录失败日志
        try:
            log = SystemLog(
                user_id=current_user.id,
                action='create_user_failed',
                details=f"创建用户失败: {str(e)}",
                ip_address=request.remote_addr,
                status='failed'  # 确保状态字段有值
            )
            db.session.add(log)
            db.session.commit()
        except Exception as log_error:
            print(f"记录错误日志失败: {log_error}")
            
        return jsonify({'error': '创建用户失败'}), 500

@user_management_bp.route('/api/users/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def get_user(user_id):
    """获取单个用户信息"""
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role.name if user.role else 'user',
        'is_active': user.is_active
    })

@user_management_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """更新用户信息"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if 'username' in data and data['username'] != user.username:
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': '用户名已存在'}), 400
        user.username = data['username']

    if 'email' in data and data['email'] != user.email:
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': '邮箱已存在'}), 400
        user.email = data['email']

    if 'password' in data and data['password']:
        user.set_password(data['password'])

    if 'role' in data:
        role = Role.query.filter_by(name=data['role']).first()
        if role:
            user.role = role

    if 'is_active' in data:
        user.is_active = data['is_active']

    db.session.commit()
    return jsonify({'message': '用户更新成功'})

@user_management_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户"""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': '用户删除成功'})
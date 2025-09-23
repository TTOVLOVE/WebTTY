from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from ...models import User, Role, InvitationCode, SystemLog
from ...extensions import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.authenticate(username, password)
        if user:
            login_user(user)
            
            # 更新最后登录时间
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # 记录登录日志
            SystemLog.log_action(
                user_id=user.id,
                action='login',
                ip_address=request.remote_addr,
                status='success'
            )
            
            flash('登录成功！', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('用户名或密码错误！', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        invitation_code = request.form.get('invitation_code')
        
        # 验证邀请码
        invite = InvitationCode.query.filter_by(code=invitation_code, is_used=False).first()
        if not invite:
            flash('邀请码无效或已被使用', 'error')
            return render_template('auth/register.html')
            
        # 检查用户名和邮箱是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return render_template('auth/register.html')
            
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册', 'error')
            return render_template('auth/register.html')
        
        # 获取创建邀请码的用户
        creator = User.query.get(invite.created_by)
        
        # 创建新用户
        user_role = Role.query.filter_by(name='user').first()
        new_user = User(
            username=username,
            email=email,
            password=password,  # 这里会调用setter方法进行哈希处理
            role_id=user_role.id,
            parent_id=creator.id if creator else None
        )
        
        # 标记邀请码为已使用
        invite.is_used = True
        invite.used_by = new_user.id
        invite.used_at = datetime.utcnow()
        
        db.session.add(new_user)
        db.session.commit()
        
        # 记录注册日志
        SystemLog.log_action(
            user_id=new_user.id,
            action='register',
            ip_address=request.remote_addr,
            details=f'通过邀请码 {invitation_code} 注册',
            status='success'
        )
        
        flash('注册成功，请登录', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """用户登出"""
    logout_user()
    flash('已成功登出！', 'success')
    return redirect(url_for('auth.login'))

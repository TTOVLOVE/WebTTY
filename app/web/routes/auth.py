from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import desc
import random
import string
from ...models import User, Role, InvitationCode, SystemLog, UserLoginLog, UserSecurityInfo
from ...extensions import db
from ...utils.captcha import CaptchaGenerator

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/captcha')
def get_captcha():
    """获取验证码图片"""
    generator = CaptchaGenerator()
    captcha_data = generator.generate_captcha()
    return jsonify({
        'image': captcha_data['image']
    })

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        captcha_input = request.form.get('captcha')
        
        # 验证验证码
        if not CaptchaGenerator.verify_captcha(captcha_input):
            flash('验证码错误！', 'error')
            return render_template('auth/login.html')
        
        user = User.authenticate(username, password)
        if user:
            login_user(user)
            
            # 更新最后登录时间 + 写入用户登录日志
            try:
                ip = request.remote_addr
                user_agent = request.headers.get('User-Agent', '')

                user.last_login = datetime.utcnow()
                
                # 记录成功登录日志
                login_log = UserLoginLog(
                    user_id=user.id,
                    login_time=datetime.utcnow(),
                    ip_address=ip,
                    user_agent=user_agent,
                    login_status='success'
                )
                db.session.add(login_log)
                
                # 确保/更新安全信息
                security = UserSecurityInfo.query.filter_by(user_id=user.id).first()
                if not security:
                    security = UserSecurityInfo(
                        user_id=user.id,
                        password_last_changed=user.created_at
                    )
                    db.session.add(security)
                
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"记录登录日志失败: {e}")
            
            # 记录系统日志（独立提交）
            SystemLog.log_action(
                user_id=user.id,
                action='login',
                ip_address=request.remote_addr,
                status='success'
            )
            
            flash('登录成功！', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            # 登录失败也尝试记录一次失败登录（若能匹配到用户ID）
            try:
                ip = request.remote_addr
                user_agent = request.headers.get('User-Agent', '')
                failed_user = User.query.filter_by(username=username).first()
                if failed_user:
                    db.session.add(UserLoginLog(
                        user_id=failed_user.id,
                        login_time=datetime.utcnow(),
                        ip_address=ip,
                        user_agent=user_agent,
                        login_status='failed',
                        failure_reason='invalid_credentials'
                    ))
                    db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"记录失败登录日志失败: {e}")
            
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
    # 在登出前补充最近一次登录会话的登出时间
    try:
        last_log = UserLoginLog.query.filter_by(user_id=current_user.id, login_status='success') \
            .order_by(desc(UserLoginLog.login_time)).first()
        if last_log and last_log.logout_time is None:
            last_log.logout_time = datetime.utcnow()
            if last_log.login_time:
                last_log.session_duration = int((last_log.logout_time - last_log.login_time).total_seconds())
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"更新登出时间失败: {e}")

    logout_user()
    flash('已成功登出！', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/guest-login', methods=['POST'])
def guest_login():
    """游客登录"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    try:
        # 生成随机游客用户名
        guest_username = generate_guest_username()
        
        # 获取游客角色（如果不存在则创建）
        guest_role = Role.query.filter_by(name='guest').first()
        if not guest_role:
            guest_role = Role(name='guest', description='游客用户')
            db.session.add(guest_role)
            db.session.flush()  # 获取ID但不提交
        
        # 创建游客用户
        guest_user = User(
            username=guest_username,
            email=f"{guest_username}@guest.local",
            password_hash=generate_password_hash('guest_temp_password'),
            role_id=guest_role.id,
            is_active=True
        )
        db.session.add(guest_user)
        db.session.flush()  # 获取用户ID
        
        # 记录登录日志
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        login_log = UserLoginLog(
            user_id=guest_user.id,
            login_time=datetime.utcnow(),
            ip_address=ip,
            user_agent=user_agent,
            login_status='success'
        )
        db.session.add(login_log)
        
        # 创建安全信息
        security = UserSecurityInfo(
            user_id=guest_user.id,
            password_last_changed=guest_user.created_at
        )
        db.session.add(security)
        
        db.session.commit()
        
        # 登录用户
        login_user(guest_user)
        
        # 记录系统日志
        SystemLog.log_action(
            user_id=guest_user.id,
            action='guest_login',
            ip_address=ip,
            status='success',
            details=f'游客用户 {guest_username} 登录'
        )
        
        flash(f'欢迎游客 {guest_username}！', 'success')
        return redirect(url_for('dashboard.index'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"游客登录失败: {e}")
        flash('游客登录失败，请稍后重试', 'error')
        return redirect(url_for('auth.login'))

def generate_guest_username():
    """生成随机游客用户名"""
    adjectives = [
        '快乐', '聪明', '勇敢', '友善', '活泼', '温暖', '阳光', '可爱',
        '机智', '幽默', '优雅', '神秘', '冷静', '热情', '善良', '坚强'
    ]
    
    nouns = [
        '小猫', '小狗', '小鸟', '小鱼', '小熊', '小兔', '小鹿', '小狐',
        '游客', '访客', '旅人', '探索者', '冒险家', '学者', '艺术家', '诗人'
    ]
    
    # 随机选择形容词和名词
    adjective = random.choice(adjectives)
    noun = random.choice(nouns)
    
    # 添加随机数字
    number = random.randint(100, 999)
    
    base_username = f"{adjective}的{noun}{number}"
    
    # 确保用户名唯一
    counter = 1
    username = base_username
    while User.query.filter_by(username=username).first():
        username = f"{base_username}_{counter}"
        counter += 1
    
    return username

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from sqlalchemy import desc, func
import os
import time

# 导入新的模型
from ...models import User, UserLoginLog, UserActivityLog, UserSecurityInfo, db

# 创建个人信息蓝图
profile_bp = Blueprint('profile', __name__, url_prefix='/profile')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_user_activity(user_id, activity_type, description, ip_address, user_agent, status='success', details=None):
    """记录用户活动日志的辅助函数"""
    try:
        log = UserActivityLog(
            user_id=user_id,
            activity_type=activity_type,
            activity_description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            details=details
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error logging user activity: {e}")


@profile_bp.route('/')
@login_required
def index():
    """个人信息页面"""
    # 直接使用Flask-Login的current_user对象，它包含role_display方法
    # 计算登录统计用于初始渲染（避免选择整行实体，规避缺列导致的错误）
    total_logins = db.session.query(func.count(UserLoginLog.id)).filter(
        UserLoginLog.user_id == current_user.id,
        UserLoginLog.login_status == 'success'
    ).scalar() or 0
    last_login_row = db.session.query(UserLoginLog.login_time).filter(
        UserLoginLog.user_id == current_user.id,
        UserLoginLog.login_status == 'success'
    ).order_by(desc(UserLoginLog.login_time)).first()
    last_login_days = None
    if last_login_row and last_login_row[0]:
        delta = datetime.utcnow() - last_login_row[0]
        last_login_days = max(0, delta.days)
    return render_template('dashboard/profile.html', user=current_user, login_count=total_logins, last_login_days=last_login_days)

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
@login_required
def update_profile():
    """更新个人信息API（数据库版）"""
    try:
        data = request.get_json()
        user = current_user
        
        # 更新允许修改的字段
        allowed_fields = ['username', 'email', 'phone']
        updated_fields = []
        
        for field in allowed_fields:
            if field in data:
                old_value = getattr(user, field, '')
                new_value = data[field]
                if old_value != new_value:
                    setattr(user, field, new_value)
                    updated_fields.append(field)
        
        if updated_fields:
            user.updated_at = datetime.utcnow()
            db.session.commit()
            
            # 记录活动日志
            log_user_activity(
                user_id=user.id,
                activity_type='profile_update',
                description=f'更新个人信息: {", ".join(updated_fields)}',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                details=f'更新字段: {updated_fields}'
            )
        
        return jsonify({
            'success': True,
            'message': '个人信息更新成功',
            'user': user.to_dict()  # 假设User模型有to_dict方法
        })
    except Exception as e:
        db.session.rollback()
        log_user_activity(
            user_id=current_user.id,
            activity_type='profile_update',
            description='更新个人信息失败',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            status='failed',
            details=str(e)
        )
        return jsonify({
            'success': False,
            'message': f'更新失败: {str(e)}'
        })


@profile_bp.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码API（数据库版）"""
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
        
        user = current_user
        
        # 验证当前密码
        if not user.verify_password(current_password):
            # 记录失败尝试
            log_user_activity(
                user_id=user.id,
                activity_type='password_change_failed',
                description='修改密码失败：当前密码错误',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                status='failed'
            )
            return jsonify({'success': False, 'message': '当前密码错误'})
        
        # 更新密码
        user.password = new_password
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # 记录成功日志
        log_user_activity(
            user_id=user.id,
            activity_type='password_change',
            description='密码修改成功',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return jsonify({
            'success': True,
            'message': '密码修改成功'
        })
        
    except Exception as e:
        db.session.rollback()
        log_user_activity(
            user_id=current_user.id,
            activity_type='password_change_failed',
            description=f'修改密码失败: {str(e)}',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            status='failed'
        )
        return jsonify({
            'success': False,
            'message': f'密码修改失败: {str(e)}'
        })

@profile_bp.route('/api/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    """上传头像API（数据库版）"""
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': '没有文件部分'})
    
    file = request.files['avatar']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'})
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            unique_filename = f"{current_user.id}_{int(time.time())}_{filename}"
            upload_folder = current_app.config['UPLOAD_FOLDER']
            
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
                
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            
            # 更新用户头像信息
            user = current_user
            user.avatar = f'/static/uploads/{unique_filename}'
            user.updated_at = datetime.utcnow()
            db.session.commit()
            
            # 记录活动日志
            log_user_activity(
                user_id=user.id,
                activity_type='avatar_upload',
                description='头像上传成功',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            return jsonify({
                'success': True,
                'message': '头像上传成功',
                'avatar_url': user.avatar
            })
            
        except Exception as e:
            db.session.rollback()
            log_user_activity(
                user_id=current_user.id,
                activity_type='avatar_upload_failed',
                description=f'头像上传失败: {str(e)}',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                status='failed'
            )
            return jsonify({'success': False, 'message': f'头像上传失败: {str(e)}'})
    
    return jsonify({'success': False, 'message': '文件类型不允许'})

@profile_bp.route('/api/activity-log')
@login_required
def get_activity_log():
    """获取活动日志API"""
    try:
        # 获取最近的活动日志（最多20条）
        activity_logs = UserActivityLog.query.filter_by(
            user_id=current_user.id
        ).order_by(desc(UserActivityLog.activity_time)).limit(20).all()
        
        # 转换为JSON格式
        activity_data = []
        for log in activity_logs:
            activity_data.append({
                'id': log.id,
                'action': log.activity_description or log.activity_type,
                'timestamp': log.activity_time.strftime('%Y-%m-%d %H:%M:%S'),
                'ip_address': log.ip_address,
                'user_agent': log.user_agent[:50] + '...' if log.user_agent and len(log.user_agent) > 50 else log.user_agent,
                'status': log.status
            })
        
        return jsonify({
            'success': True,
            'activity_log': activity_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取活动日志失败: {str(e)}'
        })


@profile_bp.route('/api/login-stats')
@login_required
def get_login_stats():
    """获取登录统计API"""
    try:
        # 获取最近30天的登录统计
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # 计数统计（避免选择整行实体）
        total_logins = db.session.query(func.count(UserLoginLog.id)).filter(
            UserLoginLog.user_id == current_user.id,
            UserLoginLog.login_status == 'success'
        ).scalar() or 0
        
        recent_logins = db.session.query(func.count(UserLoginLog.id)).filter(
            UserLoginLog.user_id == current_user.id,
            UserLoginLog.login_status == 'success',
            UserLoginLog.login_time >= thirty_days_ago
        ).scalar() or 0
        
        failed_logins = db.session.query(func.count(UserLoginLog.id)).filter(
            UserLoginLog.user_id == current_user.id,
            UserLoginLog.login_status == 'failed'
        ).scalar() or 0
        
        # 最后登录时间（仅选择需要的列）
        last_login_row = db.session.query(UserLoginLog.login_time).filter(
            UserLoginLog.user_id == current_user.id,
            UserLoginLog.login_status == 'success'
        ).order_by(desc(UserLoginLog.login_time)).first()
        
        last_login_days = None
        last_login_str = None
        last_login_iso = None
        if last_login_row and last_login_row[0]:
            last_login_time = last_login_row[0]
            delta = datetime.utcnow() - last_login_time
            last_login_days = max(0, delta.days)
            last_login_str = last_login_time.strftime('%Y-%m-%d %H:%M:%S')
            try:
                last_login_iso = last_login_time.isoformat() + 'Z'
            except Exception:
                last_login_iso = last_login_str
        
        return jsonify({
            'success': True,
            'stats': {
                'total_logins': total_logins,
                'recent_logins': recent_logins,
                'last_login': last_login_str,
                'last_login_iso': last_login_iso,
                'last_login_days': last_login_days,
                'failed_logins': failed_logins
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取登录统计失败: {str(e)}'
        })

@profile_bp.route('/api/security-settings')
@login_required
def get_security_settings():
    """获取安全设置API"""
    try:
        # 获取或创建用户安全信息
        security_info = UserSecurityInfo.query.filter_by(user_id=current_user.id).first()
        if not security_info:
            # 如果不存在，创建默认安全信息
            security_info = UserSecurityInfo(
                user_id=current_user.id,
                password_last_changed=current_user.created_at,
                failed_login_attempts=0,
                two_factor_enabled=False,
                security_questions_set=False
            )
            db.session.add(security_info)
            db.session.commit()
            db.session.add(security_info)
            db.session.commit()
        
        # 获取最后登录IP（仅选择需要的列）
        last_login_ip_row = db.session.query(UserLoginLog.ip_address, UserLoginLog.login_time).filter(
            UserLoginLog.user_id == current_user.id,
            UserLoginLog.login_status == 'success'
        ).order_by(desc(UserLoginLog.login_time)).first()
        last_login_ip = last_login_ip_row[0] if last_login_ip_row else None
        
        security_settings = {
            'two_factor_enabled': security_info.two_factor_enabled,
            'login_notifications': True,  # 可以添加到UserSecurityInfo模型中
            'session_timeout': 30,  # 可以添加到UserSecurityInfo模型中
            'password_last_changed': security_info.password_last_changed.strftime('%Y-%m-%d') if security_info.password_last_changed else None,
            'failed_login_attempts': security_info.failed_login_attempts,
            'account_status': '正常' if current_user.is_active else '已锁定',
            'last_login_ip': last_login_ip,
            'security_questions_set': security_info.security_questions_set
        }
        
        return jsonify({
            'success': True,
            'security_settings': security_settings
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取安全设置失败: {str(e)}'
        })

@profile_bp.route('/api/update-security', methods=['POST'])
@login_required
def update_security_settings():
    """更新安全设置API（数据库版）"""
    try:
        data = request.get_json()
        user = current_user
        
        # 获取或创建用户安全信息
        security_info = UserSecurityInfo.query.filter_by(user_id=user.id).first()
        if not security_info:
            security_info = UserSecurityInfo(user_id=user.id)
            db.session.add(security_info)
        
        # 更新允许修改的设置
        allowed_settings = ['two_factor_enabled', 'login_notifications', 'session_timeout']
        updated_settings = []
        
        for setting in allowed_settings:
            if setting in data:
                old_value = getattr(security_info, setting, None)
                new_value = data[setting]
                if old_value != new_value:
                    setattr(security_info, setting, new_value)
                    updated_settings.append(setting)
        
        if updated_settings:
            db.session.commit()
            
            # 记录活动日志
            log_user_activity(
                user_id=user.id,
                activity_type='security_settings_update',
                description=f'更新安全设置: {", ".join(updated_settings)}',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
        
        return jsonify({
            'success': True,
            'message': '安全设置更新成功'
        })
        
    except Exception as e:
        db.session.rollback()
        log_user_activity(
            user_id=current_user.id,
            activity_type='security_settings_update_failed',
            description=f'安全设置更新失败: {str(e)}',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            status='failed'
        )
        return jsonify({
            'success': False,
            'message': f'安全设置更新失败: {str(e)}'
        })
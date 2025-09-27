from functools import wraps
from flask import jsonify, render_template, redirect, url_for, flash, request
from flask_login import current_user

def guest_restricted(f):
    """限制游客用户访问某些功能"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.is_guest():
            # 如果是API请求，返回JSON错误
            if '/api/' in str(f):
                return jsonify({'error': '游客用户无权限访问此功能'}), 403
            # 如果是页面请求，重定向到错误页面
            flash('游客用户无权限访问此功能', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def non_guest_required(f):
    """要求非游客用户才能访问"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # 如果是API请求，返回JSON错误
            if '/api/' in str(f) or request.headers.get('Accept', '').find('application/json') != -1:
                return jsonify({'error': '未登录'}), 401
            # 如果是页面请求，重定向到登录页面
            return redirect(url_for('auth.login'))
            
        if current_user.is_guest():
            # 如果是API请求，返回JSON错误
            if '/api/' in str(f) or request.headers.get('Accept', '').find('application/json') != -1:
                return jsonify({'error': '游客用户无权限访问此功能'}), 403
            # 如果是页面请求，显示权限不足页面
            return render_template('dashboard/error.html', 
                                 error_message='权限不足，需要管理员权限才能访问此页面')
        return f(*args, **kwargs)
    return decorated_function

def admin_or_self_required(f):
    """要求管理员权限或访问自己的资源"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # 如果是API请求，返回JSON错误
            if '/api/' in str(f) or request.headers.get('Accept', '').find('application/json') != -1:
                return jsonify({'error': '未登录'}), 401
            # 如果是页面请求，重定向到登录页面
            return redirect(url_for('auth.login'))
        
        # 游客用户无权限
        if current_user.is_guest():
            # 如果是API请求，返回JSON错误
            if '/api/' in str(f) or request.headers.get('Accept', '').find('application/json') != -1:
                return jsonify({'error': '游客用户无权限访问此功能'}), 403
            # 如果是页面请求，显示权限不足页面
            return render_template('dashboard/error.html', 
                                 error_message='权限不足，需要管理员权限才能访问此页面')
            
        # 管理员可以访问所有资源
        if current_user.is_administrator():
            return f(*args, **kwargs)
            
        # 普通用户只能访问自己的资源
        user_id = kwargs.get('user_id')
        if user_id and int(user_id) != current_user.id:
            # 如果是API请求，返回JSON错误
            if '/api/' in str(f) or request.headers.get('Accept', '').find('application/json') != -1:
                return jsonify({'error': '权限不足'}), 403
            # 如果是页面请求，显示权限不足页面
            return render_template('dashboard/error.html', 
                                 error_message='权限不足，您只能访问自己的资源')
            
        return f(*args, **kwargs)
    return decorated_function
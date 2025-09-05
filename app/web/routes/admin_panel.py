"""
系统管理面板主页面路由
提供管理面板的HTML页面访问
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user

# 创建管理面板主页面蓝图
admin_panel_bp = Blueprint('admin_panel', __name__)

@admin_panel_bp.route('/admin')
@login_required
def admin_panel():
    """系统管理面板主页面"""
    # 检查用户权限
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        # 如果不是管理员，重定向到首页或显示权限不足页面
        return render_template('dashboard/error.html', 
                             error_message='权限不足，需要管理员权限才能访问系统管理面板')
    
    # 准备页面数据
    page_data = {
        'current_user': current_user,
        'page_title': '系统管理面板',
        'breadcrumb': [
            {'name': '首页', 'url': '/'},
            {'name': '系统管理', 'url': None}
        ]
    }
    
    return render_template('dashboard/admin.html', **page_data)

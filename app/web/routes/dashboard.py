from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    """主页仪表板"""
    return render_template('dashboard/index.html')

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """用户仪表板"""
    return render_template('dashboard/index.html')

@dashboard_bp.route('/clients')
@login_required
def clients():
    """客户端管理页面"""
    return render_template('dashboard/clients.html')

@dashboard_bp.route('/client/<int:client_id>')
@login_required
def client_detail(client_id):
    """客户端详情页面"""
    return render_template('dashboard/client_detail.html', client_id=client_id)

@dashboard_bp.route('/remote-sessions')
@login_required
def remote_sessions():
    """远程会话管理页面"""
    return render_template('dashboard/remote_sessions.html')

@dashboard_bp.route('/api/clients')
@login_required
def get_clients():
    """获取客户端列表的API"""
    # 这里应该从client_manager获取实际的客户端信息
    from ..services import client_manager
    clients = {cid: info for cid, info in client_manager.client_info.items()}
    return jsonify({'clients': clients})

@dashboard_bp.route('/test')
def test():
    """测试页面，不需要登录"""
    return jsonify({
        'status': 'success',
        'message': '路由测试成功！',
        'endpoint': request.endpoint,
        'blueprint': request.blueprint
    })

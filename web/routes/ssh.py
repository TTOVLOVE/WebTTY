from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
import time

ssh_bp = Blueprint('ssh', __name__)

@ssh_bp.route('/ssh')
@login_required
def ssh_index():
    """SSH连接页面"""
    return render_template('assets/ssh_view.html')

@ssh_bp.route('/ssh/connect')
@login_required
def ssh_connect():
    """SSH连接处理页面"""
    # 从URL参数获取连接信息
    host = request.args.get('host')
    port = request.args.get('port', 22)
    username = request.args.get('username', '')
    
    return render_template('assets/ssh_connect.html', 
                         host=host, 
                         port=port, 
                         username=username)

@ssh_bp.route('/api/ssh/connect', methods=['POST'])
@login_required
def ssh_connect_api():
    """SSH连接API"""
    data = request.get_json()
    host = data.get('host')
    port = data.get('port', 22)
    username = data.get('username')
    password = data.get('password')
    
    # 这里应该实现实际的SSH连接逻辑
    # 暂时返回成功状态
    
    return jsonify({
        'success': True,
        'message': f'SSH连接已建立到 {host}:{port}',
        'session_id': f'ssh_{int(time.time())}'
    })

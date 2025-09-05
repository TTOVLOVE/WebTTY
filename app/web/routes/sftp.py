from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
import time

sftp_bp = Blueprint('sftp', __name__)

@sftp_bp.route('/sftp')
@login_required
def sftp_index():
    """SFTP连接页面"""
    return render_template('assets/sftp_view.html')

@sftp_bp.route('/sftp/connect')
@login_required
def sftp_connect():
    """SFTP连接处理页面"""
    # 从URL参数获取连接信息
    host = request.args.get('host')
    port = request.args.get('port', 22)
    username = request.args.get('username', '')
    
    return render_template('assets/sftp_connect.html', 
                         host=host, 
                         port=port, 
                         username=username)

@sftp_bp.route('/api/sftp/connect', methods=['POST'])
@login_required
def sftp_connect_api():
    """SFTP连接API"""
    data = request.get_json()
    host = data.get('host')
    port = data.get('port', 22)
    username = data.get('username')
    password = data.get('password')
    
    # 这里应该实现实际的SFTP连接逻辑
    # 暂时返回成功状态
    
    return jsonify({
        'success': True,
        'message': f'SFTP连接已建立到 {host}:{port}',
        'session_id': f'sftp_{int(time.time())}'
    })

from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
import json
import os
from datetime import datetime

toolbox_bp = Blueprint('toolbox', __name__)

# 存储连接历史的文件路径
CONNECTIONS_FILE = 'connections.json'

def load_connections():
    """加载连接历史"""
    if os.path.exists(CONNECTIONS_FILE):
        try:
            with open(CONNECTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_connections(connections):
    """保存连接历史"""
    try:
        with open(CONNECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(connections, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

@toolbox_bp.route('/toolbox')
@login_required
def toolbox():
    """工具箱主页面"""
    return render_template('dashboard/toolbox.html')

@toolbox_bp.route('/api/tools')
@login_required
def get_tools():
    """获取可用工具列表"""
    tools = [
        {
            'id': 'ssh',
            'name': 'SSH连接',
            'description': '安全Shell连接工具',
            'icon': 'fas fa-terminal',
            'route': '/ssh'
        },
        {
            'id': 'sftp',
            'name': 'SFTP文件传输',
            'description': '安全文件传输协议',
            'icon': 'fas fa-folder-open',
            'route': '/sftp'
        },
        {
            'id': 'vnc',
            'name': 'VNC远程桌面',
            'description': '虚拟网络计算远程桌面',
            'icon': 'fas fa-desktop',
            'route': '/vnc'
        },
        {
            'id': 'rdp',
            'name': 'RDP远程桌面',
            'description': '远程桌面协议',
            'icon': 'fas fa-laptop',
            'route': '/rdp'
        }
    ]
    return jsonify({'tools': tools})

@toolbox_bp.route('/api/connections')
@login_required
def get_connections():
    """获取连接历史"""
    connections = load_connections()
    return jsonify({'connections': connections})

@toolbox_bp.route('/api/connections', methods=['POST'])
@login_required
def create_connection():
    """创建新连接"""
    data = request.get_json()
    
    # 验证必要字段
    required_fields = ['name', 'type', 'host', 'port']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'缺少必要字段: {field}'}), 400
    
    # 创建连接记录
    connection = {
        'id': f"{data['type']}_{int(datetime.now().timestamp())}",
        'name': data['name'],
        'type': data['type'],
        'host': data['host'],
        'port': data['port'],
        'username': data.get('username', ''),
        'password': data.get('password', ''),
        'created_at': datetime.now().isoformat(),
        'last_connected': None,
        'connection_count': 0
    }
    
    # 加载现有连接
    connections = load_connections()
    
    # 检查是否已存在相同连接
    for existing in connections:
        if (existing['name'] == connection['name'] and 
            existing['type'] == connection['type'] and
            existing['host'] == connection['host'] and
            existing['port'] == connection['port']):
            return jsonify({'error': '连接已存在'}), 400
    
    # 添加新连接
    connections.append(connection)
    
    # 保存到文件
    if save_connections(connections):
        return jsonify({'success': True, 'connection': connection})
    else:
        return jsonify({'error': '保存连接失败'}), 500

@toolbox_bp.route('/api/connections/<connection_id>/connect', methods=['POST'])
@login_required
def connect_to_device(connection_id):
    """连接到指定设备"""
    connections = load_connections()
    
    # 查找连接
    connection = None
    for conn in connections:
        if conn['id'] == connection_id:
            connection = conn
            break
    
    if not connection:
        return jsonify({'error': '连接不存在'}), 404
    
    # 更新连接统计
    connection['last_connected'] = datetime.now().isoformat()
    connection['connection_count'] = connection.get('connection_count', 0) + 1
    
    # 保存更新
    save_connections(connections)
    
    # 根据连接类型返回不同的连接信息
    if connection['type'] == 'vnc':
        return jsonify({
            'success': True,
            'type': 'vnc',
            'connection': connection,
            'redirect_url': f"/vnc/connect?host={connection['host']}&port={connection['port']}"
        })
    elif connection['type'] == 'rdp':
        return jsonify({
            'success': True,
            'type': 'rdp',
            'connection': connection,
            'redirect_url': f"/rdp/connect?host={connection['host']}&port={connection['port']}&username={connection['username']}"
        })
    elif connection['type'] == 'ssh':
        # 为SSH连接生成会话ID
        session_id = f"ssh_{connection_id}_{int(datetime.now().timestamp())}"
        return jsonify({
            'success': True,
            'type': 'ssh',
            'connection': {
                **connection,
                'session_id': session_id
            },
            'redirect_url': f"/ssh/connect?host={connection['host']}&port={connection['port']}&username={connection['username']}"
        })
    elif connection['type'] == 'sftp':
        # 为SFTP连接生成会话ID
        session_id = f"sftp_{connection_id}_{int(datetime.now().timestamp())}"
        return jsonify({
            'success': True,
            'type': 'sftp',
            'connection': {
                **connection,
                'session_id': session_id
            },
            'redirect_url': f"/sftp/connect?host={connection['host']}&port={connection['port']}&username={connection['username']}"
        })
    else:
        return jsonify({'error': '不支持的连接类型'}), 400

@toolbox_bp.route('/api/connections/<connection_id>', methods=['DELETE'])
@login_required
def delete_connection(connection_id):
    """删除连接"""
    connections = load_connections()
    
    # 查找并删除连接
    for i, conn in enumerate(connections):
        if conn['id'] == connection_id:
            del connections[i]
            if save_connections(connections):
                return jsonify({'success': True})
            else:
                return jsonify({'error': '删除失败'}), 500
    
    return jsonify({'error': '连接不存在'}), 404

@toolbox_bp.route('/api/connections/clear', methods=['POST'])
@login_required
def clear_connections():
    """清空所有连接"""
    if save_connections([]):
        return jsonify({'success': True})
    else:
        return jsonify({'error': '清空失败'}), 500

from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
from flask_login import current_user
import os
import base64
from ..utils.helpers import human_readable_size
from ..services import client_manager
from ..services.transfer_service import save_screenshot
import logging

# 一个临时存放上传数据的缓存
upload_cache = {}

def init_socketio(socketio):
    """初始化Socket.IO事件处理器"""
    
    @socketio.on('connect')
    def handle_connect():
        if current_user.is_authenticated:
            join_room(current_user.id)
            logging.info(f"Socket.IO connect: User {current_user.username} (ID: {current_user.id}, SID: {request.sid}) joined room {current_user.id}.")
        else:
            logging.warning(f"Socket.IO connect: Unauthenticated user with SID {request.sid} connected.")

    @socketio.on('disconnect')
    def handle_disconnect():
        if current_user.is_authenticated:
            leave_room(current_user.id)
            logging.info(f"Socket.IO disconnect: User {current_user.username} (ID: {current_user.id}, SID: {request.sid}) left room {current_user.id}.")
        else:
            logging.warning(f"Socket.IO disconnect: Unauthenticated user with SID {request.sid} disconnected.")
    
    @socketio.on('get_clients')
    def get_clients():
        """获取客户端列表"""
        def norm(val):
            if val is None:
                return ''
            s = str(val).strip()
            return '' if s in ('', '未知', '获取中...', 'None') else s
        
        def extract_ip(addr):
            if addr is None:
                return ''
            if isinstance(addr, (list, tuple)) and len(addr) > 0:
                return str(addr[0])
            s = str(addr)
            import re
            m = re.search(r'([0-9]{1,3}(?:\.[0-9]{1,3}){3})', s)
            return m.group(1) if m else s
        
        clients = {}
        try:
            # 延迟导入，避免模块循环
            from ..models import Client
            
            # 根据用户权限获取客户端
            if current_user.is_authenticated:
                if current_user.is_super_admin():
                    # 超级管理员可以查看所有客户端
                    query = Client.query.all()
                else:
                    # 普通用户只能查看自己的客户端
                    query = Client.query.filter_by(owner_id=current_user.id).all()
            else:
                query = []

            # 从数据库加载客户端
            db_clients = {c.id: c for c in query}
            
            # 结合在线客户端信息
            for cid, info in client_manager.client_info.items():
                db_client_id = info.get('db_client_id')
                
                # 检查此在线客户端是否应显示给当前用户
                if db_client_id in db_clients:
                    c = db_clients[db_client_id]
                    
                    # 再次检查权限（双重保险）
                    if current_user.is_authenticated and current_user.can_view_client(c):
                        datum = dict(info) if isinstance(info, dict) else {}
                        hostname = norm(c.hostname) or norm(datum.get('hostname'))
                        user = norm(datum.get('user'))
                        ip = extract_ip(datum.get('addr')) or norm(c.ip_address)
                        
                        display_name = hostname or user or ip or f"客户端 {cid}"
                        datum['display_name'] = display_name
                        datum['owner_id'] = c.owner_id
                        datum['can_operate'] = current_user.can_operate_client(c)  # 添加操作权限标识
                        clients[cid] = datum

        except Exception as e:
            logging.error(f"Error in get_clients for user {current_user.id if current_user.is_authenticated else 'Anonymous'}: {e}", exc_info=True)
            clients = {}
        
        logging.debug(f"Emitting clients_list for user {current_user.id if current_user.is_authenticated else 'Anonymous'} with {len(clients)} clients.")
        emit('clients_list', {'clients': clients})
    
    @socketio.on('send_command')
    def send_command(data):
        """发送命令到客户端"""
        target = data.get('target')  # 前端发送的是 'target'
        command = data.get('command', {})  # 前端发送的命令在 'command' 对象中
        action = command.get('action')
        arg = command.get('arg')
        
        # 权限检查：验证用户是否有权限操作该客户端
        if current_user.is_authenticated:
            try:
                from ..models import Client
                # 通过client_info获取db_client_id
                client_info = client_manager.client_info.get(target)
                if client_info:
                    db_client_id = client_info.get('db_client_id')
                    if db_client_id:
                        client = Client.query.get(db_client_id)
                        if client and not current_user.can_operate_client(client):
                            emit('command_response', {
                                'client_id': target,
                                'error': '权限不足：您无权操作此客户端'
                            })
                            return
            except Exception as e:
                logging.error(f"Error checking client permissions: {e}")
                emit('command_response', {
                    'client_id': target,
                    'error': '权限验证失败'
                })
                return
        
        print(f"Available client_queues: {list(client_manager.client_queues.keys())}")
        print(f"Available client_info: {list(client_manager.client_info.keys())}")
        
        if target not in client_manager.client_queues:
            emit('command_response', {
                'client_id': target,
                'error': f'客户端 {target} 未连接'
            })
            return
        
        try:
            # 构造命令
            cmd = {
                'action': action,
                'arg': arg
            }
            
            # 发送到客户端队列
            client_manager.client_queues[target].put(cmd)
            
            # 发送确认响应
            emit('command_response', {
                'client_id': target,
                'status': 'sent',
                'command': cmd
            })
            
        except Exception as e:
            emit('command_response', {
                'client_id': target,
                'error': str(e)
            })
    
    @socketio.on('send_batch_command')
    def send_batch_command(data):
        """批量发送命令到多个客户端"""
        command = data.get('command')
        clients = data.get('clients', [])
        
        if not command or not clients:
            emit('command_result', {'output': "命令或客户端列表为空", 'is_error': True})
            return
        
        # 解析命令
        parts = command.split()
        action = parts[0] if parts else command
        arg = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        cmd_obj = {'action': action, 'arg': arg}
        
        # 向每个客户端发送命令
        for client_id in clients:
            if client_id in client_manager.client_queues:
                client_manager.client_queues[client_id].put(cmd_obj)
            else:
                emit('batch_command_result', {
                    'client_id': client_id,
                    'output': f"客户端 {client_id} 未连接",
                    'is_error': True
                })
    
    @socketio.on('new_screenshot')
    def handle_new_screenshot(data):
        """处理来自客户端的截图数据并保存"""
        client_id = data['client_id']
        filename = data['filename']
        image_data = data['image_data']

        # 保存截图
        safe_filename = save_screenshot(client_id, filename, image_data)

        # 向前端发送新的截图信息
        emit('new_screenshot', {
            'url': f"/downloads/{safe_filename}",
            'client_id': client_id,
            'filename': safe_filename
        }, broadcast=True)
    
    # 文件管理相关的事件处理器
    @socketio.on('request_list_dir')
    def handle_list_dir(data):
        """处理目录列表请求, 将其转发给客户端"""
        client_id = data.get('client_id')
        path = data.get('path', '.')
        
        if client_id in client_manager.client_queues:
            command = {
                "action": "list_dir",
                "arg": path
            }
            client_manager.client_queues[client_id].put(command)
        else:
            emit('dir_list', {"client_id": client_id, "dir_list": None, "error": f"客户端 {client_id} 未连接"})

    @socketio.on('request_read_file')
    def handle_read_file(data):
        """处理文件读取请求，将其转发给客户端"""
        client_id = data.get('client_id')
        path = data.get('path')
        
        if client_id in client_manager.client_queues:
            command = {
                "action": "read_file",
                "arg": path
            }
            client_manager.client_queues[client_id].put(command)
        else:
            emit('file_text', {"client_id": client_id, "text": f"客户端 {client_id} 未连接", "is_base64": False})

    @socketio.on('request_delete_path')
    def handle_delete_file(data):
        """处理文件删除请求"""
        client_id = data.get('client_id')
        path = data.get('path')

        try:
            if os.path.isdir(path):
                os.rmdir(path)
            else:
                os.remove(path)
            emit('command_result', {"target_id": client_id, "output": f"删除成功: {path}"})
        except Exception as e:
            emit('command_result', {"target_id": client_id, "output": f"删除失败: {e}"})

    @socketio.on('web_upload_chunk')
    def handle_upload_chunk(data):
        """处理分片上传"""
        client_id = data.get("client_id")
        dest_path = data.get("dest_path")
        chunk_index = data.get("chunk_index")
        total_chunks = data.get("total_chunks")
        b64_data = data.get("data")
        is_last = data.get("is_last", False)

        # 初始化缓存
        if dest_path not in upload_cache:
            upload_cache[dest_path] = [None] * total_chunks

        # 保存分片
        upload_cache[dest_path][chunk_index] = base64.b64decode(b64_data)

        if is_last:
            try:
                # 确保目标目录存在
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                
                with open(dest_path, "wb") as f:
                    for chunk in upload_cache[dest_path]:
                        if chunk:
                            f.write(chunk)

                size = os.path.getsize(dest_path)
                emit("command_result", {
                    "target_id": client_id,
                    "output": f"上传完成: {dest_path} ({human_readable_size(size)})"
                })
            except Exception as e:
                emit("command_result", {
                    "target_id": client_id,
                    "output": f"上传失败: {e}"
                })
            finally:
                upload_cache.pop(dest_path, None)
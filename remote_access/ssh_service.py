import paramiko
import threading
import io
from base64 import b64decode
from ..extensions import socketio
from ..config import BaseConfig
from ..services.client_manager import clients

ssh_sessions = {}

def init_app(socketio_instance):
    def ssh_reader_loop(session_id, channel):
        try:
            while True:
                if channel.recv_ready():
                    data = channel.recv(1024)
                    if not data:
                        break
                    try:
                        text = data.decode('utf-8', errors='replace')
                    except:
                        text = data.decode('latin1', errors='replace')
                    socketio.emit('ssh_output', {'session_id': session_id, 'data': text})
                if channel.exit_status_ready():
                    break
                socketio.sleep(0.01)
        except Exception as e:
            socketio.emit('ssh_output', {'session_id': session_id, 'data': f"\n[ssh reader 异常] {e}\n"})
        finally:
            socketio.emit('ssh_closed', {'session_id': session_id})

    @socketio_instance.on('ssh_connect')
    def handle_ssh_connect(data):
        sid = data.get('session_id')
        host = data.get('host')
        port = int(data.get('port') or 22)
        username = data.get('username')
        password = data.get('password')
        pkey_b64 = data.get('pkey')

        if not sid or not host or not username:
            socketio.emit('ssh_error', {'session_id': sid, 'error': '参数缺失'})
            return

        pkey = None
        if pkey_b64:
            try:
                key_bytes = b64decode(pkey_b64)
                pkey = paramiko.RSAKey.from_private_key(io.BytesIO(key_bytes))
            except Exception as e:
                socketio.emit('ssh_error', {'session_id': sid, 'error': f'解析密钥失败: {e}'})
                return

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=host, port=port, username=username, password=password, pkey=pkey, timeout=10)
            chan = client.invoke_shell(term='xterm')
            cols = int(data.get('cols', 80))
            rows = int(data.get('rows', 24))
            try:
                chan.resize_pty(width=cols, height=rows)
            except Exception:
                pass

            t = threading.Thread(target=ssh_reader_loop, args=(sid, chan), daemon=True)
            ssh_sessions[sid] = {'client': client, 'chan': chan, 'thread': t}
            t.start()
            socketio.emit('ssh_connected', {'session_id': sid, 'msg': 'SSH 连接已建立'})
        except Exception as e:
            try:
                client.close()
            except:
                pass
            socketio.emit('ssh_error', {'session_id': sid, 'error': str(e)})

    @socketio_instance.on('ssh_input')
    def handle_ssh_input(data):
        sid = data.get('session_id')
        text = data.get('data', '')
        sess = ssh_sessions.get(sid)
        if not sess:
            socketio.emit('ssh_error', {'session_id': sid, 'error': '会话不存在'})
            return
        chan = sess.get('chan')
        try:
            if chan:
                chan.send(text)
        except Exception as e:
            socketio.emit('ssh_error', {'session_id': sid, 'error': f'发送到SSH失败: {e}'})

    @socketio_instance.on('ssh_disconnect')
    def handle_ssh_disconnect(data):
        sid = data.get('session_id')
        sess = ssh_sessions.pop(sid, None)
        if sess:
            try:
                if sess.get('chan'):
                    sess['chan'].close()
                if sess.get('client'):
                    sess['client'].close()
            except:
                pass
            try:
                sess['client'].close()
            except:
                pass
            socketio.emit('ssh_closed', {'session_id': sid})

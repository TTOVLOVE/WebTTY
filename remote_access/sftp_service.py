import paramiko
import stat
import os
from ..extensions import socketio

# SFTP会话存储
sftp_sessions = {}

def init_app(socketio_instance):
    @socketio_instance.on('sftp_connect')
    def handle_sftp_connect(data):
        sid = data.get('session_id')
        host = data.get('host')
        port = int(data.get('port', 22))
        username = data.get('username')
        password = data.get('password')

        if not sid or not host or not username:
            socketio.emit('sftp_error', {'session_id': sid, 'error': '参数缺失'})
            return

        try:
            client = paramiko.Transport((host, port))
            client.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(client)
            sftp_sessions[sid] = {'transport': client, 'sftp': sftp}
            socketio.emit('sftp_connected', {'session_id': sid, 'msg': 'SFTP 连接已建立'})
        except Exception as e:
            socketio.emit('sftp_error', {'session_id': sid, 'error': str(e)})

    @socketio_instance.on('sftp_list')
    def handle_sftp_list(data):
        sid = data.get('session_id')
        path = data.get('path', '.')
        session = sftp_sessions.get(sid)
        
        if not session or not session.get('sftp'):
            socketio.emit('sftp_error', {'session_id': sid, 'error': '未连接到SFTP'})
            return
        
        sftp = session['sftp']

        try:
            items = []
            for fn in sftp.listdir(path):
                try:
                    st = sftp.stat(os.path.join(path, fn))
                    items.append({
                        'name': fn,
                        'is_dir': stat.S_ISDIR(st.st_mode),
                        'size': st.st_size,
                        'mtime': st.st_mtime
                    })
                except Exception:
                    items.append({'name': fn, 'is_dir': False, 'size': 0, 'mtime': 0})

            socketio.emit('sftp_list_result', {'session_id': sid, 'path': path, 'list': items})
        except Exception as e:
            socketio.emit('sftp_error', {'session_id': sid, 'error': str(e)})

    @socketio_instance.on('sftp_upload')
    def handle_sftp_upload(data):
        sid = data.get('session_id')
        path = data.get('path')
        file_data = data.get('file_data')

        session = sftp_sessions.get(sid)
        
        if not session or not session.get('sftp'):
            socketio.emit('sftp_error', {'session_id': sid, 'error': '未连接到SFTP'})
            return
        
        sftp = session['sftp']

        try:
            with open(file_data, 'wb') as f:
                f.write(file_data)
            sftp.put(file_data, path)
            socketio.emit('sftp_upload_success', {'session_id': sid, 'msg': '上传成功'})
        except Exception as e:
            socketio.emit('sftp_error', {'session_id': sid, 'error': f"上传失败: {e}"})

    @socketio_instance.on('sftp_disconnect')
    def handle_sftp_disconnect(data):
        sid = data.get('session_id')
        session = sftp_sessions.pop(sid, None)
        if session:
            try:
                if session.get('sftp'):
                    session['sftp'].close()
                if session.get('transport'):
                    session['transport'].close()
            except:
                pass

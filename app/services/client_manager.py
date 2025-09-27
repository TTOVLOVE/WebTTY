import queue
import threading
import socket

# 全局锁，用于保护对客户端字典的并发访问
client_lock = threading.Lock()

clients = {}
client_queues = {}
client_info = {}

def register_client(client_id, conn, addr):
    with client_lock:
        # 如果客户端已存在，先移除旧的，确保资源被清理
        if client_id in clients:
            _remove_client_unlocked(client_id)
            print(f"[警告] 客户端 {client_id} 已存在，旧连接已被移除。")

        q = queue.Queue()
        clients[client_id] = conn
        client_queues[client_id] = q
        client_info[client_id] = {'addr': addr, 'user': '获取中...', 'initial_cwd': '获取中...', 'os': '获取中...'}
        return q

def _remove_client_unlocked(client_id):
    """Assumes client_lock is already held."""
    conn = clients.pop(client_id, None)
    if conn:
        try:
            # Set a timeout to avoid blocking indefinitely
            conn.settimeout(1.0)
            # Attempt a graceful shutdown
            conn.shutdown(socket.SHUT_RDWR)
        except (OSError, socket.error):
            # This is expected if the client has already disconnected
            pass
        finally:
            try:
                conn.close()
            except (OSError, socket.error):
                pass  # Ignore errors on close, as the socket might already be closed
    client_queues.pop(client_id, None)
    client_info.pop(client_id, None)

def remove_client(client_id):
    """Public function to remove a client, with locking."""
    with client_lock:
        _remove_client_unlocked(client_id)

def remove_client_if_match(client_id, conn_to_match):
    """Removes a client only if the connection object matches."""
    with client_lock:
        if client_id in clients and clients[client_id] == conn_to_match:
            _remove_client_unlocked(client_id)

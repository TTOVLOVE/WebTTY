import queue

clients = {}
client_queues = {}
client_info = {}

def register_client(client_id, conn, addr):
    q = queue.Queue()
    clients[client_id] = conn
    client_queues[client_id] = q
    client_info[client_id] = {'addr': addr, 'user': '获取中...', 'initial_cwd': '获取中...', 'os': '获取中...'}
    return q

def remove_client(client_id):
    clients.pop(client_id, None)
    client_queues.pop(client_id, None)
    client_info.pop(client_id, None)

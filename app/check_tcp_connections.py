#!/usr/bin/env python3
"""
检查TCP连接和客户端管理器的同步状态
"""

import sys
import os
import subprocess

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.services import client_manager
from app import create_app
from app.models import Client
from datetime import datetime

def check_tcp_connections():
    """检查TCP连接"""
    print('=' * 60)
    print('TCP连接状态检查')
    print('=' * 60)
    
    try:
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=True)
        lines = result.stdout.split('\n')
        
        tcp_2383_connections = []
        for line in lines:
            if ':2383' in line and 'TCP' in line:
                tcp_2383_connections.append(line.strip())
        
        print(f'端口2383的TCP连接数: {len(tcp_2383_connections)}')
        for conn in tcp_2383_connections:
            print(f'  {conn}')
            
        return len(tcp_2383_connections)
    except Exception as e:
        print(f'检查TCP连接时出错: {e}')
        return 0

def check_client_manager():
    """检查客户端管理器状态"""
    print('\n' + '=' * 60)
    print('客户端管理器状态检查')
    print('=' * 60)
    
    # 直接导入客户端管理器模块，而不是通过应用实例
    from app.services.client_manager import client_info, clients, client_queues
    
    print(f'client_info: {client_info}')
    print(f'clients: {clients}')
    print(f'client_queues: {client_queues}')
    
    return len(client_info)

def check_database_clients():
    """检查数据库中的客户端状态"""
    print('\n' + '=' * 60)
    print('数据库客户端状态检查')
    print('=' * 60)
    
    app = create_app()
    with app.app_context():
        online_clients = Client.query.filter_by(status='online').all()
        print(f'数据库中在线客户端数量: {len(online_clients)}')
        
        for client in online_clients:
            print(f'  客户端ID: {client.id}, 设备指纹: {client.device_fingerprint}')
            print(f'    状态: {client.status}, 最后连接: {client.last_seen}')
            print(f'    拥有者: {client.owner_id}, 连接码ID: {client.connect_code_id}')
            
        return len(online_clients)

def main():
    print('检查TCP连接、客户端管理器和数据库的同步状态')
    print('时间:', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    tcp_count = check_tcp_connections()
    manager_count = check_client_manager()
    db_count = check_database_clients()
    
    print('\n' + '=' * 60)
    print('总结')
    print('=' * 60)
    print(f'TCP连接数 (端口2383): {tcp_count}')
    print(f'客户端管理器中的客户端数: {manager_count}')
    print(f'数据库中在线客户端数: {db_count}')
    
    if tcp_count > 0 and manager_count == 0:
        print('\n[问题] TCP连接存在但客户端管理器为空！')
        print('这表明客户端连接存在但未正确注册到客户端管理器中。')
    elif tcp_count == manager_count == db_count:
        print('\n[正常] 所有状态同步正常')
    else:
        print('\n[警告] 状态不同步，需要进一步调查')

if __name__ == '__main__':
    main()
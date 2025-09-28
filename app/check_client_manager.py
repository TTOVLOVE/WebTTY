#!/usr/bin/env python3
"""
检查客户端管理器实时状态
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.services import client_manager

def main():
    print('=' * 60)
    print('客户端管理器实时状态')
    print('=' * 60)
    
    print(f'client_info 字典: {client_manager.client_info}')
    print(f'clients 字典: {client_manager.clients}')
    print(f'client_queues 字典: {client_manager.client_queues}')
    
    print('\n详细信息:')
    print(f'client_info 长度: {len(client_manager.client_info)}')
    print(f'clients 长度: {len(client_manager.clients)}')
    print(f'client_queues 长度: {len(client_manager.client_queues)}')
    
    if client_manager.client_info:
        print('\nclient_info 详细内容:')
        for client_id, info in client_manager.client_info.items():
            print(f'  客户端 {client_id}: {info}')
    
    if client_manager.clients:
        print('\nclients 详细内容:')
        for client_id, conn in client_manager.clients.items():
            print(f'  客户端 {client_id}: {conn}')

if __name__ == '__main__':
    main()
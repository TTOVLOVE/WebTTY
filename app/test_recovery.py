#!/usr/bin/env python3
"""
测试客户端状态恢复功能
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app
from app.services.client_recovery import check_recovery_needed, recover_client_manager_state
from app.services import client_manager

def main():
    print('=' * 60)
    print('测试客户端状态恢复功能')
    print('=' * 60)
    
    app = create_app()
    with app.app_context():
        print('恢复前状态:')
        print(f'  客户端管理器中的客户端数: {len(client_manager.client_info)}')
        print(f'  client_info: {client_manager.client_info}')
        
        print('\n检查是否需要恢复...')
        if check_recovery_needed():
            print('需要恢复，开始恢复过程...')
            recovered_count = recover_client_manager_state()
            print(f'恢复完成，共恢复 {recovered_count} 个客户端')
        else:
            print('不需要恢复')
        
        print('\n恢复后状态:')
        print(f'  客户端管理器中的客户端数: {len(client_manager.client_info)}')
        print(f'  client_info: {client_manager.client_info}')

if __name__ == '__main__':
    main()
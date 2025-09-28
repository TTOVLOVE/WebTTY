#!/usr/bin/env python3
"""
客户端状态恢复模块
用于在服务器重启后从现有TCP连接恢复客户端管理器状态
"""

import socket
import subprocess
import re
from datetime import datetime
from . import client_manager
from ..models import Client
from ..extensions import db

def get_established_connections(port=2383):
    """获取指定端口的已建立连接"""
    try:
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=True)
        lines = result.stdout.split('\n')
        
        connections = []
        for line in lines:
            if f':{port}' in line and 'ESTABLISHED' in line and 'TCP' in line:
                # 解析连接信息
                parts = line.strip().split()
                if len(parts) >= 4:
                    local_addr = parts[1]
                    remote_addr = parts[2]
                    pid = parts[4] if len(parts) > 4 else 'unknown'
                    
                    # 提取远程地址和端口
                    if ':' in remote_addr:
                        remote_ip, remote_port = remote_addr.rsplit(':', 1)
                        connections.append({
                            'local_addr': local_addr,
                            'remote_addr': remote_addr,
                            'remote_ip': remote_ip,
                            'remote_port': remote_port,
                            'pid': pid
                        })
        
        return connections
    except Exception as e:
        print(f"获取TCP连接时出错: {e}")
        return []

def recover_client_manager_state():
    """恢复客户端管理器状态"""
    print("[恢复] 开始恢复客户端管理器状态...")
    
    # 获取现有TCP连接
    connections = get_established_connections()
    print(f"[恢复] 发现 {len(connections)} 个已建立的TCP连接")
    
    # 获取数据库中的在线客户端
    online_clients = Client.query.filter_by(status='online').all()
    print(f"[恢复] 数据库中有 {len(online_clients)} 个在线客户端")
    
    recovered_count = 0
    
    for client in online_clients:
        # 为每个数据库中的在线客户端分配一个客户端ID
        # 这里使用简单的递增ID，实际应用中可能需要更复杂的逻辑
        client_id = recovered_count
        
        # 尝试匹配TCP连接（这里是简化的匹配逻辑）
        matched_connection = None
        if recovered_count < len(connections):
            matched_connection = connections[recovered_count]
        
        if matched_connection:
            # 创建虚拟连接对象（注意：这不是真正的socket连接）
            # 在实际应用中，我们需要重新建立与客户端的通信
            addr = (matched_connection['remote_ip'], int(matched_connection['remote_port']))
            
            # 注册到客户端管理器（使用None作为conn，因为我们无法恢复真正的socket）
            # 这需要修改register_client方法来处理恢复场景
            try:
                # 直接更新客户端管理器的状态
                client_manager.client_info[client_id] = {
                    'addr': addr,
                    'user': '恢复中...',
                    'initial_cwd': '恢复中...',
                    'os': '恢复中...',
                    'db_client_id': client.id,
                    'recovered': True,
                    'recovery_time': datetime.now()
                }
                
                print(f"[恢复] 已恢复客户端 {client_id}: db_id={client.id}, addr={addr}")
                recovered_count += 1
                
            except Exception as e:
                print(f"[恢复] 恢复客户端 {client.id} 时出错: {e}")
    
    print(f"[恢复] 完成，共恢复 {recovered_count} 个客户端到管理器中")
    return recovered_count

def check_recovery_needed():
    """检查是否需要恢复"""
    # 获取TCP连接数
    connections = get_established_connections()
    tcp_count = len(connections)
    
    # 获取客户端管理器中的客户端数
    manager_count = len(client_manager.client_info)
    
    # 获取数据库中的在线客户端数
    online_clients = Client.query.filter_by(status='online').all()
    db_count = len(online_clients)
    
    print(f"[检查] TCP连接: {tcp_count}, 管理器: {manager_count}, 数据库: {db_count}")
    
    # 如果有TCP连接和数据库记录，但管理器为空，则需要恢复
    return tcp_count > 0 and db_count > 0 and manager_count == 0

if __name__ == '__main__':
    # 测试恢复功能
    if check_recovery_needed():
        recover_client_manager_state()
    else:
        print("[检查] 不需要恢复")
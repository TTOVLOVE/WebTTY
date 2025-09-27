#!/usr/bin/env python3
"""
简化的数据库初始化脚本
直接使用SQLite创建表结构
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

def create_database():
    """
    创建数据库和表结构
    """
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'app.db')
    
    # 确保instance目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建角色表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) UNIQUE NOT NULL,
                description VARCHAR(200)
            )
        ''')
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES role (id)
            )
        ''')
        
        # 创建客户端表（包含新的设备指纹字段）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id VARCHAR(64) UNIQUE NOT NULL,
                hostname VARCHAR(128),
                ip_address VARCHAR(64),
                os_type VARCHAR(64),
                os_version VARCHAR(64),
                status VARCHAR(20) DEFAULT 'offline',
                last_seen TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                owner_id INTEGER,
                device_fingerprint VARCHAR(256) UNIQUE,
                hardware_id VARCHAR(128),
                mac_address VARCHAR(64),
                FOREIGN KEY (owner_id) REFERENCES user (id)
            )
        ''')
        
        # 创建客户端日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS client_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                user_id INTEGER,
                action VARCHAR(100),
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients (id),
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        ''')
        
        # 创建连接表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                connection_type VARCHAR(50),
                status VARCHAR(20),
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients (id)
            )
        ''')
        
        # 检查是否已有角色数据
        cursor.execute("SELECT COUNT(*) FROM role")
        role_count = cursor.fetchone()[0]
        
        if role_count == 0:
            # 插入角色数据
            roles = [
                ('admin', '超级管理员'),
                ('manager', '管理员'),
                ('user', '普通用户')
            ]
            cursor.executemany("INSERT INTO role (name, description) VALUES (?, ?)", roles)
            
            # 获取admin角色ID
            cursor.execute("SELECT id FROM role WHERE name = 'admin'")
            admin_role_id = cursor.fetchone()[0]
            
            # 创建初始管理员账户
            admin_password_hash = generate_password_hash('admin123')
            cursor.execute("""
                INSERT INTO user (username, email, password_hash, role_id) 
                VALUES (?, ?, ?, ?)
            """, ('admin', 'admin@example.com', admin_password_hash, admin_role_id))
            
            print("数据库初始化完成！")
            print("初始管理员账户: admin / admin123")
        else:
            print("数据库已初始化，无需重复操作")
        
        # 提交更改
        conn.commit()
        conn.close()
        
        print("数据库表结构创建完成！")
        return True
        
    except Exception as e:
        print(f"创建数据库时发生错误: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    print("开始创建数据库...")
    print("=" * 50)
    
    success = create_database()
    
    print("=" * 50)
    if success:
        print("数据库创建成功！")
    else:
        print("数据库创建失败！请检查错误信息并重试。")
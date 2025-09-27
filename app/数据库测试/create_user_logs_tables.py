#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建用户日志相关表的数据库迁移脚本
运行此脚本来添加个人信息页面所需的动态数据表
"""

import sqlite3
import os
from datetime import datetime

def create_user_logs_tables():
    """创建用户日志相关表"""
    
    # 数据库文件路径
    db_path = os.path.join('instance', 'app.db')
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件 {db_path} 不存在")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("开始创建用户日志相关表...")
        
        # 1. 创建用户登录日志表
        print("创建 user_login_logs 表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time DATETIME NOT NULL,
                logout_time DATETIME,
                ip_address VARCHAR(45),
                user_agent TEXT,
                login_status VARCHAR(20) DEFAULT 'success',
                failure_reason VARCHAR(255),
                session_id VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # 2. 创建用户活动日志表
        print("创建 user_activity_logs 表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action_type VARCHAR(50) NOT NULL,
                action_description TEXT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                additional_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # 3. 创建用户安全信息表
        print("创建 user_security_info 表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_security_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                password_changed_at DATETIME,
                failed_login_attempts INTEGER DEFAULT 0,
                last_failed_login_at DATETIME,
                account_locked_until DATETIME,
                two_factor_enabled BOOLEAN DEFAULT FALSE,
                login_notifications_enabled BOOLEAN DEFAULT TRUE,
                session_timeout_minutes INTEGER DEFAULT 30,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # 4. 创建索引以提高查询性能
        print("创建索引...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_login_logs_user_id ON user_login_logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_login_logs_time ON user_login_logs(login_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_logs_user_id ON user_activity_logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_logs_time ON user_activity_logs(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_security_info_user_id ON user_security_info(user_id)')
        
        # 5. 为现有用户创建安全信息记录
        print("为现有用户创建安全信息记录...")
        cursor.execute('''
            INSERT OR IGNORE INTO user_security_info (user_id, password_changed_at, created_at)
            SELECT id, created_at, CURRENT_TIMESTAMP FROM users
        ''')
        
        # 6. 插入一些示例数据（可选）
        print("插入示例数据...")
        
        # 获取第一个用户ID
        cursor.execute('SELECT id FROM users LIMIT 1')
        user_result = cursor.fetchone()
        
        if user_result:
            user_id = user_result[0]
            
            # 插入登录日志示例
            cursor.execute('''
                INSERT OR IGNORE INTO user_login_logs 
                (user_id, login_time, ip_address, user_agent, login_status)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, datetime.now(), '127.0.0.1', 'Mozilla/5.0', 'success'))
            
            # 插入活动日志示例
            cursor.execute('''
                INSERT OR IGNORE INTO user_activity_logs 
                (user_id, action_type, action_description, ip_address)
                VALUES (?, ?, ?, ?)
            ''', (user_id, 'profile_view', '查看个人信息页面', '127.0.0.1'))
        
        conn.commit()
        print("✅ 所有表创建成功！")
        
        # 验证表是否创建成功
        print("\n验证表结构...")
        tables = ['user_login_logs', 'user_activity_logs', 'user_security_info']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} 条记录")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False
    finally:
        if conn:
            conn.close()

def show_table_structure():
    """显示新创建表的结构"""
    db_path = os.path.join('instance', 'app.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        tables = ['user_login_logs', 'user_activity_logs', 'user_security_info']
        
        for table in tables:
            print(f"\n=== {table} 表结构 ===")
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            
            for col in columns:
                print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else ''} {'PRIMARY KEY' if col[5] else ''}")
    
    except sqlite3.Error as e:
        print(f"查询表结构失败: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("=== 用户日志表创建脚本 ===")
    print("此脚本将创建以下表:")
    print("1. user_login_logs - 用户登录日志")
    print("2. user_activity_logs - 用户活动日志") 
    print("3. user_security_info - 用户安全信息")
    print()
    
    if create_user_logs_tables():
        print("\n=== 创建完成 ===")
        show_table_structure()
        print("\n现在你可以:")
        print("1. 运行应用程序")
        print("2. 访问个人信息页面查看动态数据")
        print("3. 查看生成的示例数据")
    else:
        print("\n=== 创建失败 ===")
        print("请检查错误信息并重试")
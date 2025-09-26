#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的用户查询测试
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 直接使用SQLite查询
import sqlite3

def test_direct_db_query():
    db_path = r"E:\test\instance\app.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=== 直接数据库查询测试 ===")
        
        # 1. 查询用户表结构
        print("\n1. 用户表结构:")
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - NOT NULL: {col[3]}, DEFAULT: {col[4]}")
        
        # 2. 查询所有用户
        print("\n2. 所有用户数据:")
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        print(f"用户总数: {len(users)}")
        
        for user in users:
            print(f"  用户: {user}")
        
        # 3. 查询角色表
        print("\n3. 角色表数据:")
        cursor.execute("SELECT * FROM roles")
        roles = cursor.fetchall()
        print(f"角色总数: {len(roles)}")
        
        for role in roles:
            print(f"  角色: {role}")
        
        # 4. 联合查询用户和角色
        print("\n4. 用户-角色联合查询:")
        cursor.execute("""
            SELECT u.id, u.username, u.email, u.is_active, u.created_at, u.last_login, 
                   u.role_id, r.name as role_name
            FROM users u 
            LEFT JOIN roles r ON u.role_id = r.id
        """)
        user_roles = cursor.fetchall()
        
        for ur in user_roles:
            print(f"  用户ID: {ur[0]}, 用户名: {ur[1]}, 邮箱: {ur[2]}")
            print(f"    激活: {ur[3]}, 创建时间: {ur[4]}, 最后登录: {ur[5]}")
            print(f"    角色ID: {ur[6]}, 角色名: {ur[7]}")
            print("    ---")
        
        conn.close()
        
    except Exception as e:
        print(f"数据库查询出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_direct_db_query()
#!/usr/bin/env python3
"""
检查数据库表结构
"""

import sqlite3
import os

def check_database_structure():
    """
    检查数据库表结构
    """
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'app.db')
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("数据库中的表:")
        print("=" * 50)
        
        for table in tables:
            table_name = table[0]
            print(f"\n表名: {table_name}")
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print("  列信息:")
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, pk = col
                print(f"    {col_name} ({col_type}) {'NOT NULL' if not_null else ''} {'PRIMARY KEY' if pk else ''}")
            
            # 获取记录数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  记录数: {count}")
        
        conn.close()
        
    except Exception as e:
        print(f"检查数据库时发生错误: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_database_structure()
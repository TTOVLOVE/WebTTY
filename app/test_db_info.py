#!/usr/bin/env python3
"""
测试数据库信息接口
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db

def test_database_info():
    app = create_app()
    
    with app.app_context():
        # 测试数据库连接
        try:
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            db_type = db_uri.split(':')[0] if db_uri else 'sqlite'
            
            print(f"数据库URI: {db_uri}")
            print(f"数据库类型: {db_type}")
            print(f"实例路径: {app.instance_path}")
            
            # 对于SQLite数据库，获取实际文件路径
            if db_type == 'sqlite':
                if ':///' in db_uri:
                    db_path = db_uri.split(':///', 1)[1]
                    if not os.path.isabs(db_path):
                        db_path = os.path.join(app.instance_path, db_path)
                else:
                    db_path = app.config.get('DATABASE_PATH', 'app.db')
                    if not os.path.isabs(db_path):
                        db_path = os.path.join(app.instance_path, db_path)
                
                print(f"数据库文件路径: {db_path}")
                print(f"文件是否存在: {os.path.exists(db_path)}")
                
                if os.path.exists(db_path):
                    size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
                    print(f"文件大小: {size_mb} MB")
            
            # 测试数据库查询
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            print(f"表数量: {len(table_names)}")
            print(f"表名: {table_names}")
            
            # 测试查询
            from app.models import User, Client, SystemLog
            user_count = User.query.count()
            client_count = Client.query.count()
            log_count = SystemLog.query.count()
            
            print(f"用户数量: {user_count}")
            print(f"客户端数量: {client_count}")
            print(f"日志数量: {log_count}")
            
            print("数据库连接状态: connected")
            
        except Exception as e:
            print(f"数据库连接失败: {e}")
            print("数据库连接状态: error")

if __name__ == '__main__':
    test_database_info()
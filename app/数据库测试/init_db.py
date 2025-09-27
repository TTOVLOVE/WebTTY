import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from __init__ import create_app
from extensions import db
from models import Role, User
from werkzeug.security import generate_password_hash

def init_db():
    """初始化数据库，创建表和初始数据"""
    app = create_app()
    with app.app_context():
        # 创建所有表
        db.create_all()
        
        # 检查是否已有角色数据
        if Role.query.count() == 0:
            # 创建角色
            roles = [
                Role(name='admin', description='超级管理员'),
                Role(name='manager', description='管理员'),
                Role(name='user', description='普通用户')
            ]
            db.session.add_all(roles)
            db.session.commit()
            
            # 创建初始管理员账户
            admin_role = Role.query.filter_by(name='admin').first()
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                role_id=admin_role.id
            )
            db.session.add(admin)
            db.session.commit()
            
            print("数据库初始化完成！")
            print("初始管理员账户: admin / admin123")
        else:
            print("数据库已初始化，无需重复操作")

if __name__ == '__main__':
    init_db()
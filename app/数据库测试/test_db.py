"""
数据库功能测试脚本
"""
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 

from app import create_app, db
from app.models import User, Role, InvitationCode, SystemLog, Client, ClientLog, Connection

def test_db_connection():
    """测试数据库连接"""
    app = create_app()
    with app.app_context():
        try:
            # 尝试执行简单查询，使用text()函数包装SQL语句
            from sqlalchemy import text
            db.session.execute(text("SELECT 1"))
            print("数据库连接成功！")
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False

def test_create_tables():
    """测试创建数据库表"""
    app = create_app()
    with app.app_context():
        try:
            # 创建所有表
            db.create_all()
            print("数据库表创建成功！")
            return True
        except Exception as e:
            print(f"数据库表创建失败: {e}")
            return False

def test_create_initial_data():
    """测试创建初始数据"""
    app = create_app()
    with app.app_context():
        try:
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
                print("角色数据创建成功！")
            else:
                print("角色数据已存在")
                
            # 检查是否已有管理员用户
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                # 创建管理员用户
                admin_role = Role.query.filter_by(name='admin').first()
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    password='admin123',  # 会自动哈希
                    role_id=admin_role.id
                )
                db.session.add(admin)
                db.session.commit()
                print("管理员用户创建成功！")
            else:
                print("管理员用户已存在")
                
            # 创建测试邀请码
            invitation = InvitationCode(
                code=InvitationCode.generate_code(),
                created_by=admin.id
            )
            db.session.add(invitation)
            db.session.commit()
            print(f"测试邀请码创建成功: {invitation.code}")
            
            return True
        except Exception as e:
            print(f"初始数据创建失败: {e}")
            return False

def run_all_tests():
    """运行所有测试"""
    print("=== 开始数据库测试 ===")
    
    # 测试数据库连接
    if not test_db_connection():
        print("数据库连接测试失败，终止后续测试")
        return False
        
    # 测试创建表
    if not test_create_tables():
        print("数据库表创建测试失败，终止后续测试")
        return False
        
    # 测试创建初始数据
    if not test_create_initial_data():
        print("初始数据创建测试失败")
        return False
        
    print("=== 数据库测试全部通过 ===")
    return True

if __name__ == '__main__':
    run_all_tests()
import click
from flask.cli import with_appcontext
from .extensions import db
from .models import Role, User, InvitationCode
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

@click.command('init-db')
@with_appcontext
def init_db_command():
    """初始化数据库，创建表和初始数据"""
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
        
        # 创建初始邀请码
        invitation = InvitationCode(
            code=InvitationCode.generate_code(),
            created_by=admin.id,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        db.session.add(invitation)
        db.session.commit()
        
        click.echo('数据库初始化完成！')
        click.echo(f'初始管理员账户: admin / admin123')
        click.echo(f'初始邀请码: {invitation.code}')
    else:
        click.echo('数据库已初始化，无需重复操作')

def register_commands(app):
    """注册Flask CLI命令"""
    app.cli.add_command(init_db_command)
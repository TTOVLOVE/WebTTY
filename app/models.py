from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
from .extensions import db

class Role(db.Model):
    """用户角色表"""
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)  # admin, manager, user
    description = db.Column(db.String(255))
    
    users = db.relationship('User', backref='role', lazy='dynamic')

class InvitationCode(db.Model):
    """邀请码表"""
    __tablename__ = 'invitation_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_invitations')
    user = db.relationship('User', foreign_keys=[used_by], backref='used_invitation')
    
    @staticmethod
    def generate_code():
        """生成唯一邀请码"""
        return uuid.uuid4().hex[:16]

class User(db.Model, UserMixin):
    """用户表"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    parent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # 用户层级关系
    subordinates = db.relationship('User', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    
    @property
    def password(self):
        raise AttributeError('密码不可读')
        
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_administrator(self):
        return self.role.name == 'admin'
    
    def is_manager(self):
        return self.role.name == 'manager'
    
    @staticmethod
    def get(user_id):
        """根据用户ID获取用户对象"""
        try:
            return User.query.get(int(user_id))
        except ValueError:
            # 处理非数字ID的情况，尝试通过用户名查找
            return User.query.filter_by(username=user_id).first()
    
    @staticmethod
    def authenticate(username, password):
        """验证用户登录"""
        user = User.query.filter_by(username=username).first()
        if user and user.verify_password(password):
            return user
        return None

class SystemLog(db.Model):
    """系统操作日志表"""
    __tablename__ = 'system_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(64), nullable=False)  # login, logout, create_user, etc.
    resource_type = db.Column(db.String(64), nullable=True)  # user, client, connection, etc.
    resource_id = db.Column(db.String(64), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    details = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False)  # success, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='system_logs')
    
    @staticmethod
    def log_action(user_id, action, resource_type=None, resource_id=None, 
                  ip_address=None, details=None, status='success'):
        """记录系统操作"""
        log = SystemLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details,
            status=status
        )
        db.session.add(log)
        db.session.commit()
        return log

class Client(db.Model):
    """客户端表"""
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), unique=True, nullable=False)
    hostname = db.Column(db.String(128), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    os_type = db.Column(db.String(64), nullable=True)  # windows, linux, macos
    os_version = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(20), default='offline')  # online, offline
    last_seen = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    owner = db.relationship('User', backref='owned_clients')
    logs = db.relationship('ClientLog', backref='client', lazy='dynamic')

class ClientLog(db.Model):
    """客户端操作日志表"""
    __tablename__ = 'client_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(64), nullable=True)
    action = db.Column(db.String(64), nullable=False)  # command, file_upload, file_download, etc.
    command = db.Column(db.Text, nullable=True)
    output = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(255), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False)  # success, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='client_logs')

class Connection(db.Model):
    """连接配置表"""
    __tablename__ = 'connections'
    
    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # ssh, sftp, vnc, rdp
    host = db.Column(db.String(128), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(64), nullable=True)
    password = db.Column(db.String(128), nullable=True)  # 应加密存储
    private_key = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_connected = db.Column(db.DateTime, nullable=True)
    connection_count = db.Column(db.Integer, default=0)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    owner = db.relationship('User', backref='connections')

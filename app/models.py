from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
from .extensions import db
from enum import Enum

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

class RoleType(Enum):
    SUPER_ADMIN = 'super_admin'
    ADMIN = 'admin'
    USER = 'user'

class ConnectCode(db.Model):
    __tablename__ = 'connect_codes'
    id = db.Column(db.Integer, primary_key=True)
    code_hash = db.Column(db.String(255), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    guest_session_id = db.Column(db.String(64), nullable=True, index=True)
    code_type = db.Column(db.String(8), nullable=False)  # 'user' | 'guest'
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_rotated_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'is_active', name='uq_user_active_code'),
        db.UniqueConstraint('guest_session_id', 'is_active', name='uq_guest_active_code'),
    )

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
    role_type = db.Column('role', db.String(20), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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

    def to_dict(self):
        """将用户信息序列化为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role.name if self.role else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'avatar': getattr(self, 'avatar', '/static/images/default-avatar.svg')  # 假设有avatar字段
        }
    
    def is_super_admin(self):
        """检查是否为超级管理员"""
        # 新枚举：检查 role_type 是否为 super_admin
        if hasattr(self, 'role_type') and self.role_type == RoleType.SUPER_ADMIN.value:
            return True
        # 旧表：检查 role.name 是否为 admin（超级管理员）
        return bool(getattr(self, 'role', None) and self.role.name == 'admin')
    
    def is_administrator(self):
        # 新枚举：super_admin 和 admin 都视为管理员；旧表：admin/manager 也兼容
        if hasattr(self, 'role_type') and self.role_type in {RoleType.SUPER_ADMIN.value, RoleType.ADMIN.value}:
            return True
        return bool(getattr(self, 'role', None) and self.role.name in ['admin', 'manager'])
    
    def is_admin(self):
        """检查是否为管理员（包括超级管理员和普通管理员）"""
        return self.is_administrator()
    
    def is_guest(self):
        """检查是否为游客用户"""
        return self.role and self.role.name == 'guest'
    
    def is_manager(self):
        # 新枚举的 admin 等价旧的 manager
        if hasattr(self, 'role_type') and self.role_type == RoleType.ADMIN.value:
            return True
        return bool(getattr(self, 'role', None) and self.role.name == 'manager')
    
    def role_display(self):
        """统一输出角色字符串，用于模板/日志展示"""
        if hasattr(self, 'role_type') and self.role_type:
            if hasattr(self.role_type, 'value'):
                return self.role_type.value
            return self.role_type
        return getattr(self, 'role', None).name if getattr(self, 'role', None) else 'user'
    
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
    
    # 连接码归属（用户码或游客码分组）
    connect_code_id = db.Column(db.Integer, db.ForeignKey('connect_codes.id'), nullable=True, index=True)
    connect_code = db.relationship('ConnectCode', foreign_keys=[connect_code_id])
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), unique=True, nullable=False)
    # 设备唯一标识字段
    hardware_id = db.Column(db.String(128), nullable=True, index=True)  # 硬件ID（如主板序列号、CPU ID等）
    mac_address = db.Column(db.String(64), nullable=True, index=True)   # MAC地址
    device_fingerprint = db.Column(db.String(256), nullable=True, unique=True, index=True)  # 设备指纹（综合多个硬件信息生成）
    hostname = db.Column(db.String(128), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    os_type = db.Column(db.String(64), nullable=True)  # windows, linux, macos
    os_version = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(20), default='offline')  # online, offline
    last_seen = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    owner = db.relationship('User', backref='owned_clients')
    # 连接码关系已在上方声明
    logs = db.relationship('ClientLog', backref='client', lazy='dynamic')
    
    @staticmethod
    def find_or_create_by_fingerprint(device_fingerprint, **kwargs):
        """根据设备指纹查找或创建客户端记录"""
        if device_fingerprint:
            # 首先尝试通过设备指纹查找
            client = Client.query.filter_by(device_fingerprint=device_fingerprint).first()
            if client:
                # 更新现有客户端信息（不修改 device_fingerprint 与 client_id，client_id 作为稳定唯一标识）
                for key, value in kwargs.items():
                    if key in ("device_fingerprint", "client_id"):
                        continue
                    if hasattr(client, key) and value is not None:
                        setattr(client, key, value)
                return client, False  # 返回现有客户端，False表示不是新创建的
            
            # 只有在有设备指纹的情况下才创建新记录
            client_data = kwargs.copy()
            # 强制忽略外部传入的临时 client_id，统一生成稳定 UUID
            client_data.pop('client_id', None)
            client_data['device_fingerprint'] = device_fingerprint
            client_data['client_id'] = uuid.uuid4().hex
            client = Client(**client_data)
            return client, True  # 返回新客户端，True表示是新创建的
        else:
            # 没有设备指纹时，不创建新记录，返回None
            return None, False

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



class Device(db.Model):
    """设备表"""
    __tablename__ = 'devices'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # 其他设备信息字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    owner = db.relationship('User', backref='devices')


class UserLoginLog(db.Model):
    """用户登录日志表"""
    __tablename__ = 'user_login_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    logout_time = db.Column(db.DateTime, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # 支持IPv6
    user_agent = db.Column(db.String(500), nullable=True)
    device_info = db.Column(db.String(200), nullable=True)
    login_status = db.Column(db.String(20), default='success', nullable=False)  # success, failed
    failure_reason = db.Column(db.String(200), nullable=True)
    session_duration = db.Column(db.Integer, nullable=True)  # 会话时长（秒）
    
    user = db.relationship('User', backref='login_logs')
    
    def __repr__(self):
        return f'<UserLoginLog {self.user_id} at {self.login_time}>'


class UserActivityLog(db.Model):
    """用户活动日志表"""
    __tablename__ = 'user_activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # profile_update, password_change, etc.
    activity_description = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    activity_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), default='success', nullable=False)  # success, failed
    details = db.Column(db.Text, nullable=True)  # JSON格式的详细信息
    
    user = db.relationship('User', backref='activity_logs')
    
    def __repr__(self):
        return f'<UserActivityLog {self.user_id}: {self.activity_type}>'


class UserSecurityInfo(db.Model):
    """用户安全信息表"""
    __tablename__ = 'user_security_info'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    password_last_changed = db.Column('password_changed_at', db.DateTime, nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    last_failed_login = db.Column('last_failed_login_at', db.DateTime, nullable=True)
    account_locked_until = db.Column(db.DateTime, nullable=True)
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=False)
    login_notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)
    session_timeout_minutes = db.Column(db.Integer, default=30, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    user = db.relationship('User', backref=db.backref('security_info', uselist=False))
    
    def __repr__(self):
        return f'<UserSecurityInfo for user {self.user_id}>'

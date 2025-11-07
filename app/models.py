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
    
    def can_view_client(self, client):
        """检查用户是否可以查看指定客户端"""
        if self.is_super_admin():
            return True  # 超级管理员可以查看所有客户端
        return client.owner_id == self.id  # 普通用户只能查看自己的客户端
    
    def can_operate_client(self, client):
        """检查用户是否可以操作指定客户端"""
        # 客户端所有者可以操作
        if client.owner_id == self.id:
            return True
        
        # 检查是否通过该用户的连接码连接的客户端
        if client.connect_code and client.connect_code.user_id == self.id:
            return True
            
        # 超级管理员可以操作所有客户端（但在UI上可以区分显示）
        if self.is_super_admin():
            return True
            
        return False
    
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

class VulnerabilityScanRecord(db.Model):
    """漏洞扫描记录"""
    __tablename__ = 'vulnerability_scan_records'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    client_id = db.Column(db.String(64), nullable=True)
    db_client_id = db.Column(db.Integer, nullable=True)
    target_name = db.Column(db.String(255), nullable=False)
    target_ip = db.Column(db.String(64), nullable=True)
    scan_type = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    progress = db.Column(db.Integer, default=0)
    options = db.Column(db.JSON, nullable=True)
    command = db.Column(db.JSON, nullable=True)
    results = db.Column(db.JSON, nullable=True)
    vulnerabilities = db.Column(db.JSON, nullable=True)
    raw_output = db.Column(db.JSON, nullable=True)
    log_path = db.Column(db.String(255), nullable=True)
    report_path = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='vulnerability_scans')

    def to_dict(self, include_raw=False):
        data = {
            'id': self.id,
            'task_id': self.task_id,
            'user_id': self.user_id,
            'client_id': self.client_id,
            'db_client_id': self.db_client_id,
            'target': self.target_name,
            'target_name': self.target_name,
            'target_client_id': self.client_id,
            'target_ip': self.target_ip,
            'scan_type': self.scan_type,
            'status': self.status,
            'progress': self.progress,
            'options': self.options or {},
            'command': self.command or [],
            'results': self.results or [],
            'vulnerabilities': self.vulnerabilities or self.results or [],
            'log_path': self.log_path,
            'report_path': self.report_path,
            'message': self.message or '',
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_raw:
            data['raw_output'] = self.raw_output or []
        return data


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


class SecurityGroup(db.Model):
    """安全组表"""
    __tablename__ = 'security_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    group_type = db.Column(db.String(20), default='custom', nullable=False)  # default, restricted, high_security, custom
    parent_group_id = db.Column(db.Integer, db.ForeignKey('security_groups.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 关系
    parent_group = db.relationship('SecurityGroup', remote_side=[id], backref='child_groups')
    creator = db.relationship('User', backref='created_security_groups')
    rules = db.relationship('CommandBlacklistRule', backref='security_group', lazy='dynamic', cascade='all, delete-orphan')
    client_assignments = db.relationship('ClientSecurityGroup', backref='security_group', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'group_type': self.group_type,
            'parent_group_id': self.parent_group_id,
            'parent_group_name': self.parent_group.name if self.parent_group else None,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'creator_name': self.creator.username if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'rule_count': self.rules.count(),
            'client_count': self.client_assignments.filter_by(is_active=True).count()
        }
    
    @staticmethod
    def get_by_id(group_id):
        """根据ID获取安全组"""
        return SecurityGroup.query.get(group_id)
    
    @staticmethod
    def get_active_groups():
        """获取所有活跃的安全组"""
        return SecurityGroup.query.filter_by(is_active=True).all()
    
    def get_active_rules(self, os_type=None):
        """获取该安全组的活跃规则"""
        query = self.rules.filter_by(is_active=True)
        if os_type:
            query = query.filter(db.or_(
                CommandBlacklistRule.os_type == os_type,
                CommandBlacklistRule.os_type == 'all'
            ))
        return query.order_by(CommandBlacklistRule.priority.asc()).all()


class CommandBlacklistRule(db.Model):
    """命令黑名单规则表"""
    __tablename__ = 'command_blacklist_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    security_group_id = db.Column(db.Integer, db.ForeignKey('security_groups.id'), nullable=False)
    rule_type = db.Column(db.String(20), nullable=False)  # command, pattern, category
    rule_value = db.Column(db.String(255), nullable=False)
    os_type = db.Column(db.String(20), nullable=True)  # windows, linux, all
    action = db.Column(db.String(20), default='block', nullable=False)  # block, warn, allow
    priority = db.Column(db.Integer, default=100, nullable=False)  # 数值越小优先级越高
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 索引
    __table_args__ = (
        db.Index('idx_security_group_priority', 'security_group_id', 'priority'),
        db.Index('idx_rule_type_os', 'rule_type', 'os_type'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'security_group_id': self.security_group_id,
            'security_group_name': self.security_group.name if self.security_group else None,
            'rule_type': self.rule_type,
            'rule_value': self.rule_value,
            'os_type': self.os_type,
            'action': self.action,
            'priority': self.priority,
            'is_active': self.is_active,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def get_by_security_group(security_group_id, os_type=None):
        """根据安全组ID获取规则"""
        query = CommandBlacklistRule.query.filter_by(
            security_group_id=security_group_id,
            is_active=True
        )
        if os_type:
            query = query.filter(db.or_(
                CommandBlacklistRule.os_type == os_type,
                CommandBlacklistRule.os_type == 'all'
            ))
        return query.order_by(CommandBlacklistRule.priority.asc()).all()
    
    def matches_command(self, command):
        """检查规则是否匹配命令"""
        import re
        
        if self.rule_type == 'command':
            return command.strip().lower().startswith(self.rule_value.lower())
        elif self.rule_type == 'pattern':
            try:
                return bool(re.search(self.rule_value, command, re.IGNORECASE))
            except re.error:
                return False
        elif self.rule_type == 'category':
            # 可以根据需要实现分类匹配逻辑
            dangerous_commands = {
                'system': ['rm', 'del', 'format', 'fdisk', 'mkfs'],
                'network': ['wget', 'curl', 'nc', 'netcat'],
                'process': ['kill', 'killall', 'taskkill']
            }
            if self.rule_value in dangerous_commands:
                return any(command.strip().lower().startswith(cmd) for cmd in dangerous_commands[self.rule_value])
        
        return False


class ClientSecurityGroup(db.Model):
    """客户端安全组关联表"""
    __tablename__ = 'client_security_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    security_group_id = db.Column(db.Integer, db.ForeignKey('security_groups.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # 关系
    client = db.relationship('Client', backref='security_group_assignments')
    assigner = db.relationship('User', backref='assigned_security_groups')
    
    # 唯一约束：一个客户端只能分配一个活跃的安全组
    __table_args__ = (
        db.UniqueConstraint('client_id', 'is_active', name='uq_client_active_security_group'),
        db.Index('idx_client_security_group', 'client_id', 'security_group_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_hostname': self.client.hostname if self.client else None,
            'security_group_id': self.security_group_id,
            'security_group_name': self.security_group.name if self.security_group else None,
            'assigned_by': self.assigned_by,
            'assigner_name': self.assigner.username if self.assigner else None,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'is_active': self.is_active
        }
    
    @staticmethod
    def get_active_assignment(client_id):
        """获取客户端的活跃安全组分配"""
        return ClientSecurityGroup.query.filter_by(
            client_id=client_id,
            is_active=True
        ).first()
    
    @staticmethod
    def assign_security_group(client_id, security_group_id, assigned_by):
        """为客户端分配安全组"""
        # 先取消现有的活跃分配
        existing = ClientSecurityGroup.get_active_assignment(client_id)
        if existing:
            existing.is_active = False
        
        # 创建新的分配
        assignment = ClientSecurityGroup(
            client_id=client_id,
            security_group_id=security_group_id,
            assigned_by=assigned_by
        )
        db.session.add(assignment)
        return assignment


class CommandExecutionLog(db.Model):
    """命令执行日志表"""
    __tablename__ = 'command_execution_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(64), nullable=True)
    command = db.Column(db.Text, nullable=False)
    command_type = db.Column(db.String(50), nullable=True)  # execute_command, shell_command
    action = db.Column(db.String(20), nullable=False)  # allowed, blocked, warned
    security_group_id = db.Column(db.Integer, db.ForeignKey('security_groups.id'), nullable=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('command_blacklist_rules.id'), nullable=True)
    rule_matched = db.Column(db.String(255), nullable=True)  # 匹配的规则内容
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    execution_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    response_message = db.Column(db.Text, nullable=True)
    
    # 关系
    client = db.relationship('Client', backref='command_execution_logs')
    user = db.relationship('User', backref='command_execution_logs')
    security_group = db.relationship('SecurityGroup', backref='command_execution_logs')
    rule = db.relationship('CommandBlacklistRule', backref='command_execution_logs')
    
    # 索引
    __table_args__ = (
        db.Index('idx_client_execution_time', 'client_id', 'execution_time'),
        db.Index('idx_user_execution_time', 'user_id', 'execution_time'),
        db.Index('idx_action_execution_time', 'action', 'execution_time'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_hostname': self.client.hostname if self.client else None,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'session_id': self.session_id,
            'command': self.command,
            'command_type': self.command_type,
            'action': self.action,
            'security_group_id': self.security_group_id,
            'security_group_name': self.security_group.name if self.security_group else None,
            'rule_id': self.rule_id,
            'rule_matched': self.rule_matched,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'execution_time': self.execution_time.isoformat() if self.execution_time else None,
            'response_message': self.response_message
        }
    
    @staticmethod
    def log_command_execution(client_id, command, action, user_id=None, session_id=None,
                            security_group_id=None, rule_id=None, rule_matched=None,
                            ip_address=None, user_agent=None, response_message=None,
                            command_type=None):
        """记录命令执行日志"""
        log = CommandExecutionLog(
            client_id=client_id,
            user_id=user_id,
            session_id=session_id,
            command=command,
            command_type=command_type,
            action=action,
            security_group_id=security_group_id,
            rule_id=rule_id,
            rule_matched=rule_matched,
            ip_address=ip_address,
            user_agent=user_agent,
            response_message=response_message
        )
        db.session.add(log)
        return log
    
    @staticmethod
    def get_recent_logs(client_id=None, user_id=None, action=None, limit=100):
        """获取最近的命令执行日志"""
        query = CommandExecutionLog.query
        
        if client_id:
            query = query.filter_by(client_id=client_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if action:
            query = query.filter_by(action=action)
        
        return query.order_by(CommandExecutionLog.execution_time.desc()).limit(limit).all()

from flask_login import UserMixin

class User(UserMixin):
    """用户模型类"""
    
    def __init__(self, user_id, username, email, role='user'):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role
    
    @staticmethod
    def get(user_id):
        """根据用户ID获取用户对象"""
        # 这里应该从数据库获取用户信息
        # 暂时使用模拟数据
        if user_id == 'admin':
            return User('admin', 'admin', 'admin@example.com', 'admin')
        return None
    
    @staticmethod
    def authenticate(username, password):
        """验证用户登录"""
        # 这里应该实现真实的用户验证逻辑
        # 暂时使用模拟数据
        if username == 'admin' and password == 'admin123':
            return User('admin', 'admin', 'admin@example.com', 'admin')
        return None

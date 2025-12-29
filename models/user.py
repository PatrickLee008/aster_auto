"""
用户模型
"""

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

from .base import db, BaseModel


class User(UserMixin, db.Model, BaseModel):
    """用户模型"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, comment='账号')
    email = db.Column(db.String(120), unique=True, nullable=True, comment='邮箱')
    password_hash = db.Column(db.String(255), nullable=False, comment='密码哈希')
    nickname = db.Column(db.String(100), nullable=False, comment='昵称')
    max_tasks = db.Column(db.Integer, default=5, comment='可创建任务数')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    is_admin = db.Column(db.Boolean, default=False, comment='是否管理员')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    last_login = db.Column(db.DateTime, comment='最后登录时间')
    
    # 关联关系
    wallets = db.relationship('Wallet', backref='owner', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='creator', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """更新最后登录时间"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def get_task_count(self):
        """获取用户当前任务数量"""
        return len(self.tasks)
    
    def can_create_task(self):
        """检查是否可以创建新任务"""
        if self.is_admin:
            return True  # 管理员无限制
        return self.get_task_count() < self.max_tasks
    
    def get_remaining_task_quota(self):
        """获取剩余任务配额"""
        if self.is_admin:
            return float('inf')
        return max(0, self.max_tasks - self.get_task_count())
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'nickname': self.nickname,
            'email': self.email,
            'max_tasks': self.max_tasks,
            'task_count': self.get_task_count(),
            'remaining_quota': self.get_remaining_task_quota(),
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    def __repr__(self):
        return f'<User {self.username}>'
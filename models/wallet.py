"""
钱包模型
"""

from datetime import datetime
from .base import db, BaseModel


class Wallet(db.Model, BaseModel):
    """钱包API配置模型"""
    __tablename__ = 'wallets'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    wallet_type = db.Column(db.String(20), nullable=False)  # 'spot' 或 'futures'
    
    # 现货API配置
    api_key = db.Column(db.Text)  # 加密存储
    secret_key = db.Column(db.Text)  # 加密存储
    
    # 期货API配置  
    user_address = db.Column(db.String(42))
    signer_address = db.Column(db.String(42))
    private_key = db.Column(db.Text)  # 加密存储
    
    # 状态和元数据
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    # 外键
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 关联关系
    tasks = db.relationship('Task', backref='wallet', lazy=True, cascade='all, delete-orphan')
    
    def set_api_credentials(self, api_key=None, secret_key=None, private_key=None):
        """设置API凭证（自动加密）"""
        from utils.encryption import encrypt_data
        if api_key:
            self.api_key = encrypt_data(api_key)
        if secret_key:
            self.secret_key = encrypt_data(secret_key)
        if private_key:
            self.private_key = encrypt_data(private_key)
    
    def get_api_credentials(self):
        """获取API凭证（自动解密）"""
        from utils.encryption import decrypt_data
        return {
            'api_key': decrypt_data(self.api_key) if self.api_key else None,
            'secret_key': decrypt_data(self.secret_key) if self.secret_key else None,
            'private_key': decrypt_data(self.private_key) if self.private_key else None
        }
    
    def update_last_used(self):
        """更新最后使用时间"""
        self.last_used = datetime.utcnow()
        db.session.commit()
    
    def get_masked_credentials(self):
        """获取脱敏的凭证信息（用于显示）"""
        credentials = self.get_api_credentials()
        return {
            'api_key': credentials['api_key'][:8] + '...' if credentials['api_key'] else None,
            'secret_key': '***' if credentials['secret_key'] else None,
            'private_key': '***' if credentials['private_key'] else None,
            'user_address': self.user_address,
            'signer_address': self.signer_address
        }
    
    def __repr__(self):
        return f'<Wallet {self.name}({self.wallet_type})>'
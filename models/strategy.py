"""
策略模型
"""

from datetime import datetime
import json

from .base import db, BaseModel


class Strategy(db.Model, BaseModel):
    """交易策略模型"""
    __tablename__ = 'strategies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    strategy_type = db.Column(db.String(50), nullable=False)  # 'volume', 'hidden_futures', etc.
    supported_wallet_types = db.Column(db.String(100))  # 'spot,futures' 或 'spot' 或 'futures'
    module_path = db.Column(db.String(255), nullable=False)  # Python模块路径
    class_name = db.Column(db.String(100), nullable=False)   # 策略类名
    default_parameters = db.Column(db.Text)  # JSON格式的默认参数
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    tasks = db.relationship('Task', backref='strategy', lazy=True)
    
    def get_default_parameters(self):
        """获取默认参数"""
        if self.default_parameters:
            return json.loads(self.default_parameters)
        return {}
    
    def set_default_parameters(self, params_dict):
        """设置默认参数"""
        self.default_parameters = json.dumps(params_dict)
    
    def is_compatible_with_wallet(self, wallet_type):
        """检查策略是否兼容指定的钱包类型"""
        if not self.supported_wallet_types:
            return False
            
        supported_types = self.supported_wallet_types.split(',')
        
        # 统一钱包兼容所有策略类型
        if wallet_type == 'unified':
            return True
            
        # 其他类型按原逻辑匹配
        return wallet_type in supported_types
    
    def __repr__(self):
        return f'<Strategy {self.name}({self.strategy_type})>'
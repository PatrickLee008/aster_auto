"""
系统配置模型
存储系统级别的配置项
"""

from datetime import datetime
from models.base import db


class SystemConfig(db.Model):
    """系统配置表"""
    __tablename__ = 'system_config'
    
    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(50), unique=True, nullable=False, comment='配置键')
    config_value = db.Column(db.String(500), nullable=True, comment='配置值')
    config_type = db.Column(db.String(20), default='string', comment='配置类型: string/boolean/integer')
    description = db.Column(db.String(200), comment='配置说明')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    def __repr__(self):
        return f'<SystemConfig {self.config_key}={self.config_value}>'
    
    @staticmethod
    def get_value(key, default=None):
        """获取配置值"""
        config = SystemConfig.query.filter_by(config_key=key).first()
        if not config:
            return default
        
        # 根据类型转换
        if config.config_type == 'boolean':
            return config.config_value.lower() in ['true', '1', 'yes']
        elif config.config_type == 'integer':
            try:
                return int(config.config_value)
            except:
                return default
        else:
            return config.config_value
    
    @staticmethod
    def set_value(key, value, config_type='string', description=None):
        """设置配置值"""
        config = SystemConfig.query.filter_by(config_key=key).first()
        
        if config:
            config.config_value = str(value)
            config.config_type = config_type
            if description:
                config.description = description
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(
                config_key=key,
                config_value=str(value),
                config_type=config_type,
                description=description
            )
            db.session.add(config)
        
        db.session.commit()
        return config
    
    @staticmethod
    def get_all_configs():
        """获取所有配置"""
        configs = SystemConfig.query.all()
        return {c.config_key: {
            'value': SystemConfig.get_value(c.config_key),
            'type': c.config_type,
            'description': c.description,
            'updated_at': c.updated_at
        } for c in configs}

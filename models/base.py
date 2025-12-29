"""
数据库基础配置
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class BaseModel:
    """基础模型类"""
    
    def save(self):
        """保存对象到数据库"""
        db.session.add(self)
        db.session.commit()
    
    def delete(self):
        """从数据库删除对象"""
        db.session.delete(self)
        db.session.commit()
    
    def to_dict(self):
        """转换为字典格式"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
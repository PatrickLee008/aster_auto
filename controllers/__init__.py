"""
控制器包
包含所有API路由和请求处理
"""

from .auth_controller import auth_bp
from .wallet_controller import wallet_bp
from .task_controller import task_bp
from .main_controller import main_bp

# 导入新的路由模块
try:
    from routes.auth import auth_bp as new_auth_bp
    from routes.users import users_bp
    
    # 使用新的认证路由替换旧的
    auth_bp = new_auth_bp
    
except ImportError:
    # 如果新模块不存在，使用原有的
    users_bp = None

__all__ = ['auth_bp', 'wallet_bp', 'task_bp', 'main_bp', 'users_bp']
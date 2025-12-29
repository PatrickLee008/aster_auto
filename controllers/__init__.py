"""
控制器包
包含所有API路由和请求处理
"""

from .auth_controller import auth_bp
from .wallet_controller import wallet_bp
from .task_controller import task_bp
from .main_controller import main_bp

__all__ = ['auth_bp', 'wallet_bp', 'task_bp', 'main_bp']
"""
认证服务
"""

from typing import Tuple, Optional
from flask_login import login_user, logout_user
from datetime import datetime

from models import User
from models.base import db


class AuthService:
    """认证服务类"""
    
    @staticmethod
    def login(username: str, password: str, remember_me: bool = False) -> Tuple[bool, str, Optional[User]]:
        """
        用户登录
        
        Returns:
            (success, message, user)
        """
        try:
            user = User.query.filter_by(username=username).first()
            
            if not user:
                return False, "用户不存在", None
            
            if not user.check_password(password):
                return False, "密码错误", None
            
            # 更新最后登录时间
            user.update_last_login()
            
            # 执行登录
            login_user(user, remember=remember_me)
            
            return True, "登录成功", user
            
        except Exception as e:
            return False, f"登录异常: {str(e)}", None
    
    @staticmethod
    def logout() -> Tuple[bool, str]:
        """
        用户退出
        
        Returns:
            (success, message)
        """
        try:
            logout_user()
            return True, "退出成功"
        except Exception as e:
            return False, f"退出异常: {str(e)}"
    
    @staticmethod
    def create_user(username: str, email: str, password: str, is_admin: bool = False) -> Tuple[bool, str, Optional[User]]:
        """
        创建新用户
        
        Returns:
            (success, message, user)
        """
        try:
            # 检查用户名是否已存在
            if User.query.filter_by(username=username).first():
                return False, "用户名已存在", None
            
            # 检查邮箱是否已存在
            if User.query.filter_by(email=email).first():
                return False, "邮箱已存在", None
            
            # 创建新用户
            user = User(
                username=username,
                email=email,
                is_admin=is_admin
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            return True, "用户创建成功", user
            
        except Exception as e:
            db.session.rollback()
            return False, f"创建用户失败: {str(e)}", None
    
    @staticmethod
    def change_password(user: User, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        修改密码
        
        Returns:
            (success, message)
        """
        try:
            # 验证旧密码
            if not user.check_password(old_password):
                return False, "原密码错误"
            
            # 设置新密码
            user.set_password(new_password)
            db.session.commit()
            
            return True, "密码修改成功"
            
        except Exception as e:
            db.session.rollback()
            return False, f"修改密码失败: {str(e)}"
    
    @staticmethod
    def get_user_stats(user: User) -> dict:
        """获取用户统计信息"""
        try:
            from models import Wallet, Task
            
            # 管理员查看所有数据，普通用户查看自己的数据
            if user.is_admin:
                stats = {
                    'total_wallets': Wallet.query.count(),
                    'active_wallets': Wallet.query.filter_by(is_active=True).count(),
                    'total_tasks': Task.query.count(),
                    'running_tasks': Task.query.filter_by(status='running').count(),
                    'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else '首次登录',
                    'is_admin': user.is_admin
                }
            else:
                stats = {
                    'total_wallets': Wallet.query.filter_by(user_id=user.id).count(),
                    'active_wallets': Wallet.query.filter_by(user_id=user.id, is_active=True).count(),
                    'total_tasks': Task.query.filter_by(user_id=user.id).count(),
                    'running_tasks': Task.query.filter_by(user_id=user.id, status='running').count(),
                    'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else '首次登录',
                    'is_admin': user.is_admin
                }
            
            return stats
            
        except Exception as e:
            print(f"获取用户统计失败: {e}")
            return {}
    
    @staticmethod
    def get_recent_tasks(user: User, limit: int = 5):
        """获取最近任务"""
        try:
            from models import Task
            
            # 管理员查看所有任务，普通用户查看自己的任务
            if user.is_admin:
                return Task.query.order_by(Task.updated_at.desc()).limit(limit).all()
            else:
                return Task.query.filter_by(user_id=user.id)\
                               .order_by(Task.updated_at.desc())\
                               .limit(limit).all()
        except Exception as e:
            print(f"获取最近任务失败: {e}")
            return []
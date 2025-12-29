"""
主控制器
处理主页面和通用路由
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from services import AuthService, StrategyService, WalletService

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """主页"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """仪表盘"""
    try:
        # 获取用户统计信息
        stats = AuthService.get_user_stats(current_user)
        
        # 获取最近任务
        recent_tasks = AuthService.get_recent_tasks(current_user, limit=5)
        
        # 获取代理配置信息
        from utils.proxy_config import get_proxy_info
        proxy_info = get_proxy_info()
        
        return render_template('dashboard.html', stats=stats, recent_tasks=recent_tasks, proxy_info=proxy_info)
        
    except Exception as e:
        print(f"仪表盘加载失败: {e}")
        return render_template('dashboard.html', stats={}, recent_tasks=[])


@main_bp.route('/wallets')
@login_required  
def wallets():
    """钱包管理页面"""
    try:
        user_wallets = WalletService.get_user_wallets(current_user.id, include_inactive=True)
        return render_template('wallets.html', wallets=user_wallets)
    except Exception as e:
        print(f"钱包页面加载失败: {e}")
        return render_template('wallets.html', wallets=[])


@main_bp.route('/tasks')
@login_required
def tasks():
    """任务管理页面"""
    try:
        from services import TaskService
        
        user_tasks = TaskService.get_user_tasks(current_user.id)
        strategies = StrategyService.get_active_strategies()
        user_wallets = WalletService.get_user_wallets(current_user.id)
        
        return render_template('tasks.html', 
                             tasks=user_tasks, 
                             strategies=strategies, 
                             wallets=user_wallets)
    except Exception as e:
        print(f"任务页面加载失败: {e}")
        return render_template('tasks.html', tasks=[], strategies=[], wallets=[])
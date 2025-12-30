"""
主控制器
处理主页面和通用路由
"""

from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
import os
import glob

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


@main_bp.route('/settings')
@login_required
def settings():
    """系统设置页面（仅管理员）"""
    if not current_user.is_admin:
        return redirect(url_for('main.dashboard'))
    
    try:
        # 获取系统信息
        from utils.proxy_config import get_proxy_info, is_proxy_enabled
        proxy_info = get_proxy_info() if is_proxy_enabled() else None
        
        # 获取用户统计
        from models import User
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        
        system_stats = {
            'total_users': total_users,
            'active_users': active_users,
            'proxy_enabled': is_proxy_enabled(),
            'proxy_info': proxy_info
        }
        
        return render_template('settings.html', stats=system_stats)
    except Exception as e:
        print(f"系统设置页面加载失败: {e}")
        return render_template('settings.html', stats={})


@main_bp.route('/api/clear-logs', methods=['POST'])
@login_required
def clear_logs():
    """清理系统日志（仅管理员）"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    try:
        # 获取项目根目录路径
        project_root = os.path.dirname(os.path.abspath(__file__)).replace('controllers', '')
        
        # task_logs 文件夹路径
        logs_dir = os.path.join(project_root, 'task_logs')
        
        # 检查目录是否存在
        if not os.path.exists(logs_dir):
            return jsonify({'success': False, 'message': 'task_logs 目录不存在'})
        
        # 统计要删除的文件
        log_files = glob.glob(os.path.join(logs_dir, '*.log'))
        file_count = len(log_files)
        
        if file_count == 0:
            return jsonify({'success': True, 'message': '没有日志文件需要清理'})
        
        # 删除所有 .log 文件
        deleted_count = 0
        failed_files = []
        
        for log_file in log_files:
            try:
                os.remove(log_file)
                deleted_count += 1
            except Exception as e:
                failed_files.append(f"{os.path.basename(log_file)}: {str(e)}")
        
        # 返回结果
        if deleted_count == file_count:
            return jsonify({
                'success': True, 
                'message': f'成功清理了 {deleted_count} 个日志文件'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'部分清理失败: 成功删除 {deleted_count}/{file_count} 个文件',
                'details': failed_files
            })
            
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'清理日志失败: {str(e)}'
        }), 500


@main_bp.route('/api/get-logs-info', methods=['GET'])
@login_required
def get_logs_info():
    """获取日志信息（仅管理员）"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    try:
        # 获取项目根目录路径
        project_root = os.path.dirname(os.path.abspath(__file__)).replace('controllers', '')
        
        # task_logs 文件夹路径
        logs_dir = os.path.join(project_root, 'task_logs')
        
        # 检查目录是否存在
        if not os.path.exists(logs_dir):
            return jsonify({
                'success': True,
                'file_count': 0,
                'total_size': 0,
                'files': []
            })
        
        # 获取所有 .log 文件信息
        log_files = []
        total_size = 0
        
        for log_file in glob.glob(os.path.join(logs_dir, '*.log')):
            try:
                file_stat = os.stat(log_file)
                file_info = {
                    'name': os.path.basename(log_file),
                    'size': file_stat.st_size,
                    'modified': file_stat.st_mtime
                }
                log_files.append(file_info)
                total_size += file_stat.st_size
            except Exception:
                continue
        
        # 按修改时间排序
        log_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({
            'success': True,
            'file_count': len(log_files),
            'total_size': total_size,
            'files': log_files[:10]  # 只返回最新的10个文件
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'获取日志信息失败: {str(e)}'
        }), 500
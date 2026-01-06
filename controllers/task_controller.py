"""
任务控制器
处理任务管理相关的API
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from services import TaskService
from utils import task_logger

task_bp = Blueprint('task', __name__, url_prefix='/api/tasks')


@task_bp.route('', methods=['POST'])
@login_required
def create_task():
    """创建任务API"""
    try:
        data = request.get_json()
        
        # 数据类型验证
        try:
            quantity = float(data.get('quantity', 1.0)) if data.get('quantity') else 1.0
            interval = 0  # 不再使用间隔时间，设置为0
            rounds = int(data.get('rounds', 1)) if data.get('rounds') else 1
            leverage = int(data.get('leverage', 1)) if data.get('leverage') else 1
        except (ValueError, TypeError) as e:
            return jsonify({
                'success': False,
                'message': f"参数格式错误: {str(e)}"
            }), 400
        
        success, message, task = TaskService.create_task(
            user_id=current_user.id,
            name=data.get('name'),
            wallet_id=data.get('wallet_id'),
            strategy_id=data.get('strategy_id'),
            symbol=data.get('symbol'),
            quantity=quantity,
            interval=interval,
            rounds=rounds,
            leverage=leverage,
            side=data.get('side', 'buy'),
            order_type=data.get('order_type', 'market'),
            description=data.get('description')
        )
        
        return jsonify({
            'success': success,
            'message': message,
            'task_id': task.id if task else None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"创建任务异常: {str(e)}"
        }), 500


@task_bp.route('/<int:task_id>/start', methods=['POST'])
@login_required
def start_task(task_id):
    """启动任务API"""
    try:
        success, message = TaskService.start_task(task_id, current_user.id, current_user.is_admin)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"启动任务异常: {str(e)}"
        }), 500


@task_bp.route('/<int:task_id>/stop', methods=['POST'])
@login_required
def stop_task(task_id):
    """停止任务API"""
    try:
        success, message = TaskService.stop_task(task_id, current_user.id, current_user.is_admin)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"停止任务异常: {str(e)}"
        }), 500


@task_bp.route('/<int:task_id>/pause', methods=['POST'])
@login_required
def pause_task(task_id):
    """暂停任务API"""
    try:
        success, message = TaskService.pause_task(task_id, current_user.id)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"暂停任务异常: {str(e)}"
        }), 500


@task_bp.route('/<int:task_id>/resume', methods=['POST'])
@login_required
def resume_task(task_id):
    """恢复任务API"""
    try:
        success, message = TaskService.resume_task(task_id, current_user.id)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"恢复任务异常: {str(e)}"
        }), 500


@task_bp.route('/<int:task_id>/logs', methods=['GET'])
@login_required
def get_task_logs(task_id):
    """获取任务日志API"""
    try:
        success, message, logs = TaskService.get_task_logs(task_id, current_user.id)
        
        return jsonify({
            'success': success,
            'message': message,
            'logs': logs
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"获取日志异常: {str(e)}",
            'logs': ""
        }), 500


@task_bp.route('/<int:task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    """更新任务API"""
    try:
        data = request.get_json()
        
        success, message = TaskService.update_task(
            task_id=task_id,
            user_id=current_user.id,
            **data
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"更新任务异常: {str(e)}"
        }), 500


@task_bp.route('/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    """删除任务API"""
    try:
        # 管理员可以删除任意任务，普通用户只能删除自己的任务
        if current_user.is_admin:
            success, message = TaskService.delete_task(task_id, None)
        else:
            success, message = TaskService.delete_task(task_id, current_user.id)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"删除任务异常: {str(e)}"
        }), 500


@task_bp.route('', methods=['GET'])
@login_required
def get_tasks():
    """获取任务列表API"""
    try:
        # 管理员可以看到所有任务，普通用户只能看到自己的任务
        if current_user.is_admin:
            tasks = TaskService.get_all_tasks()
        else:
            tasks = TaskService.get_user_tasks(current_user.id)
        
        task_list = []
        for task in tasks:
            task_data = {
                'id': task.id,
                'name': task.name,
                'description': task.description,
                'status': task.status,
                'process_id': task.process_id,
                'total_rounds': task.total_rounds,
                'successful_rounds': task.successful_rounds,
                'failed_rounds': task.failed_rounds,
                'success_rate': task.get_success_rate(),
                'start_time': task.start_time.isoformat() if task.start_time else None,
                'end_time': task.end_time.isoformat() if task.end_time else None,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat(),
                'last_error': task.last_error,
                'user': {
                    'id': task.creator.id,
                    'username': task.creator.username,
                    'nickname': task.creator.nickname
                } if current_user.is_admin else None,
                'wallet': {
                    'id': task.wallet.id,
                    'name': task.wallet.name,
                    'wallet_type': task.wallet.wallet_type
                },
                'strategy': {
                    'id': task.strategy.id,
                    'name': task.strategy.name,
                    'strategy_type': task.strategy.strategy_type
                },
                'parameters': task.get_parameters()
            }
            task_list.append(task_data)
        
        return jsonify({
            'success': True,
            'tasks': task_list
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"获取任务列表异常: {str(e)}"
        }), 500


@task_bp.route('/<int:task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    """获取单个任务信息API"""
    try:
        # 管理员可以查看任意任务，普通用户只能查看自己的任务
        if current_user.is_admin:
            task = TaskService.get_task_by_id(task_id, None)  # None表示不限制用户
        else:
            task = TaskService.get_task_by_id(task_id, current_user.id)
        
        if not task:
            return jsonify({
                'success': False,
                'message': '任务不存在'
            }), 404
        
        task_data = {
            'id': task.id,
            'name': task.name,
            'description': task.description,
            'status': task.status,
            'process_id': task.process_id,
            'is_running': task.is_running(),
            'total_rounds': task.total_rounds,
            'successful_rounds': task.successful_rounds,
            'failed_rounds': task.failed_rounds,
            'success_rate': task.get_success_rate(),
            'duration': str(task.get_duration()) if task.get_duration() else None,
            'start_time': task.start_time.isoformat() if task.start_time else None,
            'end_time': task.end_time.isoformat() if task.end_time else None,
            'created_at': task.created_at.isoformat(),
            'updated_at': task.updated_at.isoformat(),
            'last_error': task.last_error,
            'user': {
                'id': task.creator.id,
                'username': task.creator.username,
                'nickname': task.creator.nickname
            } if current_user.is_admin else None,
            'wallet': {
                'id': task.wallet.id,
                'name': task.wallet.name,
                'wallet_type': task.wallet.wallet_type
            },
            'strategy': {
                'id': task.strategy.id,
                'name': task.strategy.name,
                'strategy_type': task.strategy.strategy_type,
                'description': task.strategy.description
            },
            'parameters': task.get_parameters()
        }
        
        return jsonify({
            'success': True,
            'task': task_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"获取任务信息异常: {str(e)}"
        }), 500


@task_bp.route('/<int:task_id>/logs/clear', methods=['POST'])
@login_required
def clear_task_logs(task_id):
    """清除任务日志API"""
    try:
        from models.task import Task
        task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
        
        if not task:
            return jsonify({
                'success': False,
                'message': '任务不存在'
            }), 404
        
        success = task_logger.clear_task_logs(task.name)
        
        return jsonify({
            'success': success,
            'message': '日志清除成功' if success else '日志清除失败'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"清除日志异常: {str(e)}"
        }), 500


@task_bp.route('/logs/list', methods=['GET'])
@login_required
def list_task_logs():
    """获取所有任务日志文件列表API"""
    try:
        log_files = task_logger.list_all_log_files()
        
        return jsonify({
            'success': True,
            'log_files': log_files
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"获取日志列表异常: {str(e)}"
        }), 500


@task_bp.route('/cleanup', methods=['POST'])
@login_required
def cleanup_orphan_tasks():
    """清理孤儿任务API"""
    try:
        success, message = TaskService.cleanup_orphan_tasks()
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"清理孤儿任务异常: {str(e)}"
        }), 500
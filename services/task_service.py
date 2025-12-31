"""
任务服务
"""

from typing import Optional, List, Tuple
import json

from models import Task, Wallet, Strategy, User
from models.base import db
from utils import ProcessManager, task_logger


class TaskService:
    """任务服务类"""
    
    @staticmethod
    def create_task(user_id: int, name: str, wallet_id: int, strategy_id: int, 
                   symbol: str, quantity: float, interval: int, rounds: int,
                   leverage: int = 1, side: str = 'buy', order_type: str = 'market',
                   strategy_parameters: str = None, description: str = None) -> Tuple[bool, str, Optional[Task]]:
        """
        创建任务
        
        Returns:
            (success, message, task)
        """
        try:
            # 验证任务名称唯一性
            if not name or not name.strip():
                return False, "任务名称不能为空", None
            
            name = name.strip()
            existing_task = Task.query.filter_by(name=name, user_id=user_id).first()
            if existing_task:
                return False, "任务名称已存在，请使用不同的名称", None
            
            # 验证用户和权限
            user = User.query.get(user_id)
            if not user:
                return False, "用户不存在", None
            
            # 检查任务数量限制
            if not user.can_create_task():
                return False, f"任务数量已达上限({user.max_tasks})，请联系管理员提升配额", None
            
            # 验证钱包和策略
            wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
            strategy = Strategy.query.filter_by(id=strategy_id).first()
            
            if not wallet:
                return False, "钱包不存在", None
            if not strategy:
                return False, "策略不存在", None
            
            # 检查钱包类型兼容性
            if not strategy.is_compatible_with_wallet(wallet.wallet_type):
                return False, "钱包类型与策略不兼容", None
            
            # 验证交易参数
            if not symbol:
                return False, "交易品种不能为空", None
            if quantity <= 0:
                return False, "交易数量必须大于0", None
            if interval <= 0:
                return False, "间隔时间必须大于0", None
            if rounds <= 0:
                return False, "循环次数必须大于0", None
            
            # 验证其他策略参数（如果有）
            if strategy_parameters:
                try:
                    json.loads(strategy_parameters)
                except json.JSONDecodeError:
                    return False, "策略参数格式错误", None
            
            # 创建任务
            task = Task(
                name=name,
                description=description,
                symbol=symbol,
                quantity=quantity,
                interval=interval,
                rounds=rounds,
                leverage=leverage,
                side=side,
                order_type=order_type,
                strategy_parameters=strategy_parameters or '{}',
                user_id=user_id,
                wallet_id=wallet_id,
                strategy_id=strategy_id
            )
            
            db.session.add(task)
            db.session.commit()
            
            return True, "任务创建成功", task
            
        except Exception as e:
            db.session.rollback()
            return False, f"创建任务失败: {str(e)}", None
    
    @staticmethod
    def start_task(task_id: int, user_id: int, is_admin: bool = False) -> Tuple[bool, str]:
        """
        启动任务
        
        Returns:
            (success, message)
        """
        try:
            # 管理员可以操作所有用户的任务，普通用户只能操作自己的任务
            if is_admin:
                task = Task.query.filter_by(id=task_id).first()
            else:
                task = Task.query.filter_by(id=task_id, user_id=user_id).first()
            
            if not task:
                return False, "任务不存在"
            
            if task.status == 'running':
                return False, "任务已在运行中"
            
            # 记录任务启动日志
            task_logger.log_task_start(task.name, task.id, task.get_trading_parameters())
            
            # 启动进程
            process_id = ProcessManager.start_task_process(task_id)
            if process_id:
                task.update_status('running', process_id=process_id)
                return True, "任务启动成功"
            else:
                return False, "任务启动失败"
                
        except Exception as e:
            return False, f"启动任务失败: {str(e)}"
    
    @staticmethod
    def stop_task(task_id: int, user_id: int, is_admin: bool = False) -> Tuple[bool, str]:
        """
        停止任务
        
        Returns:
            (success, message)
        """
        try:
            # 管理员可以操作所有用户的任务，普通用户只能操作自己的任务
            if is_admin:
                task = Task.query.filter_by(id=task_id).first()
            else:
                task = Task.query.filter_by(id=task_id, user_id=user_id).first()
                
            if not task:
                return False, "任务不存在"
            
            if task.status != 'running':
                # 如果任务不在运行中，直接设为停止状态
                task_logger.log_task_end(task.name, task.id, "stopped")
                task.update_status('stopped')
                return True, "任务已停止"
            
            # 检查进程是否存在
            if not task.process_id:
                task_logger.log_task_end(task.name, task.id, "stopped")
                task.update_status('stopped')
                return True, "任务已停止"
            
            # 检查进程是否还在运行
            if not ProcessManager.is_process_running(task.process_id):
                task_logger.log_task_end(task.name, task.id, "stopped")
                task.update_status('stopped')
                return True, "任务已停止"
            
            # 停止进程
            success = ProcessManager.stop_task_process(task.process_id)
            
            # 记录任务停止日志
            task_logger.log_task_end(task.name, task.id, "stopped")
            
            task.update_status('stopped')
            return True, "任务停止成功"
                
        except Exception as e:
            print(f"停止任务异常: {e}")
            return False, f"停止任务失败: {str(e)}"
    
    @staticmethod
    def pause_task(task_id: int, user_id: int) -> Tuple[bool, str]:
        """
        暂停任务
        
        Returns:
            (success, message)
        """
        try:
            task = Task.query.filter_by(id=task_id, user_id=user_id).first()
            if not task:
                return False, "任务不存在"
            
            if task.status != 'running':
                return False, "任务未在运行中"
            
            # 暂停任务（实际上是停止进程，但状态设为暂停）
            success = ProcessManager.stop_task_process(task.process_id)
            if success:
                task.update_status('paused')
                return True, "任务暂停成功"
            else:
                return False, "任务暂停失败"
                
        except Exception as e:
            return False, f"暂停任务失败: {str(e)}"
    
    @staticmethod
    def resume_task(task_id: int, user_id: int) -> Tuple[bool, str]:
        """
        恢复任务
        
        Returns:
            (success, message)
        """
        try:
            task = Task.query.filter_by(id=task_id, user_id=user_id).first()
            if not task:
                return False, "任务不存在"
            
            if task.status != 'paused':
                return False, "任务未处于暂停状态"
            
            # 重新启动进程
            process_id = ProcessManager.start_task_process(task_id)
            if process_id:
                task.update_status('running', process_id=process_id)
                return True, "任务恢复成功"
            else:
                return False, "任务恢复失败"
                
        except Exception as e:
            return False, f"恢复任务失败: {str(e)}"
    
    @staticmethod
    def delete_task(task_id: int, user_id: int) -> Tuple[bool, str]:
        """
        删除任务
        
        Returns:
            (success, message)
        """
        try:
            task = Task.query.filter_by(id=task_id, user_id=user_id).first()
            if not task:
                return False, "任务不存在"
            
            if task.status == 'running':
                return False, "请先停止任务"
            
            db.session.delete(task)
            db.session.commit()
            
            return True, "任务删除成功"
            
        except Exception as e:
            db.session.rollback()
            return False, f"删除任务失败: {str(e)}"
    
    @staticmethod
    def get_task_logs(task_id: int, user_id: int) -> Tuple[bool, str, str]:
        """
        获取任务日志
        
        Returns:
            (success, message, logs)
        """
        try:
            task = Task.query.filter_by(id=task_id, user_id=user_id).first()
            if not task:
                return False, "任务不存在", ""
            
            # 使用新的日志系统读取任务日志
            logs = task_logger.read_task_logs(task.name)
            return True, "获取日志成功", logs
            
        except Exception as e:
            return False, f"获取日志失败: {str(e)}", ""
    
    @staticmethod
    def update_task(task_id: int, user_id: int, **kwargs) -> Tuple[bool, str]:
        """
        更新任务信息
        
        Returns:
            (success, message)
        """
        try:
            task = Task.query.filter_by(id=task_id, user_id=user_id).first()
            if not task:
                return False, "任务不存在"
            
            if task.status == 'running':
                return False, "运行中的任务无法修改"
            
            # 更新基础字段
            if 'name' in kwargs:
                new_name = kwargs['name'].strip() if kwargs['name'] else None
                if not new_name:
                    return False, "任务名称不能为空"
                
                # 检查名称是否与其他任务重复（排除自己）
                existing_task = Task.query.filter(
                    Task.name == new_name,
                    Task.user_id == user_id,
                    Task.id != task_id
                ).first()
                if existing_task:
                    return False, "任务名称已存在，请使用不同的名称"
                
                task.name = new_name
            if 'description' in kwargs:
                task.description = kwargs['description']
            
            # 更新交易参数
            if 'symbol' in kwargs:
                if not kwargs['symbol']:
                    return False, "交易品种不能为空"
                task.symbol = kwargs['symbol']
            if 'quantity' in kwargs:
                quantity = float(kwargs['quantity'])
                if quantity <= 0:
                    return False, "交易数量必须大于0"
                task.quantity = quantity
            if 'interval' in kwargs:
                interval = int(kwargs['interval'])
                if interval <= 0:
                    return False, "间隔时间必须大于0"
                task.interval = interval
            if 'rounds' in kwargs:
                rounds = int(kwargs['rounds'])
                if rounds <= 0:
                    return False, "循环次数必须大于0"
                task.rounds = rounds
            if 'leverage' in kwargs:
                task.leverage = int(kwargs['leverage'])
            if 'side' in kwargs:
                task.side = kwargs['side']
            if 'order_type' in kwargs:
                task.order_type = kwargs['order_type']
            
            # 更新钱包和策略
            if 'wallet_id' in kwargs:
                wallet = Wallet.query.filter_by(id=kwargs['wallet_id'], user_id=user_id).first()
                if not wallet:
                    return False, "钱包不存在"
                task.wallet_id = kwargs['wallet_id']
            if 'strategy_id' in kwargs:
                strategy = Strategy.query.filter_by(id=kwargs['strategy_id']).first()
                if not strategy:
                    return False, "策略不存在"
                task.strategy_id = kwargs['strategy_id']
            
            # 更新其他策略参数
            if 'strategy_parameters' in kwargs:
                try:
                    json.loads(kwargs['strategy_parameters'])
                    task.strategy_parameters = kwargs['strategy_parameters']
                except json.JSONDecodeError:
                    return False, "策略参数格式错误"
            
            db.session.commit()
            return True, "任务更新成功"
            
        except Exception as e:
            db.session.rollback()
            return False, f"更新任务失败: {str(e)}"
    
    @staticmethod
    def get_user_tasks(user_id: int) -> List[Task]:
        """获取用户任务列表"""
        try:
            return Task.query.filter_by(user_id=user_id)\
                           .order_by(Task.updated_at.desc()).all()
        except Exception as e:
            print(f"获取任务列表失败: {e}")
            return []
    
    @staticmethod
    def get_all_tasks() -> List[Task]:
        """获取所有任务列表（管理员用）"""
        try:
            return Task.query.order_by(Task.updated_at.desc()).all()
        except Exception as e:
            print(f"获取所有任务失败: {e}")
            return []
    
    @staticmethod
    def get_task_by_id(task_id: int, user_id: int) -> Optional[Task]:
        """根据ID获取任务"""
        try:
            return Task.query.filter_by(id=task_id, user_id=user_id).first()
        except Exception as e:
            print(f"获取任务失败: {e}")
            return None
    
    @staticmethod
    def check_running_tasks():
        """检查运行中的任务状态"""
        try:
            running_tasks = Task.query.filter_by(status='running').all()
            
            for task in running_tasks:
                if not task.is_running():
                    # 进程已停止，更新任务状态
                    task.update_status('error', "进程意外停止")
                    print(f"任务 {task.id} 进程意外停止")
            
        except Exception as e:
            print(f"检查运行中任务失败: {e}")
    
    @staticmethod
    def cleanup_orphan_tasks():
        """清理孤儿任务（手动清理接口）"""
        try:
            import psutil
            
            running_tasks = Task.query.filter_by(status='running').all()
            cleaned_count = 0
            
            for task in running_tasks:
                should_clean = False
                reason = ""
                
                if not task.process_id:
                    should_clean = True
                    reason = "无进程ID"
                else:
                    try:
                        if not psutil.pid_exists(task.process_id):
                            should_clean = True
                            reason = "进程不存在"
                        else:
                            proc = psutil.Process(task.process_id)
                            cmdline = ' '.join(proc.cmdline())
                            if 'task_runner.py' not in cmdline:
                                should_clean = True
                                reason = "非任务进程"
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        should_clean = True
                        reason = "进程无法访问"
                
                if should_clean:
                    task.update_status('stopped', f"手动清理: {reason}")
                    cleaned_count += 1
            
            return True, f"清理完成，共清理 {cleaned_count} 个孤儿任务"
            
        except Exception as e:
            return False, f"清理失败: {e}"
#!/usr/bin/env python3
"""
任务运行器
独立进程执行交易策略任务
"""

import sys
import os
import json
import importlib
from datetime import datetime
import traceback

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import Task, Wallet, Strategy
from models.base import db
from utils import task_logger


class TaskRunner:
    """任务运行器"""
    
    def __init__(self, task_id):
        self.task_id = task_id
        self.task = None
        self.wallet = None
        self.strategy = None
        self.logger = None
        self.app = None
        
        # 创建应用上下文
        self.setup_app()
        
        # 初始化加载任务数据以获取任务名称
        self.load_task_data_for_logger()
        
        # 设置日志
        self.setup_logging()
        
    def setup_app(self):
        """设置应用上下文"""
        self.app = create_app()
    
    def load_task_data_for_logger(self):
        """为日志系统预加载任务数据"""
        try:
            with self.app.app_context():
                task = db.session.get(Task, self.task_id)
                if task:
                    self.task_name = task.name
                else:
                    self.task_name = f"Unknown_Task_{self.task_id}"
        except Exception:
            self.task_name = f"Unknown_Task_{self.task_id}"
        
    def setup_logging(self):
        """设置日志系统"""
        self.logger = task_logger.create_logger(self.task_name, self.task_id)
        
    def load_task_data(self):
        """加载任务数据"""
        try:
            with self.app.app_context():
                from models.base import db
                self.task = db.session.get(Task, self.task_id)
                if not self.task:
                    raise Exception(f"任务 {self.task_id} 不存在")
                
                self.wallet = db.session.get(Wallet, self.task.wallet_id)
                self.strategy = db.session.get(Strategy, self.task.strategy_id)
                
                if not self.wallet:
                    raise Exception(f"钱包 {self.task.wallet_id} 不存在")
                if not self.strategy:
                    raise Exception(f"策略 {self.task.strategy_id} 不存在")
                
                self.logger.info(f"任务数据加载成功: {self.task.name}")
                self.logger.info(f"钱包: {self.wallet.name} ({self.wallet.wallet_type})")
                self.logger.info(f"策略: {self.strategy.name} ({self.strategy.strategy_type})")
                
                return True
                
        except Exception as e:
            self.logger.error(f"加载任务数据失败: {e}")
            return False
    
    def prepare_strategy_config(self):
        """准备策略配置"""
        try:
            # 获取策略参数（现在直接从任务模型字段获取）
            parameters = {
                'symbol': self.task.symbol,
                'quantity': str(self.task.quantity),
                'interval': self.task.interval,
                'rounds': self.task.rounds,
                'leverage': self.task.leverage,
                'side': self.task.side,
                'order_type': self.task.order_type
            }
            self.logger.info(f"策略参数: {parameters}")
            
            # 获取钱包凭证
            credentials = self.wallet.get_api_credentials()
            
            # 获取全局代理配置
            proxy_config = self.get_global_proxy_config()
            
            # 根据钱包类型准备配置
            if self.wallet.wallet_type == 'spot':
                config = {
                    'api_key': credentials['api_key'],
                    'secret_key': credentials['secret_key'],
                    **proxy_config
                }
            elif self.wallet.wallet_type == 'futures':
                config = {
                    'user_address': self.wallet.user_address,
                    'signer_address': self.wallet.signer_address,
                    'private_key': credentials['private_key'],
                    **proxy_config
                }
            else:
                raise Exception(f"不支持的钱包类型: {self.wallet.wallet_type}")
            
            return config, parameters
            
        except Exception as e:
            self.logger.error(f"准备策略配置失败: {e}")
            raise
    
    def load_strategy_class(self):
        """加载策略类"""
        try:
            # 动态导入策略模块
            module = importlib.import_module(self.strategy.module_path)
            strategy_class = getattr(module, self.strategy.class_name)
            
            self.logger.info(f"策略类加载成功: {self.strategy.class_name}")
            return strategy_class
            
        except Exception as e:
            self.logger.error(f"加载策略类失败: {e}")
            raise
    
    def update_task_status(self, status, error_message=None):
        """更新任务状态"""
        try:
            with self.app.app_context():
                from models.base import db
                task = db.session.get(Task, self.task_id)
                if task:
                    task.status = status
                    if error_message:
                        task.last_error = error_message
                    if status == 'stopped':
                        task.end_time = datetime.utcnow()
                        task.process_id = None
                    db.session.commit()
                    
        except Exception as e:
            self.logger.error(f"更新任务状态失败: {e}")
    
    def get_global_proxy_config(self):
        """获取全局代理配置"""
        try:
            from utils.proxy_config import is_proxy_enabled, get_proxy_info
            
            proxy_enabled = is_proxy_enabled()
            
            if proxy_enabled:
                proxy_info = get_proxy_info()
                return {
                    'proxy_enabled': True,
                    'proxy_host': proxy_info.get('host', '127.0.0.1'),
                    'proxy_port': proxy_info.get('port', 7890)
                }
            else:
                return {
                    'proxy_enabled': False,
                    'proxy_host': None,
                    'proxy_port': None
                }
        except Exception as e:
            self.logger.warning(f"获取全局代理配置失败: {e}，使用默认配置")
            return {
                'proxy_enabled': False,
                'proxy_host': None,
                'proxy_port': None
            }
    
    def update_task_stats(self, total_rounds=0, successful_rounds=0, failed_rounds=0):
        """更新任务统计信息"""
        try:
            with self.app.app_context():
                from models.base import db
                task = db.session.get(Task, self.task_id)
                if task:
                    if total_rounds > 0:
                        task.total_rounds += total_rounds
                    if successful_rounds > 0:
                        task.successful_rounds += successful_rounds
                    if failed_rounds > 0:
                        task.failed_rounds += failed_rounds
                    db.session.commit()
                    
        except Exception as e:
            self.logger.error(f"更新任务统计失败: {e}")
    
    def run(self):
        """运行任务"""
        self.logger.info("="*60)
        self.logger.info(f"任务运行器启动 - 任务ID: {self.task_id}")
        self.logger.info("="*60)
        
        try:
            # 1. 加载任务数据
            if not self.load_task_data():
                return False
            
            # 2. 准备策略配置
            config, parameters = self.prepare_strategy_config()
            
            # 3. 加载策略类
            strategy_class = self.load_strategy_class()
            
            # 4. 创建策略实例
            if self.strategy.strategy_type == 'volume':
                # 现货刷量策略
                strategy_instance = strategy_class(
                    symbol=parameters['symbol'],
                    quantity=parameters['quantity'],
                    interval=int(parameters['interval']),
                    rounds=int(parameters['rounds'])
                )
                # 为策略设置钱包配置
                strategy_instance.wallet_config = config
            elif self.strategy.strategy_type == 'hidden_futures':
                # 合约HIDDEN策略
                strategy_instance = strategy_class(
                    symbol=parameters['symbol'],
                    quantity=parameters['quantity'],
                    leverage=int(parameters['leverage']),
                    rounds=int(parameters['rounds']),
                    interval=int(parameters['interval'])
                )
                # 为策略设置钱包配置
                strategy_instance.wallet_config = config
            else:
                raise Exception(f"不支持的策略类型: {self.strategy.strategy_type}")
            
            self.logger.info(f"策略实例创建成功: {strategy_instance.__class__.__name__}")
            
            # 5. 更新任务状态为运行中
            self.update_task_status('running')
            
            # 6. 执行策略
            self.logger.info("开始执行策略...")
            
            # 检查策略实例是否有run方法
            if not hasattr(strategy_instance, 'run'):
                raise Exception(f"策略类 {strategy_instance.__class__.__name__} 缺少 run() 方法")
            
            # 检查策略配置是否正确传递
            self.logger.info(f"策略配置: {config}")
            
            # 为策略提供 logger 以便记录输出
            if hasattr(strategy_instance, 'set_logger'):
                strategy_instance.set_logger(self.logger)
            
            try:
                success = strategy_instance.run()
                
                # 7. 更新最终状态和统计
                if success:
                    self.logger.info("策略执行成功！")
                    self.update_task_status('stopped')
                    
                    # 获取执行统计（如果策略提供）
                    if hasattr(strategy_instance, 'successful_rounds'):
                        self.update_task_stats(
                            total_rounds=getattr(strategy_instance, 'rounds', 0),
                            successful_rounds=getattr(strategy_instance, 'successful_rounds', 0),
                            failed_rounds=getattr(strategy_instance, 'rounds', 0) - getattr(strategy_instance, 'successful_rounds', 0)
                        )
                else:
                    self.logger.error("策略执行失败！")
                    self.update_task_status('error', '策略执行失败')
            except Exception as strategy_error:
                self.logger.error(f"策略执行异常: {strategy_error}")
                self.logger.error(f"策略执行异常详情: {traceback.format_exc()}")
                self.update_task_status('error', f'策略执行异常: {strategy_error}')
                return False
            
            return success
            
        except KeyboardInterrupt:
            self.logger.info("任务被用户中断")
            self.update_task_status('stopped')
            return False
            
        except Exception as e:
            error_msg = f"任务执行异常: {e}"
            self.logger.error(error_msg)
            self.logger.error(f"异常详情: {traceback.format_exc()}")
            self.update_task_status('error', error_msg)
            return False
        
        finally:
            self.logger.info("="*60)
            self.logger.info(f"任务运行器结束 - 任务ID: {self.task_id}")
            self.logger.info("="*60)


def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python task_runner.py <task_id>")
        sys.exit(1)
    
    try:
        task_id = int(sys.argv[1])
        runner = TaskRunner(task_id)
        success = runner.run()
        sys.exit(0 if success else 1)
        
    except ValueError:
        print("错误: 任务ID必须是数字")
        sys.exit(1)
    except Exception as e:
        print(f"任务运行器启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
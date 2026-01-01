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
            
            # 检查凭证是否正确解密
            if credentials['api_key'] and credentials['secret_key']:
                self.logger.info(f"钱包凭证获取完成，api_key前8位: {credentials['api_key'][:8]}...{credentials['api_key'][-4:]}")
            else:
                self.logger.error(f"钱包凭证解密失败或为空: api_key={'存在' if self.wallet.api_key else '不存在'}, secret_key={'存在' if self.wallet.secret_key else '不存在'}")
                # 检查加密密钥是否可用
                from utils.encryption import test_encryption
                try:
                    test_result = test_encryption()
                    self.logger.info(f"加密测试结果: {test_result}")
                    if test_result == "加密解密功能正常":
                        self.logger.error("加密系统正常但钱包凭证解密失败，可能的原因:")
                        self.logger.error("1. 钱包凭证是用不同的加密密钥加密的")
                        self.logger.error("2. 请检查 ENCRYPTION_KEY 环境变量是否与加密时一致")
                        self.logger.error("3. 可以使用 reset_wallet_credentials.py 重新设置钱包凭证")
                except Exception as e:
                    self.logger.error(f"加密系统异常: {e}")
            
            # 获取全局代理配置
            proxy_config = self.get_global_proxy_config()
            
            # 根据钱包类型和策略类型准备配置
            if self.wallet.wallet_type == 'unified':
                # 统一钱包根据策略类型使用相应的API配置
                if self.strategy.strategy_type in ['volume', 'spot']:
                    # 现货策略使用现货API
                    config = {
                        'api_key': credentials['api_key'],
                        'secret_key': credentials['secret_key'],
                        **proxy_config
                    }
                    self.logger.info(f"统一钱包现货配置准备完成，使用钱包: {self.wallet.name}")
                elif self.strategy.strategy_type in ['hidden_futures', 'futures']:
                    # 期货策略使用期货API
                    config = {
                        'user_address': self.wallet.user_address,
                        'signer_address': self.wallet.signer_address,
                        'private_key': credentials['private_key'],
                        **proxy_config
                    }
                    self.logger.info(f"统一钱包期货配置准备完成，使用钱包: {self.wallet.name}")
                else:
                    raise Exception(f"策略类型 {self.strategy.strategy_type} 与统一钱包不兼容")
            elif self.wallet.wallet_type == 'spot':
                config = {
                    'api_key': credentials['api_key'],
                    'secret_key': credentials['secret_key'],
                    **proxy_config
                }
                self.logger.info(f"现货钱包配置准备完成，使用钱包: {self.wallet.name}")
            elif self.wallet.wallet_type == 'futures':
                config = {
                    'user_address': self.wallet.user_address,
                    'signer_address': self.wallet.signer_address,
                    'private_key': credentials['private_key'],
                    **proxy_config
                }
                self.logger.info(f"期货钱包配置准备完成，使用钱包: {self.wallet.name}")
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
    
    def update_task_stats(self, total_rounds=0, successful_rounds=0, failed_rounds=0, 
                          supplement_orders=0, total_cost_diff=0, buy_volume_usdt=0,
                          sell_volume_usdt=0, total_fees_usdt=0, initial_usdt_balance=None,
                          final_usdt_balance=None, usdt_balance_diff=0, net_loss_usdt=0):
        """更新任务统计信息"""
        try:
            with self.app.app_context():
                from models.base import db
                from decimal import Decimal
                task = db.session.get(Task, self.task_id)
                if task:
                    # 更新基础统计
                    if total_rounds > 0:
                        task.total_rounds = total_rounds  # 直接设置，不累加
                    if successful_rounds > 0:
                        task.successful_rounds = successful_rounds
                    if failed_rounds > 0:
                        task.failed_rounds = failed_rounds
                    
                    # 更新原有的统计字段
                    if supplement_orders > 0:
                        task.supplement_orders = supplement_orders
                    if total_cost_diff > 0:
                        task.total_cost_diff = Decimal(str(total_cost_diff))
                    
                    # 更新新的交易量和手续费统计字段 - 使用累加方式
                    if buy_volume_usdt > 0:
                        task.buy_volume_usdt = (task.buy_volume_usdt or 0) + Decimal(str(buy_volume_usdt))
                    if sell_volume_usdt > 0:
                        task.sell_volume_usdt = (task.sell_volume_usdt or 0) + Decimal(str(sell_volume_usdt))
                    if total_fees_usdt > 0:
                        task.total_fees_usdt = (task.total_fees_usdt or 0) + Decimal(str(total_fees_usdt))
                    
                    # 余额相关的字段使用最新值，不累加
                    if initial_usdt_balance is not None:
                        task.initial_usdt_balance = Decimal(str(initial_usdt_balance))
                    if final_usdt_balance is not None:
                        task.final_usdt_balance = Decimal(str(final_usdt_balance))
                    if usdt_balance_diff != 0:
                        task.usdt_balance_diff = Decimal(str(usdt_balance_diff))
                    if net_loss_usdt != 0:
                        task.net_loss_usdt = Decimal(str(net_loss_usdt))
                    
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
                self.logger.info(f"钱包配置已设置到策略实例，配置包含: {list(config.keys())}")
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
                self.logger.info(f"钱包配置已设置到策略实例，配置包含: {list(config.keys())}")
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
                    if hasattr(strategy_instance, 'completed_rounds'):
                        total_rounds = getattr(strategy_instance, 'completed_rounds', 0)
                        supplement_orders = getattr(strategy_instance, 'supplement_orders', 0)
                        total_cost_diff = getattr(strategy_instance, 'total_cost_diff', 0)
                        
                        # 获取新的统计数据
                        buy_volume_usdt = getattr(strategy_instance, 'buy_volume_usdt', 0)
                        sell_volume_usdt = getattr(strategy_instance, 'sell_volume_usdt', 0)
                        total_fees_usdt = getattr(strategy_instance, 'total_fees_usdt', 0)
                        initial_usdt_balance = getattr(strategy_instance, 'initial_usdt_balance', None)
                        final_usdt_balance = getattr(strategy_instance, 'final_usdt_balance', None)
                        usdt_balance_diff = getattr(strategy_instance, 'usdt_balance_diff', 0)
                        net_loss_usdt = getattr(strategy_instance, 'net_loss_usdt', 0)
                        
                        # 获取失败轮次统计
                        failed_rounds = getattr(strategy_instance, 'failed_rounds', 0)
                        
                        self.update_task_stats(
                            total_rounds=total_rounds,
                            successful_rounds=total_rounds,  # completed_rounds就是成功轮次
                            failed_rounds=failed_rounds,
                            supplement_orders=supplement_orders,
                            total_cost_diff=total_cost_diff,
                            buy_volume_usdt=buy_volume_usdt,
                            sell_volume_usdt=sell_volume_usdt,
                            total_fees_usdt=total_fees_usdt,
                            initial_usdt_balance=initial_usdt_balance,
                            final_usdt_balance=final_usdt_balance,
                            usdt_balance_diff=usdt_balance_diff,
                            net_loss_usdt=net_loss_usdt
                        )
                        
                        total_volume = buy_volume_usdt + sell_volume_usdt
                        self.logger.info(f"策略统计 - 完成轮次: {total_rounds}, 补单数: {supplement_orders}, 总损耗: {total_cost_diff:.4f} USDT")
                        self.logger.info(f"交易统计 - 总交易量: {total_volume:.2f} USDT, 手续费: {total_fees_usdt:.4f} USDT")
                        self.logger.info(f"USDT余额 - 差值: {usdt_balance_diff:+.4f}, 净损耗: {net_loss_usdt:+.4f} USDT")
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
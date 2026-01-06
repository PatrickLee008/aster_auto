#!/usr/bin/env python3
"""
任务运行器 - 在独立进程中运行策略任务
"""

import sys
import os
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import Task
from services import WalletService
from utils import TaskLogger


def run_task(task_id: int):
    """运行任务"""
    app = create_app()
    
    with app.app_context():
        try:
            # 获取任务信息
            task = Task.query.get(task_id)
            if not task:
                print(f"任务 {task_id} 不存在")
                return
            
            # 创建日志记录器
            logger = TaskLogger(task.name)
            logger.log_task_start(task.name, task.id, task.get_trading_parameters())
            
            # 获取策略信息
            from models import Strategy
            strategy = Strategy.query.get(task.strategy_id)
            if not strategy:
                logger.error(f"策略 {task.strategy_id} 不存在")
                task.update_status('error', error_message="策略不存在")
                return
            
            # 获取钱包配置
            wallet = task.wallet
            if not wallet:
                logger.error(f"钱包 {task.wallet_id} 不存在")
                task.update_status('error', error_message="钱包不存在")
                return
            
            # 获取钱包凭据
            credentials = wallet.get_api_credentials()
            if not credentials:
                logger.error("无法获取钱包凭据")
                task.update_status('error', error_message="无法获取钱包凭据")
                return
            
            # 准备钱包配置
            from utils.proxy_config import is_proxy_enabled, get_proxy_info
            proxy_enabled = is_proxy_enabled()
            proxy_info = get_proxy_info() if proxy_enabled else {}
            
            wallet_config = {
                'user_address': wallet.user_address,
                'signer_address': wallet.signer_address,
                'private_key': credentials.get('private_key'),
                'api_key': credentials.get('api_key'),
                'secret_key': credentials.get('secret_key'),
                'proxy_enabled': proxy_enabled,
                'proxy_host': proxy_info.get('host', '127.0.0.1'),
                'proxy_port': proxy_info.get('port', 7890)
            }
            
            # 根据策略类型实例化策略
            logger.info(f"开始执行策略: {strategy.name} ({strategy.class_name})")
            
            if strategy.class_name == 'VolumeStrategy':
                from strategies.volume_strategy import VolumeStrategy
                strategy_instance = VolumeStrategy(
                    symbol=task.symbol,
                    quantity=str(task.quantity),
                    interval=task.interval,
                    rounds=task.rounds
                )
                
            elif strategy.class_name == 'HiddenFuturesStrategy':
                from strategies.hidden_futures_strategy import HiddenFuturesStrategy
                strategy_instance = HiddenFuturesStrategy(
                    symbol=task.symbol,
                    quantity=str(task.quantity),
                    leverage=task.leverage,
                    rounds=task.rounds,
                    interval=task.interval
                )
                
            else:
                logger.error(f"未知的策略类型: {strategy.class_name}")
                task.update_status('error', error_message=f"未知的策略类型: {strategy.class_name}")
                return
            
            # 设置钱包配置和日志记录器
            strategy_instance.wallet_config = wallet_config
            strategy_instance.set_logger(logger)
            
            # 连接交易所
            logger.info("正在连接交易所...")
            if not strategy_instance.connect():
                logger.error("连接交易所失败")
                task.update_status('error', error_message="连接交易所失败")
                return
            
            # 执行策略
            logger.info("开始执行交易...")
            task.update_status('running')
            
            success = strategy_instance.run()
            
            # 更新任务统计
            if hasattr(strategy_instance, 'completed_rounds'):
                task.successful_rounds = strategy_instance.completed_rounds
            if hasattr(strategy_instance, 'failed_rounds'):
                task.failed_rounds = strategy_instance.failed_rounds
            if hasattr(strategy_instance, 'supplement_orders'):
                task.supplement_orders = strategy_instance.supplement_orders
            if hasattr(strategy_instance, 'total_cost_diff'):
                task.total_cost_diff = strategy_instance.total_cost_diff
            if hasattr(strategy_instance, 'buy_volume_usdt'):
                task.buy_volume_usdt = strategy_instance.buy_volume_usdt
            if hasattr(strategy_instance, 'sell_volume_usdt'):
                task.sell_volume_usdt = strategy_instance.sell_volume_usdt
            if hasattr(strategy_instance, 'total_fees_usdt'):
                task.total_fees_usdt = strategy_instance.total_fees_usdt
            if hasattr(strategy_instance, 'initial_usdt_balance'):
                task.initial_usdt_balance = strategy_instance.initial_usdt_balance
            if hasattr(strategy_instance, 'final_usdt_balance'):
                task.final_usdt_balance = strategy_instance.final_usdt_balance
            if hasattr(strategy_instance, 'usdt_balance_diff'):
                task.usdt_balance_diff = strategy_instance.usdt_balance_diff
            if hasattr(strategy_instance, 'net_loss_usdt'):
                task.net_loss_usdt = strategy_instance.net_loss_usdt
            
            task.total_rounds = task.successful_rounds + task.failed_rounds
            
            # 更新任务状态
            if success:
                logger.info("任务执行完成")
                task.update_status('stopped')
            else:
                logger.error("任务执行失败")
                task.update_status('error', error_message="策略执行失败")
            
            logger.log_task_end(task.name, task.id)
            
        except Exception as e:
            print(f"任务执行异常: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                task = Task.query.get(task_id)
                if task:
                    task.update_status('error', error_message=str(e))
            except:
                pass


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python task_runner.py <task_id>")
        sys.exit(1)
    
    task_id = int(sys.argv[1])
    print(f"启动任务运行器 - 任务ID: {task_id}")
    run_task(task_id)

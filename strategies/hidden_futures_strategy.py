#!/usr/bin/env python3
"""
HIDDEN隐藏订单合约自成交策略
使用批量下单API和HIDDEN参数实现真正的同时成交
"""

import sys
import os
import time

# 添加父目录到路径以导入客户端
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from futures_client import AsterFuturesClient
# 注意：不再使用FUTURES_CONFIG回退，策略必须通过钱包配置获取期货账户信息


class HiddenFuturesStrategy:
    """HIDDEN隐藏订单合约自成交策略"""
    
    def __init__(self, symbol: str, quantity: str, leverage: int = 20, rounds: int = 1, interval: int = 5):
        """
        初始化策略
        
        Args:
            symbol (str): 交易对，如 'SKYUSDT'
            quantity (str): 每次交易张数
            leverage (int): 杠杆倍数
            rounds (int): 循环执行轮次
            interval (int): 每轮间隔秒数
        """
        self.symbol = symbol
        self.quantity = quantity
        self.leverage = leverage
        self.rounds = rounds
        self.interval = interval
        self.client = None
        self.logger = None  # 日志记录器
        
        # 交易对精度信息
        self.tick_size = None  # 价格精度
        self.step_size = None  # 数量精度
        
        # 统计变量
        self.completed_rounds = 0
        self.failed_rounds = 0
        self.supplement_orders = 0
        self.total_cost_diff = 0.0
        self.buy_volume_usdt = 0.0
        self.sell_volume_usdt = 0.0
        self.total_fees_usdt = 0.0
        self.initial_usdt_balance = 0.0
        self.final_usdt_balance = 0.0
        self.usdt_balance_diff = 0.0
        self.net_loss_usdt = 0.0
        
        print(f"=== HIDDEN隐藏订单合约自成交策略 ===")
        print(f"交易对: {symbol}")
        print(f"数量: {quantity}张")
        print(f"杠杆: {leverage}倍")
        print(f"执行轮次: {rounds}轮")
        print(f"间隔时间: {interval}秒")
    
    def set_logger(self, logger):
        """设置日志记录器"""
        self.logger = logger
    
    def log(self, message, level='info'):
        """记录日志"""
        if self.logger:
            if level == 'error':
                self.logger.error(message)
            elif level == 'warning':
                self.logger.warning(message)
            else:
                self.logger.info(message)
        else:
            print(message)
    
    def connect(self) -> bool:
        """连接交易所"""
        try:
            # 必须使用任务运行器传递的钱包配置
            if not hasattr(self, 'wallet_config') or not self.wallet_config:
                self.log("[FAILED] 未提供钱包配置，无法连接", 'error')
                return False
                
            config = self.wallet_config
            self.client = AsterFuturesClient(
                user_address=config['user_address'],
                signer_address=config['signer_address'],
                private_key=config['private_key'],
                proxy_host=config.get('proxy_host', '127.0.0.1'),
                proxy_port=config.get('proxy_port', 7890),
                use_proxy=config.get('proxy_enabled', True)
            )
            
            if not self.client.test_connection():
                self.log("[FAILED] 连接测试失败", 'error')
                return False
            
            # 设置杠杆
            leverage_result = self.client.set_leverage(self.symbol, self.leverage)
            if not leverage_result:
                self.log("[FAILED] 杠杆设置失败", 'error')
                return False
            
            # 获取交易对精度信息
            if not self.get_symbol_precision():
                self.log("[FAILED] 无法获取交易对精度信息", 'error')
                return False
                
            self.log("[SUCCESS] 连接和配置完成")
            
            # 检查账户余额并初始化统计
            if not self.check_account_balance():
                return False
            
            # 初始化USDT余额统计
            try:
                account_info = self.client.get_account_info()
                if account_info:
                    self.initial_usdt_balance = float(account_info.get('totalWalletBalance', 0))
                    self.log(f"初始USDT余额: {self.initial_usdt_balance:.4f}")
            except Exception as e:
                self.log(f"获取初始余额失败，将使用0作为初始值: {e}", 'warning')
                self.initial_usdt_balance = 0.0
            
            return True
            
        except Exception as e:
            self.log(f"[ERROR] 连接错误: {e}", 'error')
            return False
    
    def get_symbol_precision(self) -> bool:
        """获取交易对的精度信息"""
        try:
            self.log("获取交易对精度信息...")
            
            # 获取交易所信息
            exchange_info = self.client.get_exchange_info()
            if not exchange_info:
                self.log("❌ 无法获取交易所信息", 'error')
                return False
            
            # 查找对应的交易对信息
            symbols = exchange_info.get('symbols', [])
            for symbol_info in symbols:
                if symbol_info.get('symbol') == self.symbol:
                    # 提取价格和数量精度信息
                    filters = symbol_info.get('filters', [])
                    for filter_item in filters:
                        if filter_item.get('filterType') == 'PRICE_FILTER':
                            self.tick_size = filter_item.get('tickSize')
                        elif filter_item.get('filterType') == 'LOT_SIZE':
                            self.step_size = filter_item.get('stepSize')
                    
                    self.log(f"✅ 交易对精度信息获取成功:")
                    self.log(f"   价格精度 (tick_size): {self.tick_size}")
                    self.log(f"   数量精度 (step_size): {self.step_size}")
                    return True
            
            self.log(f"❌ 未找到交易对 {self.symbol} 的信息", "error")
            return False
            
        except Exception as e:
            self.log(f"❌ 获取交易对精度信息失败: {e}", "error")
            return False
    
    def format_price(self, price: float) -> str:
        """根据tick_size格式化价格"""
        if not self.tick_size:
            return f"{price:.5f}"  # 默认5位小数
            
        try:
            tick_size_float = float(self.tick_size)
            if tick_size_float == 0:
                return str(price)
            
            # 计算精度位数
            precision = len(self.tick_size.rstrip('0').split('.')[1]) if '.' in self.tick_size else 0
            
            # 根据tick_size调整价格（向下取整到最近的tick）
            adjusted_price = round(price / tick_size_float) * tick_size_float
            
            return f"{adjusted_price:.{precision}f}"
            
        except Exception as e:
            self.log(f"价格格式化失败: {e}", 'warning')
            return f"{price:.5f}"  # 降级到默认格式
    
    def check_account_balance(self) -> bool:
        """检查账户余额是否充足"""
        try:
            self.log("检查账户余额...")
            
            # 获取账户信息
            account_info = self.client.get_account_info()
            if not account_info:
                self.log("[FAILED] 无法获取账户信息", 'error')
                return False
            
            # 获取可用余额
            available_balance = float(account_info.get('availableBalance', 0))
            total_wallet_balance = float(account_info.get('totalWalletBalance', 0))
            
            self.log(f"账户余额信息:")
            self.log(f"  钱包总余额: {total_wallet_balance:.4f} USDT")
            self.log(f"  可用余额: {available_balance:.4f} USDT")
            
            # 估算所需保证金（使用当前价格估算）
            try:
                # 获取当前价格用于保证金计算
                book_ticker = self.client.get_book_ticker(self.symbol)
                if book_ticker:
                    current_price = float(book_ticker.get('bidPrice', 0))
                    quantity = float(self.quantity)
                    
                    # 计算所需保证金 = 价格 * 数量 / 杠杆
                    required_margin = (current_price * quantity) / self.leverage
                    
                    self.log(f"交易估算:")
                    self.log(f"  当前价格: {current_price:.5f} USDT")
                    self.log(f"  交易数量: {quantity:.0f} 张")
                    self.log(f"  杠杆倍数: {self.leverage}x")
                    self.log(f"  所需保证金: {required_margin:.4f} USDT")
                    
                    # 检查保证金是否充足（留20%的安全边际）
                    safety_margin = required_margin * 1.2
                    if available_balance >= safety_margin:
                        self.log("[SUCCESS] 账户余额充足")
                        return True
                    else:
                        self.log(f"[FAILED] 账户余额不足", 'error')
                        self.log(f"  需要保证金: {safety_margin:.4f} USDT (含20%安全边际)", 'error')
                        self.log(f"  当前可用: {available_balance:.4f} USDT", 'error')
                        self.log(f"  缺少: {safety_margin - available_balance:.4f} USDT", 'error')
                        return False
                else:
                    self.log("[WARNING] 无法获取当前价格，跳过保证金检查", 'warning')
                    return True
                    
            except Exception as price_error:
                self.log(f"[WARNING] 保证金计算失败，跳过检查: {price_error}", 'warning')
                return True
                
        except Exception as e:
            self.log(f"[ERROR] 账户余额检查失败: {e}", 'error')
            return False
    
    def get_mid_price(self) -> float:
        """获取中间价格，并按照tick_size格式化"""
        try:
            # 获取深度信息
            book_ticker = self.client.get_book_ticker(self.symbol)
            if not book_ticker:
                self.log("[FAILED] 无法获取价格信息", 'error')
                raise Exception("无法获取价格信息")
            
            bid_price = float(book_ticker['bidPrice'])  # 买一价格
            ask_price = float(book_ticker['askPrice'])  # 卖一价格
            
            # 计算中间价格
            mid_price = (bid_price + ask_price) / 2
            spread = ask_price - bid_price
            
            # 使用tick_size格式化价格
            formatted_price = self.format_price(mid_price)
            mid_price = float(formatted_price)
            
            self.log(f"深度信息: 买一={bid_price:.5f}, 卖一={ask_price:.5f}")
            self.log(f"价差: {spread:.5f}")
            self.log(f"中间价格: {formatted_price} (符合tick_size)")
            
            return mid_price
            
            return mid_price
            
        except Exception as e:
            self.log(f"[ERROR] 获取价格失败: {e}", 'error')
            raise
    
    def monitor_and_handle_orders(self, long_order_id: str, short_order_id: str) -> bool:
        """监控订单状态，3秒内未成交则取消"""
        monitor_start_time = time.time()
        check_interval = 0.5  # 每0.5秒检查一次
        max_wait_time = 3.0   # 最多等待3秒
        
        print(f"监控订单状态，最多等待{max_wait_time}秒...")
        
        while True:
            try:
                elapsed_time = time.time() - monitor_start_time
                
                if elapsed_time >= max_wait_time:
                    print(f"[TIMEOUT] 等待{max_wait_time}秒后订单未成交，开始取消订单...")
                    return self.cancel_pending_orders(long_order_id, short_order_id)
                
                # 查询订单状态
                long_order_status = self.client.get_order(self.symbol, order_id=long_order_id)
                short_order_status = self.client.get_order(self.symbol, order_id=short_order_id)
                
                if not long_order_status or not short_order_status:
                    print("[ERROR] 无法获取订单状态")
                    return self.cancel_pending_orders(long_order_id, short_order_id)
                
                long_status = long_order_status.get('status')
                short_status = short_order_status.get('status')
                
                print(f"[{elapsed_time:.1f}s] 订单状态: 多头={long_status}, 空头={short_status}")
                
                # 检查是否都成交了
                if long_status == 'FILLED' and short_status == 'FILLED':
                    print("[SUCCESS] 订单成功成交!")
                    
                    # 显示成交信息
                    long_fill_price = long_order_status.get('avgPrice', long_order_status.get('price'))
                    short_fill_price = short_order_status.get('avgPrice', short_order_status.get('price'))
                    long_qty = float(long_order_status.get('executedQty', 0))
                    short_qty = float(short_order_status.get('executedQty', 0))
                    
                    print(f"多头成交价格: {long_fill_price}")
                    print(f"空头成交价格: {short_fill_price}")
                    print(f"价格一致性: {'✅' if long_fill_price == short_fill_price else '❌'}")
                    print(f"多头成交数量: {long_qty}张")
                    print(f"空头成交数量: {short_qty}张")
                    
                    # 累计交易统计
                    if long_fill_price and long_qty > 0:
                        volume_usdt = float(long_fill_price) * long_qty
                        self.buy_volume_usdt += volume_usdt
                    if short_fill_price and short_qty > 0:
                        volume_usdt = float(short_fill_price) * short_qty
                        self.sell_volume_usdt += volume_usdt
                    
                    # 累计手续费（假设0.02%的手续费率）
                    if long_fill_price and short_fill_price and long_qty > 0 and short_qty > 0:
                        total_volume = float(long_fill_price) * long_qty + float(short_fill_price) * short_qty
                        fees = total_volume * 0.0002  # 0.02% 手续费
                        self.total_fees_usdt += fees
                    
                    return True
                
                # 检查是否有订单被取消或失败
                if long_status in ['CANCELED', 'REJECTED', 'EXPIRED'] or short_status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    print(f"[FAILED] 订单异常状态: 多头={long_status}, 空头={short_status}")
                    return self.cancel_pending_orders(long_order_id, short_order_id)
                
                # 等待下次检查
                time.sleep(check_interval)
                
            except Exception as e:
                print(f"[ERROR] 监控订单状态异常: {e}")
                return self.cancel_pending_orders(long_order_id, short_order_id)
    
    def cancel_pending_orders(self, long_order_id: str, short_order_id: str) -> bool:
        """取消未成交的订单"""
        print("取消未成交订单...")
        
        cancel_success = True
        
        # 尝试取消多头订单
        try:
            long_cancel_result = self.client.cancel_order(self.symbol, order_id=long_order_id)
            if long_cancel_result:
                print(f"✅ 多头订单 {long_order_id} 取消成功")
            else:
                print(f"⚠️ 多头订单 {long_order_id} 可能已成交或已取消")
        except Exception as e:
            print(f"❌ 取消多头订单失败: {e}")
            cancel_success = False
        
        # 尝试取消空头订单  
        try:
            short_cancel_result = self.client.cancel_order(self.symbol, order_id=short_order_id)
            if short_cancel_result:
                print(f"✅ 空头订单 {short_order_id} 取消成功")
            else:
                print(f"⚠️ 空头订单 {short_order_id} 可能已成交或已取消")
        except Exception as e:
            print(f"❌ 取消空头订单失败: {e}")
            cancel_success = False
        
        if cancel_success:
            print("[INFO] 订单取消完成，本轮结束")
        else:
            print("[WARNING] 订单取消过程中出现问题，但继续下一轮")
        
        # 不管取消是否完全成功，都返回False表示本轮未成功成交
        return False
    
    def execute_hidden_orders(self, mid_price: float, round_num: int = 1) -> bool:
        """执行HIDDEN隐藏订单自成交"""
        self.log(f"\\n=== 第{round_num}轮: 执行HIDDEN隐藏订单自成交 ===")
        self.log(f"中间价格: {mid_price:.5f}")
        self.log(f"数量: {self.quantity}张 (多空各{self.quantity}张)")
        
        # 确保价格字符串完全一致
        price_str = f"{mid_price:.5f}"
        self.log(f"统一价格字符串: '{price_str}'")
        
        # 构建批量隐藏订单
        batch_orders = [
            {
                "symbol": self.symbol,
                "side": "BUY",         # 买入开多仓
                "type": "LIMIT",
                "timeInForce": "HIDDEN",  # 🔑 隐藏订单关键参数
                "price": price_str,
                "quantity": self.quantity,
                "positionSide": "BOTH"
            },
            {
                "symbol": self.symbol,
                "side": "SELL",        # 卖出开空仓
                "type": "LIMIT", 
                "timeInForce": "HIDDEN",  # 🔑 隐藏订单关键参数
                "price": price_str,
                "quantity": self.quantity,
                "positionSide": "BOTH"
            }
        ]
        
        self.log("HIDDEN隐藏订单详情:")
        for i, order in enumerate(batch_orders):
            self.log(f"  订单{i+1}: {order['side']} {order['quantity']}张 @{order['price']} ({order['timeInForce']})")
        
        try:
            self.log("\\n提交批量HIDDEN订单...")
            start_time = time.time()
            
            # 使用批量下单API
            order_results = self.client.place_batch_orders(batch_orders)
            
            end_time = time.time()
            self.log(f"批量下单耗时: {(end_time - start_time)*1000:.0f}毫秒")
            
            if not order_results or len(order_results) != 2:
                self.log("[FAILED] 批量HIDDEN订单失败", 'error')
                self.log(f"返回结果: {order_results}", 'error')
                return False
            
            # 解析结果
            long_order = None
            short_order = None
            
            for result in order_results:
                if isinstance(result, dict) and 'side' in result:
                    if result['side'] == 'BUY':
                        long_order = result
                    elif result['side'] == 'SELL':
                        short_order = result
            
            if not long_order or not short_order:
                print("[FAILED] 批量订单结果异常")
                return False
            
            long_order_id = long_order.get('orderId')
            short_order_id = short_order.get('orderId')
            
            print("[SUCCESS] 批量HIDDEN订单提交成功!")
            print(f"多头订单ID: {long_order_id} (状态: {long_order.get('status', 'N/A')})")
            print(f"空头订单ID: {short_order_id} (状态: {short_order.get('status', 'N/A')})")
            
            # 检查是否立即成交
            if long_order.get('status') == 'FILLED' and short_order.get('status') == 'FILLED':
                print("[SUCCESS] HIDDEN订单立即成交成功!")
                
                # 显示成交信息
                long_fill_price = long_order.get('avgPrice', long_order.get('price'))
                short_fill_price = short_order.get('avgPrice', short_order.get('price'))
                long_qty = float(long_order.get('executedQty', 0))
                short_qty = float(short_order.get('executedQty', 0))
                
                print(f"多头成交价格: {long_fill_price}")
                print(f"空头成交价格: {short_fill_price}")
                print(f"价格一致性: {'✅' if long_fill_price == short_fill_price else '❌'}")
                print(f"成交数量: {long_qty}张")
                
                # 累计交易统计
                if long_fill_price and long_qty > 0:
                    volume_usdt = float(long_fill_price) * long_qty
                    self.buy_volume_usdt += volume_usdt
                if short_fill_price and short_qty > 0:
                    volume_usdt = float(short_fill_price) * short_qty
                    self.sell_volume_usdt += volume_usdt
                
                # 累计手续费（假设0.02%的手续费率）
                if long_fill_price and short_fill_price and long_qty > 0 and short_qty > 0:
                    total_volume = float(long_fill_price) * long_qty + float(short_fill_price) * short_qty
                    fees = total_volume * 0.0002  # 0.02% 手续费
                    self.total_fees_usdt += fees
                
                return True
            else:
                print("[INFO] 订单未立即成交，开始监控订单状态...")
                print(f"  多头状态: {long_order.get('status')}")
                print(f"  空头状态: {short_order.get('status')}")
                
                # 持续监控订单状态，最多3秒
                return self.monitor_and_handle_orders(long_order_id, short_order_id)
            
        except Exception as e:
            self.log(f"[ERROR] 批量HIDDEN订单异常: {e}", 'error')
            return False
    
    def run(self) -> bool:
        """运行策略"""
        self.log(f"\\n开始执行HIDDEN隐藏订单合约自成交策略...")
        self.log(f"计划执行 {self.rounds} 轮，每轮间隔 {self.interval} 秒")
        
        # 连接交易所
        if not self.connect():
            return False
        
        try:
            total_start_time = time.time()
            successful_rounds = 0
            failed_rounds = 0
            
            # 循环执行指定轮次
            for round_num in range(1, self.rounds + 1):
                self.log(f"\\n{'='*60}")
                self.log(f"开始第 {round_num}/{self.rounds} 轮交易")
                self.log(f"{'='*60}")
                
                try:
                    round_start_time = time.time()
                    
                    # 获取当前轮次的中间价格
                    mid_price = self.get_mid_price()
                    
                    # 执行HIDDEN隐藏订单自成交
                    round_success = self.execute_hidden_orders(mid_price, round_num)
                    
                    round_end_time = time.time()
                    round_duration = (round_end_time - round_start_time) * 1000
                    
                    if round_success:
                        successful_rounds += 1
                        self.completed_rounds += 1
                        self.log(f"[SUCCESS] 第{round_num}轮执行成功! 耗时: {round_duration:.0f}毫秒")
                    else:
                        failed_rounds += 1
                        self.failed_rounds += 1
                        self.log(f"[FAILED] 第{round_num}轮执行失败! 耗时: {round_duration:.0f}毫秒", 'error')
                    
                    # 如果不是最后一轮，等待间隔时间
                    if round_num < self.rounds:
                        self.log(f"\\n等待 {self.interval} 秒进入下一轮...")
                        for i in range(self.interval, 0, -1):
                            print(f"倒计时: {i}秒", end="\\r")
                            time.sleep(1)
                        print(" " * 20, end="\\r")  # 清除倒计时
                        
                except Exception as e:
                    failed_rounds += 1
                    self.failed_rounds += 1
                    self.log(f"[ERROR] 第{round_num}轮执行异常: {e}", 'error')
                    
                    # 如果不是最后一轮，继续执行下一轮
                    if round_num < self.rounds:
                        self.log(f"等待 {self.interval} 秒后继续下一轮...")
                        time.sleep(self.interval)
            
            total_end_time = time.time()
            total_duration = (total_end_time - total_start_time) * 1000
            
            # 输出最终统计
            self.log(f"\\n{'='*60}")
            self.log(f"=== 策略执行完成 ===")
            self.log(f"{'='*60}")
            
            if successful_rounds > 0:
                self.log(f"[SUCCESS] HIDDEN隐藏订单自成交策略执行完成!")
            else:
                self.log(f"[FAILED] HIDDEN隐藏订单策略执行失败!", 'error')
                
            self.log(f"[SUMMARY] 执行总结:")
            self.log(f"  交易对: {self.symbol}")
            self.log(f"  单次数量: {self.quantity}张 (多空各{self.quantity}张)")
            self.log(f"  总轮次: {self.rounds}轮")
            self.log(f"  成功轮次: {successful_rounds}轮")
            self.log(f"  失败轮次: {failed_rounds}轮") 
            self.log(f"  成功率: {(successful_rounds/self.rounds)*100:.1f}%")
            self.log(f"  间隔时间: {self.interval}秒")
            self.log(f"  订单类型: HIDDEN隐藏订单")
            self.log(f"  成交方式: 批量API同时提交，立即内部匹配")
            self.log(f"  总耗时: {total_duration:.0f}毫秒")
            self.log(f"  平均每轮: {total_duration/self.rounds:.0f}毫秒")
            
            # 计算最终统计数据（不调用API）
            self.final_usdt_balance = self.initial_usdt_balance - self.total_fees_usdt
            self.usdt_balance_diff = self.final_usdt_balance - self.initial_usdt_balance
            self.net_loss_usdt = self.usdt_balance_diff
            
            # 如果有成功的轮次就算成功
            return successful_rounds > 0
            
        except Exception as e:
            self.log(f"[ERROR] 策略执行异常: {e}", 'error')
            return False


def main():
    """主函数"""
    # 策略参数
    SYMBOL = "SKYUSDT"
    QUANTITY = "3249.0"
    LEVERAGE = 20
    ROUNDS = 5  # 默认执行5轮
    INTERVAL = 3  # 默认间隔3秒
    
    print("=== AsterDEX HIDDEN隐藏订单合约自成交策略 ===")
    print(f"交易对: {SYMBOL}")
    print(f"数量: {QUANTITY}张")
    print(f"杠杆: {LEVERAGE}倍")
    print(f"执行轮次: {ROUNDS}轮")
    print(f"间隔时间: {INTERVAL}秒")
    print("\\n策略说明:")
    print("1. 获取买一卖一价格，计算中间价")
    print("2. 批量提交HIDDEN隐藏订单(多空同价)")
    print("3. 隐藏订单立即内部匹配成交")
    print("4. 循环执行指定轮次，每轮间隔指定时间")
    print("5. 实现零风险自成交")
    
    # 创建并运行策略
    strategy = HiddenFuturesStrategy(
        symbol=SYMBOL,
        quantity=QUANTITY,
        leverage=LEVERAGE,
        rounds=ROUNDS,
        interval=INTERVAL
    )
    
    return strategy.run()


if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\\n[INTERRUPT] 用户中断策略执行")
        sys.exit(1)
    except Exception as e:
        print(f"\\n[ERROR] 策略启动错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
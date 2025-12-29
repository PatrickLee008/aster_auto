"""
刷量交易策略
主要目的：通过卖出和买入相同价格和数量的现货来刷交易量，避免亏损
"""

import time
import random
from typing import Optional, Dict, Any
import sys
import os

# 添加父目录到路径以导入客户端
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simple_trading_client import SimpleTradingClient
from config_env import SPOT_CONFIG


class VolumeStrategy:
    """刷量交易策略"""
    
    def __init__(self, symbol: str, quantity: str, interval: int = 10, rounds: int = 10):
        """
        初始化策略
        
        Args:
            symbol (str): 交易对，如 'ASTERUSDT'
            quantity (str): 每次交易数量
            interval (int): 交易间隔时间(秒)，默认10秒
            rounds (int): 交易轮次，默认10次
        """
        self.symbol = symbol
        self.quantity = quantity
        self.interval = interval
        self.rounds = rounds
        self.client = None
        self.logger = None  # 日志记录器
        
        # 风险控制参数
        self.buy_timeout = 0.5  # 买入检查时间(300毫秒)
        self.max_price_deviation = 0.01  # 最大价格偏差(1%)
        
        print(f"=== 刷量策略初始化 ===")
        print(f"交易对: {symbol}")
        print(f"数量: {quantity}")
        print(f"间隔: {interval}秒")
        print(f"轮次: {rounds}次")
        print(f"买入检查: {self.buy_timeout}秒")
    
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
            # 始终使用SimpleTradingClient，因为它的签名实现是正确的
            self.client = SimpleTradingClient()
            
            if self.client.test_connection():
                print("交易所连接成功")
                
                # 预热连接 - 获取一次服务器时间以稳定连接
                print("预热网络连接...")
                for i in range(2):
                    try:
                        time_result = self.client.get_server_time()
                        if time_result:
                            print(f"连接预热 {i+1}/2 完成")
                            break
                    except:
                        pass
                    time.sleep(0.5)
                
                # 检查账户余额 - 根据交易对自动检测
                base_asset = self.symbol.replace('USDT', '')  # 从SENTISUSDT获取SENTIS
                account_info = self.client.get_account_info()
                if account_info and 'balances' in account_info:
                    for balance in account_info['balances']:
                        if balance['asset'] == base_asset:
                            asset_balance = float(balance['free'])
                            print(f"{base_asset}余额: {asset_balance:.2f}")
                            
                            required_quantity = float(self.quantity)
                            if asset_balance < required_quantity:
                                print(f"警告: {base_asset}余额不足 ({asset_balance:.2f} < {required_quantity:.2f})")
                                print("刷量策略可能会在卖出时失败")
                            else:
                                print(f"{base_asset}余额充足 ({asset_balance:.2f} >= {required_quantity:.2f})")
                            break
                    else:
                        print(f"未找到{base_asset}余额信息")
                
                return True
            else:
                print("交易所连接失败")
                return False
                
        except Exception as e:
            print(f"连接错误: {e}")
            return False
    
    def get_order_book(self) -> Optional[Dict[str, Any]]:
        """获取深度订单薄数据"""
        try:
            # 尝试获取深度数据
            depth_response = self.client.get_depth(self.symbol, 5)
            
            if depth_response and 'bids' in depth_response and 'asks' in depth_response:
                bids = depth_response['bids']  # 买单 [[price, quantity], ...]
                asks = depth_response['asks']  # 卖单 [[price, quantity], ...]
                
                if bids and asks:
                    # 买方第一档价格（买一价格 - 最高买价）
                    first_bid_price = float(bids[0][0])
                    # 买方最后一档价格（买单中最低的价格）
                    last_bid_price = float(bids[-1][0]) if len(bids) > 1 else float(bids[0][0])
                    # 卖方第一档价格（卖一价格 - 最低卖价）
                    first_ask_price = float(asks[0][0])
                    # 卖方最后一档价格
                    last_ask_price = float(asks[-1][0]) if len(asks) > 1 else float(asks[0][0])
                    
                    print(f"买方价格区间: {first_bid_price} - {last_bid_price}")
                    print(f"卖方价格区间: {first_ask_price} - {last_ask_price}")
                    print(f"使用价格区间: [{first_bid_price}, {first_ask_price}]")
                    
                    return {
                        'bid_price': first_bid_price,  # 买方第一档（买一价格）
                        'ask_price': first_ask_price,  # 卖方第一档（卖一价格）
                        'bid_depth': len(bids),
                        'ask_depth': len(asks)
                    }
            
            # 如果深度数据获取失败，回退到简单模式
            print("深度数据获取失败，使用简单买卖一价格")
            book_ticker = self.client.get_book_ticker(self.symbol)
            if book_ticker:
                bid_price = float(book_ticker['bidPrice'])  # 买一价格
                ask_price = float(book_ticker['askPrice'])  # 卖一价格
                
                print(f"买一价格: {bid_price}, 卖一价格: {ask_price}")
                return {
                    'bid_price': bid_price,
                    'ask_price': ask_price
                }
            return None
            
        except Exception as e:
            self.log(f"获取订单薄失败: {e}", 'error')
            return None
    
    def generate_trade_price(self, bid_price: float, ask_price: float) -> float:
        """生成交易价格，在原区间基础上稍微卖高一点点提高命中率"""
        if bid_price >= ask_price:
            # 如果买卖价差很小或无价差，使用买一价格作为基准
            base_price = bid_price
        else:
            # 在买一价格和卖一价格之间生成价格，偏向卖一价格（稍微卖高）
            price_range = ask_price - bid_price
            # 在价格区间的70%-90%位置生成价格，让卖出价格偏高
            offset = random.uniform(0.7, 0.9)
            base_price = bid_price + (price_range * offset)
        
        # 保留5位小数精度
        trade_price = round(base_price, 5)
        
        # 检查订单价值是否满足5 USDT最小限制
        order_value = trade_price * float(self.quantity)
        if order_value < 5.0:
            # 如果订单价值不足，调整价格确保满足最小限制
            min_price = 5.0 / float(self.quantity)
            trade_price = max(trade_price, round(min_price, 5))
        
        print(f"生成交易价格: {trade_price:.5f} (偏向高价，提高命中率)")
        print(f"订单价值: {trade_price * float(self.quantity):.2f} USDT")
        return trade_price
    
    def place_sell_order(self, price: float) -> Optional[Dict[str, Any]]:
        """下达卖出订单"""
        try:
            # 确保数量精度正确(ASTER通常2位小数)
            import math
            adjusted_quantity = math.floor(float(self.quantity) * 100) / 100
            quantity_str = f"{adjusted_quantity:.2f}"
            
            # 格式化价格为5位小数以保持精度
            price_str = f"{price:.5f}"
            
            result = self.client.place_order(
                symbol=self.symbol,
                side='SELL',
                order_type='LIMIT',
                quantity=quantity_str,
                price=price_str,
                time_in_force='GTC'
            )
            
            if result:
                print(f"卖出订单成功: ID {result.get('orderId')}")
                return result
            else:
                print(f"卖出订单失败: 无返回结果")
                return None
                
        except Exception as e:
            print(f"卖出订单错误: {e}")
            return None
    
    def place_buy_order(self, price: float, quantity: float = None) -> Optional[Dict[str, Any]]:
        """下达买入订单"""
        try:
            # 使用传入的数量或默认数量
            if quantity is None:
                quantity = float(self.quantity)
            
            # 确保数量精度正确(SENTIS通常2位小数)
            import math
            adjusted_quantity = math.floor(quantity * 100) / 100
            quantity_str = f"{adjusted_quantity:.2f}"
            
            # 格式化价格为5位小数以保持精度
            price_str = f"{price:.5f}"
            
            result = self.client.place_order(
                symbol=self.symbol,
                side='BUY',
                order_type='LIMIT',
                quantity=quantity_str,
                price=price_str,
                time_in_force='GTC'
            )
            
            if result:
                print(f"买入订单成功: ID {result.get('orderId')}")
                return result
            else:
                print(f"买入订单失败: 无返回结果")
                return None
                
        except Exception as e:
            print(f"买入订单错误: {e}")
            return None
    
    def check_order_status(self, order_id: int) -> Optional[str]:
        """检查订单状态"""
        try:
            result = self.client.get_order(self.symbol, order_id)
            if result:
                return result.get('status')
            return None
            
        except Exception as e:
            print(f"查询订单状态错误: {e}")
            return None
    
    def cancel_order(self, order_id: int) -> bool:
        """撤销订单"""
        try:
            result = self.client.cancel_order(symbol=self.symbol, order_id=order_id)
            return result is not None
            
        except Exception as e:
            print(f"撤销订单错误: {e}")
            return False
    
    def get_market_depth(self) -> dict:
        """获取市场深度数据"""
        try:
            depth = self.client.get_depth(symbol=self.symbol, limit=20)
            if not depth or 'asks' not in depth or 'bids' not in depth:
                return None
            
            return {
                'bids': [[float(bid[0]), float(bid[1])] for bid in depth['bids']],  # [[价格, 数量], ...]
                'asks': [[float(ask[0]), float(ask[1])] for ask in depth['asks']]   # [[价格, 数量], ...]
            }
        except Exception as e:
            print(f"获取市场深度失败: {e}")
            return None
    
    def smart_buy_order(self, original_price: float) -> bool:
        """智能买入补单 - 寻找更容易成交且亏损最小的价格"""
        print("\\n--- 智能买入补单策略 ---")
        
        # 获取最新市场深度
        depth = self.get_market_depth()
        if not depth:
            print("无法获取市场深度，补单失败")
            return False
        
        asks = depth['asks']  # 卖盘 [[价格, 数量], ...]
        if not asks:
            print("卖盘为空，补单失败")
            return False
        
        print(f"原始价格: {original_price:.5f}")
        print(f"当前卖盘档位: {len(asks)}档")
        
        # 寻找最优补单价格
        target_quantity = float(self.quantity)
        best_price = None
        min_loss = float('inf')
        total_available = 0
        
        for ask in asks:
            ask_price = ask[0]
            ask_quantity = ask[1]
            
            # 计算相对于原始价格的损失
            loss = ask_price - original_price
            
            # 检查订单价值是否满足5 USDT最小限制
            order_value = ask_price * target_quantity
            if order_value < 5.0:
                continue
            
            # 检查深度是否足够
            if ask_quantity >= target_quantity:
                # 单档就能满足，这是最优选择
                if loss < min_loss:
                    min_loss = loss
                    best_price = ask_price
                print(f"可选价格: {ask_price:.5f}, 损失: {loss:.5f}, 深度: {ask_quantity:.2f}")
                break
            else:
                # 累计深度检查
                total_available += ask_quantity
                if total_available >= target_quantity and loss < min_loss:
                    min_loss = loss
                    best_price = ask_price
                print(f"可选价格: {ask_price:.5f}, 损失: {loss:.5f}, 累计深度: {total_available:.2f}")
        
        if not best_price:
            print("未找到合适的补单价格")
            return False
        
        print(f"\\n选择补单价格: {best_price:.5f}")
        print(f"价格损失: {min_loss:.5f} ({(min_loss/original_price)*100:.2f}%)")
        print(f"订单价值: {best_price * target_quantity:.2f} USDT")
        
        # 执行补单
        try:
            result = self.place_buy_order(best_price, self.quantity)
            if result:
                print(f"✅ 智能买入补单成功: ID {result.get('orderId')}")
                return True
            else:
                print("❌ 智能买入补单失败")
                return False
        except Exception as e:
            print(f"❌ 智能买入补单异常: {e}")
            return False
    
    def smart_sell_order(self, original_price: float) -> bool:
        """智能卖出补单 - 寻找更容易成交且亏损最小的价格"""
        print("\\n--- 智能卖出补单策略 ---")
        
        # 获取最新市场深度  
        depth = self.get_market_depth()
        if not depth:
            print("无法获取市场深度，补单失败")
            return False
        
        bids = depth['bids']  # 买盘 [[价格, 数量], ...]
        if not bids:
            print("买盘为空，补单失败")
            return False
        
        print(f"原始价格: {original_price:.5f}")
        print(f"当前买盘档位: {len(bids)}档")
        
        # 寻找最优补单价格
        target_quantity = float(self.quantity)
        best_price = None
        min_loss = float('inf')
        total_available = 0
        
        for bid in bids:
            bid_price = bid[0]
            bid_quantity = bid[1]
            
            # 计算相对于原始价格的损失
            loss = original_price - bid_price  # 卖出价格越低损失越大
            
            # 检查订单价值是否满足5 USDT最小限制
            order_value = bid_price * target_quantity
            if order_value < 5.0:
                continue
            
            # 检查深度是否足够
            if bid_quantity >= target_quantity:
                # 单档就能满足，这是最优选择
                if loss < min_loss:
                    min_loss = loss
                    best_price = bid_price
                print(f"可选价格: {bid_price:.5f}, 损失: {loss:.5f}, 深度: {bid_quantity:.2f}")
                break
            else:
                # 累计深度检查
                total_available += bid_quantity
                if total_available >= target_quantity and loss < min_loss:
                    min_loss = loss
                    best_price = bid_price
                print(f"可选价格: {bid_price:.5f}, 损失: {loss:.5f}, 累计深度: {total_available:.2f}")
        
        if not best_price:
            print("未找到合适的补单价格")
            return False
        
        print(f"\\n选择补单价格: {best_price:.5f}")
        print(f"价格损失: {min_loss:.5f} ({(min_loss/original_price)*100:.2f}%)")
        print(f"订单价值: {best_price * target_quantity:.2f} USDT")
        
        # 执行补单
        try:
            result = self.place_sell_order(best_price)
            if result:
                print(f"✅ 智能卖出补单成功: ID {result.get('orderId')}")
                return True
            else:
                print("❌ 智能卖出补单失败")
                return False
        except Exception as e:
            print(f"❌ 智能卖出补单异常: {e}")
            return False
    
    def emergency_buy(self, target_sell_price: float) -> bool:
        """智能紧急买入 - 逐档补货直到完全补齐卖出数量"""
        try:
            print("执行风险控制 - 逐档智能补货")
            print(f"目标价格: {target_sell_price:.5f} (原卖出价格)")
            
            target_quantity = float(self.quantity)  # 需要补回的总数量
            filled_quantity = 0.0  # 已补回的数量
            total_cost = 0.0  # 总成本
            buy_orders = []  # 记录所有买入订单
            
            print(f"需要补回数量: {target_quantity:.2f} {self.symbol.replace('USDT', '')}")
            
            while filled_quantity < target_quantity:
                remaining_quantity = target_quantity - filled_quantity
                print(f"\n还需补回: {remaining_quantity:.2f}")
                
                # 获取当前订单薄深度
                depth_data = self.client.get_depth(self.symbol, 20)  # 获取更多档深度
                
                if not depth_data or 'asks' not in depth_data:
                    print("❌ 无法获取订单薄深度")
                    break
                
                asks = depth_data['asks']  # 卖单 [[price, quantity], ...]
                print(f"当前卖盘深度: {len(asks)}档")
                
                if not asks:
                    print("❌ 卖盘为空")
                    break
                
                # 选择最优价格（最接近目标价格的卖单）
                best_ask = None
                min_loss = float('inf')
                
                for ask in asks:
                    ask_price = float(ask[0])
                    ask_quantity = float(ask[1])
                    
                    if ask_quantity > 0:  # 确保有数量
                        loss = max(0, ask_price - target_sell_price)  # 计算损失
                        if loss < min_loss:
                            min_loss = loss
                            best_ask = ask
                
                if not best_ask:
                    print("❌ 没有找到合适的卖单")
                    break
                
                ask_price = float(best_ask[0])
                ask_quantity = float(best_ask[1])
                
                # 决定本次买入数量
                buy_quantity = min(remaining_quantity, ask_quantity)
                buy_quantity = round(buy_quantity, 2)  # 保持2位小数精度
                
                # 检查订单价值是否满足5 USDT最小限制
                order_value = buy_quantity * ask_price
                if order_value < 5.0:
                    # 调整数量以满足最小订单价值
                    min_quantity = 5.0 / ask_price
                    buy_quantity = min(remaining_quantity, min_quantity)
                    buy_quantity = round(buy_quantity, 2)
                    order_value = buy_quantity * ask_price
                    
                    print(f"调整买入数量以满足5 USDT限制: {buy_quantity:.2f}")
                    print(f"调整后订单价值: {order_value:.4f} USDT")
                    
                    # 如果调整后仍然不足5 USDT，跳过这个价格
                    if order_value < 5.0:
                        print(f"⚠️  价格 {ask_price:.5f} 无法满足5 USDT限制，跳过")
                        continue
                
                # 确保不超买（买入数量不超过剩余需求）
                if buy_quantity > remaining_quantity:
                    buy_quantity = remaining_quantity
                    buy_quantity = round(buy_quantity, 2)
                    order_value = buy_quantity * ask_price
                    print(f"限制买入数量不超过剩余需求: {buy_quantity:.2f}")
                
                print(f"选择价格: {ask_price:.5f} (损失: {min_loss:.5f})")
                print(f"可用数量: {ask_quantity:.2f}, 本次买入: {buy_quantity:.2f}")
                print(f"订单价值: {order_value:.4f} USDT")
                
                # 执行买入
                result = self.place_buy_order(ask_price, buy_quantity)
                
                if result:
                    buy_order_id = result.get('orderId')
                    buy_orders.append(buy_order_id)
                    print(f"✅ 买入订单成功: ID {buy_order_id}")
                    
                    # 简单等待成交确认
                    time.sleep(0.3)
                    
                    # 简化处理：假设按期望数量完全成交
                    filled_quantity += buy_quantity
                    cost = buy_quantity * ask_price
                    total_cost += cost
                    
                    print(f"✅ 补货成交: {buy_quantity:.2f} @ {ask_price:.5f}")
                    print(f"累计补回: {filled_quantity:.2f}/{target_quantity:.2f}")
                    print(f"累计成本: {total_cost:.4f} USDT")
                else:
                    print("❌ 买入订单失败")
                    break
                
                # 防止无限循环
                if len(buy_orders) >= 10:
                    print("⚠️  已尝试10次买入，停止补货")
                    break
            
            # 总结补货结果
            print(f"\n=== 补货完成 ===")
            print(f"目标数量: {target_quantity:.2f}")
            print(f"实际补回: {filled_quantity:.2f}")
            print(f"补货率: {(filled_quantity/target_quantity)*100:.1f}%")
            print(f"总成本: {total_cost:.4f} USDT")
            
            if target_cost := target_quantity * target_sell_price:
                extra_cost = total_cost - target_cost
                print(f"额外成本: {extra_cost:.4f} USDT")
            
            # 如果补货完成度达到95%以上认为成功
            success_rate = filled_quantity / target_quantity
            if success_rate >= 0.95:
                print("✅ 补货基本完成")
                return True
            else:
                print("❌ 补货未完全完成")
                return False
                
        except Exception as e:
            print(f"补货过程错误: {e}")
            return False
    
    def execute_round(self, round_num: int) -> bool:
        """执行一轮交易"""
        print(f"\n=== 第 {round_num}/{self.rounds} 轮交易 ===")
        
        try:
            # 1. 获取当前订单薄
            book_data = self.get_order_book()
            if not book_data:
                self.log("无法获取订单薄，跳过本轮", 'error')
                return False
            
            # 2. 生成交易价格（偏向高价提高命中率）
            trade_price = self.generate_trade_price(
                book_data['bid_price'],  # 买一价格
                book_data['ask_price']   # 卖一价格
            )
            
            # 3. 有序快速执行：先发起卖出，立即发起买入
            print(f"有序提交订单: {self.quantity} {self.symbol} @ {trade_price:.5f}")
            
            import threading
            import time
            
            print("执行顺序: 卖出 -> 买入 (最小延迟)")
            start_time = time.time()
            
            # 用于存储订单结果的变量
            sell_order = None
            buy_order = None
            sell_exception = None
            buy_exception = None
            
            # 最优方案：使用异步HTTP请求减少延迟
            try:
                print("同时发起请求（卖出略优先）...")
                
                # 方案A：使用线程池，最小延迟
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    # 立即提交卖出任务
                    sell_future = executor.submit(self.place_sell_order, trade_price)
                    
                    # 微秒级延迟后提交买入任务
                    time.sleep(0.001)  # 1毫秒延迟
                    buy_future = executor.submit(self.place_buy_order, trade_price)
                    
                    # 并行等待结果 - 改进错误处理避免重复下单
                    try:
                        sell_order = sell_future.result(timeout=8)
                        buy_order = buy_future.result(timeout=8)
                    except Exception as result_e:
                        # 如果获取结果失败，检查订单是否已经提交
                        print(f"获取并行结果异常: {result_e}")
                        
                        # 尝试从future获取已完成的结果
                        try:
                            sell_order = sell_future.result(timeout=1) if sell_future.done() else None
                        except:
                            sell_order = None
                        
                        try:
                            buy_order = buy_future.result(timeout=1) if buy_future.done() else None
                        except:
                            buy_order = None
                        
                        # 如果订单提交失败，直接取消并跳过本轮（不使用补单）
                        if not sell_order and not buy_order:
                            print("并行订单提交完全失败，跳过本轮")
                            return False
                        elif sell_order and not buy_order:
                            print("卖出提交成功，买入提交失败 - 取消卖出订单")
                            sell_order_id = sell_order.get('orderId')
                            if sell_order_id:
                                try:
                                    self.cancel_order(sell_order_id)
                                    print(f"✅ 已取消卖出订单: {sell_order_id}")
                                except Exception as cancel_e:
                                    print(f"❌ 取消卖出订单失败: {cancel_e}")
                            print("跳过本轮")
                            return False
                        elif buy_order and not sell_order:
                            print("买入提交成功，卖出提交失败 - 取消买入订单")
                            buy_order_id = buy_order.get('orderId')
                            if buy_order_id:
                                try:
                                    self.cancel_order(buy_order_id)
                                    print(f"✅ 已取消买入订单: {buy_order_id}")
                                except Exception as cancel_e:
                                    print(f"❌ 取消买入订单失败: {cancel_e}")
                            print("跳过本轮")
                            return False
                        else:
                            print(f"并行订单都提交成功: 卖出={bool(sell_order)}, 买入={bool(buy_order)}")
                        
            except Exception as e:
                print(f"执行异常: {e}")
                print("并行执行失败，跳过本轮")
                return False
            
            end_time = time.time()
            print(f"有序下单耗时: {(end_time - start_time)*1000:.0f}毫秒")
            
            # 4. 检查异常和订单提交结果
            if sell_exception:
                print(f"❌ 卖出订单异常: {sell_exception}")
            if buy_exception:
                print(f"❌ 买入订单异常: {buy_exception}")
            
            # 这里不应该再有订单提交失败的情况，因为前面已经处理过了
            if not sell_order or not buy_order:
                print("❌ 程序逻辑错误：订单提交失败但未在前面处理")
                return False
            
            # 5. 两个订单都成功提交
            sell_order_id = sell_order.get('orderId')
            buy_order_id = buy_order.get('orderId')
            print(f"✅ 卖出订单ID: {sell_order_id}")
            print(f"✅ 买入订单ID: {buy_order_id}")
            print("真正并行下单完成！")
            
            # 6. 等待300毫秒后检查订单成交状态
            time.sleep(self.buy_timeout)  # 等待300毫秒
            
            # 检查买入和卖出订单状态
            buy_status = self.check_order_status(buy_order_id)
            sell_status = self.check_order_status(sell_order_id)
            
            buy_filled = buy_status in ['FILLED', 'PARTIALLY_FILLED']
            sell_filled = sell_status in ['FILLED', 'PARTIALLY_FILLED']
            
            print(f"订单状态检查: 买入={buy_status}, 卖出={sell_status}")
            
            # 7. 根据成交情况处理
            if buy_filled and sell_filled:
                print("✅ 买卖订单都已成交，本轮成功")
            elif sell_filled and not buy_filled:
                print("❌ 卖出已成交，买入未成交 - 执行智能买入补单")
                # 取消未成交的买入订单
                self.cancel_order(buy_order_id)
                # 执行智能补单策略
                success = self.smart_buy_order(trade_price)
                if not success:
                    print("❌ 智能买入补单失败")
                    return False
            elif buy_filled and not sell_filled:
                print("❌ 买入已成交，卖出未成交 - 执行智能卖出补单")
                # 取消未成交的卖出订单
                self.cancel_order(sell_order_id)
                # 执行智能补单策略
                success = self.smart_sell_order(trade_price)
                if not success:
                    print("❌ 智能卖出补单失败")
                    return False
            else:
                print("❌ 买卖订单都未成交，取消订单并跳过本轮")
                self.cancel_order(buy_order_id)
                self.cancel_order(sell_order_id)
                return False
            
            print(f"第 {round_num} 轮交易完成")
            return True
            
        except Exception as e:
            print(f"交易轮次错误: {e}")
            return False
    
    def run(self) -> bool:
        """运行策略"""
        print(f"\n开始执行刷量策略...")
        
        if not self.connect():
            print("无法连接交易所，策略终止")
            return False
        
        # 检查初始余额 - 根据交易对自动检测
        base_asset = self.symbol.replace('USDT', '')  # 自动获取基础资产
        account_info = self.client.get_account_info()
        if account_info and 'balances' in account_info:
            for balance in account_info['balances']:
                if balance['asset'] == base_asset:
                    asset_balance = float(balance['free'])
                    required_quantity = float(self.quantity)
                    
                    if asset_balance < required_quantity:
                        print(f"错误: {base_asset}余额不足!")
                        print(f"当前余额: {asset_balance:.2f} {base_asset}")
                        print(f"需要数量: {required_quantity:.2f} {base_asset}")
                        print("程序停止")
                        return False
                    break
        
        success_rounds = 0
        
        try:
            for round_num in range(1, self.rounds + 1):
                if self.execute_round(round_num):
                    success_rounds += 1
                else:
                    print(f"第 {round_num} 轮失败")
                
                # 等待间隔时间(除了最后一轮)
                if round_num < self.rounds:
                    print(f"等待 {self.interval} 秒...")
                    time.sleep(self.interval)
            
            print(f"\n=== 策略执行完成 ===")
            print(f"成功轮次: {success_rounds}/{self.rounds}")
            print(f"成功率: {success_rounds/self.rounds*100:.1f}%")
            
            return success_rounds > 0
            
        except KeyboardInterrupt:
            print("\n用户中断策略执行")
            return False
        except Exception as e:
            print(f"策略执行错误: {e}")
            return False


def main():
    """主函数 - 策略参数配置"""
    
    # 策略参数配置
    SYMBOL = "SENTISUSDT"     # 交易对 (已从ASTERUSDT改为SENTISUSDT)
    QUANTITY = "8.0"          # 每次交易数量 (需根据SENTIS价格调整确保 >= 5 USDT)
    INTERVAL = 10             # 交易间隔(秒)
    ROUNDS = 10               # 交易轮次
    
    print("=== AsterDEX 刷量交易策略 ===")
    print(f"交易对: {SYMBOL}")
    print(f"数量: {QUANTITY}")
    print(f"间隔: {INTERVAL}秒")
    print(f"轮次: {ROUNDS}次")
    
    # 确认执行
    confirm = input("\n确认执行策略? (y/N): ").strip().lower()
    if confirm != 'y':
        print("策略已取消")
        return
    
    # 创建并运行策略
    strategy = VolumeStrategy(
        symbol=SYMBOL,
        quantity=QUANTITY,
        interval=INTERVAL,
        rounds=ROUNDS
    )
    
    success = strategy.run()
    
    if success:
        print("\n策略执行成功!")
    else:
        print("\n策略执行失败!")


if __name__ == "__main__":
    main()


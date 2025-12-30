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
from market_trading_client import MarketTradingClient
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
        self.market_client = None  # 市价单客户端
        self.logger = None  # 日志记录器
        
        # 风险控制参数 - 优化时间参数提高成交率
        self.buy_timeout = 1.0  # 买入检查时间(改为1秒，给订单更多成交时间)
        self.max_price_deviation = 0.01  # 最大价格偏差(1%)
        
        # 统计数据
        self.original_balance = 0.0  # 真正的原始余额（用于最终恢复）
        self.initial_balance = 0.0   # 策略开始时的初始余额（用于循环期间的平衡检验）
        self.completed_rounds = 0    # 完成的轮次
        self.supplement_orders = 0   # 补单次数
        self.total_cost_diff = 0.0   # 总损耗（价格差累计）
        self.auto_purchased = 0.0    # 自动购买的数量（需要最终卖出）
        
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
            # 使用任务运行器传递的钱包配置
            if hasattr(self, 'wallet_config') and self.wallet_config:
                config = self.wallet_config
                api_key = config.get('api_key')
                secret_key = config.get('secret_key')
                
                if api_key and secret_key:
                    self.client = SimpleTradingClient(
                        api_key=api_key,
                        secret_key=secret_key
                    )
                    self.market_client = MarketTradingClient(
                        api_key=api_key,
                        secret_key=secret_key
                    )
                    self.log(f"使用任务钱包配置连接交易所，API密钥: {api_key[:8]}...{api_key[-4:]}")
                else:
                    # API密钥或secret为空，回退到默认配置
                    self.client = SimpleTradingClient()
                    self.market_client = MarketTradingClient()
                    self.log("钱包API密钥为空，使用默认配置连接交易所", 'warning')
            else:
                # 回退到原有的配置方式
                self.client = SimpleTradingClient()
                self.market_client = MarketTradingClient()
                self.log("未找到钱包配置，使用默认配置连接交易所（回退模式）", 'warning')
            
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
                    usdt_balance = 0.0
                    asset_balance = 0.0
                    
                    for balance in account_info['balances']:
                        if balance['asset'] == 'USDT':
                            usdt_balance = float(balance['free'])
                        elif balance['asset'] == base_asset:
                            asset_balance = float(balance['free'])
                    
                    print(f"USDT余额: {usdt_balance:.2f}")
                    print(f"{base_asset}余额: {asset_balance:.2f}")
                    
                    required_quantity = float(self.quantity)
                    if asset_balance < required_quantity:
                        print(f"警告: {base_asset}余额不足 ({asset_balance:.2f} < {required_quantity:.2f})")
                        print("刷量策略可能会在卖出时失败")
                        print(f"需要使用USDT余额({usdt_balance:.2f})进行补齐")
                    else:
                        print(f"{base_asset}余额充足 ({asset_balance:.2f} >= {required_quantity:.2f})")
                else:
                    print("未能获取账户余额信息")
                
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
        """生成交易价格，更接近市场中心价提高成交率"""
        if bid_price >= ask_price:
            # 如果买卖价差很小或无价差，使用买一价格作为基准
            base_price = bid_price
        else:
            # 优化策略：更接近买一卖一的中心价格，提高成交率
            price_range = ask_price - bid_price
            # 改为在价格区间的45%-55%位置生成价格（接近中心）
            offset = random.uniform(0.45, 0.55)
            base_price = bid_price + (price_range * offset)
            
        print(f"价格优化: 买一={bid_price:.5f}, 卖一={ask_price:.5f}, 选择={base_price:.5f}")
        
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
                return result
            else:
                print(f"买入订单失败: 无返回结果")
                return None
                
        except Exception as e:
            print(f"买入订单错误: {e}")
            return None
    
    def check_order_status(self, order_id: int, max_retries: int = 3) -> Optional[str]:
        """检查订单状态 - 带重试机制"""
        for attempt in range(max_retries):
            try:
                result = self.client.get_order(self.symbol, order_id)
                if result:
                    return result.get('status')
                return None
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    if "SSL" in error_msg or "EOF" in error_msg or "Connection" in error_msg:
                        print(f"⚠️ 网络连接异常 (第{attempt+1}次尝试): {type(e).__name__}")
                        print(f"等待1秒后重试...")
                        time.sleep(1)
                        continue
                    else:
                        # 非网络错误，不重试
                        print(f"查询订单状态错误: {e}")
                        return None
                else:
                    # 最后一次尝试失败
                    print(f"❌ 查询订单状态最终失败 (已重试{max_retries}次): {type(e).__name__}")
                    print("💡 可能的原因: 网络不稳定、代理服务器问题或API服务异常")
                    return None
        
        return None
    
    def get_order_details(self, order_id: int, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """获取订单详细信息，包括执行数量"""
        for attempt in range(max_retries):
            try:
                result = self.client.get_order(self.symbol, order_id)
                if result:
                    return result
                return None
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    if "SSL" in error_msg or "EOF" in error_msg or "Connection" in error_msg:
                        print(f"⚠️ 获取订单详情网络异常 (第{attempt+1}次尝试): {type(e).__name__}")
                        print(f"等待1秒后重试...")
                        time.sleep(1)
                        continue
                    else:
                        # 非网络错误，不重试
                        print(f"获取订单详情错误: {e}")
                        return None
                else:
                    # 最后一次尝试失败
                    print(f"❌ 获取订单详情最终失败 (已重试{max_retries}次): {type(e).__name__}")
                    return None
        
        return None
    
    def get_asset_balance(self, max_retries: int = 3) -> float:
        """获取交易资产的当前余额 - 带重试机制"""
        for attempt in range(max_retries):
            try:
                base_asset = self.symbol.replace('USDT', '')  # 从SENTISUSDT获取SENTIS
                account_info = self.client.get_account_info()
                
                if account_info and 'balances' in account_info:
                    for balance in account_info['balances']:
                        if balance['asset'] == base_asset:
                            return float(balance['free'])
                return 0.0
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    if "SSL" in error_msg or "EOF" in error_msg or "Connection" in error_msg:
                        print(f"⚠️ 获取余额网络异常 (第{attempt+1}次尝试): {type(e).__name__}")
                        time.sleep(1)
                        continue
                    else:
                        self.log(f"获取余额失败: {e}", 'error')
                        return 0.0
                else:
                    print(f"❌ 获取余额最终失败 (已重试{max_retries}次): {type(e).__name__}")
                    self.log(f"获取余额失败: {e}", 'error')
                    return 0.0
        
        return 0.0
    
    def cancel_order(self, order_id: int, max_retries: int = 3) -> bool:
        """撤销订单 - 带重试机制"""
        for attempt in range(max_retries):
            try:
                result = self.client.cancel_order(symbol=self.symbol, order_id=order_id)
                return result is not None
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    if "SSL" in error_msg or "EOF" in error_msg or "Connection" in error_msg:
                        print(f"⚠️ 撤销订单网络异常 (第{attempt+1}次尝试): {type(e).__name__}")
                        time.sleep(1)
                        continue
                    else:
                        print(f"撤销订单错误: {e}")
                        return False
                else:
                    print(f"❌ 撤销订单最终失败 (已重试{max_retries}次): {type(e).__name__}")
                    return False
        
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
    
    def place_market_buy_order(self, quantity: float) -> Optional[Dict[str, Any]]:
        """下达市价买入订单"""
        try:
            if quantity <= 0:
                return None
            
            # 确保数量至少为1
            import math
            adjusted_quantity = max(1, math.floor(quantity))
            quantity_str = str(int(adjusted_quantity))
            
            # 使用专用的市价单客户端
            result = self.market_client.place_market_buy_order(self.symbol, quantity_str)
            
            if result:
                return result
            else:
                return "ORDER_VALUE_TOO_SMALL"
                
        except Exception as e:
            self.log(f"市价买入错误: {e}", 'error')
            return None
    
    def place_market_sell_order(self, quantity: float) -> Optional[Dict[str, Any]]:
        """下达市价卖出订单"""
        try:
            # 检查输入参数
            if quantity <= 0:
                self.log(f"❌ 无效数量: {quantity}", 'error')
                return None
            
            # 简化处理：去掉小数点，直接使用整数
            import math
            adjusted_quantity = math.floor(quantity)
            quantity_str = str(int(adjusted_quantity))
            
            self.log(f"市价卖出原始数量: {quantity:.6f}")
            self.log(f"市价卖出调整为整数: {quantity_str}")
            
            # 使用专用的市价单客户端
            result = self.market_client.place_market_sell_order(self.symbol, quantity_str)
            
            if result:
                self.log(f"✅ 市价卖出成功: ID {result.get('orderId')}")
                return result
            else:
                self.log("❌ 市价卖出失败: 无返回结果", 'error')
                # 返回特殊值表示订单价值不足错误
                return "ORDER_VALUE_TOO_SMALL"
                
        except Exception as e:
            self.log(f"❌ 市价卖出错误: {e}", 'error')
            return None
    
    def smart_buy_order(self, original_price: float, needed_quantity: float = None) -> bool:
        """市价买入补单 - 策略执行过程中的补货，直接补货不分批"""
        self.log("\\n--- 市价买入补单 ---")
        self.log(f"原始限价: {original_price:.5f} (仅供参考)")
        
        target_quantity = needed_quantity if needed_quantity else float(self.quantity)
        self.log(f"需要补单数量: {target_quantity:.2f}")
        
        # 检查订单价值是否满足最小限制
        estimated_value = target_quantity * original_price
        if estimated_value < 5.0:
            self.log(f"⚠️ 补单价值不足5 USDT (约{estimated_value:.2f} USDT)")
            self.log("💡 跳过补单，视为完成")
            return True  # 返回True以继续下一轮
        
        # 执行市价买入补单
        result = self.place_market_buy_order(target_quantity)
        
        if result == "ORDER_VALUE_TOO_SMALL":
            self.log("💡 订单价值不足5 USDT，跳过补单视为完成")
            return True  # 返回True以继续下一轮
        elif result and isinstance(result, dict):
            self.log(f"✅ 市价买入补单成功: ID {result.get('orderId')}")
            self.supplement_orders += 1  # 增加补单计数
            # 计算损耗（按原始价格估算）
            cost_diff = abs(target_quantity * original_price * 0.001)  # 假设0.1%的价格差
            self.total_cost_diff += cost_diff
            return True
        else:
            self.log("❌ 市价买入补单失败", 'error')
            return False
    
    def smart_sell_order(self, original_price: float, needed_quantity: float = None) -> bool:
        """市价卖出补单 - 策略执行过程中的补货，直接补货不分批"""
        self.log("\\n--- 市价卖出补单 ---")
        self.log(f"原始限价: {original_price:.5f} (仅供参考)")
        
        target_quantity = needed_quantity if needed_quantity else float(self.quantity)
        self.log(f"需要补单数量: {target_quantity:.2f}")
        
        # 检查订单价值是否满足最小限制
        estimated_value = target_quantity * original_price
        if estimated_value < 5.0:
            self.log(f"⚠️ 补单价值不足5 USDT (约{estimated_value:.2f} USDT)")
            self.log("💡 跳过补单，视为完成")
            return True  # 返回True以继续下一轮
        
        # 执行市价卖出补单
        result = self.place_market_sell_order(target_quantity)
        
        if result == "ORDER_VALUE_TOO_SMALL":
            self.log("💡 订单价值不足5 USDT，跳过补单视为完成")
            return True  # 返回True以继续下一轮
        elif result and isinstance(result, dict):
            self.log(f"✅ 市价卖出补单成功: ID {result.get('orderId')}")
            self.supplement_orders += 1  # 增加补单计数
            # 计算损耗（按原始价格估算）
            cost_diff = abs(target_quantity * original_price * 0.001)  # 假设0.1%的价格差
            self.total_cost_diff += cost_diff
            return True
        else:
            self.log("❌ 市价卖出补单失败", 'error')
            return False
    
    def ensure_balance_consistency(self, initial_balance: float, max_attempts: int = 5) -> bool:
        """确保账户余额与初始余额一致 - 持续补单直到平衡"""
        self.log("\\n=== 检查账户余额一致性 ===")
        self.log(f"初始余额: {initial_balance:.2f}")
        
        for attempt in range(1, max_attempts + 1):
            current_balance = self.get_asset_balance()
            balance_diff = current_balance - initial_balance
            
            self.log(f"第{attempt}次检查:")
            self.log(f"  当前余额: {current_balance:.2f}")
            self.log(f"  余额差异: {balance_diff:.2f}")
            
            # 允许较小的误差（0.1个币以内可忽略）
            if abs(balance_diff) <= 0.1:
                self.log(f"✅ 余额差异在可接受范围内: {balance_diff:.2f} (≤0.1)")
                self.log("✅ 余额一致性检查通过")
                return True
            
            # 余额不一致且超过0.1，需要补单
            if balance_diff > 0.1:
                # 余额增加了，说明买入多了，需要卖出
                sell_quantity = abs(balance_diff)
                self.log(f"余额增加 {balance_diff:.2f}，执行市价卖出补单")
                
                result = self.place_market_sell_order(sell_quantity)
                
                if result == "ORDER_VALUE_TOO_SMALL":
                    self.log("💡 平衡订单价值不足5 USDT，视为余额已平衡")
                    return True  # 直接视为成功
                elif result and isinstance(result, dict):
                    self.log(f"✅ 平衡卖出成功: {sell_quantity:.2f}")
                    time.sleep(1)  # 等待成交
                    continue
                else:
                    self.log("❌ 平衡卖出失败", 'error')
                    
            elif balance_diff < -0.1:
                # 余额减少了，说明卖出多了，需要买入
                buy_quantity = abs(balance_diff)
                self.log(f"余额减少 {abs(balance_diff):.2f}，执行市价买入补单")
                
                result = self.place_market_buy_order(buy_quantity)
                
                if result == "ORDER_VALUE_TOO_SMALL":
                    self.log("💡 平衡订单价值不足5 USDT，视为余额已平衡")
                    return True  # 直接视为成功
                elif result and isinstance(result, dict):
                    self.log(f"✅ 平衡买入成功: {buy_quantity:.2f}")
                    time.sleep(1)  # 等待成交
                    continue
                else:
                    self.log("❌ 平衡买入失败", 'error')
            
            # 如果达到这里，说明补单失败，等待一下再试
            if attempt < max_attempts:
                self.log(f"第{attempt}次平衡失败，等待3秒后重试...")
                time.sleep(3)
        
        # 最终检查
        final_balance = self.get_asset_balance()
        final_diff = final_balance - initial_balance
        
        if abs(final_diff) <= 0.1:
            self.log(f"✅ 最终余额差异在可接受范围内: {final_diff:.2f} (≤0.1)")
            self.log("✅ 最终余额检查通过")
            return True
        else:
            self.log(f"❌ 最终余额检查失败，差异: {final_diff:.2f} (>0.1)", 'error')
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
    
    def auto_purchase_if_insufficient(self) -> bool:
        """如果余额不足则自动补齐 - 按USDT价值分批买入"""
        try:
            current_balance = self.get_asset_balance()
            required_quantity = float(self.quantity)
            
            print(f"检查余额是否足够交易...")
            print(f"当前余额: {current_balance:.2f}")
            print(f"每轮需要: {required_quantity:.2f}")
            
            if current_balance >= required_quantity:
                print("✅ 余额充足，无需补齐")
                return True
            
            # 计算缺少的数量
            shortage = required_quantity - current_balance
            print(f"⚠️ 余额不足，缺少: {shortage:.2f}")
            
            # 检查USDT余额
            account_info = self.client.get_account_info()
            usdt_balance = 0.0
            if account_info and 'balances' in account_info:
                for balance in account_info['balances']:
                    if balance['asset'] == 'USDT':
                        usdt_balance = float(balance['free'])
                        break
            
            print(f"可用USDT余额: {usdt_balance:.2f}")
            
            # 获取当前价格
            book_data = self.get_order_book()
            if not book_data:
                print("❌ 无法获取市场价格")
                return False
            
            estimated_price = book_data['ask_price']
            total_usdt_needed = shortage * estimated_price
            
            # 详细调试信息
            print(f"=== 补齐计算详情 ===")
            print(f"需要补齐数量: {shortage:.2f}")
            print(f"当前市场价格 (ask): {estimated_price:.6f}")
            print(f"估算需要USDT: {total_usdt_needed:.2f}")
            print(f"可用USDT余额: {usdt_balance:.2f}")
            print(f"差额: {usdt_balance - total_usdt_needed:.2f}")
            
            if usdt_balance < total_usdt_needed:
                print(f"❌ USDT余额不足: {usdt_balance:.2f} < {total_usdt_needed:.2f}")
                print("💡 请检查:")
                print(f"  1. 交易数量是否过大: {shortage:.2f} 个")
                print(f"  2. 市场价格是否正常: {estimated_price:.6f}")
                print(f"  3. 账户USDT余额是否正确: {usdt_balance:.2f}")
                return False
            
            # 策略开始时分批买入，最大分10批
            max_batches = 10
            batch_usdt_value = min(45.0, total_usdt_needed / max_batches)  # 每批USDT等价，最大分10批
            batch_quantity = batch_usdt_value / estimated_price
            total_purchased = 0.0
            batch_count = 0
            
            print(f"开始分批补齐，最大{max_batches}批，每批约{batch_usdt_value:.1f} USDT等价 ({batch_quantity:.2f}个)")
            
            while shortage > 0 and total_purchased < required_quantity and batch_count < max_batches:
                # 计算本批买入数量
                current_batch = min(shortage, batch_quantity)
                
                # 如果数量小于1，使用5.1 USDT等价的最小数量
                if current_batch < 1:
                    min_quantity_for_5usdt = 5.1 / estimated_price
                    current_batch = max(1, min_quantity_for_5usdt)
                    print(f"数量不足1个，改为5.1 USDT等价数量: {current_batch:.2f}")
                
                result = self.place_market_buy_order(current_batch)
                
                if not result or result == "ORDER_VALUE_TOO_SMALL":
                    print(f"❌ 第{batch_count + 1}批失败")
                    # 如果常规批次失败，尝试最小5.1 USDT购买
                    if current_batch >= 1:
                        min_quantity_for_5usdt = 5.1 / estimated_price
                        print(f"尝试最小5.1 USDT购买: {min_quantity_for_5usdt:.2f}")
                        result = self.place_market_buy_order(min_quantity_for_5usdt)
                        if result and result != "ORDER_VALUE_TOO_SMALL":
                            batch_count += 1
                            total_purchased += min_quantity_for_5usdt
                            time.sleep(3)
                            new_balance = self.get_asset_balance()
                            print(f"第{batch_count}批(最小)完成，余额: {new_balance:.2f}")
                            shortage = required_quantity - new_balance
                            continue
                    break
                
                batch_count += 1
                total_purchased += current_batch
                
                # 等待成交并检查实际余额
                time.sleep(3)
                new_balance = self.get_asset_balance()
                actual_shortage = required_quantity - new_balance
                
                print(f"第{batch_count}批完成，余额: {new_balance:.2f}")
                
                # 如果余额已经足够，提前结束
                if actual_shortage <= 0:
                    print("✅ 余额已足够")
                    break
                
                shortage = actual_shortage
            
            # 最终检查
            final_balance = self.get_asset_balance()
            shortage_final = required_quantity - final_balance
            
            if shortage_final <= 0:
                print(f"✅ 补齐完成: {final_balance:.2f} >= {required_quantity:.2f}")
                self.auto_purchased = total_purchased
                return True
            elif shortage_final < 1:
                # 如果只差不到1个，视为足够（避免因为小数量无法交易而卡住）
                print(f"⚠️ 余额差异很小({shortage_final:.2f})，视为足够: {final_balance:.2f}")
                self.auto_purchased = total_purchased
                return True
            elif batch_count >= max_batches:
                # 如果已经达到最大批次，剩余数量直接一次性买入
                print(f"已完成{max_batches}批，剩余{shortage_final:.2f}个直接买入")
                final_result = self.place_market_buy_order(shortage_final)
                
                if final_result and final_result != "ORDER_VALUE_TOO_SMALL":
                    final_balance = self.get_asset_balance()
                    print(f"✅ 最终补齐完成: {final_balance:.2f}")
                    self.auto_purchased = total_purchased + shortage_final
                    return True
                else:
                    print(f"❌ 最终补齐失败")
                    return False
            else:
                print(f"❌ 补齐不完整: {final_balance:.2f} < {required_quantity:.2f}")
                return False
                
        except Exception as e:
            print(f"❌ 自动补齐失败: {e}")
            return False
    
    def restore_original_balance(self) -> bool:
        """恢复到原始余额 - 卖出所有自动购买的数量"""
        try:
            if self.auto_purchased <= 0:
                print("✅ 无需恢复余额，未进行自动购买")
                return True
            
            print(f"\n=== 恢复原始余额 ===")
            print(f"需要卖出自动购买的数量: {self.auto_purchased:.2f}")
            
            # 获取当前市场价格
            book_data = self.get_order_book()
            if not book_data:
                print("❌ 无法获取市场价格，跳过余额恢复")
                return False
            
            estimated_price = (book_data['bid_price'] + book_data['ask_price']) / 2
            estimated_value = self.auto_purchased * estimated_price
            
            print(f"估算卖出价格: {estimated_price:.5f}")
            print(f"估算卖出价值: {estimated_value:.2f} USDT")
            
            # 检查订单价值
            if estimated_value < 5.0:
                print(f"⚠️ 卖出价值不足5 USDT，跳过余额恢复")
                print("💡 保留微小余额差异")
                return True
            
            # 执行卖出恢复
            print("执行余额恢复卖出...")
            result = self.place_market_sell_order(self.auto_purchased)
            
            if result == "ORDER_VALUE_TOO_SMALL":
                print("💡 卖出价值不足，跳过恢复")
                return True
            elif result and isinstance(result, dict):
                print(f"✅ 余额恢复成功: ID {result.get('orderId')}")
                
                # 等待成交并检查最终余额
                time.sleep(2)
                final_balance = self.get_asset_balance()
                balance_diff = final_balance - self.original_balance
                
                print(f"原始余额: {self.original_balance:.2f}")
                print(f"最终余额: {final_balance:.2f}")
                print(f"余额差异: {balance_diff:+.2f}")
                
                if abs(balance_diff) <= 0.1:
                    print("✅ 余额恢复成功，与原始余额一致")
                    return True
                else:
                    print(f"⚠️ 余额恢复后仍有差异: {balance_diff:+.2f}")
                    return True  # 仍然认为成功，因为已经尽力了
            else:
                print("❌ 余额恢复失败")
                return False
                
        except Exception as e:
            print(f"❌ 余额恢复异常: {e}")
            return False
    
    def final_balance_reconciliation(self) -> bool:
        """最终余额校验和补单 - 确保策略前后余额完全一致"""
        try:
            print("检查策略执行前后的余额变化...")
            
            # 获取当前余额
            current_balance = self.get_asset_balance()
            balance_difference = current_balance - self.initial_balance
            
            print(f"初始余额: {self.initial_balance:.2f}")
            print(f"当前余额: {current_balance:.2f}")
            print(f"余额差异: {balance_difference:+.2f}")
            
            # 如果差异在容忍范围内，认为平衡
            if abs(balance_difference) <= 0.1:
                print("✅ 余额差异在可接受范围内 (±0.1)，无需补单")
                return True
            
            # 获取当前市场价格用于估算订单价值
            book_data = self.get_order_book()
            if not book_data:
                print("❌ 无法获取市场价格，跳过最终补单")
                return False
                
            estimated_price = (book_data['bid_price'] + book_data['ask_price']) / 2
            print(f"当前估算价格: {estimated_price:.5f}")
            
            # 根据余额差异决定补单方向
            if balance_difference > 0.1:
                # 余额增加了，说明买入多了，需要卖出
                sell_quantity = abs(balance_difference)
                estimated_value = sell_quantity * estimated_price
                
                print(f"💡 检测到余额增加 {balance_difference:.2f}，需要卖出补单")
                print(f"卖出数量: {sell_quantity:.2f}")
                print(f"估算订单价值: {estimated_value:.2f} USDT")
                
                if estimated_value < 5.0:
                    print(f"⚠️ 补单价值不足5 USDT，取消补单")
                    print("💡 微小余额差异，视为正常范围")
                    return True
                
                # 执行卖出补单
                print("执行最终卖出补单...")
                result = self.place_market_sell_order(sell_quantity)
                
                if result == "ORDER_VALUE_TOO_SMALL":
                    print("💡 补单价值不足，视为完成")
                    return True
                elif result and isinstance(result, dict):
                    print(f"✅ 最终卖出补单成功: ID {result.get('orderId')}")
                    self.supplement_orders += 1
                    
                    # 等待成交后再次检查
                    time.sleep(2)
                    new_balance = self.get_asset_balance()
                    final_diff = new_balance - self.initial_balance
                    print(f"补单后余额: {new_balance:.2f} (差异: {final_diff:+.2f})")
                    
                    return abs(final_diff) <= 0.1
                else:
                    print("❌ 最终卖出补单失败")
                    return False
                    
            elif balance_difference < -0.1:
                # 余额减少了，说明卖出多了，需要买入
                buy_quantity = abs(balance_difference)
                estimated_value = buy_quantity * estimated_price
                
                print(f"💡 检测到余额减少 {abs(balance_difference):.2f}，需要买入补单")
                print(f"买入数量: {buy_quantity:.2f}")
                print(f"估算订单价值: {estimated_value:.2f} USDT")
                
                if estimated_value < 5.0:
                    print(f"⚠️ 补单价值不足5 USDT，取消补单")
                    print("💡 微小余额差异，视为正常范围")
                    return True
                
                # 执行买入补单
                print("执行最终买入补单...")
                result = self.place_market_buy_order(buy_quantity)
                
                if result == "ORDER_VALUE_TOO_SMALL":
                    print("💡 补单价值不足，视为完成")
                    return True
                elif result and isinstance(result, dict):
                    print(f"✅ 最终买入补单成功: ID {result.get('orderId')}")
                    self.supplement_orders += 1
                    
                    # 等待成交后再次检查
                    time.sleep(2)
                    new_balance = self.get_asset_balance()
                    final_diff = new_balance - self.initial_balance
                    print(f"补单后余额: {new_balance:.2f} (差异: {final_diff:+.2f})")
                    
                    return abs(final_diff) <= 0.1
                else:
                    print("❌ 最终买入补单失败")
                    return False
                    
        except Exception as e:
            print(f"❌ 最终余额校验异常: {e}")
            return False
    
    def execute_round(self, round_num: int) -> bool:
        """执行一轮交易"""
        print(f"\n=== 第 {round_num}/{self.rounds} 轮交易 ===")
        self.log(f"开始执行第 {round_num} 轮交易", 'info')
        
        # 初始化本轮状态
        round_completed = False
        
        try:
            # 使用策略开始时记录的初始余额作为基准
            initial_balance = self.initial_balance
            
            # 强制日志：关键检查点
            self.log(f"=== 第{round_num}轮: 开始获取订单薄 ===", 'info')
            
            # 1. 获取当前订单薄
            book_data = self.get_order_book()
            if not book_data:
                self.log("无法获取订单薄，跳过本轮", 'error')
                return False
            
            self.log(f"=== 第{round_num}轮: 订单薄获取成功，开始生成价格 ===", 'info')
            
            # 2. 生成交易价格（偏向高价提高命中率）
            trade_price = self.generate_trade_price(
                book_data['bid_price'],  # 买一价格
                book_data['ask_price']   # 卖一价格
            )
            
            # 强制日志：价格生成完成
            self.log(f"=== 第{round_num}轮: 价格生成完成 {trade_price:.5f}, 开始下单 ===", 'info')
            
            # 3. 有序快速执行：先发起卖出，立即发起买入
            print(f"有序提交订单: {self.quantity} {self.symbol} @ {trade_price:.5f}")
            
            import threading
            import time
            
            print("执行顺序: 卖出 -> 买入 (250毫秒延迟)")
            start_time = time.time()
            
            # 强制日志：即将下单
            self.log(f"=== 第{round_num}轮: 即将提交双向订单 ===", 'info')
            
            # 用于存储订单结果的变量
            sell_order = None
            buy_order = None
            sell_exception = None
            buy_exception = None
            
            # 最优方案：使用异步HTTP请求减少延迟
            try:
                # 使用线程池，50ms延迟
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    # 立即提交卖出任务
                    sell_future = executor.submit(self.place_sell_order, trade_price)
                    
                    # 优化延迟为250ms，给订单更好的匹配时间
                    time.sleep(0.25)  # 250ms延迟
                    buy_future = executor.submit(self.place_buy_order, trade_price)
                    
                    # 并行等待结果
                    try:
                        sell_order = sell_future.result(timeout=10)
                        buy_order = buy_future.result(timeout=10)
                    except Exception as result_e:
                        # 如果获取结果失败，等待一下再检查
                        print(f"获取并行结果异常: {result_e}")
                        print("等待额外时间确保订单完全处理...")
                        time.sleep(3)
                        
                        # 重新尝试获取结果，无论future是否done都尝试获取
                        sell_order = None
                        buy_order = None
                        
                        # 尝试获取卖出订单结果
                        try:
                            sell_order = sell_future.result(timeout=2)
                            print(f"✅ 延迟获取到卖出订单结果")
                        except Exception as e:
                            print(f"延迟获取卖出订单结果失败: {e}")
                            sell_order = None
                        
                        # 尝试获取买入订单结果
                        try:
                            buy_order = buy_future.result(timeout=2)
                            print(f"✅ 延迟获取到买入订单结果")
                        except Exception as e:
                            print(f"延迟获取买入订单结果失败: {e}")
                            buy_order = None
                        
                        print(f"最终订单状态: 卖出={bool(sell_order)}, 买入={bool(buy_order)}")
                        
                        # 重要：即使获取结果失败，订单可能已经成功提交
                        # 不要立即跳过，让后续的状态检查逻辑来判断实际情况
                        if not sell_order and not buy_order:
                            print("⚠️ 无法获取订单结果，但继续检查订单状态")
                            # 创建临时订单对象以便后续状态检查
                            sell_order = {'orderId': 'unknown_sell'}
                            buy_order = {'orderId': 'unknown_buy'}
                        
            except Exception as e:
                print(f"执行异常: {e}")
                print("并行执行失败，跳过本轮")
                return False
            
            end_time = time.time()
            print(f"有序下单耗时: {(end_time - start_time)*1000:.0f}毫秒")
            
            # 强制日志：下单完成
            self.log(f"=== 第{round_num}轮: 双向下单完成，开始检查结果 ===", 'info')
            
            # 4. 检查异常和订单提交结果
            if sell_exception:
                print(f"❌ 卖出订单异常: {sell_exception}")
            if buy_exception:
                print(f"❌ 买入订单异常: {buy_exception}")
            
            # 确保订单对象存在
            if not sell_order or not buy_order:
                print("❌ 无法获取订单结果，本轮交易失败")
                return False
            
            # 5. 获取订单ID
            sell_order_id = sell_order.get('orderId')
            buy_order_id = buy_order.get('orderId')
            
            # 处理未知订单ID的情况
            has_unknown_orders = (sell_order_id == 'unknown_sell' or buy_order_id == 'unknown_buy')
            
            if has_unknown_orders:
                print("⚠️ 检测到未知订单ID，改为通过余额变化判断交易结果")
                print("等待5秒后检查余额变化...")
                time.sleep(5)
                
                # 通过余额变化判断交易是否成功
                current_balance = self.get_asset_balance()
                balance_change = current_balance - initial_balance
                
                print(f"余额变化检测: 初始={initial_balance:.2f}, 当前={current_balance:.2f}, 变化={balance_change:.2f}")
                
                # 如果余额没有显著变化，说明交易可能未成功
                if abs(balance_change) <= 0.01:
                    print("💡 余额无显著变化，可能订单未成交或获取结果超时")
                    print("跳过本轮，让订单自然处理")
                    return False
                else:
                    print(f"💡 检测到余额变化，执行余额平衡补单")
                    # 直接进行余额平衡
                    balance_ok = self.ensure_balance_consistency(initial_balance)
                    return balance_ok
            else:
                print(f"✅ 订单提交成功 - 卖出:{sell_order_id} 买入:{buy_order_id}")
            
            # 强制日志：开始状态检查
            self.log(f"=== 第{round_num}轮: 开始检查订单状态 ===", 'info')
            
            # 6. 等待300毫秒后检查订单成交状态（仅当有有效订单ID时）
            time.sleep(self.buy_timeout)  # 等待300毫秒
            
            # 检查买入和卖出订单状态
            buy_status = self.check_order_status(buy_order_id)
            sell_status = self.check_order_status(sell_order_id)
            
            # 强制日志：状态检查完成
            self.log(f"=== 第{round_num}轮: 状态检查完成 买入:{buy_status} 卖出:{sell_status} ===", 'info')
            
            # 获取详细订单信息以查看执行数量
            buy_details = self.get_order_details(buy_order_id)
            sell_details = self.get_order_details(sell_order_id)
            
            # 分析订单执行情况
            buy_filled = buy_status == 'FILLED'
            sell_filled = sell_status == 'FILLED'
            buy_partially = buy_status == 'PARTIALLY_FILLED'
            sell_partially = sell_status == 'PARTIALLY_FILLED'
            
            print(f"订单状态检查: 买入={buy_status}, 卖出={sell_status}")
            
            # 显示执行数量信息
            if buy_details:
                buy_executed = float(buy_details.get('executedQty', 0))
                buy_original = float(buy_details.get('origQty', 0))
                print(f"买入执行情况: {buy_executed}/{buy_original}")
            else:
                buy_executed = 0
                buy_original = float(self.quantity)
                
            if sell_details:
                sell_executed = float(sell_details.get('executedQty', 0))
                sell_original = float(sell_details.get('origQty', 0))
                print(f"卖出执行情况: {sell_executed}/{sell_original}")
            else:
                sell_executed = 0
                sell_original = float(self.quantity)
            
            # 7. 根据成交情况处理
            need_balance_check = False
            
            if buy_filled and sell_filled:
                print("✅ 买卖订单都已成交，无需补单，直接进入下一轮")
                # 买卖都成交，理论上余额平衡，无需检查
                round_completed = True
                self.completed_rounds += 1
                print(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易双向成交完成", 'info')
                return True
                
            elif sell_filled and (not buy_filled or buy_partially):
                # 卖出完全成交，买入未成交或部分成交
                if buy_partially:
                    print(f"❌ 卖出已成交，买入部分成交 ({buy_executed}/{buy_original}) - 取消买单，补足剩余数量")
                    remaining_buy = buy_original - buy_executed
                else:
                    print("❌ 卖出已成交，买入未成交 - 先取消未成交买单，再市价买入补回")
                    remaining_buy = buy_original
                
                # 1. 取消未成交或部分成交的买入订单
                print(f"取消买入订单: {buy_order_id}")
                cancel_success = self.cancel_order(buy_order_id)
                if cancel_success:
                    print("✅ 买入订单取消成功")
                else:
                    print("⚠️ 买入订单取消失败，可能已成交或已取消")
                
                # 2. 等待一下确保取消生效
                time.sleep(0.5)
                
                # 3. 执行市价买入补单 - 精确补足剩余数量
                print(f"需要补买: {remaining_buy:.2f}")
                success = self.smart_buy_order(trade_price, remaining_buy)
                if not success:
                    print("❌ 市价买入补单失败")
                    return False
                print("✅ 买入补单完成，数量已平衡")
                # 统计完成的轮次
                round_completed = True
                self.completed_rounds += 1
                print(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易通过买入补单完成", 'info')
                return True
                
            elif buy_filled and (not sell_filled or sell_partially):
                # 买入完全成交，卖出未成交或部分成交
                if sell_partially:
                    print(f"❌ 买入已成交，卖出部分成交 ({sell_executed}/{sell_original}) - 取消卖单，补足剩余数量")
                    remaining_sell = sell_original - sell_executed
                else:
                    print("❌ 买入已成交，卖出未成交 - 先取消未成交卖单，再市价卖出处理")
                    remaining_sell = sell_original
                
                # 1. 取消未成交或部分成交的卖出订单
                print(f"取消卖出订单: {sell_order_id}")
                cancel_success = self.cancel_order(sell_order_id)
                if cancel_success:
                    print("✅ 卖出订单取消成功")
                else:
                    print("⚠️ 卖出订单取消失败，可能已成交或已取消")
                
                # 2. 等待一下确保取消生效
                time.sleep(0.5)
                
                # 3. 执行市价卖出补单 - 精确补足剩余数量
                print(f"需要补卖: {remaining_sell:.2f}")
                success = self.smart_sell_order(trade_price, remaining_sell)
                if not success:
                    print("❌ 市价卖出补单失败")
                    return False
                print("✅ 卖出补单完成，数量已平衡")
                # 统计完成的轮次
                round_completed = True
                self.completed_rounds += 1
                print(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易通过卖出补单完成", 'info')
                return True
                
            elif buy_partially and sell_partially:
                # 都是部分成交的情况
                print(f"⚠️ 买卖都部分成交 - 买入: {buy_executed}/{buy_original}, 卖出: {sell_executed}/{sell_original}")
                
                remaining_buy = buy_original - buy_executed
                remaining_sell = sell_original - sell_executed
                
                # 取消两个部分成交的订单
                print("取消两个部分成交的订单...")
                self.cancel_order(buy_order_id)
                self.cancel_order(sell_order_id)
                time.sleep(0.5)
                
                # 补足剩余数量
                if remaining_buy > 0:
                    print(f"补买剩余数量: {remaining_buy:.2f}")
                    self.smart_buy_order(trade_price, remaining_buy)
                
                if remaining_sell > 0:
                    print(f"补卖剩余数量: {remaining_sell:.2f}")
                    self.smart_sell_order(trade_price, remaining_sell)
                
                print("✅ 部分成交补单完成")
                # 统计完成的轮次
                round_completed = True
                self.completed_rounds += 1
                print(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易通过部分成交补单完成", 'info')
                return True
                
            else:
                print("❌ 买卖订单都未成交或无法获取订单状态")
                
                # 如果无法获取订单状态，通过余额对比判断实际情况
                if buy_status is None or sell_status is None:
                    print("⚠️ 无法获取订单状态，使用余额对比判断")
                    current_balance = self.get_asset_balance()
                    balance_change = current_balance - initial_balance
                    
                    print(f"余额变化: {balance_change:.2f}")
                    
                    if abs(balance_change) <= 0.1:
                        print("💡 余额无显著变化，可能订单都未成交")
                        # 取消所有订单
                        self.cancel_order(buy_order_id)
                        self.cancel_order(sell_order_id)
                        print("ℹ️ 已尝试取消所有订单，本轮结束")
                        return False
                    elif balance_change > 0.1:
                        print("💡 余额增加，可能有买入成交，执行卖出补单")
                        success = self.smart_sell_order(trade_price, abs(balance_change))
                        if success:
                            round_completed = True
                            self.completed_rounds += 1
                            print(f"✅ 第 {round_num} 轮交易完成")
                            self.log(f"第 {round_num} 轮交易通过余额判断卖出补单完成", 'info')
                        return success
                    elif balance_change < -0.1:
                        print("💡 余额减少，可能有卖出成交，执行买入补单")
                        success = self.smart_buy_order(trade_price, abs(balance_change))
                        if success:
                            round_completed = True
                            self.completed_rounds += 1
                            print(f"✅ 第 {round_num} 轮交易完成")
                            self.log(f"第 {round_num} 轮交易通过余额判断买入补单完成", 'info')
                        return success
                else:
                    # 正常情况：都未成交，取消所有订单
                    print("取消所有未成交订单")
                    self.cancel_order(buy_order_id)
                    self.cancel_order(sell_order_id)
                    time.sleep(1)
                    print("ℹ️ 所有未成交订单已取消，本轮结束")
                    return False
                
            # 这里不应该到达，但如果到达了就标记为完成
            if not round_completed:
                round_completed = True
                self.completed_rounds += 1
                print(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易成功完成", 'info')
            return True
            
        except Exception as e:
            print(f"交易轮次错误: {e}")
            self.log(f"第 {round_num} 轮交易出现异常: {e}", 'error')
            return False
        
        finally:
            # 确保每一轮都有日志输出，便于调试
            if not round_completed:
                self.log(f"第 {round_num} 轮交易结束 (未完成)", 'warning')
    
    def run(self) -> bool:
        """运行策略"""
        print(f"\n开始执行刷量策略...")
        
        if not self.connect():
            print("无法连接交易所，策略终止")
            return False
        
        # 获取原始余额并记录
        self.original_balance = self.get_asset_balance()
        print(f"原始余额: {self.original_balance:.2f}")
        
        # 检查余额并自动补齐
        if not self.auto_purchase_if_insufficient():
            print("❌ 余额补齐失败，无法执行策略")
            return False
        
        # 重新获取余额作为循环期间的基准
        self.initial_balance = self.get_asset_balance()
        print(f"策略执行基准余额: {self.initial_balance:.2f}")
        
        if self.auto_purchased > 0:
            print(f"📝 已自动购买 {self.auto_purchased:.2f}，策略结束后将自动卖出恢复原始余额")
        
        print(f"✅ 余额检查通过，开始执行 {self.rounds} 轮交易")
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
            
            # 执行最终余额校验和补单
            print(f"\n=== 执行最终余额校验 ===")
            final_success = self.final_balance_reconciliation()
            
            # 恢复到原始余额
            restore_success = self.restore_original_balance()
            
            print(f"\n=== 策略执行完成 ===")
            print(f"完成轮次: {self.completed_rounds}/{self.rounds}")
            print(f"成功率: {(self.completed_rounds/self.rounds*100):.1f}%")
            print(f"补单次数: {self.supplement_orders}")
            print(f"估算损耗: {self.total_cost_diff:.4f} USDT")
            
            if self.auto_purchased > 0:
                print(f"自动购买数量: {self.auto_purchased:.2f} ({'✅ 已恢复' if restore_success else '❌ 恢复失败'})")
            
            final_balance = self.get_asset_balance()
            original_change = final_balance - self.original_balance
            execution_change = final_balance - self.initial_balance
            
            print(f"原始余额: {self.original_balance:.2f}")
            print(f"执行基准余额: {self.initial_balance:.2f}")
            print(f"最终余额: {final_balance:.2f}")
            print(f"与原始余额差异: {original_change:+.2f}")
            print(f"与执行基准差异: {execution_change:+.2f}")
            print(f"余额校验: {'✅ 通过' if final_success else '⚠️ 存在差异'}")
            print(f"余额恢复: {'✅ 成功' if restore_success else '⚠️ 未完全恢复'}")
            
            return self.completed_rounds > 0
            
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


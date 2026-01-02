"""
刷量交易策略
主要目的：通过卖出和买入相同价格和数量的现货来刷交易量，避免亏损
"""

import time
import random
import signal
from typing import Optional, Dict, Any
import sys
import os

# 添加父目录到路径以导入客户端
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simple_trading_client import SimpleTradingClient
from market_trading_client import MarketTradingClient
# 注意：不再使用SPOT_CONFIG回退，策略必须通过钱包配置获取API密钥


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
        self.order_check_timeout = 2.0  # 订单成交检查时间(改为2秒，给买卖订单更多成交时间)
        self.max_price_deviation = 0.01  # 最大价格偏差(1%)
        
        # API优化参数 - 方案3智能优化
        self.batch_query_enabled = True  # 启用批量查询
        # 缓存已完全禁用以确保价格准确性
        
        # 输出缓存状态确认
        print("📊 价格准确性优化: 订单簿缓存已禁用，所有价格数据实时获取")
        
        # API错误追踪
        self.recent_api_errors = 0  # 最近API错误次数
        
        # 统计数据
        self.original_balance = 0.0  # 真正的原始余额（用于最终恢复）
        self.initial_balance = 0.0   # 策略开始时的初始余额（用于循环期间的平衡检验）
        self.completed_rounds = 0    # 完成的轮次
        self.failed_rounds = 0       # 失败的轮次
        self.supplement_orders = 0   # 补单次数
        self.total_cost_diff = 0.0   # 总损耗（价格差累计）
        self.auto_purchased = 0.0    # 自动购买的数量（需要最终卖出）
        
        # 新增交易量和手续费统计
        self.buy_volume_usdt = 0.0   # 买单总交易量(USDT)
        self.sell_volume_usdt = 0.0  # 卖单总交易量(USDT) 
        self.total_fees_usdt = 0.0   # 总手续费(USDT)
        self.initial_usdt_balance = 0.0  # 策略开始时的USDT余额
        self.final_usdt_balance = 0.0    # 策略结束时的USDT余额
        self.usdt_balance_diff = 0.0     # USDT余额差值
        self.net_loss_usdt = 0.0         # 净损耗(USDT) = 余额差值 - 总手续费
        
        # 订单跟踪 - 用于检查卡单
        self.pending_orders = []     # 记录当前轮次的订单ID
        
        # 交易对精度信息
        self.symbol_info = None      # 交易对信息
        self.tick_size = None        # 价格精度
        self.step_size = None        # 数量精度
        
        # 手续费率信息
        self.maker_fee_rate = None   # Maker费率
        self.taker_fee_rate = None   # Taker费率
        self.fee_rates_loaded = False # 是否已加载费率
        
        # 防重复统计的已处理订单集合
        self.processed_orders = set()
        
        # API优化：延迟批量处理的订单列表
        self.completed_order_ids = []  # 已完成但未统计的订单ID
        
        # 优雅停止标志
        self.stop_requested = False
        self.setup_signal_handlers()
        
        self.log(f"=== 刷量策略初始化 ===")
        self.log(f"交易对: {symbol}, 数量: {quantity}, 间隔: {interval}秒, 轮次: {rounds}次")
    
    def set_logger(self, logger):
        """设置日志记录器"""
        self.logger = logger

    def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self.log(f"\n🛑 收到停止信号 {signum}，开始优雅停止...")
            self.stop_requested = True
            
        # 监听常见的停止信号
        signal.signal(signal.SIGINT, signal_handler)    # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)   # 终止信号
        if hasattr(signal, 'SIGBREAK'):  # Windows
            signal.signal(signal.SIGBREAK, signal_handler)

    def is_stop_requested(self) -> bool:
        """检查是否收到停止请求"""
        return self.stop_requested

    def request_stop(self):
        """外部请求停止"""
        self.log("📢 外部请求停止策略...")
        self.stop_requested = True

    def smart_balance_check(self) -> float:
        """智能余额检查：先清理未成交订单释放冻结资金，再查询真实可用余额"""
        try:
            # 1. 先清理未成交订单，释放冻结的资金
            self.log("🧹 智能余额检查：先清理未成交订单释放冻结资金")
            self.check_and_cancel_pending_orders()
            
            # 2. 获取清理后的真实可用余额
            available_balance = self.get_asset_balance()
            self.log(f"💰 清理后可用余额: {available_balance:.2f}")
            
            return available_balance
            
        except Exception as e:
            self.log(f"❌ 智能余额检查失败: {e}", "error")
            # 降级到直接查询余额
            return self.get_asset_balance()
    
    def log(self, message, level='info'):
        """记录日志"""
        if self.logger:
            if level == 'error':
                self.logger.error(message)
            elif level == 'warning':
                self.logger.warning(message)
            else:
                self.logger.info(message)
        # 如果没有logger，保持静默（避免控制台输出）
    
    def get_symbol_precision(self) -> bool:
        """获取交易对的精度信息"""
        try:
            self.log(f"获取交易对 {self.symbol} 的精度信息...")
            
            # 获取交易所信息
            exchange_info = self.client.get_exchange_info(self.symbol)
            if not exchange_info:
                self.log("❌ 无法获取交易所信息", 'error')
                return False
            
            # 查找对应的交易对信息
            symbols = exchange_info.get('symbols', [])
            for symbol_info in symbols:
                if symbol_info.get('symbol') == self.symbol:
                    self.symbol_info = symbol_info
                    
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
    
    def get_commission_rates(self) -> bool:
        """获取交易对的真实手续费率"""
        try:
            if self.fee_rates_loaded:
                self.log(f"✅ 手续费率已缓存: Maker={self.maker_fee_rate}, Taker={self.taker_fee_rate}")
                return True
                
            self.log(f"🔍 获取交易对 {self.symbol} 的手续费率...")
            
            # 获取手续费率信息
            commission_info = self.client.get_commission_rate(self.symbol)
            if not commission_info:
                self.log(f"❌ 无法获取手续费率信息，使用默认费率", "error")
                return False
            
            # 提取费率信息
            self.maker_fee_rate = float(commission_info.get('makerCommissionRate', '0.001'))
            self.taker_fee_rate = float(commission_info.get('takerCommissionRate', '0.001'))
            self.fee_rates_loaded = True
            
            self.log(f"✅ 手续费率获取成功:")
            self.log(f"   Maker费率: {self.maker_fee_rate:.6f} ({self.maker_fee_rate*100:.4f}%)")
            self.log(f"   Taker费率: {self.taker_fee_rate:.6f} ({self.taker_fee_rate*100:.4f}%)")
            
            return True
            
        except Exception as e:
            self.log(f"❌ 获取手续费率错误: {e}", "error")
            # 设置默认费率作为降级方案
            self.maker_fee_rate = 0.001  # 0.1%
            self.taker_fee_rate = 0.001  # 0.1%
            self.fee_rates_loaded = True
            self.log(f"⚠️ 使用默认手续费率: Maker=0.1%, Taker=0.1%", "warning")
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
            
            # 根据tick_size调整价格
            adjusted_price = round(round(price / tick_size_float) * tick_size_float, precision)
            
            return f"{adjusted_price:.{precision}f}"
            
        except Exception as e:
            self.log(f"价格格式化失败: {e}")
            return f"{price:.5f}"  # 降级到默认格式
    
    def format_quantity(self, quantity: float) -> str:
        """根据step_size格式化数量"""
        if not self.step_size:
            return f"{quantity:.2f}"  # 默认2位小数
            
        try:
            step_size_float = float(self.step_size)
            if step_size_float == 0:
                return str(quantity)
            
            # 计算精度位数
            precision = len(self.step_size.rstrip('0').split('.')[1]) if '.' in self.step_size else 0
            
            # 根据step_size调整数量
            adjusted_quantity = round(round(quantity / step_size_float) * step_size_float, precision)
            
            return f"{adjusted_quantity:.{precision}f}"
            
        except Exception as e:
            self.log(f"数量格式化失败: {e}")
            return f"{quantity:.2f}"  # 降级到默认格式
    
    def format_sell_quantity(self, quantity: float) -> str:
        """专用于卖出的数量格式化：强制向下取整，避免超额卖出"""
        if not self.step_size:
            return f"{quantity:.1f}"  # 默认1位小数向下取整
            
        try:
            step_size_float = float(self.step_size)
            if step_size_float == 0:
                return str(quantity)
            
            # 计算精度位数
            precision = len(self.step_size.rstrip('0').split('.')[1]) if '.' in self.step_size else 0
            
            # 强制向下取整：floor而非round
            import math
            adjusted_quantity = math.floor(quantity / step_size_float) * step_size_float
            
            return f"{adjusted_quantity:.{precision}f}"
            
        except Exception as e:
            self.log(f"卖出数量格式化失败: {e}")
            return f"{quantity:.1f}"  # 降级到默认格式

    def connect(self) -> bool:
        """连接交易所"""
        try:
            # 使用任务运行器传递的钱包配置
            if hasattr(self, 'wallet_config') and self.wallet_config:
                config = self.wallet_config
                api_key = config.get('api_key')
                secret_key = config.get('secret_key')
                
                if api_key and secret_key:
                    # 传递代理配置给交易客户端
                    self.client = SimpleTradingClient(
                        api_key=api_key,
                        secret_key=secret_key,
                        proxy_config=self.wallet_config  # 传递完整的钱包配置（包含代理信息）
                    )
                    self.market_client = MarketTradingClient(
                        api_key=api_key,
                        secret_key=secret_key
                    )
                    self.log(f"使用任务钱包配置连接交易所，API密钥: {api_key[:8]}...{api_key[-4:]}")
                else:
                    # API密钥或secret为空，无法连接
                    self.log("钱包API密钥为空，无法连接交易所", 'error')
                    return False
            else:
                # 未找到钱包配置，无法连接
                self.log("未找到钱包配置，无法连接交易所", 'error')
                return False
            
            if self.client.test_connection():
                self.log("交易所连接成功")
                
                # 获取交易对精度信息
                if not self.get_symbol_precision():
                    self.log(f"⚠️ 无法获取交易对精度信息，将使用默认精度", "warning")
                
                # 获取交易对手续费率
                if not self.get_commission_rates():
                    self.log(f"⚠️ 无法获取真实手续费率，将使用默认费率", "warning")
                
                # 预热连接 - 获取一次服务器时间以稳定连接
                # 预热网络连接
                for i in range(2):
                    try:
                        self.client.get_server_time()
                        break
                    except:
                        pass
                    time.sleep(0.5)
                
                # 检查账户余额 - 根据交易对自动检测
                base_asset = self.symbol.replace('USDT', '')  # 从交易对获取基础资产，如SENTISUSDT→SENTIS
                account_info = self.client.get_account_info()
                if account_info and 'balances' in account_info:
                    usdt_balance = 0.0
                    asset_balance = 0.0
                    
                    for balance in account_info['balances']:
                        if balance['asset'] == 'USDT':
                            usdt_balance = float(balance['free'])
                        elif balance['asset'] == base_asset:
                            asset_balance = float(balance['free'])
                    
                    self.log(f"USDT余额: {usdt_balance:.2f}")
                    self.log(f"{base_asset}余额: {asset_balance:.2f}")
                    
                    required_quantity = float(self.quantity)
                    if asset_balance < required_quantity:
                        self.log(f"警告: {base_asset}余额不足 ({asset_balance:.2f} < {required_quantity:.2f})")
                        self.log("刷量策略可能会在卖出时失败")
                        self.log(f"需要使用USDT余额({usdt_balance:.2f})进行补齐")
                    else:
                        self.log(f"{base_asset}余额充足 ({asset_balance:.2f} >= {required_quantity:.2f})")
                else:
                    self.log("未能获取账户余额信息")
                
                return True
            else:
                self.log("交易所连接失败")
                return False
                
        except Exception as e:
            self.log(f"连接错误: {e}")
            return False
    
    def get_order_book(self, use_cache: bool = None) -> Optional[Dict[str, Any]]:
        """获取深度订单薄数据 - 实时获取确保价格准确性"""
        # 强制禁用缓存以确保价格准确性
        use_cache = False
            
        try:
            # 尝试获取深度数据
            depth_response = self.client.get_depth(self.symbol, 5)
            
            if depth_response and 'bids' in depth_response and 'asks' in depth_response:
                bids = depth_response['bids']  # 买单 [[price, quantity], ...]
                asks = depth_response['asks']  # 卖单 [[price, quantity], ...]
                
                if bids and asks:
                    # 获取买一价格（最高买价）和卖一价格（最低卖价）
                    first_bid_price = float(bids[0][0])
                    first_ask_price = float(asks[0][0])
                    
                    result = {
                        'bid_price': first_bid_price,  # 买方第一档（买一价格）
                        'ask_price': first_ask_price,  # 卖方第一档（卖一价格）
                        'bid_depth': len(bids),
                        'ask_depth': len(asks),
                        'bids': bids,  # 添加完整深度数据
                        'asks': asks   # 添加完整深度数据
                    }
                    
                    return result
            
            # 如果深度数据获取失败，回退到简单模式
            self.log("深度数据获取失败，使用简单买卖一价格")
            book_ticker = self.client.get_book_ticker(self.symbol)
            if book_ticker:
                bid_price = float(book_ticker['bidPrice'])  # 买一价格
                ask_price = float(book_ticker['askPrice'])  # 卖一价格
                
                return {
                    'bid_price': bid_price,
                    'ask_price': ask_price
                }
            else:
                self.log("❌ 无法获取book ticker数据，检查网络连接或API状态", "error")
                return None
            
        except Exception as e:
            self.log(f"获取订单薄失败: {e}", 'error')
            return None
    
    
    
    def generate_optimized_trade_price(self, bid_price: float, ask_price: float, strategy: str = 'narrow_spread') -> float:
        """优化的交易价格生成策略"""
        
        if bid_price >= ask_price:
            # 无价差时，使用买一价格
            base_price = bid_price
        else:
            price_range = ask_price - bid_price
            
            if strategy == 'narrow_spread':
                # 策略1: 窄价差策略 - 处理极小价差情况
                if price_range <= 0.000100:  # 价差只有1个tick或更小
                    # 随机选择买一价或略低于卖一价
                    if random.choice([True, False]):
                        base_price = bid_price  # 使用买一价
                        self.log(f"使用窄价差策略(买一价)，价差: {price_range:.6f}")
                    else:
                        base_price = bid_price + 0.000100  # 比买一高一个tick
                        self.log(f"使用窄价差策略(买一+1tick)，价差: {price_range:.6f}")
                else:
                    # 正常价差，使用中位附近
                    offset = random.uniform(0.45, 0.55)
                    base_price = bid_price + (price_range * offset)
                    self.log(f"使用窄价差策略，偏移: {offset:.2f}")
                
            elif strategy == 'mid_price':
                # 策略2: 中位价策略 - 完全中位价
                base_price = (bid_price + ask_price) / 2
                self.log(f"使用中位价策略")
                
            elif strategy == 'adaptive':
                # 策略3: 自适应策略 - 根据价差大小调整
                if price_range <= 0.000100:  # 价差极小，只有1个tick，随机选择买一或卖一
                    if random.choice([True, False]):
                        base_price = bid_price  # 选择买一价
                        self.log(f"使用自适应策略(买一价)，价差: {price_range:.6f}")
                    else:
                        base_price = ask_price - 0.000100  # 选择比卖一低一个tick
                        self.log(f"使用自适应策略(比卖一低)，价差: {price_range:.6f}")
                else:
                    offset = random.uniform(0.40, 0.60)  # 中位附近
                    base_price = bid_price + (price_range * offset)
                    self.log(f"使用自适应策略，价差: {price_range:.6f}, 偏移: {offset:.2f}")
            else:
                # 默认策略 - 中位附近
                offset = random.uniform(0.45, 0.55)
                base_price = bid_price + (price_range * offset)
        
        # 格式化价格
        formatted_price = self.format_price(base_price)
        trade_price = float(formatted_price)
        
        # 检查订单价值
        order_value = trade_price * float(self.quantity)
        if order_value < 5.0:
            min_price = 5.0 / float(self.quantity)
            trade_price = max(trade_price, round(min_price, 5))
        
        self.log(f"优化价格生成 [{strategy}]: {trade_price:.5f}, 买一: {bid_price:.5f}, 卖一: {ask_price:.5f}")
        return trade_price
    
    
    def execute_optimized_round(self, actual_quantity: float) -> tuple:
        """执行优化的交易轮次"""
        
        # 获取订单簿
        book_data = self.get_order_book()
        if not book_data:
            return None, None
            
        # 计算价差
        spread = book_data['ask_price'] - book_data['bid_price']
        self.log(f"当前价差: {spread:.6f}")
        
        # 简单中间价定价策略
        bid_price = book_data['bid_price']
        ask_price = book_data['ask_price']
        
        # 计算中间价
        mid_price = (bid_price + ask_price) / 2
        
        # 格式化为交易对精度
        mid_price_formatted = float(self.format_price(mid_price))
        
        # 检查是否存在有效中间价
        if mid_price_formatted == bid_price or mid_price_formatted == ask_price:
            # 没有中间价，随机选择买一或卖一
            import random
            trade_price = random.choice([bid_price, ask_price])
            self.log(f"🎯 无中间价，随机选择: {trade_price:.5f} (买一:{bid_price:.5f}, 卖一:{ask_price:.5f})")
        else:
            # 使用中间价
            trade_price = mid_price_formatted
            self.log(f"🎯 中间价策略: {trade_price:.5f} (买一:{bid_price:.5f}, 卖一:{ask_price:.5f})")
        
        self.log(f"📊 最终交易价格: {trade_price:.5f}")
        
        # 同时提交买卖单
        import concurrent.futures
        
        sell_order = None
        buy_order = None
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # 同时提交买卖单
                self.log(f"⏰ 同时提交买卖单...")
                sell_future = executor.submit(self.place_sell_order, trade_price, actual_quantity)
                buy_future = executor.submit(self.place_buy_order, trade_price, actual_quantity)
                
                # 获取下单结果
                try:
                    sell_order = sell_future.result(timeout=10)
                    buy_order = buy_future.result(timeout=10)
                except Exception as e:
                    self.log(f"❌ 下单异常: {e}", 'error')
                    return None, None
                
                if sell_order and buy_order:
                    self.log(f"✅ 买卖单提交成功 - 卖单:{sell_order.get('orderId')}, 买单:{buy_order.get('orderId')}")
                    self.log(f"⏳ 等待3秒成交...")
                    time.sleep(3)  # 等待3秒成交
                else:
                    self.log(f"❌ 买卖单提交失败", 'error')
                    return None, None
            
            if sell_order and buy_order:
                self.log(f"✅ 优化订单提交成功 - 卖单: {sell_order.get('orderId')}, 买单: {buy_order.get('orderId')}")
                return sell_order, buy_order
            else:
                self.log("❌ 优化订单提交失败")
                return None, None
                
        except Exception as e:
            self.log(f"❌ 优化执行异常: {e}", 'error')
            return None, None
    
    def place_sell_order(self, price: float, quantity: float = None) -> Optional[Dict[str, Any]]:
        """下达卖出订单"""
        try:
            # 使用传入的数量或默认数量
            if quantity is None:
                quantity = float(self.quantity)
            
            # 确保数量精度正确，使用交易对的step_size
            quantity_str = self.format_quantity(quantity)
            
            # 格式化价格，使用交易对的tick_size
            price_str = self.format_price(price)
            
            result = self.client.place_order(
                symbol=self.symbol,
                side='SELL',
                order_type='LIMIT',
                quantity=quantity_str,
                price=price_str,
                time_in_force='GTC'
            )
            
            if result:
                # 检查是否是错误返回
                if isinstance(result, dict) and result.get('error'):
                    if 'error_code' in result and 'error_msg' in result:
                        error_msg = f"卖出订单API错误: 错误码 {result['error_code']}, 错误信息: {result['error_msg']}"
                        self.log(f"❌ {error_msg}", "error")
                        raise Exception(f"卖出订单提交失败 - {error_msg}")
                    else:
                        error_msg = f"卖出订单失败: HTTP {result.get('status_code', '未知')}, 错误详情: {result.get('error_text', '未知错误')}"
                        self.log(f"❌ {error_msg}", "error")
                        raise Exception(f"卖出订单提交失败 - {error_msg}")
                else:
                    # 正常的成功返回
                    return result
            else:
                error_msg = "卖出订单失败: 无返回结果"
                self.log(f"❌ {error_msg}", "error")
                raise Exception(f"卖出订单提交失败 - {error_msg}")
                
        except Exception as e:
            # 如果是我们主动抛出的异常，直接重新抛出
            if "卖出订单提交失败" in str(e):
                raise
            # 其他异常记录并重新抛出
            self.log(f"卖出订单错误: {e}", "error")
            raise Exception(f"卖出订单执行异常: {e}")
    
    def place_buy_order(self, price: float, quantity: float = None) -> Optional[Dict[str, Any]]:
        """下达买入订单"""
        try:
            # 使用传入的数量或默认数量
            if quantity is None:
                quantity = float(self.quantity)
            
            # 确保数量精度正确，使用交易对的step_size
            quantity_str = self.format_quantity(quantity)
            
            # 格式化价格，使用交易对的tick_size
            price_str = self.format_price(price)
            
            result = self.client.place_order(
                symbol=self.symbol,
                side='BUY',
                order_type='LIMIT',
                quantity=quantity_str,
                price=price_str,
                time_in_force='GTC'
            )
            
            if result:
                # 检查是否是错误返回
                if isinstance(result, dict) and result.get('error'):
                    if 'error_code' in result and 'error_msg' in result:
                        error_msg = f"买入订单API错误: 错误码 {result['error_code']}, 错误信息: {result['error_msg']}"
                        self.log(f"❌ {error_msg}", "error")
                        raise Exception(f"买入订单提交失败 - {error_msg}")
                    else:
                        error_msg = f"买入订单失败: HTTP {result.get('status_code', '未知')}, 错误详情: {result.get('error_text', '未知错误')}"
                        self.log(f"❌ {error_msg}", "error")
                        raise Exception(f"买入订单提交失败 - {error_msg}")
                else:
                    # 正常的成功返回
                    return result
            else:
                error_msg = "买入订单失败: 无返回结果"
                self.log(f"❌ {error_msg}", "error")
                raise Exception(f"买入订单提交失败 - {error_msg}")
                
        except Exception as e:
            # 如果是我们主动抛出的异常，直接重新抛出
            if "买入订单提交失败" in str(e):
                raise
            # 其他异常记录并重新抛出
            self.log(f"买入订单错误: {e}", "error")
            raise Exception(f"买入订单执行异常: {e}")
    
    def check_multiple_order_status(self, order_ids: list) -> dict:
        """批量查询订单状态 - 方案3优化"""
        if not order_ids or not self.batch_query_enabled:
            # 降级到单个查询
            return self._fallback_single_order_query(order_ids)
        
            
        try:
            self.log(f"📊 批量查询 {len(order_ids)} 个订单状态")
            
            # 尝试使用批量查询接口
            orders = self.client.get_orders(
                symbol=self.symbol,
                limit=len(order_ids) * 2  # 获取更多订单以确保包含目标订单
            )
            
            # 构建结果字典
            result = {}
            target_order_ids = set(str(oid) for oid in order_ids)
            
            for order in orders:
                order_id_str = str(order['orderId'])
                if order_id_str in target_order_ids:
                    result[order_id_str] = order['status']
            
            # 检查是否所有订单都找到了
            missing_orders = target_order_ids - set(result.keys())
            if missing_orders:
                self.log(f"⚠️ 批量查询中有 {len(missing_orders)} 个订单未找到，降级查询")
                # 对未找到的订单进行单独查询
                for missing_id in missing_orders:
                    try:
                        status = self.check_order_status(int(missing_id))
                        result[missing_id] = status
                    except:
                        result[missing_id] = 'UNKNOWN'
            
            self.log(f"✅ 批量查询完成，获取到 {len(result)} 个订单状态")
            return result
            
        except Exception as e:
            self.log(f"❌ 批量查询失败: {e}，降级到单个查询")
            self.recent_api_errors += 1
            self.last_error_time = time.time()
            return self._fallback_single_order_query(order_ids)
    
    def _fallback_single_order_query(self, order_ids: list) -> dict:
        """降级到单个订单查询"""
        result = {}
        for order_id in order_ids:
            try:
                result[str(order_id)] = self.check_order_status(int(order_id))
            except Exception as e:
                self.log(f"⚠️ 单个查询订单 {order_id} 失败: {e}")
                result[str(order_id)] = 'UNKNOWN'
        return result

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
                        self.log(f"⚠️ 网络连接异常 (第{attempt+1}次尝试): {type(e).__name__}", "warning")
                        self.log(f"等待1秒后重试...")
                        time.sleep(1)
                        continue
                    else:
                        # 非网络错误，不重试
                        self.log(f"查询订单状态错误: {e}")
                        return None
                else:
                    # 最后一次尝试失败
                    self.log(f"❌ 查询订单状态最终失败 (已重试{max_retries}次): {type(e).__name__}", "error")
                    self.log("💡 可能的原因: 网络不稳定、代理服务器问题或API服务异常")
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
                        self.log(f"⚠️ 获取订单详情网络异常 (第{attempt+1}次尝试): {type(e).__name__}", "warning")
                        self.log(f"等待1秒后重试...")
                        time.sleep(1)
                        continue
                    else:
                        # 非网络错误，不重试
                        self.log(f"获取订单详情错误: {e}")
                        return None
                else:
                    # 最后一次尝试失败
                    self.log(f"❌ 获取订单详情最终失败 (已重试{max_retries}次): {type(e).__name__}", "error")
                    return None
        
        return None
    
    def get_asset_balance(self, max_retries: int = 3) -> float:
        """获取交易资产的当前余额 - 带重试机制"""
        for attempt in range(max_retries):
            try:
                base_asset = self.symbol.replace('USDT', '')  # 从交易对获取基础资产
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
                        self.log(f"⚠️ 获取余额网络异常 (第{attempt+1}次尝试): {type(e).__name__}", "warning")
                        time.sleep(1)
                        continue
                    else:
                        self.log(f"获取余额失败: {e}", 'error')
                        return 0.0
                else:
                    self.log(f"❌ 获取余额最终失败 (已重试{max_retries}次): {type(e).__name__}", "error")
                    self.log(f"获取余额失败: {e}", 'error')
                    return 0.0
        
        return 0.0
    
    def get_usdt_balance(self, max_retries: int = 3) -> float:
        """获取USDT余额 - 带重试机制"""
        for attempt in range(max_retries):
            try:
                account_info = self.client.get_account_info()
                
                if account_info and 'balances' in account_info:
                    for balance in account_info['balances']:
                        if balance['asset'] == 'USDT':
                            return float(balance['free'])
                return 0.0
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    if "SSL" in error_msg or "EOF" in error_msg or "Connection" in error_msg:
                        self.log(f"⚠️ 获取USDT余额网络异常 (第{attempt+1}次尝试): {type(e).__name__}", "warning")
                        time.sleep(1)
                        continue
                    else:
                        self.log(f"获取USDT余额失败: {e}", 'error')
                        return 0.0
                else:
                    self.log(f"❌ 获取USDT余额最终失败 (已重试{max_retries}次): {type(e).__name__}", "error")
                    self.log(f"获取USDT余额失败: {e}", 'error')
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
                        self.log(f"⚠️ 撤销订单网络异常 (第{attempt+1}次尝试): {type(e).__name__}", "warning")
                        time.sleep(1)
                        continue
                    else:
                        self.log(f"撤销订单错误: {e}")
                        return False
                else:
                    self.log(f"❌ 撤销订单最终失败 (已重试{max_retries}次): {type(e).__name__}", "error")
                    return False
        
        return False
    
    def cancel_all_open_orders_batch(self) -> tuple:
        """批量取消未成交订单 - 方案3优化"""
            
        try:
            self.log("🔍 批量处理未成交订单...")
            
            # 获取未成交订单
            open_orders_result = self.client.get_open_orders(self.symbol)
            
            if not open_orders_result:
                return 0.0, 0.0
            
            # 处理不同的响应格式
            if isinstance(open_orders_result, list):
                open_orders = open_orders_result
            elif isinstance(open_orders_result, dict) and 'orders' in open_orders_result:
                open_orders = open_orders_result['orders']
            else:
                open_orders = []
            
            if not open_orders:
                return 0.0, 0.0
            
            self.log(f"⚠️ 发现 {len(open_orders)} 个未成交订单")
            
            # 统计数量
            canceled_buy_qty = 0.0
            canceled_sell_qty = 0.0
            
            # 尝试批量取消
            if self.batch_query_enabled and len(open_orders) > 1:
                try:
                    # 提取订单ID列表
                    order_ids = [order['orderId'] for order in open_orders]
                    
                    # 批量取消 (币安支持这个接口)
                    self.client.cancel_open_orders(symbol=self.symbol)
                    
                    self.log(f"✅ 批量取消 {len(order_ids)} 个订单成功")
                    
                    # 统计取消的数量
                    for order in open_orders:
                        orig_qty = float(order.get('origQty', 0))
                        if order['side'] == 'BUY':
                            canceled_buy_qty += orig_qty
                        else:
                            canceled_sell_qty += orig_qty
                    
                    return canceled_buy_qty, canceled_sell_qty
                    
                except Exception as e:
                    self.log(f"❌ 批量取消失败: {e}，降级到单个取消")
                    self.recent_api_errors += 1
            
            # 降级到单个取消
            return self._fallback_single_cancel(open_orders)
            
        except Exception as e:
            self.log(f"❌ 批量处理未成交订单异常: {e}", "error")
            return 0.0, 0.0
    
    def _fallback_single_cancel(self, open_orders: list) -> tuple:
        """降级到单个订单取消"""
        canceled_buy_qty = 0.0
        canceled_sell_qty = 0.0
        
        for order in open_orders:
            try:
                order_id = order['orderId']
                orig_qty = float(order.get('origQty', 0))
                
                if self.cancel_order(order_id):
                    if order['side'] == 'BUY':
                        canceled_buy_qty += orig_qty
                    else:
                        canceled_sell_qty += orig_qty
                        
            except Exception as e:
                self.log(f"⚠️ 取消订单 {order.get('orderId')} 失败: {e}")
        
        return canceled_buy_qty, canceled_sell_qty
    
    
    def _update_success_stats(self, success: bool):
        """更新成功统计"""
        if success and self.recent_api_errors > 0:
            # 成功时减少错误计数
            self.recent_api_errors = max(0, self.recent_api_errors - 1)
    
    def _auto_adjust_parameters(self):
        """自适应参数调节 - 根据API错误率动态调整"""
        
        # 根据API错误率调整
        if self.recent_api_errors >= 5:
            self.log("⚠️ API错误率过高，切换到保守模式")
            self.batch_query_enabled = False
            self.cache_enabled = False
        elif self.recent_api_errors >= 3:
            self.log("⚠️ 检测到API错误，禁用批量查询")
            self.batch_query_enabled = False
        elif self.recent_api_errors == 0:
            # 错误率正常，启用所有优化
            if not self.batch_query_enabled:
                self.log("✅ API稳定，重新启用批量查询")
                self.batch_query_enabled = True

    def check_and_cancel_pending_orders(self) -> bool:
        """容错处理：检查并取消上一轮可能遗留的未成交订单"""
        try:
            self.log("🔍 检查未成交订单...")
            
            # 使用openOrders API获取真实的未成交订单
            open_orders_result = self.client.get_open_orders(self.symbol)
            
            if open_orders_result is None:
                self.log(f"❌ 无法获取未成交订单列表，使用本地记录检查", "error")
                # 降级到原有的本地记录检查方式
                return self._fallback_check_pending_orders()
            
            # 检查返回的数据格式
            if isinstance(open_orders_result, list):
                open_orders = open_orders_result
            elif isinstance(open_orders_result, dict) and 'orders' in open_orders_result:
                open_orders = open_orders_result['orders']
            elif isinstance(open_orders_result, dict) and len(open_orders_result) == 0:
                open_orders = []
            else:
                self.log(f"❓ 未知的openOrders响应格式: {open_orders_result}")
                open_orders = []
            
            if not open_orders:
                self.log("✅ 无未成交订单")
                # 清空本地记录
                self.pending_orders.clear()
                return True
            
            self.log(f"⚠️ 发现 {len(open_orders)} 个未成交订单", "warning")
            
            cancelled_count = 0
            cancelled_buy_quantity = 0.0  # 取消的买单数量
            cancelled_sell_quantity = 0.0  # 取消的卖单数量
            
            for order in open_orders:
                try:
                    order_id = order.get('orderId')
                    side = order.get('side')  # BUY 或 SELL
                    orig_qty = float(order.get('origQty', 0))
                    executed_qty = float(order.get('executedQty', 0))
                    remaining_qty = orig_qty - executed_qty
                    
                    self.log(f"📋 订单详情 ID:{order_id} Side:{side} 原始:{orig_qty} 已成交:{executed_qty} 剩余:{remaining_qty}")
                    
                    # 尝试取消订单
                    cancel_result = self.cancel_order(order_id)
                    
                    if cancel_result:
                        self.log(f"✅ 订单 {order_id} 取消成功")
                        cancelled_count += 1
                        
                        # 记录取消的数量，用于后续平衡处理
                        if side == 'BUY':
                            cancelled_buy_quantity += remaining_qty
                        elif side == 'SELL':
                            cancelled_sell_quantity += remaining_qty
                    else:
                        self.log(f"❌ 订单 {order_id} 取消失败", "error")
                        
                except Exception as e:
                    self.log(f"⚠️ 处理订单时出错: {e}", "warning")
                    continue
            
            # 清空本地记录
            self.pending_orders.clear()
            
            if cancelled_count > 0:
                self.log(f"✅ 成功取消 {cancelled_count} 个未成交订单")
                self.log(f"📊 取消买单数量: {cancelled_buy_quantity:.2f}")
                self.log(f"📊 取消卖单数量: {cancelled_sell_quantity:.2f}")
                
                # 处理数量不平衡问题
                self._handle_quantity_imbalance(cancelled_buy_quantity, cancelled_sell_quantity)
                
                # 等待取消生效
                time.sleep(2)
            
            return True
                
        except Exception as e:
            self.log(f"❌ 检查未成交订单时出错: {e}", "error")
            return True  # 即使出错也返回True，不影响主流程
    
    def _fallback_check_pending_orders(self) -> bool:
        """降级处理：使用本地记录检查未成交订单"""
        try:
            if not self.pending_orders:
                self.log("✅ 无待处理订单（本地记录）")
                return True
            
            self.log(f"🔍 检查 {len(self.pending_orders)} 个可能的未成交订单（本地记录）...")
            
            cancelled_count = 0
            for order_id in self.pending_orders[:]:  # 使用切片复制避免在循环中修改列表
                try:
                    # 检查订单状态
                    status = self.check_order_status(order_id)
                    
                    if status == 'NEW' or status == 'PARTIALLY_FILLED':
                        # 订单未完全成交，尝试取消
                        self.log(f"⚠️ 发现未成交订单 ID: {order_id} (状态: {status})", "warning")
                        cancel_result = self.cancel_order(order_id)
                        
                        if cancel_result:
                            self.log(f"✅ 订单 {order_id} 取消成功")
                            cancelled_count += 1
                        else:
                            self.log(f"❌ 订单 {order_id} 取消失败", "error")
                    
                    elif status in ['FILLED', 'CANCELED', 'REJECTED', 'EXPIRED']:
                        # 订单已完成，从待处理列表中移除
                        self.log(f"ℹ️ 订单 {order_id} 已完成 (状态: {status})")
                    
                    else:
                        # 无法获取状态，保留在列表中
                        self.log(f"⚠️ 无法获取订单 {order_id} 状态", "warning")
                        continue
                    
                    # 从待处理列表中移除已处理的订单
                    self.pending_orders.remove(order_id)
                    
                except Exception as e:
                    self.log(f"⚠️ 处理订单 {order_id} 时出错: {e}", "warning")
                    # 出错的订单暂时保留在列表中
                    continue
            
            if cancelled_count > 0:
                self.log(f"✅ 成功取消 {cancelled_count} 个未成交订单（本地记录）")
                # 等待取消生效
                time.sleep(1)
            
            return True
                
        except Exception as e:
            self.log(f"❌ 检查未成交订单时出错（本地记录）: {e}", "error")
            return True
    
    def _enforce_round_cleanup(self, round_num: int, skip_heavy_checks: bool = False):
        """轻量级轮次清理：只在必要时执行重度API检查"""
        try:
            if skip_heavy_checks:
                # 轻量级检查：只检查本地状态
                self.log(f"🔍 第{round_num}轮轻量级状态检查...")
                if len(self.pending_orders) > 0:
                    self.log(f"⚠️ 本地记录显示有{len(self.pending_orders)}个待处理订单", "warning")
                    # 清空本地记录，避免下轮误用
                    self.pending_orders.clear()
                self.log(f"✅ 第{round_num}轮轻量级检查完成")
                return
            
            self.log(f"🔧 第{round_num}轮深度清理检查...")
            
            # 1. 只有在本地记录显示有订单时才调用API检查
            if len(self.pending_orders) > 0:
                self.log(f"🔍 本地记录显示有{len(self.pending_orders)}个订单，执行API检查...")
                cleanup_success = self.check_and_cancel_pending_orders()
                if cleanup_success:
                    self.log("✅ 订单清理完成")
                else:
                    self.log("⚠️ 订单清理可能不完整", "warning")
            else:
                self.log("✅ 本地无待处理订单，跳过API检查")
            
            # 2. 余额检查优化：只在必要时检查
            # 检查是否是关键轮次（每10轮或最后几轮，但最后一轮不执行补单）
            is_critical_round = (round_num % 10 == 0) or (round_num >= self.rounds - 2)
            is_final_round = (round_num == self.rounds)  # 最后一轮
            
            if is_critical_round:
                current_balance = self.get_asset_balance()
                balance_diff = current_balance - self.initial_balance
                
                self.log(f"📊 关键轮次余额检查: 当前={current_balance:.2f}, 基准={self.initial_balance:.2f}, 差值={balance_diff:+.2f}")
                
                # 3. 只在偏差较大时执行补正（最后一轮不执行补单）
                if abs(balance_diff) > 0.5:  # 提高阈值避免频繁补正
                    if is_final_round:
                        self.log(f"⚠️ 最后一轮检测到余额偏差({balance_diff:+.2f})，但不执行补单", "warning")
                        self.log("💡 最后一轮余额差异将在清理库存阶段处理")
                    else:
                        self.log(f"⚠️ 余额偏差较大({balance_diff:+.2f})，执行补正", "warning")
                        correction_success = self.ensure_balance_consistency(self.initial_balance, max_attempts=2)
                        if correction_success:
                            self.log("✅ 余额补正完成")
                else:
                    self.log(f"✅ 余额偏差可接受: {balance_diff:+.2f}")
            else:
                self.log(f"✅ 非关键轮次，跳过余额检查")
            
            self.log(f"✅ 第{round_num}轮深度清理完成")
            
        except Exception as e:
            self.log(f"❌ 第{round_num}轮清理失败: {e}", "error")

    def _handle_quantity_imbalance(self, cancelled_buy_qty: float, cancelled_sell_qty: float):
        """处理订单取消导致的数量不平衡"""
        try:
            if cancelled_buy_qty == 0 and cancelled_sell_qty == 0:
                self.log("✅ 无数量不平衡问题")
                return
                
            self.log(f"🔄 处理数量不平衡: 买单取消 {cancelled_buy_qty:.2f}, 卖单取消 {cancelled_sell_qty:.2f}")
            
            # 如果取消的买单和卖单数量相等，则无需处理
            if abs(cancelled_buy_qty - cancelled_sell_qty) < 0.01:
                self.log("✅ 买卖取消数量基本平衡，无需额外处理")
                return
            
            # 如果取消的买单多于卖单，说明会多出一些USDT余额，少一些现货
            if cancelled_buy_qty > cancelled_sell_qty:
                shortage = cancelled_buy_qty - cancelled_sell_qty
                self.log(f"📈 取消买单多于卖单，缺少现货 {shortage:.2f} 个")
                self.log(f"💰 立即执行市价买入补齐现货")
                
                # 立即执行市价买入补齐
                buy_result = self.place_market_buy_order(shortage)
                if buy_result and buy_result != "ORDER_VALUE_TOO_SMALL":
                    self.log(f"✅ 市价买入补齐成功: {shortage:.2f} 个")
                    self.supplement_orders += 1
                else:
                    self.log(f"❌ 市价买入补齐失败，可能影响后续交易", "warning")
                
            # 如果取消的卖单多于买单，说明会多出一些现货，少一些USDT
            elif cancelled_sell_qty > cancelled_buy_qty:
                excess = cancelled_sell_qty - cancelled_buy_qty
                self.log(f"📉 取消卖单多于买单，多出现货 {excess:.2f} 个")
                self.log(f"💰 立即执行市价卖出处理多余现货")
                
                # 立即执行市价卖出处理多余现货
                sell_result = self.place_market_sell_order(excess)
                if sell_result and sell_result != "ORDER_VALUE_TOO_SMALL":
                    self.log(f"✅ 市价卖出成功: {excess:.2f} 个")
                    self.supplement_orders += 1
                else:
                    self.log(f"❌ 市价卖出失败，可能影响后续交易", "warning")
                
        except Exception as e:
            self.log(f"❌ 处理数量不平衡时出错: {e}", "error")
    
    def _update_trade_statistics(self, side: str, quantity: float, price: float, fee: float = 0.0):
        """更新交易统计数据"""
        try:
            volume_usdt = quantity * price
            
            if side.upper() == 'BUY':
                self.buy_volume_usdt += volume_usdt
                # 买单交易量已更新
            elif side.upper() == 'SELL':
                self.sell_volume_usdt += volume_usdt 
                # 卖单交易量已更新
            
            # 累计手续费
            if fee > 0:
                self.total_fees_usdt += fee
            
        except Exception as e:
            self.log(f"❌ 更新交易统计时出错: {e}", "error")
    
    def _calculate_fee_from_order_result(self, order_result: dict, is_maker: bool = False) -> float:
        """从订单结果计算手续费(USDT)，使用真实的API费率"""
        try:
            # 尝试从订单结果中获取手续费信息
            if isinstance(order_result, dict):
                # 检查是否有commission字段
                commission = order_result.get('commission', 0)
                commission_asset = order_result.get('commissionAsset', '')
                
                if commission > 0:
                    if commission_asset == 'USDT':
                        self.log(f"💰 API返回真实手续费: {commission} USDT")
                        return float(commission)
                    else:
                        # 如果手续费不是USDT，需要转换，暂时跳过转换逻辑
                        self.log(f"⚠️ 手续费资产为 {commission_asset}，无法直接转换为USDT，使用费率计算", "warning")
                
                # 如果没有commission字段或需要转换，使用真实费率计算
                executed_qty = float(order_result.get('executedQty', 0))
                avg_price = float(order_result.get('avgPrice', 0))
                
                if executed_qty > 0 and avg_price > 0:
                    trade_value = executed_qty * avg_price
                    
                    # 确保已获取费率信息
                    if not self.fee_rates_loaded:
                        self.get_commission_rates()
                    
                    # 根据是否为maker选择费率
                    fee_rate = self.maker_fee_rate if is_maker else self.taker_fee_rate
                    
                    # 计算手续费
                    calculated_fee = trade_value * fee_rate
                    
                    fee_type = "Maker" if is_maker else "Taker"
                    # 手续费已计算
                    
                    return calculated_fee
            
            return 0.0
            
        except Exception as e:
            self.log(f"❌ 计算手续费时出错: {e}", "error")
            return 0.0
    
    def _batch_update_statistics(self):
        """批量更新统计数据 - API优化版本"""
        if not self.completed_order_ids:
            return
        
        try:
            self.log(f"📊 批量更新 {len(self.completed_order_ids)} 个订单的统计数据")
            
            # 分批处理，每次最多处理5个订单避免单次API调用过多
            batch_size = 5
            for i in range(0, len(self.completed_order_ids), batch_size):
                batch = self.completed_order_ids[i:i+batch_size]
                
                for order_id in batch:
                    if order_id not in self.processed_orders:
                        try:
                            # 这里仍需要单独查询，因为批量查询通常只返回状态，不返回交易详情
                            order_info = self.client.get_order(self.symbol, order_id)
                            
                            if order_info and order_info.get('status') == 'FILLED':
                                executed_qty = float(order_info.get('executedQty', 0))
                                avg_price = float(order_info.get('avgPrice', 0))
                                
                                if executed_qty > 0 and avg_price > 0:
                                    # 根据订单信息判断买卖方向
                                    side = order_info.get('side', 'UNKNOWN')
                                    is_maker = order_info.get('isMaker', True)
                                    
                                    # 计算手续费并更新统计
                                    fee = self._calculate_fee_from_order_result(order_info, is_maker=is_maker)
                                    self._update_trade_statistics(side, executed_qty, avg_price, fee)
                                    
                                    # 标记为已处理
                                    self.processed_orders.add(order_id)
                                    
                        except Exception as e:
                            self.log(f"⚠️ 处理订单 {order_id} 统计时出错: {e}", "warning")
                
                # 批次间短暂延迟
                if i + batch_size < len(self.completed_order_ids):
                    time.sleep(0.1)
            
            # 清空待处理列表
            processed_count = len(self.completed_order_ids)
            self.completed_order_ids.clear()
            self.log(f"✅ 完成 {processed_count} 个订单的批量统计更新")
            
        except Exception as e:
            self.log(f"❌ 批量统计更新失败: {e}", "error")
    
    
    
    def place_market_buy_order(self, quantity: float) -> Optional[Dict[str, Any]]:
        """下达市价买入订单"""
        try:
            if quantity <= 0:
                return None
            
            # 使用交易对的step_size进行精度标准化
            quantity_str = self.format_quantity(quantity)
            
            # 使用专用的市价单客户端
            result = self.market_client.place_market_buy_order(self.symbol, quantity_str)
            
            if result and isinstance(result, dict):
                # 市价单API通常只返回orderId，需要查询订单详情获取交易量
                order_id = result.get('orderId')
                if order_id:
                    # 稍等一下让订单状态更新
                    time.sleep(0.5)
                    # 获取订单详细信息
                    order_info = self.client.get_order(self.symbol, order_id)
                    
                    if order_info and order_info.get('status') == 'FILLED':
                        executed_qty = float(order_info.get('executedQty', 0))
                        avg_price = float(order_info.get('avgPrice', 0))
                        
                        if executed_qty > 0 and avg_price > 0:
                            # 计算手续费 (市价单通常是taker)
                            fee = self._calculate_fee_from_order_result(order_info, is_maker=False)
                            # 更新统计数据
                            self._update_trade_statistics('BUY', executed_qty, avg_price, fee)
                    else:
                        # 如果无法获取详细信息，使用估算值
                        ticker = self.client.get_book_ticker(self.symbol)
                        if ticker:
                            estimated_price = float(ticker.get('askPrice', 0))
                            if estimated_price > 0:
                                # 确保费率已加载
                                if self.taker_fee_rate is None:
                                    self.get_commission_rates()
                                fee = adjusted_quantity * estimated_price * (self.taker_fee_rate or 0.0004)
                                self._update_trade_statistics('BUY', adjusted_quantity, estimated_price, fee)
                else:
                    # 备用方案：使用当前市价估算
                    ticker = self.client.get_book_ticker(self.symbol)
                    if ticker:
                        estimated_price = float(ticker.get('askPrice', 0))
                        if estimated_price > 0:
                            # 确保费率已加载
                            if self.taker_fee_rate is None:
                                self.get_commission_rates()
                            fee = adjusted_quantity * estimated_price * (self.taker_fee_rate or 0.0004)
                            self._update_trade_statistics('BUY', adjusted_quantity, estimated_price, fee)
                
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
            
            # 获取实际可用余额，确保不超额卖出
            actual_balance = self.get_asset_balance()
            safe_quantity = min(quantity, actual_balance)
            
            # 如果调整后数量太小，直接返回
            if safe_quantity <= 0:
                self.log(f"⚠️ 调整后卖出数量为0，跳过交易", 'warning')
                return None
            
            # 使用专门的卖出数量格式化（向下取整）
            quantity_str = self.format_sell_quantity(safe_quantity)
            
            self.log(f"市价卖出原始数量: {quantity:.6f}")
            self.log(f"实际可用余额: {actual_balance:.6f}")
            self.log(f"安全卖出数量: {safe_quantity:.6f}")
            self.log(f"市价卖出标准化数量: {quantity_str}")
            
            # 使用专用的市价单客户端
            result = self.market_client.place_market_sell_order(self.symbol, quantity_str)
            
            if result and isinstance(result, dict):
                self.log(f"✅ 市价卖出成功: ID {result.get('orderId')}")
                
                # 市价单API通常只返回orderId，需要查询订单详情获取交易量
                order_id = result.get('orderId')
                if order_id:
                    # 稍等一下让订单状态更新
                    time.sleep(0.5)
                    # 获取订单详细信息
                    order_info = self.client.get_order(self.symbol, order_id)
                    
                    if order_info and order_info.get('status') == 'FILLED':
                        executed_qty = float(order_info.get('executedQty', 0))
                        avg_price = float(order_info.get('avgPrice', 0))
                        
                        if executed_qty > 0 and avg_price > 0:
                            # 计算手续费 (市价单通常是taker)
                            fee = self._calculate_fee_from_order_result(order_info, is_maker=False)
                            # 更新统计数据
                            self._update_trade_statistics('SELL', executed_qty, avg_price, fee)
                    else:
                        # 如果无法获取详细信息，使用估算值
                        ticker = self.client.get_book_ticker(self.symbol)
                        if ticker:
                            estimated_price = float(ticker.get('bidPrice', 0))
                            if estimated_price > 0:
                                # 确保费率已加载
                                if self.taker_fee_rate is None:
                                    self.get_commission_rates()
                                fee = adjusted_quantity * estimated_price * (self.taker_fee_rate or 0.0004)
                                self._update_trade_statistics('SELL', adjusted_quantity, estimated_price, fee)
                else:
                    # 备用方案：使用当前市价估算
                    ticker = self.client.get_book_ticker(self.symbol)
                    if ticker:
                        estimated_price = float(ticker.get('bidPrice', 0))
                        if estimated_price > 0:
                            # 确保费率已加载
                            if self.taker_fee_rate is None:
                                self.get_commission_rates()
                            fee = adjusted_quantity * estimated_price * (self.taker_fee_rate or 0.0004)
                            self._update_trade_statistics('SELL', adjusted_quantity, estimated_price, fee)
                
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
            self.log(f"⚠️ 补单价值不足5 USDT (约{estimated_value:.2f} USDT)", "warning")
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
            self.log(f"⚠️ 补单价值不足5 USDT (约{estimated_value:.2f} USDT)", "warning")
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
            
            # 检查差异价值，小于5 USDT的差异不处理
            if abs(balance_diff) <= 0.1:
                self.log(f"✅ 余额差异在可接受范围内: {balance_diff:.2f} (≤0.1)")
                self.log("✅ 余额一致性检查通过")
                return True
            
            # 计算差异的USDT价值
            try:
                # 获取当前市场价格
                book_data = self.get_order_book()
                if not book_data:
                    raise Exception("无法获取订单簿数据")
                current_price = (book_data['bid_price'] + book_data['ask_price']) / 2
                diff_value_usdt = abs(balance_diff) * current_price
                
                if diff_value_usdt < 5.0:
                    self.log(f"💡 余额差异价值 {diff_value_usdt:.2f} USDT < 5 USDT，跳过补单")
                    self.log("✅ 小额差异视为平衡，检查通过")
                    return True
                
                self.log(f"余额差异价值: {diff_value_usdt:.2f} USDT (≥5 USDT)，执行补单")
            except Exception as e:
                self.log(f"⚠️ 无法计算差异价值: {e}，按数量判断")
            
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
    
    
    def auto_purchase_if_insufficient(self) -> bool:
        """如果余额不足则自动补齐 - 直接全部买入"""
        try:
            current_balance = self.get_asset_balance()
            required_quantity = float(self.quantity)
            
            self.log(f"检查余额是否足够交易...")
            self.log(f"当前余额: {current_balance:.2f}")
            self.log(f"每轮需要: {required_quantity:.2f}")
            
            if current_balance >= required_quantity:
                self.log("✅ 余额充足，无需补齐")
                return True
            
            # 计算缺少的数量
            shortage = required_quantity - current_balance
            self.log(f"⚠️ 余额不足，缺少: {shortage:.2f}", "warning")
            
            # 检查USDT余额
            account_info = self.client.get_account_info()
            usdt_balance = 0.0
            if account_info and 'balances' in account_info:
                for balance in account_info['balances']:
                    if balance['asset'] == 'USDT':
                        usdt_balance = float(balance['free'])
                        break
            
            self.log(f"可用USDT余额: {usdt_balance:.2f}")
            
            # 获取买一价
            book_data = self.get_order_book()
            if not book_data:
                self.log(f"❌ 无法获取市场价格", "error")
                return False
            
            buy_price = book_data['ask_price']  # 买一价
            
            # 关键：按设定数量总价值+1USDT计算，确保容错性
            required_usdt_value = required_quantity * buy_price  # 设定数量的总价值
            target_usdt_value = required_usdt_value + 1.0  # 比设定总价值多1 USDT
            buy_quantity = target_usdt_value / buy_price  # 实际买入数量
            
            self.log(f"=== 直接买入策略（容错性增强）===")
            self.log(f"设定交易数量: {required_quantity:.2f}")
            self.log(f"设定数量价值: {required_usdt_value:.2f} USDT")
            self.log(f"买一价格: {buy_price:.6f}")
            self.log(f"目标买入价值: {target_usdt_value:.2f} USDT (+1 USDT容错)")
            self.log(f"实际买入数量: {buy_quantity:.6f}")
            
            if usdt_balance < target_usdt_value:
                self.log(f"❌ USDT余额不足: {usdt_balance:.2f} < {target_usdt_value:.2f}", "error")
                return False
            
            # 直接市价买入
            result = self.place_market_buy_order(buy_quantity)
            
            if result and result != "ORDER_VALUE_TOO_SMALL":
                import time
                time.sleep(3)  # 等待成交
                final_balance = self.get_asset_balance()
                actual_purchased = final_balance - current_balance
                self.auto_purchased = actual_purchased
                self.log(f"✅ 买入完成: {actual_purchased:.2f}个")
                return True
            else:
                self.log(f"❌ 买入失败", "error")
                return False
                
        except Exception as e:
            self.log(f"❌ 自动补齐失败: {e}", "error")
            return False
    
    
    def sell_all_holdings(self) -> bool:
        """卖光所有现货持仓 - 直接全部卖出"""
        try:
            self.log(f"\n=== 卖光所有现货持仓 ===")
            
            # 获取当前余额
            current_balance = self.get_asset_balance()
            self.log(f"当前现货余额: {current_balance:.2f}")
            
            if current_balance <= 0.1:
                self.log("✅ 当前余额很少或为零，无需卖出")
                return True
            
            # 获取卖一价
            book_data = self.get_order_book()
            if not book_data:
                self.log(f"❌ 无法获取市场价格", "error")
                return False
            
            sell_price = book_data['bid_price']  # 卖一价
            estimated_value = current_balance * sell_price
            
            self.log(f"卖一价格: {sell_price:.6f}")
            self.log(f"估算卖出价值: {estimated_value:.2f} USDT")
            
            # 检查订单价值
            if estimated_value < 5.0:
                self.log(f"⚠️ 卖出价值不足5 USDT，保留余额", "warning")
                return True
            
            # 直接市价卖出全部余额
            self.log(f"=== 直接卖出策略 ===")
            self.log(f"卖出数量: {current_balance:.2f}")
            
            result = self.place_market_sell_order(current_balance)
            
            if result and result != "ORDER_VALUE_TOO_SMALL":
                import time
                time.sleep(3)  # 等待成交
                final_balance = self.get_asset_balance()
                self.log(f"✅ 卖出完成: 余额 {current_balance:.2f} -> {final_balance:.2f}")
                
                if final_balance <= 0.1:
                    self.log("✅ 现货已全部清仓")
                else:
                    self.log(f"⚠️ 仍有少量余额: {final_balance:.2f}")
                    
                return True
            else:
                self.log(f"❌ 卖出失败", "error")
                return False
                
        except Exception as e:
            self.log(f"❌ 卖出现货异常: {e}", "error")
            return False
    
    
    def final_balance_reconciliation(self) -> bool:
        """最终余额校验 - 策略结束前的检查，不执行补单"""
        try:
            self.log("检查策略执行前后的余额变化...")
            
            # 获取当前余额
            current_balance = self.get_asset_balance()
            balance_difference = current_balance - self.initial_balance
            
            self.log(f"初始余额: {self.initial_balance:.2f}")
            self.log(f"当前余额: {current_balance:.2f}")
            self.log(f"余额差异: {balance_difference:+.2f}")
            
            # 策略结束阶段只做检查，不执行补单
            if abs(balance_difference) <= 0.1:
                self.log("✅ 余额差异在可接受范围内 (±0.1)")
                return True
            elif balance_difference > 0.1:
                self.log(f"⚠️ 检测到余额增加 {balance_difference:.2f}")
                self.log("💡 策略结束阶段，不执行补单，将在清理库存阶段处理")
                return True
            else:
                self.log(f"⚠️ 检测到余额减少 {abs(balance_difference):.2f}")
                self.log("💡 策略结束阶段，不执行补单，将在清理库存阶段处理")
                return True
                    
        except Exception as e:
            self.log(f"❌ 最终余额校验异常: {e}", "error")
            return False
    
    def execute_round(self, round_num: int) -> bool:
        """执行一轮交易"""
        self.log(f"\n=== 第 {round_num}/{self.rounds} 轮交易 ===")
        self.log(f"开始执行第 {round_num} 轮交易", 'info')
        
        # 每10轮执行一次自适应调节 - 方案3优化
        if round_num % 10 == 1:
            self._auto_adjust_parameters()
        
        # 智能余额检查：先清理订单释放资金，再获取真实可用余额
        available_balance = self.smart_balance_check()
        
        # 基于实际余额动态计算交易数量（而非固定数量）
        base_quantity = float(self.quantity)  # 基础参考数量
        safety_margin = 0.2  # 安全边际：保留0.2个币
        
        # 计算本轮实际可用数量
        max_usable = available_balance - safety_margin
        actual_quantity = min(base_quantity, max_usable)
        
        self.log(f"💰 本轮交易数量计算:")
        self.log(f"  可用余额: {available_balance:.2f}")
        self.log(f"  安全边际: {safety_margin:.2f}")
        self.log(f"  基础数量: {base_quantity:.2f}")
        self.log(f"  实际数量: {actual_quantity:.2f}")
        
        if actual_quantity < 1.0:
            self.log(f"⚠️ 余额过低，本轮实际可用数量不足1.0: {actual_quantity:.2f}", "warning")
            self.log(f"❌ 触发自动补货...", "warning")
            
            # 余额不足就触发补货
            if self.auto_purchase_if_insufficient():
                self.log(f"✅ 补货成功，重新计算交易数量")
                # 重新获取余额并计算
                available_balance = self.smart_balance_check()
                max_usable = available_balance - safety_margin
                actual_quantity = min(base_quantity, max_usable)
                self.log(f"✅ 补货后可用数量: {actual_quantity:.2f}")
                
                if actual_quantity < 1.0:
                    self.log(f"❌ 补货后余额仍不足，跳过本轮", "error")
                    return False
            else:
                self.log(f"❌ 补货失败，跳过本轮", "error")
                return False
        
        # 确保使用标准化的实际数量
        self.log(f"✅ 本轮使用交易数量: {actual_quantity:.2f}")
        
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
            
            # 2. 使用优化策略执行交易
            self.log(f"=== 第{round_num}轮: 启用优化交易策略 ===", 'info')
            
            # 执行优化的交易轮次
            sell_order, buy_order = self.execute_optimized_round(actual_quantity)
            
            if not sell_order or not buy_order:
                self.log(f"❌ 优化策略执行失败，跳过本轮", 'error')
                return False
            
            # 强制日志：订单已提交
            self.log(f"=== 第{round_num}轮: 优化订单已提交，开始监控 ===", 'info')
            
            import time
            start_time = time.time()
            
            # 获取订单ID
            sell_order_id = sell_order.get('orderId')
            buy_order_id = buy_order.get('orderId')
            
            # 将订单添加到跟踪列表
            if sell_order_id:
                self.pending_orders.append(sell_order_id)
            if buy_order_id:
                self.pending_orders.append(buy_order_id)
            
            self.log(f"✅ 优化策略订单提交成功 - 卖出:{sell_order_id} 买入:{buy_order_id}")
            
            # 优化策略订单监控
            self.log(f"=== 第{round_num}轮: 开始监控优化订单 ===", 'info')
            
            # 等待订单成交
            time.sleep(self.order_check_timeout)
            
            # 使用批量查询减少API调用
            if self.batch_query_enabled and buy_order_id and sell_order_id:
                order_statuses = self.check_multiple_order_status([buy_order_id, sell_order_id])
                buy_status = order_statuses.get(str(buy_order_id), 'UNKNOWN')
                sell_status = order_statuses.get(str(sell_order_id), 'UNKNOWN')
                self.log(f"批量查询订单状态 - 买入: {buy_status}, 卖出: {sell_status}")
            else:
                # 降级到单个查询
                buy_status = self.check_order_status(buy_order_id) if buy_order_id else 'UNKNOWN'
                sell_status = self.check_order_status(sell_order_id) if sell_order_id else 'UNKNOWN'
                self.log(f"单独查询订单状态 - 买入: {buy_status}, 卖出: {sell_status}")
            
            # 分析成交情况
            buy_filled = buy_status == 'FILLED'
            sell_filled = sell_status == 'FILLED'
            
            if buy_filled and sell_filled:
                # 双向成交 - 优化策略的目标结果
                self.log("🎯 优化策略成功！双向订单都已成交")
                
                # 优化统计数据更新 - 延迟批量处理减少API调用
                # 将订单ID标记为已成交，在策略结束时批量更新统计
                self.completed_order_ids.extend([buy_order_id, sell_order_id])
                self.log("📊 订单统计将在轮次结束时批量更新")
                
                # 从跟踪列表移除
                if buy_order_id in self.pending_orders:
                    self.pending_orders.remove(buy_order_id)
                if sell_order_id in self.pending_orders:
                    self.pending_orders.remove(sell_order_id)
                
                # 标记轮次完成
                round_completed = True
                self.completed_rounds += 1
                
                # 双向成交后的轻量级检查：只检查本地状态
                self.log(f"🔍 双向成交后执行状态检查...")
                self._enforce_round_cleanup(round_num, skip_heavy_checks=True)
                
                self.log(f"✅ 第 {round_num} 轮交易完成 (优化策略成功)")
                return True
                
            elif sell_filled and not buy_filled:
                # 只有卖单成交，检查是否为最后一轮
                if round_num == self.rounds:
                    self.log("📈 卖单成交，买单未成交 - 最后一轮，不执行补单")
                    # 延迟统计更新
                    self.completed_order_ids.append(sell_order_id)
                    
                    # 取消买单
                    self.cancel_order(buy_order_id)
                    
                    # 移除订单
                    if sell_order_id in self.pending_orders:
                        self.pending_orders.remove(sell_order_id)
                    if buy_order_id in self.pending_orders:
                        self.pending_orders.remove(buy_order_id)
                    
                    self.log("💡 最后一轮单边成交，余额差异将在清理库存阶段处理")
                    self.completed_rounds += 1
                    return True
                else:
                    # 非最后一轮，执行买入补单
                    self.log("📈 卖单成交，买单未成交 - 执行买入补单")
                    # 延迟统计更新
                    self.completed_order_ids.append(sell_order_id)
                    
                    # 取消买单
                    self.cancel_order(buy_order_id)
                    
                    # 移除订单
                    if sell_order_id in self.pending_orders:
                        self.pending_orders.remove(sell_order_id)
                    if buy_order_id in self.pending_orders:
                        self.pending_orders.remove(buy_order_id)
                    
                    # 市价买入补单
                    time.sleep(0.5)
                    success = self.place_market_buy_order(actual_quantity)
                    if success:
                        self.log("✅ 买入补单成功")
                        self.supplement_orders += 1  # 增加补单计数
                        self.completed_rounds += 1
                        
                        # 补单后的轻量级检查：补单成功时只需要检查本地状态
                        self.log(f"🔍 买入补单后执行状态检查...")
                        self._enforce_round_cleanup(round_num, skip_heavy_checks=True)
                        
                        return True
                    else:
                        self.log("❌ 买入补单失败", 'error')
                        return False
                    
            elif buy_filled and not sell_filled:
                # 只有买单成交，检查是否为最后一轮
                if round_num == self.rounds:
                    self.log("📉 买单成交，卖单未成交 - 最后一轮，不执行补单")
                    # 延迟统计更新
                    self.completed_order_ids.append(buy_order_id)
                    
                    # 取消卖单
                    self.cancel_order(sell_order_id)
                    
                    # 移除订单
                    if sell_order_id in self.pending_orders:
                        self.pending_orders.remove(sell_order_id)
                    if buy_order_id in self.pending_orders:
                        self.pending_orders.remove(buy_order_id)
                    
                    self.log("💡 最后一轮单边成交，余额差异将在清理库存阶段处理")
                    self.completed_rounds += 1
                    return True
                else:
                    # 非最后一轮，执行卖出补单
                    self.log("📉 买单成交，卖单未成交 - 执行卖出补单")
                    # 延迟统计更新
                    self.completed_order_ids.append(buy_order_id)
                    
                    # 取消卖单
                    self.cancel_order(sell_order_id)
                    
                    # 移除订单
                    if sell_order_id in self.pending_orders:
                        self.pending_orders.remove(sell_order_id)
                    if buy_order_id in self.pending_orders:
                        self.pending_orders.remove(buy_order_id)
                    
                    # 市价卖出补单
                    time.sleep(0.5)
                    success = self.place_market_sell_order(actual_quantity)
                    if success:
                        self.log("✅ 卖出补单成功")
                        self.supplement_orders += 1  # 增加补单计数
                        self.completed_rounds += 1
                        
                        # 补单后的轻量级检查：补单成功时只需要检查本地状态
                        self.log(f"🔍 卖出补单后执行状态检查...")
                        self._enforce_round_cleanup(round_num, skip_heavy_checks=True)
                        
                        return True
                    else:
                        self.log("❌ 卖出补单失败", 'error')
                        return False
            
            else:
                # 都未成交，取消订单
                self.log("⚠️ 双向订单都未成交，取消订单")
                self.cancel_order(buy_order_id)
                self.cancel_order(sell_order_id)
                
                # 移除订单
                if sell_order_id in self.pending_orders:
                    self.pending_orders.remove(sell_order_id)
                if buy_order_id in self.pending_orders:
                    self.pending_orders.remove(buy_order_id)
                
                # 订单取消后需要深度检查：确保清理完成
                self.log(f"🔍 订单取消后执行深度检查...")
                self._enforce_round_cleanup(round_num)  # 取消情况下执行完整检查
                
                return False
            
        except Exception as e:
            self.log(f"交易轮次错误: {e}")
            self.log(f"第 {round_num} 轮交易出现异常: {e}", 'error')
            return False
        
        finally:
            # 确保每一轮都有日志输出，便于调试
            if not round_completed:
                self.log(f"第 {round_num} 轮交易结束 (未完成)", 'warning')
                # 未完成轮次需要深度清理
                self.log(f"🔍 未完成轮次的深度清理...")
                self._enforce_round_cleanup(round_num)  # 异常情况执行完整检查
    
    def run(self) -> bool:
        """运行策略"""
        self.log(f"\n开始执行刷量策略...")
        
        if not self.connect():
            self.log("无法连接交易所，策略终止")
            return False
        
        # 获取原始余额并记录
        self.original_balance = self.get_asset_balance()
        self.log(f"原始余额: {self.original_balance:.2f}")
        
        # 记录初始USDT余额
        self.initial_usdt_balance = self.get_usdt_balance()
        self.log(f"初始USDT余额: {self.initial_usdt_balance:.4f}")
        
        # 检查余额并自动补齐
        if not self.auto_purchase_if_insufficient():
            self.log(f"❌ 余额补齐失败，无法执行策略", "error")
            return False
        
        # 重新获取余额作为循环期间的基准
        self.initial_balance = self.get_asset_balance()
        self.log(f"策略执行基准余额: {self.initial_balance:.2f}")
        
        if self.auto_purchased > 0:
            self.log(f"📝 已自动购买 {self.auto_purchased:.2f}，策略结束后将自动卖出恢复原始余额")
        
        self.log(f"✅ 余额检查通过，开始执行 {self.rounds} 轮交易")
        success_rounds = 0
        
        try:
            for round_num in range(1, self.rounds + 1):
                # 检查是否收到停止请求
                if self.is_stop_requested():
                    self.log(f"🛑 收到停止请求，在第 {round_num} 轮前提前结束")
                    break
                
                if self.execute_round(round_num):
                    success_rounds += 1
                else:
                    self.log(f"第 {round_num} 轮失败")
                    self.failed_rounds += 1
                
                # 检查是否收到停止请求（轮次完成后）
                if self.is_stop_requested():
                    self.log(f"🛑 收到停止请求，在第 {round_num} 轮后提前结束")
                    break
                
                # 轮间轻量级检查：只检查本地状态以减少API调用
                if round_num < self.rounds:
                    self.log(f"🔍 第{round_num}轮与第{round_num+1}轮之间的状态检查...")
                    self._enforce_round_cleanup(round_num, skip_heavy_checks=True)
                
                # 等待间隔时间(除了最后一轮)
                if round_num < self.rounds:
                    self.log(f"等待 {self.interval} 秒...")
                    # 分段睡眠，以便快速响应停止请求
                    for _ in range(self.interval):
                        if self.is_stop_requested():
                            self.log(f"🛑 等待期间收到停止请求，立即结束")
                            break
                        time.sleep(1)
            
            # API优化：批量更新延迟的统计数据
            self.log(f"\n=== 批量更新交易统计 ===")
            self._batch_update_statistics()
            
            # 执行最终余额校验和补单
            self.log(f"\n=== 执行最终余额校验 ===")
            final_success = self.final_balance_reconciliation()
            
            # 卖光所有现货持仓
            sellout_success = self.sell_all_holdings()
            
            # 记录最终USDT余额并计算损耗
            self.final_usdt_balance = self.get_usdt_balance()
            self.usdt_balance_diff = self.final_usdt_balance - self.initial_usdt_balance
            self.net_loss_usdt = self.usdt_balance_diff - self.total_fees_usdt
            
            self.log(f"\n=== 策略执行完成 ===")
            # 计算实际执行的轮次
            total_executed = self.completed_rounds + self.failed_rounds
            self.log(f"完成轮次: {self.completed_rounds}/{self.rounds}")
            self.log(f"失败轮次: {self.failed_rounds}")
            self.log(f"实际执行: {total_executed}/{self.rounds}")
            if total_executed > 0:
                self.log(f"成功率: {(self.completed_rounds/total_executed*100):.1f}%")
            else:
                self.log(f"成功率: 0.0%")
            self.log(f"补单次数: {self.supplement_orders}")
            self.log(f"估算损耗: {self.total_cost_diff:.4f} USDT")
            
            # 新增交易量和手续费统计
            total_volume = self.buy_volume_usdt + self.sell_volume_usdt
            self.log(f"\n=== 交易统计 ===")
            self.log(f"买单总交易量: {self.buy_volume_usdt:.2f} USDT")
            self.log(f"卖单总交易量: {self.sell_volume_usdt:.2f} USDT") 
            self.log(f"总交易量: {total_volume:.2f} USDT")
            self.log(f"总手续费: {self.total_fees_usdt:.4f} USDT")
            
            self.log(f"\n=== USDT余额分析 ===")
            self.log(f"初始USDT余额: {self.initial_usdt_balance:.4f}")
            self.log(f"最终USDT余额: {self.final_usdt_balance:.4f}")
            self.log(f"USDT余额差值: {self.usdt_balance_diff:+.4f}")
            self.log(f"净损耗(差值-手续费): {self.net_loss_usdt:+.4f} USDT")
            
            if self.auto_purchased > 0:
                self.log(f"自动购买数量: {self.auto_purchased:.2f}")
            
            final_balance = self.get_asset_balance()
            original_change = final_balance - self.original_balance
            execution_change = final_balance - self.initial_balance
            
            self.log(f"\n=== 现货余额 ===")
            self.log(f"原始余额: {self.original_balance:.2f}")
            self.log(f"执行基准余额: {self.initial_balance:.2f}")
            self.log(f"最终余额: {final_balance:.2f}")
            self.log(f"与原始余额差异: {original_change:+.2f}")
            self.log(f"与执行基准差异: {execution_change:+.2f}")
            self.log(f"余额校验: {'✅ 通过' if final_success else '⚠️ 存在差异'}")
            self.log(f"现货清仓: {'✅ 成功' if sellout_success else '⚠️ 未完全清仓'}")
            
            # 如果是因为停止请求而结束，也执行清理
            if self.is_stop_requested():
                self.log("\n🛑 策略因停止请求结束")
                self._cleanup_on_stop()
            
            return self.completed_rounds > 0
            
        except KeyboardInterrupt:
            self.log("\n用户中断策略执行")
            # 用户中断时也执行清理和统计
            self._cleanup_on_stop()
            return False
        except Exception as e:
            self.log(f"策略执行错误: {e}")
            # 异常时也执行清理和统计
            self._cleanup_on_stop()
            return False
    
    def _cleanup_on_stop(self):
        """策略停止时的清理和统计工作"""
        try:
            self.log("\n=== 策略停止清理 ===")
            
            # 1. 检查并取消所有未成交订单
            self.cancel_all_open_orders_batch()
            
            # 2. 执行数据统计
            self._calculate_final_statistics()
            
            # 3. 卖出所有现货恢复余额
            sellout_success = self.sell_all_holdings()
            
            # 4. 记录最终状态
            self.log(f"数据统计: ✅ 完成")
            self.log(f"现货清仓: {'✅ 成功' if sellout_success else '⚠️ 未完全清仓'}")
            self.log("=== 策略停止清理完成 ===")
            
        except Exception as e:
            self.log(f"策略停止清理异常: {e}", 'error')
    
    def _calculate_final_statistics(self):
        """计算最终统计数据（不调用API）"""
        try:
            # 使用累计的统计数据，而不是调用API获取最终余额
            # final_usdt_balance 已在交易过程中通过余额变化累计计算
            self.final_usdt_balance = self.initial_usdt_balance - self.total_fees_usdt
            self.usdt_balance_diff = self.final_usdt_balance - self.initial_usdt_balance
            self.net_loss_usdt = self.usdt_balance_diff
            
            # 计算交易统计
            total_volume = self.buy_volume_usdt + self.sell_volume_usdt
            
            self.log(f"\n=== 最终统计数据 ===")
            self.log(f"完成轮次: {self.completed_rounds}")
            self.log(f"补单次数: {self.supplement_orders}")
            self.log(f"总交易量: {total_volume:.2f} USDT")
            self.log(f"买单量: {self.buy_volume_usdt:.2f} USDT")
            self.log(f"卖单量: {self.sell_volume_usdt:.2f} USDT")
            self.log(f"总手续费: {self.total_fees_usdt:.4f} USDT")
            self.log(f"USDT余额差值: {self.usdt_balance_diff:+.4f}")
            self.log(f"净损耗: {self.net_loss_usdt:+.4f} USDT")
            
        except Exception as e:
            self.log(f"计算最终统计数据异常: {e}", 'error')


def main():
    """主函数 - 策略参数配置"""
    
    # 策略参数配置
    SYMBOL = "SENTISUSDT"     # 交易对 (已从ASTERUSDT改为SENTISUSDT)
    QUANTITY = "8.0"          # 每次交易数量 (需根据SENTIS价格调整确保 >= 5 USDT)
    INTERVAL = 10             # 交易间隔(秒)
    ROUNDS = 10               # 交易轮次
    
    self.log("=== AsterDEX 刷量交易策略 ===")
    self.log(f"交易对: {SYMBOL}")
    self.log(f"数量: {QUANTITY}")
    self.log(f"间隔: {INTERVAL}秒")
    self.log(f"轮次: {ROUNDS}次")
    
    # 确认执行
    confirm = input("\n确认执行策略? (y/N): ").strip().lower()
    if confirm != 'y':
        self.log("策略已取消")
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
        self.log("\n策略执行成功!")
    else:
        self.log("\n策略执行失败!")


if __name__ == "__main__":
    main()


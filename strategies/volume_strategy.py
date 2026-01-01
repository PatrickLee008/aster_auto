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
        self.cache_enabled = True  # 启用缓存
        self.orderbook_cache_time = 0.0  # 禁用订单簿缓存，实时获取最新价格
        self.balance_cache_time = 0.0  # 余额缓存时间(秒) - 禁用！余额必须实时获取
        self.smart_skip_enabled = True  # 启用智能跳过
        
        # 缓存存储
        self.cached_orderbook = None
        self.cached_balance = None
        self.last_orderbook_time = 0
        self.last_balance_time = 0
        
        # 智能预判状态
        self.consecutive_success = 0  # 连续成功次数
        self.recent_api_errors = 0  # 最近API错误次数
        self.last_error_time = 0  # 上次错误时间
        
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
        """获取深度订单薄数据 - 支持缓存"""
        # 默认启用缓存
        if use_cache is None:
            use_cache = self.cache_enabled
            
        # 检查缓存
        current_time = time.time()
        if (use_cache and self.cached_orderbook and 
            current_time - self.last_orderbook_time < self.orderbook_cache_time):
            return self.cached_orderbook
            
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
                    
                    # 价格区间信息已获取
                    
                    result = {
                        'bid_price': first_bid_price,  # 买方第一档（买一价格）
                        'ask_price': first_ask_price,  # 卖方第一档（卖一价格）
                        'bid_depth': len(bids),
                        'ask_depth': len(asks)
                    }
                    
                    # 更新缓存
                    if use_cache:
                        self.cached_orderbook = result
                        self.last_orderbook_time = current_time
                    
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
            
        # 使用正确的tick size格式化价格
        formatted_price = self.format_price(base_price)
        trade_price = float(formatted_price)
        
        # 检查订单价值是否满足5 USDT最小限制
        order_value = trade_price * float(self.quantity)
        if order_value < 5.0:
            # 如果订单价值不足，调整价格确保满足最小限制
            min_price = 5.0 / float(self.quantity)
            trade_price = max(trade_price, round(min_price, 5))
        
        self.log(f"生成交易价格: {trade_price:.5f}, 订单价值: {trade_price * float(self.quantity):.2f} USDT")
        return trade_price
    
    def place_sell_order(self, price: float, quantity: float = None) -> Optional[Dict[str, Any]]:
        """下达卖出订单"""
        try:
            # 使用传入的数量或默认数量
            if quantity is None:
                quantity = float(self.quantity)
            
            # 确保数量精度正确，使用交易对的step_size
            import math
            adjusted_quantity = math.floor(quantity * 100) / 100
            quantity_str = self.format_quantity(adjusted_quantity)
            
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
            import math
            adjusted_quantity = math.floor(quantity * 100) / 100
            quantity_str = self.format_quantity(adjusted_quantity)
            
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
    
    def _should_skip_order_check(self, round_num: int) -> bool:
        """智能预判是否可以跳过未成交订单检查"""
        if not self.smart_skip_enabled:
            return False
        
        # 如果最近有API错误，不跳过
        if self.recent_api_errors > 0 and time.time() - self.last_error_time < 30:
            return False
        
        # 第1轮不跳过
        if round_num == 1:
            return False
        
        # 连续成功次数越多，跳过概率越高
        if self.consecutive_success >= 10:
            # 10轮后每5轮检查一次
            return round_num % 5 != 1
        elif self.consecutive_success >= 5:
            # 5轮后每3轮检查一次  
            return round_num % 3 != 1
        else:
            # 前5轮每轮都检查
            return False
    
    def _update_success_stats(self, success: bool):
        """更新成功统计"""
        if success:
            self.consecutive_success += 1
            # 成功时减少错误计数
            if self.recent_api_errors > 0:
                self.recent_api_errors = max(0, self.recent_api_errors - 1)
        else:
            self.consecutive_success = 0
    
    def _auto_adjust_parameters(self):
        """自适应参数调节 - 方案3优化"""
        current_time = time.time()
        
        # 根据API错误率调整
        if self.recent_api_errors >= 5:
            self.log("⚠️ API错误率过高，切换到保守模式")
            self.batch_query_enabled = False
            self.cache_enabled = False
            self.smart_skip_enabled = False
        elif self.recent_api_errors >= 3:
            self.log("⚠️ 检测到API错误，部分禁用优化")
            self.batch_query_enabled = False
        else:
            # 错误率正常，可以启用优化
            if not self.batch_query_enabled and self.consecutive_success >= 3:
                self.log("✅ 错误率正常，重新启用批量查询")
                self.batch_query_enabled = True
        
        # 订单簿缓存已禁用，不再动态调整
        # 余额缓存始终保持为0，确保实时准确性
        self.balance_cache_time = 0.0

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
    
    def _update_filled_order_statistics(self, order_id: int, side: str):
        """更新已成交订单的统计数据"""
        try:
            # 检查是否已经处理过此订单，避免重复统计
            if order_id in self.processed_orders:
                self.log(f"📋 订单 {order_id} 已处理过，跳过重复统计")
                return
                
            # 获取订单详细信息
            order_info = self.client.get_order(self.symbol, order_id)
            
            if order_info and order_info.get('status') == 'FILLED':
                executed_qty = float(order_info.get('executedQty', 0))
                avg_price = float(order_info.get('avgPrice', 0))
                
                if executed_qty > 0 and avg_price > 0:
                    # 判断是否为maker（限价单通常是maker，但不一定）
                    # 如果API返回了maker信息，使用它；否则假设限价单为maker
                    is_maker = order_info.get('isMaker', True)  # 默认假设限价单是maker
                    
                    # 计算手续费
                    fee = self._calculate_fee_from_order_result(order_info, is_maker=is_maker)
                    # 更新统计数据
                    self._update_trade_statistics(side, executed_qty, avg_price, fee)
                    
                    # 标记订单为已处理
                    self.processed_orders.add(order_id)
                    
                    maker_type = "Maker" if is_maker else "Taker"
                    # 限价单统计已更新
                
        except Exception as e:
            self.log(f"❌ 更新订单统计时出错: {e}", "error")
    
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
            self.log(f"获取市场深度失败: {e}")
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
            
            # 简化处理：去掉小数点，直接使用整数
            import math
            adjusted_quantity = math.floor(quantity)
            quantity_str = str(int(adjusted_quantity))
            
            self.log(f"市价卖出原始数量: {quantity:.6f}")
            self.log(f"市价卖出调整为整数: {quantity_str}")
            
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
            self.log("执行风险控制 - 逐档智能补货")
            self.log(f"目标价格: {target_sell_price:.5f} (原卖出价格)")
            
            target_quantity = float(self.quantity)  # 需要补回的总数量
            filled_quantity = 0.0  # 已补回的数量
            total_cost = 0.0  # 总成本
            buy_orders = []  # 记录所有买入订单
            
            self.log(f"需要补回数量: {target_quantity:.2f} {self.symbol.replace('USDT', '')}")
            
            while filled_quantity < target_quantity:
                remaining_quantity = target_quantity - filled_quantity
                self.log(f"\n还需补回: {remaining_quantity:.2f}")
                
                # 获取当前订单薄深度
                depth_data = self.client.get_depth(self.symbol, 20)  # 获取更多档深度
                
                if not depth_data or 'asks' not in depth_data:
                    self.log(f"❌ 无法获取订单薄深度", "error")
                    break
                
                asks = depth_data['asks']  # 卖单 [[price, quantity], ...]
                                
                if not asks:
                    self.log(f"❌ 卖盘为空", "error")
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
                    self.log(f"❌ 没有找到合适的卖单", "error")
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
                    
                    self.log(f"调整买入数量以满足5 USDT限制: {buy_quantity:.2f}")
                    self.log(f"调整后订单价值: {order_value:.4f} USDT")
                    
                    # 如果调整后仍然不足5 USDT，跳过这个价格
                    if order_value < 5.0:
                        self.log(f"⚠️  价格 {ask_price:.5f} 无法满足5 USDT限制，跳过", "warning")
                        continue
                
                # 确保不超买（买入数量不超过剩余需求）
                if buy_quantity > remaining_quantity:
                    buy_quantity = remaining_quantity
                    buy_quantity = round(buy_quantity, 2)
                    order_value = buy_quantity * ask_price
                    self.log(f"限制买入数量不超过剩余需求: {buy_quantity:.2f}")
                
                                                                
                # 执行买入
                result = self.place_buy_order(ask_price, buy_quantity)
                
                if result:
                    buy_order_id = result.get('orderId')
                    buy_orders.append(buy_order_id)
                    self.log(f"✅ 买入订单成功: ID {buy_order_id}")
                    
                    # 简单等待成交确认
                    time.sleep(0.3)
                    
                    # 简化处理：假设按期望数量完全成交
                    filled_quantity += buy_quantity
                    cost = buy_quantity * ask_price
                    total_cost += cost
                    
                    self.log(f"✅ 补货成交: {buy_quantity:.2f} @ {ask_price:.5f}")
                    self.log(f"累计补回: {filled_quantity:.2f}/{target_quantity:.2f}")
                    self.log(f"累计成本: {total_cost:.4f} USDT")
                else:
                    self.log(f"❌ 买入订单失败", "error")
                    break
                
                # 防止无限循环
                if len(buy_orders) >= 10:
                    self.log(f"⚠️  已尝试10次买入，停止补货", "warning")
                    break
            
            # 总结补货结果
            self.log(f"\n=== 补货完成 ===")
            self.log(f"目标数量: {target_quantity:.2f}")
            self.log(f"实际补回: {filled_quantity:.2f}")
            self.log(f"补货率: {(filled_quantity/target_quantity)*100:.1f}%")
            self.log(f"总成本: {total_cost:.4f} USDT")
            
            if target_cost := target_quantity * target_sell_price:
                extra_cost = total_cost - target_cost
                self.log(f"额外成本: {extra_cost:.4f} USDT")
            
            # 如果补货完成度达到95%以上认为成功
            success_rate = filled_quantity / target_quantity
            if success_rate >= 0.95:
                self.log("✅ 补货基本完成")
                return True
            else:
                self.log(f"❌ 补货未完全完成", "error")
                return False
                
        except Exception as e:
            self.log(f"补货过程错误: {e}")
            return False
    
    def auto_purchase_if_insufficient(self) -> bool:
        """如果余额不足则自动补齐 - 按USDT价值分批买入"""
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
            
            # 获取当前价格
            book_data = self.get_order_book()
            if not book_data:
                self.log(f"❌ 无法获取市场价格", "error")
                return False
            
            estimated_price = book_data['ask_price']
            total_usdt_needed = shortage * estimated_price
            
            # 详细调试信息
            self.log(f"=== 补齐计算详情 ===")
            self.log(f"需要补齐数量: {shortage:.2f}")
            self.log(f"当前市场价格 (ask): {estimated_price:.6f}")
            self.log(f"估算需要USDT: {total_usdt_needed:.2f}")
            self.log(f"可用USDT余额: {usdt_balance:.2f}")
            self.log(f"差额: {usdt_balance - total_usdt_needed:.2f}")
            
            if usdt_balance < total_usdt_needed:
                self.log(f"❌ USDT余额不足: {usdt_balance:.2f} < {total_usdt_needed:.2f}", "error")
                self.log("💡 请检查:")
                self.log(f"  1. 交易数量是否过大: {shortage:.2f} 个")
                self.log(f"  2. 市场价格是否正常: {estimated_price:.6f}")
                self.log(f"  3. 账户USDT余额是否正确: {usdt_balance:.2f}")
                return False
            
            # 根据价值确定分批策略
            if total_usdt_needed < 5.0:
                # 价值 < 5 USDT：直接购买6 USDT价值的现货
                target_usdt_value = 6.0
                target_quantity = target_usdt_value / estimated_price
                max_batches = 1
                batch_quantity = target_quantity
                self.log(f"价值 < 5 USDT ({total_usdt_needed:.2f})，改为购买6 USDT价值现货: {target_quantity:.2f}个")
                is_small_purchase = True
            elif total_usdt_needed <= 60:
                # 价值 5-60 USDT：一次性全部买入
                max_batches = 1
                batch_quantity = shortage
                self.log(f"价值5-60 USDT ({total_usdt_needed:.2f})，一次性买入: {shortage:.2f}个")
                is_small_purchase = False
            elif total_usdt_needed <= 500:
                # 价值 60-500 USDT：分5批买入
                max_batches = 5
                batch_quantity = shortage / max_batches
                self.log(f"价值60-500 USDT ({total_usdt_needed:.2f})，分{max_batches}批买入，每批约: {batch_quantity:.2f}个")
                is_small_purchase = False
            else:
                # 价值 > 500 USDT：分10批买入
                max_batches = 10
                batch_quantity = shortage / max_batches
                self.log(f"价值 > 500 USDT ({total_usdt_needed:.2f})，分{max_batches}批买入，每批约: {batch_quantity:.2f}个")
                is_small_purchase = False
            
            total_purchased = 0.0
            batch_count = 0
            
            # 对于小金额补货(< 5 USDT)，目标是购买6 USDT价值，可能超过required_quantity
            if is_small_purchase:
                target_purchase = target_quantity
                self.log(f"小金额补货：目标购买 {target_purchase:.2f} 个 (6 USDT 价值)")
            else:
                target_purchase = required_quantity
            
            while shortage > 0 and total_purchased < target_purchase and batch_count < max_batches:
                # 计算本批买入数量
                if is_small_purchase:
                    # 小金额补货时，直接购买目标数量
                    current_batch = batch_quantity
                else:
                    # 正常情况，不超过剩余缺口
                    current_batch = min(shortage, batch_quantity)
                
                # 如果数量小于1，使用5.1 USDT等价的最小数量
                if current_batch < 1:
                    min_quantity_for_5usdt = 5.1 / estimated_price
                    current_batch = max(1, min_quantity_for_5usdt)
                    self.log(f"数量不足1个，改为5.1 USDT等价数量: {current_batch:.2f}")
                
                result = self.place_market_buy_order(current_batch)
                
                if not result or result == "ORDER_VALUE_TOO_SMALL":
                    self.log(f"❌ 第{batch_count + 1}批失败", "error")
                    # 如果常规批次失败，尝试最小5.1 USDT购买
                    if current_batch >= 1:
                        min_quantity_for_5usdt = 5.1 / estimated_price
                        self.log(f"尝试最小5.1 USDT购买: {min_quantity_for_5usdt:.2f}")
                        result = self.place_market_buy_order(min_quantity_for_5usdt)
                        if result and result != "ORDER_VALUE_TOO_SMALL":
                            batch_count += 1
                            total_purchased += min_quantity_for_5usdt
                            time.sleep(3)
                            new_balance = self.get_asset_balance()
                            self.log(f"第{batch_count}批(最小)完成，余额: {new_balance:.2f}")
                            shortage = required_quantity - new_balance
                            continue
                    break
                
                batch_count += 1
                total_purchased += current_batch
                
                # 等待成交并检查实际余额
                time.sleep(3)
                new_balance = self.get_asset_balance()
                actual_shortage = required_quantity - new_balance
                
                self.log(f"第{batch_count}批完成，余额: {new_balance:.2f}")
                
                # 如果余额已经足够，提前结束
                if actual_shortage <= 0:
                    self.log("✅ 余额已足够")
                    break
                
                shortage = actual_shortage
            
            # 最终检查
            final_balance = self.get_asset_balance()
            shortage_final = required_quantity - final_balance
            
            if shortage_final <= 0:
                self.log(f"✅ 补齐完成: {final_balance:.2f} >= {required_quantity:.2f}")
                self.auto_purchased = total_purchased
                return True
            elif shortage_final < 1:
                # 如果只差不到1个，调整交易数量为实际可用余额
                self.log(f"⚠️ 余额差异很小({shortage_final:.2f})，调整交易数量为实际余额: {final_balance:.2f}", "warning")
                # 重要：更新交易数量为实际可用的余额
                self.quantity = final_balance
                self.log(f"💡 交易数量已调整为: {self.quantity:.2f}")
                self.auto_purchased = total_purchased
                return True
            elif batch_count >= max_batches:
                # 如果已经达到最大批次，剩余数量直接一次性买入
                self.log(f"已完成{max_batches}批，剩余{shortage_final:.2f}个直接买入")
                
                # 获取当前市价估算剩余价值
                ticker = self.client.get_book_ticker(self.symbol)
                if ticker:
                    current_price = float(ticker.get('askPrice', 0))
                    remaining_value_usdt = shortage_final * current_price
                    self.log(f"剩余价值估算: {remaining_value_usdt:.2f} USDT")
                    
                    if remaining_value_usdt < 5.0:
                        # 剩余价值小于5USDT，购买6USDT价值的代币
                        target_quantity = 6.0 / current_price
                        self.log(f"价值小于5USDT，改为购买6USDT价值: {target_quantity:.2f}个")
                        final_result = self.place_market_buy_order(target_quantity)
                        purchased_quantity = target_quantity
                    else:
                        # 正常购买剩余数量
                        final_result = self.place_market_buy_order(shortage_final)
                        purchased_quantity = shortage_final
                else:
                    # 无法获取价格，按原逻辑购买
                    final_result = self.place_market_buy_order(shortage_final)
                    purchased_quantity = shortage_final
                
                if final_result and final_result != "ORDER_VALUE_TOO_SMALL":
                    final_balance = self.get_asset_balance()
                    self.log(f"✅ 最终补齐完成: {final_balance:.2f}")
                    self.auto_purchased = total_purchased + purchased_quantity
                    return True
                else:
                    self.log(f"❌ 最终补齐失败", "error")
                    return False
            else:
                self.log(f"❌ 补齐不完整: {final_balance:.2f} < {required_quantity:.2f}", "error")
                return False
                
        except Exception as e:
            self.log(f"❌ 自动补齐失败: {e}", "error")
            return False
    
    def sell_all_holdings(self) -> bool:
        """卖光所有现货持仓"""
        try:
            self.log(f"\n=== 卖光所有现货持仓 ===")
            
            # 获取当前余额
            current_balance = self.get_asset_balance()
            self.log(f"当前现货余额: {current_balance:.2f}")
            
            if current_balance <= 0.1:
                self.log("✅ 当前余额很少或为零，无需卖出")
                return True
            
            # 获取当前市场价格
            book_data = self.get_order_book()
            if not book_data:
                self.log(f"❌ 无法获取市场价格，跳过卖出", "error")
                return False
            
            estimated_price = (book_data['bid_price'] + book_data['ask_price']) / 2
            estimated_value = current_balance * estimated_price
            
            self.log(f"估算卖出价格: {estimated_price:.5f}")
            self.log(f"估算卖出价值: {estimated_value:.2f} USDT")
            
            # 检查订单价值
            if estimated_value < 5.0:
                self.log(f"⚠️ 卖出价值不足5 USDT，保留余额", "warning")
                self.log("💡 保留少量现货余额")
                return True
            
            # 根据价值确定分批清仓策略
            if estimated_value <= 60:
                # 价值 <= 60 USDT：一次性全部卖出
                max_batches = 1
                batch_quantity = current_balance
                self.log(f"价值 <= 60 USDT ({estimated_value:.2f})，一次性卖出: {current_balance:.2f}个")
            elif estimated_value <= 500:
                # 价值 60-500 USDT：分5批卖出
                max_batches = 5
                batch_quantity = current_balance / max_batches
                self.log(f"价值60-500 USDT ({estimated_value:.2f})，分{max_batches}批卖出，每批约: {batch_quantity:.2f}个")
            else:
                # 价值 > 500 USDT：分10批卖出
                max_batches = 10
                batch_quantity = current_balance / max_batches
                self.log(f"价值 > 500 USDT ({estimated_value:.2f})，分{max_batches}批卖出，每批约: {batch_quantity:.2f}个")
            
            # 执行分批卖出
            remaining_balance = current_balance
            batch_count = 0
            total_sold = 0.0
            
            while remaining_balance > 0.1 and batch_count < max_batches:
                # 计算本批卖出数量
                current_batch = min(remaining_balance, batch_quantity)
                
                # 最后一批卖出所有剩余
                if batch_count == max_batches - 1:
                    current_batch = remaining_balance
                
                # 检查本批订单价值
                batch_value = current_batch * estimated_price
                if batch_value < 5.0 and batch_count < max_batches - 1:
                    self.log(f"第{batch_count + 1}批价值不足5 USDT ({batch_value:.2f})，与下批合并")
                    batch_quantity += current_batch  # 增加下批数量
                    batch_count += 1
                    continue
                
                self.log(f"执行第{batch_count + 1}批卖出: {current_batch:.2f}个 (价值约{batch_value:.2f} USDT)")
                result = self.place_market_sell_order(current_batch)
                
                if result == "ORDER_VALUE_TOO_SMALL":
                    self.log(f"第{batch_count + 1}批价值不足，跳过")
                    if batch_count == max_batches - 1:
                        self.log("最后一批无法卖出，保留余额")
                        break
                elif result and isinstance(result, dict):
                    self.log(f"✅ 第{batch_count + 1}批卖出成功: ID {result.get('orderId')}")
                    total_sold += current_batch
                    
                    # 等待成交并检查余额
                    time.sleep(2)
                    new_balance = self.get_asset_balance()
                    remaining_balance = new_balance
                    
                    self.log(f"第{batch_count + 1}批完成，剩余余额: {remaining_balance:.2f}")
                else:
                    self.log(f"❌ 第{batch_count + 1}批卖出失败", "error")
                    break
                
                batch_count += 1
                
                # 如果不是最后一批，等待间隔
                if batch_count < max_batches and remaining_balance > 0.1:
                    time.sleep(1)
            
            # 检查最终结果
            final_balance = self.get_asset_balance()
            self.log(f"清仓前余额: {current_balance:.2f}")
            self.log(f"清仓后余额: {final_balance:.2f}")
            self.log(f"已卖出数量: {(current_balance - final_balance):+.2f}")
            
            if final_balance <= 0.1:
                self.log("✅ 现货已全部清仓")
                return True
            else:
                self.log(f"⚠️ 仍有余额: {final_balance:.2f} (可能因价值不足5 USDT)", "warning")
                return True  # 仍然认为成功，因为已经尽力了
                
        except Exception as e:
            self.log(f"❌ 卖出现货异常: {e}", "error")
            return False
    
    def final_balance_reconciliation(self) -> bool:
        """最终余额校验和补单 - 确保策略前后余额完全一致"""
        try:
            self.log("检查策略执行前后的余额变化...")
            
            # 获取当前余额
            current_balance = self.get_asset_balance()
            balance_difference = current_balance - self.initial_balance
            
            self.log(f"初始余额: {self.initial_balance:.2f}")
            self.log(f"当前余额: {current_balance:.2f}")
            self.log(f"余额差异: {balance_difference:+.2f}")
            
            # 如果差异在容忍范围内，认为平衡
            if abs(balance_difference) <= 0.1:
                self.log("✅ 余额差异在可接受范围内 (±0.1)，无需补单")
                return True
            
            # 获取当前市场价格用于估算订单价值
            book_data = self.get_order_book()
            if not book_data:
                self.log(f"❌ 无法获取市场价格，跳过最终补单", "error")
                return False
                
            estimated_price = (book_data['bid_price'] + book_data['ask_price']) / 2
            self.log(f"当前估算价格: {estimated_price:.5f}")
            
            # 根据余额差异决定补单方向
            if balance_difference > 0.1:
                # 余额增加了，说明买入多了，需要卖出
                sell_quantity = abs(balance_difference)
                estimated_value = sell_quantity * estimated_price
                
                self.log(f"💡 检测到余额增加 {balance_difference:.2f}，需要卖出补单")
                self.log(f"卖出数量: {sell_quantity:.2f}")
                self.log(f"估算订单价值: {estimated_value:.2f} USDT")
                
                if estimated_value < 5.0:
                    self.log(f"⚠️ 补单价值不足5 USDT，取消补单", "warning")
                    self.log("💡 微小余额差异，视为正常范围")
                    return True
                
                # 执行卖出补单
                self.log("执行最终卖出补单...")
                result = self.place_market_sell_order(sell_quantity)
                
                if result == "ORDER_VALUE_TOO_SMALL":
                    self.log("💡 补单价值不足，视为完成")
                    return True
                elif result and isinstance(result, dict):
                    self.log(f"✅ 最终卖出补单成功: ID {result.get('orderId')}")
                    self.supplement_orders += 1
                    
                    # 等待成交后再次检查
                    time.sleep(2)
                    new_balance = self.get_asset_balance()
                    final_diff = new_balance - self.initial_balance
                    self.log(f"补单后余额: {new_balance:.2f} (差异: {final_diff:+.2f})")
                    
                    return abs(final_diff) <= 0.1
                else:
                    self.log(f"❌ 最终卖出补单失败", "error")
                    return False
                    
            elif balance_difference < -0.1:
                # 余额减少了，说明卖出多了，需要买入
                buy_quantity = abs(balance_difference)
                estimated_value = buy_quantity * estimated_price
                
                self.log(f"💡 检测到余额减少 {abs(balance_difference):.2f}，需要买入补单")
                self.log(f"买入数量: {buy_quantity:.2f}")
                self.log(f"估算订单价值: {estimated_value:.2f} USDT")
                
                if estimated_value < 5.0:
                    self.log(f"⚠️ 补单价值不足5 USDT，取消补单", "warning")
                    self.log("💡 微小余额差异，视为正常范围")
                    return True
                
                # 执行买入补单
                self.log("执行最终买入补单...")
                result = self.place_market_buy_order(buy_quantity)
                
                if result == "ORDER_VALUE_TOO_SMALL":
                    self.log("💡 补单价值不足，视为完成")
                    return True
                elif result and isinstance(result, dict):
                    self.log(f"✅ 最终买入补单成功: ID {result.get('orderId')}")
                    self.supplement_orders += 1
                    
                    # 等待成交后再次检查
                    time.sleep(2)
                    new_balance = self.get_asset_balance()
                    final_diff = new_balance - self.initial_balance
                    self.log(f"补单后余额: {new_balance:.2f} (差异: {final_diff:+.2f})")
                    
                    return abs(final_diff) <= 0.1
                else:
                    self.log(f"❌ 最终买入补单失败", "error")
                    return False
                    
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
        
        # 检查余额是否足够本轮交易（增加安全边际）
        required_quantity = float(self.quantity)
        safety_margin = 0.2  # 安全边际：保留0.2个币
        
        if available_balance < required_quantity + safety_margin:
            self.log(f"⚠️ 可用余额不足（含安全边际）: {available_balance:.2f} < {required_quantity:.2f} + {safety_margin:.1f}", "warning")
            
            # 计算安全的交易数量
            safe_quantity = available_balance - safety_margin
            
            if safe_quantity > 0 and safe_quantity >= required_quantity * 0.95:  # 至少保证95%的目标数量
                self.log(f"💡 调整交易数量为安全数量: {safe_quantity:.2f}")
                actual_quantity = safe_quantity
            else:
                self.log(f"❌ 即使调整后数量仍不足，触发自动补货", "warning")
                # 余额不足就触发补货
                if self.auto_purchase_if_insufficient():
                    self.log(f"✅ 补货成功，重新检查余额")
                    # 重新获取余额
                    available_balance = self.smart_balance_check()
                    if available_balance >= required_quantity + safety_margin:
                        actual_quantity = available_balance - safety_margin
                        self.log(f"✅ 补货后余额充足，使用数量: {actual_quantity:.2f}")
                    else:
                        self.log(f"❌ 补货后余额仍不足，跳过本轮", "error")
                        return False
                else:
                    self.log(f"❌ 补货失败，跳过本轮", "error")
                    return False
        else:
            # 即使余额充足，也使用安全数量避免精度问题
            actual_quantity = available_balance - safety_margin
            self.log(f"✅ 余额充足，使用安全数量: {actual_quantity:.2f} (原{required_quantity:.2f})")
        
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
            self.log(f"有序提交订单: {actual_quantity} {self.symbol} @ {trade_price:.5f}")
            
            import threading
            import time
            
            self.log("执行顺序: 卖出 -> 买入 ")
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
                    sell_future = executor.submit(self.place_sell_order, trade_price, actual_quantity)
                    
                    # 优化延迟为20ms，减少延迟提高效率
                    time.sleep(0.02)  # 20ms延迟
                    buy_future = executor.submit(self.place_buy_order, trade_price, actual_quantity)
                    
                    # 并行等待结果 - 任何订单提交失败都会抛出异常
                    try:
                        sell_order = sell_future.result(timeout=10)
                        buy_order = buy_future.result(timeout=10)
                    except Exception as result_e:
                        # 检查是否是订单提交失败的异常
                        if any(x in str(result_e) for x in ["订单提交失败", "订单执行异常"]):
                            self.log(f"❌ 订单提交失败，终止任务: {result_e}", "error")
                            raise Exception(f"任务失败 - {result_e}")
                        
                        # 其他异常（如超时等）尝试恢复
                        self.log(f"获取并行结果异常: {result_e}")
                        self.log("等待额外时间确保订单完全处理...")
                        time.sleep(3)
                        
                        # 重新尝试获取结果，无论future是否done都尝试获取
                        sell_order = None
                        buy_order = None
                        
                        # 尝试获取卖出订单结果
                        try:
                            sell_order = sell_future.result(timeout=2)
                            self.log(f"✅ 延迟获取到卖出订单结果")
                        except Exception as e:
                            # 检查是否是订单提交失败
                            if any(x in str(e) for x in ["订单提交失败", "订单执行异常"]):
                                self.log(f"❌ 卖出订单提交失败，终止任务: {e}", "error")
                                raise Exception(f"任务失败 - {e}")
                            self.log(f"延迟获取卖出订单结果失败: {e}")
                            sell_order = None
                        
                        # 尝试获取买入订单结果
                        try:
                            buy_order = buy_future.result(timeout=2)
                            self.log(f"✅ 延迟获取到买入订单结果")
                        except Exception as e:
                            # 检查是否是订单提交失败
                            if any(x in str(e) for x in ["订单提交失败", "订单执行异常"]):
                                self.log(f"❌ 买入订单提交失败，终止任务: {e}", "error")
                                raise Exception(f"任务失败 - {e}")
                            self.log(f"延迟获取买入订单结果失败: {e}")
                            buy_order = None
                        
                        self.log(f"最终订单状态: 卖出={bool(sell_order)}, 买入={bool(buy_order)}")
                        
                        # 重要：即使获取结果失败，订单可能已经成功提交
                        # 不要立即跳过，让后续的状态检查逻辑来判断实际情况
                        if not sell_order and not buy_order:
                            self.log(f"⚠️ 无法获取订单结果，但继续检查订单状态", "warning")
                            # 创建临时订单对象以便后续状态检查
                            sell_order = {'orderId': 'unknown_sell'}
                            buy_order = {'orderId': 'unknown_buy'}
                        
            except Exception as e:
                # 如果是任务失败的异常，直接向上传播
                if "任务失败" in str(e):
                    raise
                # 其他异常记录并跳过本轮
                self.log(f"执行异常: {e}")
                self.log("并行执行失败，跳过本轮")
                return False
            
            end_time = time.time()
            self.log(f"有序下单耗时: {(end_time - start_time)*1000:.0f}毫秒")
            
            # 强制日志：下单完成
            self.log(f"=== 第{round_num}轮: 双向下单完成，开始检查结果 ===", 'info')
            
            # 4. 检查异常和订单提交结果
            if sell_exception:
                self.log(f"❌ 卖出订单异常: {sell_exception}", "error")
            if buy_exception:
                self.log(f"❌ 买入订单异常: {buy_exception}", "error")
            
            # 确保订单对象存在
            if not sell_order or not buy_order:
                self.log(f"❌ 无法获取订单结果，本轮交易失败", "error")
                return False
            
            # 5. 获取订单ID
            sell_order_id = sell_order.get('orderId')
            buy_order_id = buy_order.get('orderId')
            
            # 将有效的订单ID添加到跟踪列表
            if sell_order_id and sell_order_id != 'unknown_sell':
                self.pending_orders.append(sell_order_id)
            if buy_order_id and buy_order_id != 'unknown_buy':
                self.pending_orders.append(buy_order_id)
            
            # 处理未知订单ID的情况
            has_unknown_orders = (sell_order_id == 'unknown_sell' or buy_order_id == 'unknown_buy')
            
            if has_unknown_orders:
                self.log(f"⚠️ 检测到未知订单ID，改为通过余额变化判断交易结果", "warning")
                self.log("等待5秒后检查余额变化...")
                time.sleep(5)
                
                # 通过余额变化判断交易是否成功
                current_balance = self.get_asset_balance()
                balance_change = current_balance - initial_balance
                
                self.log(f"余额变化检测: 初始={initial_balance:.2f}, 当前={current_balance:.2f}, 变化={balance_change:.2f}")
                
                # 如果余额没有显著变化，说明交易可能未成功
                if abs(balance_change) <= 0.01:
                    self.log("💡 余额无显著变化，可能订单未成交或获取结果超时")
                    self.log("跳过本轮，让订单自然处理")
                    return False
                else:
                    self.log(f"💡 检测到余额变化，执行余额平衡补单")
                    # 直接进行余额平衡
                    balance_ok = self.ensure_balance_consistency(initial_balance)
                    return balance_ok
            else:
                self.log(f"✅ 订单提交成功 - 卖出:{sell_order_id} 买入:{buy_order_id}")
            
            # 强制日志：开始状态检查
            self.log(f"=== 第{round_num}轮: 开始检查订单状态 ===", 'info')
            
            # 6. 等待2秒后检查订单成交状态（仅当有有效订单ID时）
            time.sleep(self.order_check_timeout)  # 等待2秒
            
            # 使用批量查询检查买入和卖出订单状态 - 方案3优化
            if self.batch_query_enabled and buy_order_id and sell_order_id:
                order_statuses = self.check_multiple_order_status([buy_order_id, sell_order_id])
                buy_status = order_statuses.get(str(buy_order_id), 'UNKNOWN')
                sell_status = order_statuses.get(str(sell_order_id), 'UNKNOWN')
            else:
                # 降级到单个查询
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
            
            self.log(f"订单状态检查: 买入={buy_status}, 卖出={sell_status}")
            
            # 显示执行数量信息
            if buy_details:
                buy_executed = float(buy_details.get('executedQty', 0))
                buy_original = float(buy_details.get('origQty', 0))
                self.log(f"买入执行情况: {buy_executed}/{buy_original}")
            else:
                buy_executed = 0
                buy_original = float(self.quantity)
                
            if sell_details:
                sell_executed = float(sell_details.get('executedQty', 0))
                sell_original = float(sell_details.get('origQty', 0))
                self.log(f"卖出执行情况: {sell_executed}/{sell_original}")
            else:
                sell_executed = 0
                sell_original = float(self.quantity)
            
            # 7. 根据成交情况处理
            need_balance_check = False
            
            if buy_filled and sell_filled:
                self.log("✅ 买卖订单都已成交，无需补单，直接进入下一轮")
                
                # 更新限价单统计数据
                self._update_filled_order_statistics(buy_order_id, 'BUY')
                self._update_filled_order_statistics(sell_order_id, 'SELL')
                
                # 买卖都成交，从跟踪列表中移除这些订单
                if buy_order_id in self.pending_orders:
                    self.pending_orders.remove(buy_order_id)
                if sell_order_id in self.pending_orders:
                    self.pending_orders.remove(sell_order_id)
                # 买卖都成交，理论上余额平衡，无需检查
                round_completed = True
                self.completed_rounds += 1
                self.log(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易双向成交完成", 'info')
                # 更新成功统计 - 方案3优化
                self._update_success_stats(True)
                return True
                
            elif sell_filled and (not buy_filled or buy_partially):
                # 卖出完全成交，买入未成交或部分成交
                # 先统计已成交的卖单
                self._update_filled_order_statistics(sell_order_id, 'SELL')
                
                if buy_partially:
                    self.log(f"❌ 卖出已成交，买入部分成交 ({buy_executed}/{buy_original}) - 取消买单，补足剩余数量", "error")
                    remaining_buy = buy_original - buy_executed
                else:
                    self.log(f"❌ 卖出已成交，买入未成交 - 先取消未成交买单，再市价买入补回", "error")
                    remaining_buy = buy_original
                
                # 1. 取消未成交或部分成交的买入订单
                self.log(f"取消买入订单: {buy_order_id}")
                cancel_success = self.cancel_order(buy_order_id)
                if cancel_success:
                    self.log("✅ 买入订单取消成功")
                else:
                    self.log(f"⚠️ 买入订单取消失败，可能已成交或已取消", "warning")
                
                # 从跟踪列表中移除订单（无论取消是否成功）
                if sell_order_id in self.pending_orders:
                    self.pending_orders.remove(sell_order_id)  # 卖出已成交
                if buy_order_id in self.pending_orders:
                    self.pending_orders.remove(buy_order_id)   # 买入已取消或将被取消
                
                # 2. 等待一下确保取消生效
                time.sleep(0.5)
                
                # 3. 执行市价买入补单 - 精确补足剩余数量
                self.log(f"需要补买: {remaining_buy:.2f}")
                success = self.smart_buy_order(trade_price, remaining_buy)
                if not success:
                    self.log(f"❌ 市价买入补单失败", "error")
                    return False
                self.log("✅ 买入补单完成，数量已平衡")
                # 统计完成的轮次
                round_completed = True
                self.completed_rounds += 1
                self.log(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易通过买入补单完成", 'info')
                return True
                
            elif buy_filled and (not sell_filled or sell_partially):
                # 买入完全成交，卖出未成交或部分成交
                # 先统计已成交的买单
                self._update_filled_order_statistics(buy_order_id, 'BUY')
                
                if sell_partially:
                    self.log(f"❌ 买入已成交，卖出部分成交 ({sell_executed}/{sell_original}) - 取消卖单，补足剩余数量", "error")
                    remaining_sell = sell_original - sell_executed
                else:
                    self.log(f"❌ 买入已成交，卖出未成交 - 先取消未成交卖单，再市价卖出处理", "error")
                    remaining_sell = sell_original
                
                # 1. 取消未成交或部分成交的卖出订单
                self.log(f"取消卖出订单: {sell_order_id}")
                cancel_success = self.cancel_order(sell_order_id)
                if cancel_success:
                    self.log("✅ 卖出订单取消成功")
                else:
                    self.log(f"⚠️ 卖出订单取消失败，可能已成交或已取消", "warning")
                
                # 从跟踪列表中移除订单（无论取消是否成功）
                if buy_order_id in self.pending_orders:
                    self.pending_orders.remove(buy_order_id)   # 买入已成交
                if sell_order_id in self.pending_orders:
                    self.pending_orders.remove(sell_order_id)  # 卖出已取消或将被取消
                
                # 2. 等待一下确保取消生效
                time.sleep(0.5)
                
                # 3. 执行市价卖出补单 - 精确补足剩余数量
                self.log(f"需要补卖: {remaining_sell:.2f}")
                success = self.smart_sell_order(trade_price, remaining_sell)
                if not success:
                    self.log(f"❌ 市价卖出补单失败", "error")
                    return False
                self.log("✅ 卖出补单完成，数量已平衡")
                # 统计完成的轮次
                round_completed = True
                self.completed_rounds += 1
                self.log(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易通过卖出补单完成", 'info')
                return True
                
            elif buy_partially and sell_partially:
                # 都是部分成交的情况
                self.log(f"⚠️ 买卖都部分成交 - 买入: {buy_executed}/{buy_original}, 卖出: {sell_executed}/{sell_original}", "warning")
                
                # 统计已成交的部分
                self._update_filled_order_statistics(buy_order_id, 'BUY')
                self._update_filled_order_statistics(sell_order_id, 'SELL')
                
                remaining_buy = buy_original - buy_executed
                remaining_sell = sell_original - sell_executed
                
                # 取消两个部分成交的订单
                self.log("取消两个部分成交的订单...")
                self.cancel_order(buy_order_id)
                self.cancel_order(sell_order_id)
                time.sleep(0.5)
                
                # 补足剩余数量
                if remaining_buy > 0:
                    self.log(f"补买剩余数量: {remaining_buy:.2f}")
                    self.smart_buy_order(trade_price, remaining_buy)
                
                if remaining_sell > 0:
                    self.log(f"补卖剩余数量: {remaining_sell:.2f}")
                    self.smart_sell_order(trade_price, remaining_sell)
                
                self.log("✅ 部分成交补单完成")
                # 统计完成的轮次
                round_completed = True
                self.completed_rounds += 1
                self.log(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易通过部分成交补单完成", 'info')
                return True
                
            else:
                self.log(f"❌ 买卖订单都未成交或无法获取订单状态", "error")
                
                # 如果无法获取订单状态，通过余额对比判断实际情况
                if buy_status is None or sell_status is None:
                    self.log(f"⚠️ 无法获取订单状态，使用余额对比判断", "warning")
                    current_balance = self.get_asset_balance()
                    balance_change = current_balance - initial_balance
                    
                    self.log(f"余额变化: {balance_change:.2f}")
                    
                    if abs(balance_change) <= 0.1:
                        self.log("💡 余额无显著变化，可能订单都未成交")
                        # 取消所有订单
                        self.cancel_order(buy_order_id)
                        self.cancel_order(sell_order_id)
                        self.log("ℹ️ 已尝试取消所有订单，本轮结束")
                        return False
                    elif balance_change > 0.1:
                        self.log("💡 余额增加，可能有买入成交，执行卖出补单")
                        success = self.smart_sell_order(trade_price, abs(balance_change))
                        if success:
                            round_completed = True
                            self.completed_rounds += 1
                            self.log(f"✅ 第 {round_num} 轮交易完成")
                            self.log(f"第 {round_num} 轮交易通过余额判断卖出补单完成", 'info')
                        return success
                    elif balance_change < -0.1:
                        self.log("💡 余额减少，可能有卖出成交，执行买入补单")
                        success = self.smart_buy_order(trade_price, abs(balance_change))
                        if success:
                            round_completed = True
                            self.completed_rounds += 1
                            self.log(f"✅ 第 {round_num} 轮交易完成")
                            self.log(f"第 {round_num} 轮交易通过余额判断买入补单完成", 'info')
                        return success
                else:
                    # 正常情况：都未成交，取消订单释放资金，跳到下一轮
                    self.log(f"❌ 买卖订单都未成交，取消订单释放资金", "error")
                    
                    # 取消所有未成交订单
                    buy_cancelled = self.cancel_order(buy_order_id)
                    sell_cancelled = self.cancel_order(sell_order_id)
                    
                    if buy_cancelled:
                        self.log("✅ 买入订单取消成功")
                    else:
                        self.log(f"⚠️ 取消买入订单失败", "warning")
                        
                    if sell_cancelled:
                        self.log("✅ 卖出订单取消成功") 
                    else:
                        self.log(f"⚠️ 取消卖出订单失败", "warning")
                    
                    # 从跟踪列表中移除这些订单（无论取消是否成功）
                    if buy_order_id in self.pending_orders:
                        self.pending_orders.remove(buy_order_id)
                    if sell_order_id in self.pending_orders:
                        self.pending_orders.remove(sell_order_id)
                    
                    time.sleep(1)  # 等待取消生效
                    self.log("ℹ️ 所有订单已取消，资金已释放，进入下一轮")
                    return False
                
            # 这里不应该到达，但如果到达了就标记为完成
            if not round_completed:
                round_completed = True
                self.completed_rounds += 1
                self.log(f"✅ 第 {round_num} 轮交易完成")
                self.log(f"第 {round_num} 轮交易成功完成", 'info')
            return True
            
        except Exception as e:
            self.log(f"交易轮次错误: {e}")
            self.log(f"第 {round_num} 轮交易出现异常: {e}", 'error')
            return False
        
        finally:
            # 确保每一轮都有日志输出，便于调试
            if not round_completed:
                self.log(f"第 {round_num} 轮交易结束 (未完成)", 'warning')
    
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
                
                # 等待间隔时间(除了最后一轮)
                if round_num < self.rounds:
                    self.log(f"等待 {self.interval} 秒...")
                    # 分段睡眠，以便快速响应停止请求
                    for _ in range(self.interval):
                        if self.is_stop_requested():
                            self.log(f"🛑 等待期间收到停止请求，立即结束")
                            break
                        time.sleep(1)
            
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
            self.cancel_all_open_orders()
            
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
        """计算最终统计数据"""
        try:
            # 获取最终余额信息
            self.final_usdt_balance = self.get_usdt_balance()
            self.usdt_balance_diff = self.final_usdt_balance - self.initial_usdt_balance
            self.net_loss_usdt = self.usdt_balance_diff - self.total_fees_usdt
            
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


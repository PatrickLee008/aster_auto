"""
AsterDEX 现货交易客户端
支持现货交易的完整封装
"""

import json
import time
import requests
import hmac
import hashlib
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AsterSpotClient:
    """
    AsterDEX 现货交易客户端
    """
    
    def __init__(self, api_key: str, secret_key: str, 
                 proxy_host: str = '127.0.0.1', proxy_port: int = 7890, use_proxy: bool = True):
        """
        初始化现货交易客户端
        
        Args:
            api_key (str): API密钥
            secret_key (str): 密钥
            proxy_host (str): 代理服务器地址
            proxy_port (int): 代理服务器端口
            use_proxy (bool): 是否使用代理
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.host = 'https://sapi.asterdex.com'
        
        # 设置代理
        if use_proxy:
            self.proxies = {
                'http': f'socks5://{proxy_host}:{proxy_port}',
                'https': f'socks5://{proxy_host}:{proxy_port}'
            }
        else:
            self.proxies = None
            
        print(f"AsterDEX现货客户端初始化完成")
        if self.proxies:
            print(f"使用代理: {self.proxies['https']}")
        else:
            print("未使用代理")
    
    def _get_server_time(self) -> Optional[int]:
        """获取服务器时间"""
        try:
            response = requests.get(
                self.host + "/api/v1/time",
                proxies=self.proxies,
                timeout=10,
                verify=False
            )
            if response.status_code == 200:
                return response.json()['serverTime']
        except:
            pass
        return None
    
    def _sign_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        对参数进行HMAC SHA256签名
        
        Args:
            params (dict): 待签名的参数
            
        Returns:
            dict: 包含签名的完整参数
        """
        # 清理空值参数，保持原始顺序
        clean_params = {}
        for key, value in params.items():
            if value is not None:
                clean_params[key] = value
        
        # 强制获取最新服务器时间并添加时间戳和接收窗口
        try:
            # 每次都获取最新的服务器时间
            server_time = self._get_server_time()
            if server_time:
                clean_params['timestamp'] = server_time
            else:
                clean_params['timestamp'] = int(round(time.time() * 1000))
        except Exception as e:
            clean_params['timestamp'] = int(round(time.time() * 1000))
            
        if 'recvWindow' not in clean_params:
            clean_params['recvWindow'] = 60000  # 增加到60秒的时间窗口
        
        # 生成查询字符串用于签名 - 关键修复: 使用正确的参数顺序
        # 根据测试发现，timestamp必须在recvWindow之前
        ordered_params = []
        
        # 按照正确顺序添加参数（参考API文档示例）
        param_order = ['symbol', 'side', 'type', 'timeInForce', 'quantity', 'price', 
                      'quoteOrderQty', 'stopPrice', 'newClientOrderId', 'orderId', 
                      'origClientOrderId', 'startTime', 'endTime', 'fromId', 'limit',
                      'timestamp', 'recvWindow']  # timestamp在recvWindow之前
        
        # 按预定义顺序添加存在的参数
        for key in param_order:
            if key in clean_params:
                ordered_params.append(f"{key}={clean_params[key]}")
        
        # 添加任何未在预定义顺序中的其他参数
        for key, value in clean_params.items():
            if key not in param_order:
                ordered_params.append(f"{key}={value}")
        
        query_string = "&".join(ordered_params)
        
        # 使用HMAC SHA256签名 - 使用实例的密钥而不是配置文件
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        
        # 添加签名到参数中
        clean_params['signature'] = signature
        
        
        return clean_params
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                     need_signature: bool = False) -> Optional[Dict[str, Any]]:
        """
        发起HTTP请求
        
        Args:
            method (str): HTTP方法 (GET, POST, DELETE)
            endpoint (str): API端点
            params (dict): 请求参数
            need_signature (bool): 是否需要签名
            
        Returns:
            dict: 响应数据
        """
        url = self.host + endpoint
        
        if params is None:
            params = {}
            
        # 如果需要签名，对参数进行签名
        if need_signature:
            params = self._sign_params(params)
        
        try:
            headers = {
                'User-Agent': 'PythonApp/1.0',
                'Accept': 'application/json',
                'X-MBX-APIKEY': self.api_key
            }
            
            # 禁用SSL验证以避免代理SSL问题
            verify_ssl = False
            
            if method == 'POST':
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                response = requests.post(url, data=params, headers=headers, 
                                       proxies=self.proxies, timeout=30, verify=verify_ssl)
            elif method == 'GET':
                response = requests.get(url, params=params, headers=headers,
                                      proxies=self.proxies, timeout=30, verify=verify_ssl)
            elif method == 'DELETE':
                response = requests.delete(url, data=params, headers=headers,
                                         proxies=self.proxies, timeout=30, verify=verify_ssl)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            # 添加响应内容调试信息
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.text
                    print(f"错误详情: {error_detail}")
                except:
                    pass
            return None
    
    def test_connection(self) -> bool:
        """
        测试与服务器的连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 直接测试ping，避免通过_make_request的复杂逻辑
            response = requests.get(
                self.host + "/api/v1/ping",
                proxies=self.proxies,
                timeout=10,
                verify=False
            )
            if response.status_code == 200:
                print("现货服务器连接正常")
                return True
        except Exception as e:
            print(f"现货服务器连接失败: {e}")
        
        print("现货服务器连接失败")
        return False
    
    # 价格查询相关方法
    
    def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取现货最新价格
        
        Args:
            symbol (str): 交易对符号，如 'BTCUSDT'
            
        Returns:
            dict: 价格信息 {"symbol": "BTCUSDT", "price": "43250.50", "time": 1649666690902}
        """
        result = self._make_request('GET', '/api/v1/ticker/price', {'symbol': symbol})
        if result:
            print(f"获取 {symbol} 现货价格: {result}")
        return result
    
    def get_24hr_ticker(self, symbol: str = None) -> Optional[Dict[str, Any]]:
        """
        获取24小时价格变动统计
        
        Args:
            symbol (str, optional): 交易对符号，不传则返回所有交易对
            
        Returns:
            dict: 24小时统计信息
        """
        params = {'symbol': symbol} if symbol else {}
        return self._make_request('GET', '/api/v1/ticker/24hr', params)
    
    def get_book_ticker(self, symbol: str = None) -> Optional[Dict[str, Any]]:
        """
        获取最优挂单价格
        
        Args:
            symbol (str, optional): 交易对符号，不传则返回所有交易对
            
        Returns:
            dict: 最优挂单信息
        """
        params = {'symbol': symbol} if symbol else {}
        return self._make_request('GET', '/api/v1/ticker/bookTicker', params)
    
    def get_depth(self, symbol: str, limit: int = 100) -> Optional[Dict[str, Any]]:
        """
        获取订单薄深度信息
        
        Args:
            symbol (str): 交易对符号
            limit (int): 返回的深度档数，默认100
            
        Returns:
            dict: 订单薄深度信息，包含 bids 和 asks
        """
        params = {
            'symbol': symbol,
            'limit': limit
        }
        return self._make_request('GET', '/api/v1/depth', params)
    
    # 交易相关方法
    
    def place_order_direct(self, symbol: str, side: str, order_type: str,
                          quantity: Optional[str] = None, price: Optional[str] = None,
                          time_in_force: str = 'GTC') -> Optional[Dict[str, Any]]:
        """
        直接下单方法 - 使用成功的签名逻辑
        """
        try:
            # 获取服务器时间
            server_time = self._get_server_time()
            if not server_time:
                server_time = int(time.time() * 1000)
            
            # 构造订单参数
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'timestamp': server_time,
                'recvWindow': 60000
            }
            
            if quantity:
                params['quantity'] = quantity
            if price:
                params['price'] = price
            if time_in_force and order_type in ['LIMIT', 'STOP', 'TAKE_PROFIT']:
                params['timeInForce'] = time_in_force
            
            # 按正确顺序生成查询字符串
            ordered_params = []
            param_order = ['symbol', 'side', 'type', 'timeInForce', 'quantity', 'price', 
                          'timestamp', 'recvWindow']
            
            for key in param_order:
                if key in params:
                    ordered_params.append(f"{key}={params[key]}")
            
            query_string = "&".join(ordered_params)
            
            # 生成签名 - 使用实例的密钥而不是配置文件
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # 添加签名到参数
            params['signature'] = signature
            
            # 发送请求
            url = self.host + '/api/v1/order'
            headers = {
                'X-MBX-APIKEY': self.api_key,
                'User-Agent': 'PythonApp/1.0',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(
                url,
                data=params,
                headers=headers,
                proxies=self.proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"现货订单已提交: {result}")
                return result
            else:
                print(f"请求失败: {response.status_code} {response.reason}")
                print(f"错误详情: {response.text}")
                return None
                
        except Exception as e:
            print(f"下单错误: {e}")
            return None
    
    def place_order(self, symbol: str, side: str, order_type: str, 
                   quantity: Optional[str] = None, quote_order_qty: Optional[str] = None,
                   price: Optional[str] = None, time_in_force: str = 'GTC',
                   stop_price: Optional[str] = None, client_order_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        下现货订单 - 使用直接签名方法
        
        Args:
            symbol (str): 交易对符号
            side (str): 买卖方向 'BUY' 或 'SELL'
            order_type (str): 订单类型 'LIMIT', 'MARKET', 'STOP', 'TAKE_PROFIT' 等
            quantity (str, optional): 数量
            quote_order_qty (str, optional): 报价资产数量(市价买单用)
            price (str, optional): 价格 (限价单必填)
            time_in_force (str): 时效性 'GTC', 'IOC', 'FOK'
            stop_price (str, optional): 触发价格(止损止盈单必填)
            client_order_id (str, optional): 自定义订单ID
            
        Returns:
            dict: 订单信息
        """
        # 对于复杂参数，仍使用原来的方法
        if quote_order_qty or stop_price or client_order_id:
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type
            }
            
            if quantity:
                params['quantity'] = quantity
            if quote_order_qty:
                params['quoteOrderQty'] = quote_order_qty
            if price:
                params['price'] = price
            if time_in_force and order_type in ['LIMIT', 'STOP', 'TAKE_PROFIT']:
                params['timeInForce'] = time_in_force
            if stop_price:
                params['stopPrice'] = stop_price
            if client_order_id:
                params['newClientOrderId'] = client_order_id
            
            result = self._make_request('POST', '/api/v1/order', params, need_signature=True)
            if result:
                print(f"现货订单已提交: {result}")
            return result
        else:
            # 对于简单的LIMIT/MARKET订单，使用直接方法
            return self.place_order_direct(symbol, side, order_type, quantity, price, time_in_force)
    
    def cancel_order(self, symbol: str, order_id: Optional[int] = None, 
                    client_order_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        撤销订单
        
        Args:
            symbol (str): 交易对符号
            order_id (int, optional): 系统订单ID
            client_order_id (str, optional): 自定义订单ID
            
        Returns:
            dict: 撤销结果
        """
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id 之一")
        
        params = {'symbol': symbol}
        
        if order_id:
            params['orderId'] = order_id
        if client_order_id:
            params['origClientOrderId'] = client_order_id
        
        result = self._make_request('DELETE', '/api/v1/order', params, need_signature=True)
        if result:
            print(f"现货订单已撤销: {result}")
        return result
    
    def get_order(self, symbol: str, order_id: Optional[int] = None, 
                 client_order_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        查询订单
        
        Args:
            symbol (str): 交易对符号
            order_id (int, optional): 系统订单ID
            client_order_id (str, optional): 自定义订单ID
            
        Returns:
            dict: 订单信息
        """
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id 之一")
        
        params = {'symbol': symbol}
        
        if order_id:
            params['orderId'] = order_id
        if client_order_id:
            params['origClientOrderId'] = client_order_id
        
        result = self._make_request('GET', '/api/v1/order', params, need_signature=True)
        if result:
            print(f"现货订单查询结果: {result}")
        return result
    
    def get_open_orders(self, symbol: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        查询当前挂单
        
        Args:
            symbol (str, optional): 交易对符号，不传则查询所有
            
        Returns:
            list: 挂单列表
        """
        params = {'symbol': symbol} if symbol else {}
        result = self._make_request('GET', '/api/v1/openOrders', params, need_signature=True)
        if result:
            print(f"当前挂单: {len(result) if isinstance(result, list) else 'N/A'} 个")
        return result
    
    def get_all_orders(self, symbol: str, order_id: Optional[int] = None,
                      start_time: Optional[int] = None, end_time: Optional[int] = None,
                      limit: int = 500) -> Optional[List[Dict[str, Any]]]:
        """
        查询所有订单(包括历史订单)
        
        Args:
            symbol (str): 交易对符号
            order_id (int, optional): 起始订单ID
            start_time (int, optional): 起始时间戳
            end_time (int, optional): 结束时间戳
            limit (int): 返回数量限制，最大1000
            
        Returns:
            list: 订单列表
        """
        params = {
            'symbol': symbol,
            'limit': min(limit, 1000)
        }
        
        if order_id:
            params['orderId'] = order_id
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        result = self._make_request('GET', '/api/v1/allOrders', params, need_signature=True)
        if result:
            print(f"历史订单查询: {len(result) if isinstance(result, list) else 'N/A'} 个")
        return result
    
    def cancel_all_orders(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        撤销指定交易对的所有订单
        
        Args:
            symbol (str): 交易对
            
        Returns:
            dict: 撤销结果
        """
        result = self._make_request('DELETE', '/api/v1/allOpenOrders', 
                                   {'symbol': symbol}, need_signature=True)
        if result:
            print(f"已撤销 {symbol} 所有现货订单")
        return result
    
    # 账户相关方法
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        获取账户信息
        
        Returns:
            dict: 账户信息
        """
        try:
            # 获取服务器时间
            server_time = self._get_server_time()
            if not server_time:
                server_time = int(time.time() * 1000)
            
            params = {
                'timestamp': server_time,
                'recvWindow': 60000
            }
            
            # 简化签名方式，参照SimpleTradingClient的成功实现
            query_string = f"timestamp={server_time}&recvWindow=60000"
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            params['signature'] = signature
            
            # 直接发送请求
            response = requests.get(
                f"{self.host}/api/v1/account",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key},
                proxies=self.proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                print("账户信息获取成功")
                return response.json()
            else:
                print(f"获取账户信息失败: {response.status_code} {response.text}")
                return None
                
        except Exception as e:
            print(f"获取账户信息异常: {e}")
            return None
    
    def get_trade_list(self, symbol: str, order_id: Optional[int] = None,
                      start_time: Optional[int] = None, end_time: Optional[int] = None,
                      from_id: Optional[int] = None, limit: int = 500) -> Optional[List[Dict[str, Any]]]:
        """
        获取成交历史
        
        Args:
            symbol (str): 交易对符号
            order_id (int, optional): 订单ID
            start_time (int, optional): 起始时间戳
            end_time (int, optional): 结束时间戳
            from_id (int, optional): 起始交易ID
            limit (int): 返回数量限制，最大1000
            
        Returns:
            list: 成交历史列表
        """
        params = {
            'symbol': symbol,
            'limit': min(limit, 1000)
        }
        
        if order_id:
            params['orderId'] = order_id
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        if from_id:
            params['fromId'] = from_id
        
        result = self._make_request('GET', '/api/v1/myTrades', params, need_signature=True)
        if result:
            print(f"成交历史查询: {len(result) if isinstance(result, list) else 'N/A'} 个")
        return result
    
    # 便捷方法
    
    def buy_limit(self, symbol: str, quantity: str, price: str) -> Optional[Dict[str, Any]]:
        """
        限价买入
        """
        return self.place_order(symbol, 'BUY', 'LIMIT', quantity=quantity, price=price)
    
    def sell_limit(self, symbol: str, quantity: str, price: str) -> Optional[Dict[str, Any]]:
        """
        限价卖出
        """
        return self.place_order(symbol, 'SELL', 'LIMIT', quantity=quantity, price=price)
    
    def buy_market(self, symbol: str, quantity: Optional[str] = None, 
                  quote_order_qty: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        市价买入
        
        Args:
            symbol (str): 交易对
            quantity (str, optional): 买入数量
            quote_order_qty (str, optional): 使用报价资产数量买入
        """
        return self.place_order(symbol, 'BUY', 'MARKET', 
                               quantity=quantity, quote_order_qty=quote_order_qty)
    
    def sell_market(self, symbol: str, quantity: str) -> Optional[Dict[str, Any]]:
        """
        市价卖出
        """
        return self.place_order(symbol, 'SELL', 'MARKET', quantity=quantity)


# 示例使用
if __name__ == '__main__':
    # 现货交易需要API密钥，请在AsterDEX官网申请
    API_KEY = "YOUR_API_KEY_HERE"
    SECRET_KEY = "YOUR_SECRET_KEY_HERE"
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("请先设置API_KEY和SECRET_KEY")
        print("在 https://www.asterdex.com 申请API密钥")
    else:
        # 创建现货客户端
        spot_client = AsterSpotClient(API_KEY, SECRET_KEY)
        
        # 测试连接
        if spot_client.test_connection():
            print("\n=== 现货价格查询测试 ===")
            # 查询BTC价格
            btc_price = spot_client.get_price('BTCUSDT')
            
            print("\n=== 现货订单查询测试 ===")
            # 查询当前挂单
            open_orders = spot_client.get_open_orders('BTCUSDT')
            
            print("\n=== 示例：限价买单 (测试，请谨慎使用) ===")
            print("# spot_client.buy_limit('BTCUSDT', '0.001', '45000')")
            
            print("\n现货客户端初始化完成，可以开始交易")
        else:
            print("连接失败，请检查网络和代理设置")
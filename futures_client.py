"""
AsterDEX 期货交易客户端
支持期货合约交易的完整封装
"""

import json
import math
import time
import requests
from typing import Optional, Dict, Any, List
import urllib3

from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AsterFuturesClient:
    """
    AsterDEX 期货交易客户端
    """
    
    def __init__(self, user_address: str, signer_address: str, private_key: str, 
                 proxy_host: str = '127.0.0.1', proxy_port: int = 7890, use_proxy: bool = True):
        """
        初始化期货交易客户端
        
        Args:
            user_address (str): 用户钱包地址
            signer_address (str): 签名钱包地址 
            private_key (str): 签名私钥
            proxy_host (str): 代理服务器地址
            proxy_port (int): 代理服务器端口
            use_proxy (bool): 是否使用代理
        """
        # 确保地址格式正确（checksum格式）
        from web3 import Web3
        try:
            self.user = Web3.to_checksum_address(user_address)
            self.signer = Web3.to_checksum_address(signer_address)
        except Exception as e:
            print(f"⚠️  地址格式转换失败: {e}")
            self.user = user_address
            self.signer = signer_address
            
        self.private_key = private_key
        self.host = 'https://fapi.asterdex.com'
        
        # 设置代理
        if use_proxy:
            self.proxies = {
                'http': f'socks5://{proxy_host}:{proxy_port}',
                'https': f'socks5://{proxy_host}:{proxy_port}'
            }
        else:
            self.proxies = None
            
        print(f"AsterDEX期货客户端初始化完成")
        if self.proxies:
            print(f"使用代理: {self.proxies['https']}")
        else:
            print("未使用代理")
    
    def _sign_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        对参数进行以太坊风格签名
        
        Args:
            params (dict): 待签名的参数
            
        Returns:
            dict: 包含签名的完整参数
        """
        try:
            # print(f"🔐 [期货签名调试] 开始签名参数...")
            # print(f"📋 原始参数: {params}")
            # print(f"👤 用户地址: {self.user}")
            # print(f"✍️  签名地址: {self.signer}")
            # print(f"🔑 私钥长度: {len(self.private_key) if self.private_key else 'None'}")
            
            # 检查私钥是否为None
            if self.private_key is None:
                raise ValueError("私钥为None，请检查配置")
                
            # 生成nonce (微秒时间戳) + 随机数避免冲突
            import random
            nonce = math.trunc(time.time() * 1000000) + random.randint(1, 1000)
            
            # 清理空值参数
            clean_params = {key: value for key, value in params.items() if value is not None}
            
            # 添加必要参数
            clean_params['recvWindow'] = 50000
            clean_params['timestamp'] = int(round(time.time() * 1000))
            
            # print(f"⏰ Nonce: {nonce}")
            # print(f"📅 Timestamp: {clean_params['timestamp']}")
            
            # 生成签名消息
            msg_hash = self._generate_message_hash(clean_params, nonce)
            # print(f"🔒 消息哈希: {msg_hash}")
            
            if msg_hash is None:
                raise ValueError("生成的消息哈希为None")
            
            # 使用私钥签名
            signable_msg = encode_defunct(hexstr=msg_hash)
            signed_message = Account.sign_message(signable_message=signable_msg, private_key=self.private_key)
            
            # 添加签名相关参数
            clean_params['nonce'] = nonce
            clean_params['user'] = self.user
            clean_params['signer'] = self.signer
            clean_params['signature'] = '0x' + signed_message.signature.hex()
            
            # print(f"✅ 签名完成: {clean_params['signature'][:20]}...")
            # print(f"📤 最终参数: {clean_params}")
            
            return clean_params
            
        except Exception as e:
            print(f"❌ 签名失败: {e}")
            print(f"🔑 私钥: {self.private_key}")
            print(f"👤 用户地址: {self.user}")
            print(f"✍️  签名地址: {self.signer}")
            print(f"📋 原始参数: {params}")
            raise
    
    def _generate_message_hash(self, params: Dict[str, Any], nonce: int) -> str:
        """
        生成用于签名的消息哈希
        
        Args:
            params (dict): 参数字典
            nonce (int): 随机数
            
        Returns:
            str: 消息哈希
        """
        # 递归处理参数
        self._trim_dict(params)
        
        # 生成JSON字符串
        json_str = json.dumps(params, sort_keys=True).replace(' ', '').replace('\'', '\"')
        
        # ABI编码
        encoded = encode(['string', 'address', 'address', 'uint256'], 
                        [json_str, self.user, self.signer, nonce])
        
        # 生成Keccak哈希
        keccak_hex = Web3.keccak(encoded).hex()
        
        return keccak_hex
    
    def _trim_dict(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        递归处理参数字典，将所有值转换为字符串
        
        Args:
            params (dict): 参数字典
            
        Returns:
            dict: 处理后的参数字典
        """
        for key in params:
            value = params[key]
            if isinstance(value, list):
                new_value = []
                for item in value:
                    if isinstance(item, dict):
                        new_value.append(json.dumps(self._trim_dict(item)))
                    else:
                        new_value.append(str(item))
                params[key] = json.dumps(new_value)
                continue
            if isinstance(value, dict):
                params[key] = json.dumps(self._trim_dict(value))
                continue
            params[key] = str(value)
        
        return params
    
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
                'Accept': 'application/json'
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
            
            # print(f"📡 响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                # print(f"✅ 成功响应: {result}")
                return result
            else:
                print(f"❌ 请求失败: HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"🚨 错误详情 (JSON): {error_data}")
                except:
                    print(f"🚨 错误详情 (TEXT): {response.text}")
                return None
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求异常: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        测试与服务器的连接，带重试机制
        
        Returns:
            bool: 连接是否成功
        """
        # 在Flask线程中简化连接测试，只尝试一次以避免事件循环问题
        try:
            print(f"期货连接测试 (超时: 10s)")
            
            response = requests.get(
                self.host + "/fapi/v3/ping",
                proxies=self.proxies,
                timeout=10,
                verify=False
            )
            if response.status_code == 200:
                print("期货服务器连接正常")
                return True
        except Exception as e:
            print(f"期货服务器连接失败: {e}")
        
        print("期货服务器连接失败")
        return False
    
    
    # 价格查询相关方法
    
    def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取合约最新价格
        
        Args:
            symbol (str): 交易对符号，如 'BTCUSDT'
            
        Returns:
            dict: 价格信息 {"symbol": "BTCUSDT", "price": "43250.50"}
        """
        result = self._make_request('GET', '/fapi/v3/ticker/price', {'symbol': symbol})
        if result:
            print(f"获取 {symbol} 合约价格: {result}")
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
        return self._make_request('GET', '/fapi/v3/ticker/24hr', params)
    
    # 交易相关方法
    
    def place_order(self, symbol: str, side: str, order_type: str, quantity: str,
                   price: Optional[str] = None, position_side: str = 'BOTH',
                   time_in_force: str = 'GTC', reduce_only: bool = False,
                   client_order_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        下期货合约订单
        
        Args:
            symbol (str): 交易对符号
            side (str): 买卖方向 'BUY' 或 'SELL'
            order_type (str): 订单类型 'LIMIT', 'MARKET', 'STOP', 'TAKE_PROFIT' 等
            quantity (str): 数量
            price (str, optional): 价格 (限价单必填)
            position_side (str): 持仓方向 'LONG', 'SHORT', 'BOTH' (双向持仓时为BOTH)
            time_in_force (str): 时效性 'GTC', 'IOC', 'FOK'
            reduce_only (bool): 是否仅减仓
            client_order_id (str, optional): 自定义订单ID
            
        Returns:
            dict: 订单信息
        """
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity,
            'positionSide': position_side
        }
        
        # 只有限价单才需要timeInForce，市价单不需要
        if order_type in ['LIMIT', 'STOP', 'TAKE_PROFIT', 'STOP_MARKET', 'TAKE_PROFIT_MARKET']:
            params['timeInForce'] = time_in_force
        
        # reduceOnly应该是字符串，且只在需要时添加
        if reduce_only:
            params['reduceOnly'] = 'true'
        
        if price:
            params['price'] = price
            
        if client_order_id:
            params['newClientOrderId'] = client_order_id
        
        result = self._make_request('POST', '/fapi/v3/order', params, need_signature=True)
        if result:
            print(f"期货订单已提交: {result}")
        else:
            print(f"期货下单失败，参数: {params}")
        return result
    
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
        
        result = self._make_request('DELETE', '/fapi/v3/order', params, need_signature=True)
        if result:
            print(f"期货订单已撤销: {result}")
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
        
        result = self._make_request('GET', '/fapi/v3/order', params, need_signature=True)
        if result:
            print(f"期货订单查询结果: {result}")
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
        result = self._make_request('GET', '/fapi/v3/openOrders', params, need_signature=True)
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
        
        result = self._make_request('GET', '/fapi/v3/allOrders', params, need_signature=True)
        if result:
            print(f"历史订单查询: {len(result) if isinstance(result, list) else 'N/A'} 个")
        return result
    
    # 便捷方法
    
    def buy_limit(self, symbol: str, quantity: str, price: str, 
                 reduce_only: bool = False) -> Optional[Dict[str, Any]]:
        """
        限价买入
        """
        return self.place_order(symbol, 'BUY', 'LIMIT', quantity, 
                               price=price, reduce_only=reduce_only)
    
    def sell_limit(self, symbol: str, quantity: str, price: str,
                  reduce_only: bool = False) -> Optional[Dict[str, Any]]:
        """
        限价卖出
        """
        return self.place_order(symbol, 'SELL', 'LIMIT', quantity,
                               price=price, reduce_only=reduce_only)
    
    def buy_market(self, symbol: str, quantity: str) -> Optional[Dict[str, Any]]:
        """
        市价买入
        """
        return self.place_order(symbol, 'BUY', 'MARKET', quantity)
    
    def sell_market(self, symbol: str, quantity: str) -> Optional[Dict[str, Any]]:
        """
        市价卖出
        """
        return self.place_order(symbol, 'SELL', 'MARKET', quantity)
    
    def cancel_all_orders(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        撤销指定交易对的所有订单
        """
        result = self._make_request('DELETE', '/fapi/v3/allOpenOrders', 
                                   {'symbol': symbol}, need_signature=True)
        if result:
            print(f"已撤销 {symbol} 所有订单")
        return result
    
    def get_depth(self, symbol: str, limit: int = 5) -> Optional[Dict[str, Any]]:
        """
        获取深度信息
        
        Args:
            symbol (str): 交易对符号
            limit (int): 档位数量，默认5档
            
        Returns:
            dict: 深度信息 {"bids": [[price, qty], ...], "asks": [[price, qty], ...]}
        """
        params = {'symbol': symbol, 'limit': limit}
        return self._make_request('GET', '/fapi/v3/depth', params)
    
    def get_book_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取最优挂单价格
        
        Args:
            symbol (str): 交易对符号
            
        Returns:
            dict: 最优挂单价格 {"bidPrice": "xxx", "askPrice": "xxx", "bidQty": "xxx", "askQty": "xxx"}
        """
        params = {'symbol': symbol}
        return self._make_request('GET', '/fapi/v3/ticker/bookTicker', params)
    
    def set_leverage(self, symbol: str, leverage: int) -> Optional[Dict[str, Any]]:
        """
        调整开仓杠杆
        
        Args:
            symbol (str): 交易对符号
            leverage (int): 目标杠杆倍数，1到125
            
        Returns:
            dict: 杠杆设置结果 {"leverage": 21, "maxNotionalValue": "1000000", "symbol": "BTCUSDT"}
        """
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        result = self._make_request('POST', '/fapi/v3/leverage', params, need_signature=True)
        if result:
            print(f"杠杆设置成功: {symbol} 杠杆倍数={leverage}倍")
            print(f"最大名义价值: {result.get('maxNotionalValue', 'N/A')}")
        return result
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        获取账户信息
        
        Returns:
            dict: 账户信息，包含资产、持仓等详细信息
        """
        params = {
            'timestamp': int(round(time.time() * 1000)),
            'recvWindow': 50000
        }
        result = self._make_request('GET', '/fapi/v3/account', params, need_signature=True)
        return result
    
    def get_account_balance(self) -> Optional[List[Dict[str, Any]]]:
        """
        获取账户余额 v3
        
        Returns:
            list: 资产余额列表，每个元素包含 asset, balance, availableBalance 等
        """
        params = {
            'timestamp': int(round(time.time() * 1000)),
            'recvWindow': 50000
        }
        result = self._make_request('GET', '/fapi/v3/balance', params, need_signature=True)
        if result:
            print(f"账户余额查询成功: {len(result) if isinstance(result, list) else 'N/A'} 种资产")
        return result
    
    def set_margin_type(self, symbol: str, margin_type: str) -> Optional[Dict[str, Any]]:
        """
        变换逐全仓模式
        
        Args:
            symbol (str): 交易对符号
            margin_type (str): 保证金模式 ISOLATED(逐仓), CROSSED(全仓)
            
        Returns:
            dict: 设置结果 {"code": 200, "msg": "success"}
        """
        params = {
            'symbol': symbol,
            'marginType': margin_type
        }
        result = self._make_request('POST', '/fapi/v3/marginType', params, need_signature=True)
        if result and result.get('code') == 200:
            mode_name = "逐仓" if margin_type == "ISOLATED" else "全仓"
            print(f"仓位模式设置成功: {symbol} -> {mode_name}")
        return result
    
    def place_batch_orders(self, batch_orders: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """
        批量下订单
        
        Args:
            batch_orders (list): 订单列表，最多支持5个订单
            
        Returns:
            list: 订单结果列表
        """
        if not batch_orders or len(batch_orders) > 5:
            raise ValueError("批量订单数量必须在1-5之间")
        
        params = {
            'batchOrders': batch_orders
        }
        
        result = self._make_request('POST', '/fapi/v3/batchOrders', params, need_signature=True)
        if result:
            print(f"批量订单已提交: {len(batch_orders)}个订单")
            for i, order_result in enumerate(result):
                if isinstance(order_result, dict) and 'orderId' in order_result:
                    print(f"  订单{i+1}: ID {order_result['orderId']} - {order_result.get('side', 'N/A')}")
                else:
                    print(f"  订单{i+1}: {order_result}")
        else:
            print(f"批量下单失败，参数: {params}")
        return result
    
    def cancel_batch_orders(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        批量撤销指定交易对的所有订单
        
        Args:
            symbol (str): 交易对符号
            
        Returns:
            dict: 撤销结果
        """
        params = {'symbol': symbol}
        result = self._make_request('DELETE', '/fapi/v3/batchOrders', params, need_signature=True)
        if result:
            print(f"批量撤销订单成功: {symbol}")
        return result
    
    def get_position_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取指定交易对的持仓信息
        
        Args:
            symbol (str): 交易对符号
            
        Returns:
            dict: 持仓信息，包含杠杆倍数和仓位模式
        """
        account_info = self.get_account_info()
        if account_info and 'positions' in account_info:
            for position in account_info['positions']:
                if position.get('symbol') == symbol:
                    return position
        return None


# 示例使用
if __name__ == '__main__':
    # 从tx.py导入配置信息
    try:
        from tx import user, signer, priKey
        
        # 创建期货客户端
        futures_client = AsterFuturesClient(user, signer, priKey)
        
        # 测试连接
        if futures_client.test_connection():
            print("\n=== 期货价格查询测试 ===")
            # 查询BTC价格
            btc_price = futures_client.get_price('BTCUSDT')
            
            print("\n=== 期货订单查询测试 ===")
            # 查询当前挂单
            open_orders = futures_client.get_open_orders('BTCUSDT')
            
            print("\n=== 示例：限价买单 (测试，请谨慎使用) ===")
            print("# futures_client.buy_limit('SANDUSDT', '10', '0.30')")
            
            print("\n期货客户端初始化完成，可以开始交易")
        else:
            print("连接失败，请检查网络和代理设置")
            
    except ImportError:
        print("无法导入tx.py中的配置，请手动设置:")
        print("futures_client = AsterFuturesClient('用户地址', '签名地址', '私钥')")
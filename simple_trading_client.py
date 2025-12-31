#!/usr/bin/env python3
"""
简化交易客户端 - 使用验证成功的签名方法
专门为刷量策略设计，确保可靠运行
"""

import hmac
import hashlib
import time
import requests
from typing import Optional, Dict, Any
from config_env import SPOT_CONFIG, PROXY_CONFIG

class SimpleTradingClient:
    """简化交易客户端 - 确保签名验证成功"""
    
    def __init__(self, api_key=None, secret_key=None):
        """初始化客户端"""
        if not api_key or not secret_key:
            raise ValueError("API密钥和密钥不能为空，必须从钱包配置中提供")
        self.api_key = api_key
        self.secret_key = secret_key
        self.host = 'https://sapi.asterdex.com'
        
        # 设置代理
        if PROXY_CONFIG['enabled']:
            proxy_url = f"{PROXY_CONFIG['type']}://{PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}"
            self.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        else:
            self.proxies = None
        
        print(f"简化交易客户端初始化完成")
        if self.proxies:
            print(f"使用代理: {self.proxies['https']}")
    
    def get_server_time(self) -> int:
        """获取服务器时间"""
        try:
            response = requests.get(
                f"{self.host}/api/v1/time",
                proxies=self.proxies,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()['serverTime']
        except:
            pass
        return int(time.time() * 1000)
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            response = requests.get(
                f"{self.host}/api/v1/ping",
                proxies=self.proxies,
                timeout=10
            )
            if response.status_code == 200:
                print("服务器连接正常")
                return True
        except:
            pass
        print("服务器连接失败")
        return False
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """获取账户信息"""
        try:
            server_time = self.get_server_time()
            
            params = {
                'timestamp': server_time,
                'recvWindow': 60000
            }
            
            # 生成签名
            query_string = f"timestamp={server_time}&recvWindow=60000"
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            params['signature'] = signature
            
            response = requests.get(
                f"{self.host}/api/v1/account",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key},
                proxies=self.proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取账户信息失败: {response.text}")
                return None
                
        except Exception as e:
            print(f"获取账户信息错误: {e}")
            return None
    
    def get_book_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取最优挂单价格"""
        try:
            response = requests.get(
                f"{self.host}/api/v1/ticker/bookTicker",
                params={'symbol': symbol},
                proxies=self.proxies,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def get_depth(self, symbol: str, limit: int = 5) -> Optional[Dict[str, Any]]:
        """获取深度数据"""
        try:
            response = requests.get(
                f"{self.host}/api/v1/depth",
                params={'symbol': symbol, 'limit': limit},
                proxies=self.proxies,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def place_order(self, symbol: str, side: str, order_type: str,
                   quantity: str, price: str, time_in_force: str = 'GTC') -> Optional[Dict[str, Any]]:
        """
        下单 - 使用验证成功的签名方法
        """
        try:
            server_time = self.get_server_time()
            
            # 构造订单参数
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'timeInForce': time_in_force,
                'quantity': quantity,
                'price': price,
                'timestamp': server_time,
                'recvWindow': 60000
            }
            
            # 按正确顺序生成查询字符串
            ordered_params = []
            param_order = ['symbol', 'side', 'type', 'timeInForce', 'quantity', 'price', 
                          'timestamp', 'recvWindow']
            
            for key in param_order:
                if key in params:
                    ordered_params.append(f"{key}={params[key]}")
            
            query_string = "&".join(ordered_params)
            
            # 生成签名 - 使用成功的方法
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # 添加签名到参数
            params['signature'] = signature
            
            # 发送请求
            response = requests.post(
                f"{self.host}/api/v1/order",
                data=params,
                headers={
                    'X-MBX-APIKEY': self.api_key,
                    'User-Agent': 'PythonApp/1.0',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                proxies=self.proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                error_msg = f"下单失败: HTTP {response.status_code}"
                error_detail = f"错误详情: {response.text}"
                print(error_msg)
                print(error_detail)
                
                # 尝试解析JSON错误信息
                try:
                    error_json = response.json()
                    if 'code' in error_json and 'msg' in error_json:
                        api_error = f"API错误码: {error_json['code']}, 错误信息: {error_json['msg']}"
                        print(api_error)
                        # 将错误信息存储到result中，让调用方能够获取并记录到日志
                        return {'error': True, 'status_code': response.status_code, 
                               'error_code': error_json['code'], 'error_msg': error_json['msg']}
                except:
                    pass
                # 如果无法解析JSON，返回基本错误信息
                return {'error': True, 'status_code': response.status_code, 'error_text': response.text}
                
        except Exception as e:
            print(f"下单错误: {e}")
            return None
    
    def cancel_order(self, symbol: str, order_id: int) -> Optional[Dict[str, Any]]:
        """撤销订单"""
        try:
            server_time = self.get_server_time()
            
            params = {
                'symbol': symbol,
                'orderId': order_id,
                'timestamp': server_time,
                'recvWindow': 60000
            }
            
            # 生成查询字符串
            query_parts = []
            for key in ['symbol', 'orderId', 'timestamp', 'recvWindow']:
                if key in params:
                    query_parts.append(f"{key}={params[key]}")
            
            query_string = "&".join(query_parts)
            
            # 生成签名
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            params['signature'] = signature
            
            response = requests.delete(
                f"{self.host}/api/v1/order",
                data=params,
                headers={
                    'X-MBX-APIKEY': self.api_key,
                    'User-Agent': 'PythonApp/1.0'
                },
                proxies=self.proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"订单已撤销: ID {order_id}")
                return result
            else:
                print(f"撤销失败: {response.text}")
                return None
                
        except Exception as e:
            print(f"撤销错误: {e}")
            return None
    
    def get_order(self, symbol: str, order_id: int) -> Optional[Dict[str, Any]]:
        """查询订单状态"""
        try:
            server_time = self.get_server_time()
            
            params = {
                'symbol': symbol,
                'orderId': order_id,
                'timestamp': server_time,
                'recvWindow': 60000
            }
            
            # 生成查询字符串
            query_parts = []
            for key in ['symbol', 'orderId', 'timestamp', 'recvWindow']:
                if key in params:
                    query_parts.append(f"{key}={params[key]}")
            
            query_string = "&".join(query_parts)
            
            # 生成签名
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            params['signature'] = signature
            
            response = requests.get(
                f"{self.host}/api/v1/order",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key},
                proxies=self.proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"查询订单失败: {response.text}")
                return None
                
        except Exception as e:
            print(f"查询订单错误: {e}")
            return None
    
    def get_exchange_info(self, symbol: str = None) -> Optional[Dict[str, Any]]:
        """获取交易所信息，包括交易对的精度要求"""
        try:
            url = f"{self.host}/api/v1/exchangeInfo"
            if symbol:
                url += f"?symbol={symbol}"
            
            response = requests.get(
                url,
                proxies=self.proxies,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取交易所信息失败: {response.text}")
                return None
                
        except Exception as e:
            print(f"获取交易所信息错误: {e}")
            return None
    
    def get_open_orders(self, symbol: str = None) -> Optional[Dict[str, Any]]:
        """获取当前未成交订单"""
        try:
            server_time = self.get_server_time()
            
            # 构造参数，使用与get_account_info相同的模式
            if symbol:
                query_string = f"symbol={symbol}&timestamp={server_time}&recvWindow=60000"
                params = {
                    'symbol': symbol,
                    'timestamp': server_time,
                    'recvWindow': 60000
                }
            else:
                query_string = f"timestamp={server_time}&recvWindow=60000"
                params = {
                    'timestamp': server_time,
                    'recvWindow': 60000
                }
            
            # 生成签名 - 使用与get_account_info完全相同的方法
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            params['signature'] = signature
            
            response = requests.get(
                f"{self.host}/api/v1/openOrders",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key},
                proxies=self.proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取未成交订单失败: {response.text}")
                return None
                
        except Exception as e:
            print(f"获取未成交订单错误: {e}")
            return None
    
    def get_commission_rate(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取交易对的手续费率"""
        try:
            server_time = self.get_server_time()
            
            params = {
                'symbol': symbol,
                'timestamp': server_time,
                'recvWindow': 60000
            }
            
            # 生成查询字符串
            query_parts = []
            query_parts.append(f"symbol={symbol}")
            query_parts.append(f"timestamp={server_time}")
            query_parts.append(f"recvWindow=60000")
            
            query_string = "&".join(query_parts)
            
            # 生成签名
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            params['signature'] = signature
            
            response = requests.get(
                f"{self.host}/api/v1/commissionRate",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key},
                proxies=self.proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取手续费率失败: {response.text}")
                return None
                
        except Exception as e:
            print(f"获取手续费率错误: {e}")
            return None

if __name__ == '__main__':
    # 测试简化客户端
    print("测试简化交易客户端")
    client = SimpleTradingClient()
    
    if client.test_connection():
        print("连接测试成功")
        
        # 测试下单
        print("\n测试下单...")
        result = client.place_order(
            symbol='ASTERUSDT',
            side='SELL',
            order_type='LIMIT',
            quantity='8.00',
            price='0.69585',
            time_in_force='GTC'
        )
        
        if result:
            print("✅ 简化客户端下单成功!")
            # 立即撤销测试订单
            client.cancel_order('ASTERUSDT', result.get('orderId'))
        else:
            print("❌ 简化客户端下单失败")
    else:
        print("连接测试失败")
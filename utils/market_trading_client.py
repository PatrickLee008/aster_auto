#!/usr/bin/env python3
"""
市价单交易客户端 - 单独处理市价单逻辑
专门为市价补单策略设计，不影响原有的限价单逻辑
"""

import hmac
import hashlib
import time
import requests
from typing import Optional, Dict, Any
from config_env import SPOT_CONFIG, PROXY_CONFIG

class MarketTradingClient:
    """市价单交易客户端 - 专门处理市价单"""
    
    def __init__(self, api_key=None, secret_key=None):
        """初始化客户端"""
        if not api_key or not secret_key:
            raise ValueError("API密钥和密钥不能为空，必须从钱包配置中提供")
        self.api_key = api_key
        self.secret_key = secret_key
        self.host = 'https://sapi.asterdex.com'
        
        # 代理配置始终使用全局设置
        if PROXY_CONFIG['enabled']:
            proxy_url = f"{PROXY_CONFIG['type']}://{PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}"
            self.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        else:
            self.proxies = None
        
        print(f"市价单交易客户端初始化完成")
        print("使用钱包提供的API配置")
        if self.proxies:
            print(f"使用全局代理配置: {self.proxies['https']}")
        else:
            print("未启用代理")
    
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
    
    def place_market_order(self, symbol: str, side: str, quantity: str) -> Optional[Dict[str, Any]]:
        """
        下达市价单 - 专门处理MARKET订单类型
        """
        try:
            server_time = self.get_server_time()
            
            # 构造市价单参数 - 不包含price和timeInForce
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity,
                'timestamp': server_time,
                'recvWindow': 60000
            }
            
            # 按标准顺序生成查询字符串（市价单专用顺序）
            ordered_params = []
            param_order = ['symbol', 'side', 'type', 'quantity', 'timestamp', 'recvWindow']
            
            for key in param_order:
                if key in params:
                    ordered_params.append(f"{key}={params[key]}")
            
            query_string = "&".join(ordered_params)
            
            # 生成签名
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
                print(f"市价单成功: ID {result.get('orderId')}")
                return result
            else:
                print(f"市价单失败: HTTP {response.status_code}")
                print(f"错误详情: {response.text}")
                # 尝试解析JSON错误信息
                try:
                    error_json = response.json()
                    if 'code' in error_json and 'msg' in error_json:
                        print(f"API错误码: {error_json['code']}")
                        print(f"API错误信息: {error_json['msg']}")
                except:
                    pass
                return None
                
        except Exception as e:
            print(f"市价单错误: {e}")
            return None
    
    def place_market_buy_order(self, symbol: str, quantity: str) -> Optional[Dict[str, Any]]:
        """下达市价买入订单"""
        return self.place_market_order(symbol, 'BUY', quantity)
    
    def place_market_sell_order(self, symbol: str, quantity: str) -> Optional[Dict[str, Any]]:
        """下达市价卖出订单"""
        return self.place_market_order(symbol, 'SELL', quantity)


if __name__ == '__main__':
    # 测试市价单客户端
    print("测试市价单交易客户端")
    client = MarketTradingClient()
    
    print("市价单客户端初始化完成")
    print("注意: 这是专门用于市价补单的客户端")
    print("与原有的限价单客户端完全独立，不会相互影响")
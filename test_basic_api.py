#!/usr/bin/env python3
"""
基础API测试 - 使用最简单的方式测试API
"""

import requests
import hmac
import hashlib
import time

def test_basic_api():
    """测试最基础的API调用"""
    
    # 你的API凭证
    api_key = '395f519b65a36d2b4e326abe8554af9b0e5745c5219b0863d0ab14818b0099eb'
    secret_key = 'f272c49bc65b4375420e262497441b7a42991864e921ffb30cd0c449405da859'
    base_url = 'https://sapi.asterdex.com'
    
    print("🧪 AsterDEX API基础测试")
    print("=" * 50)
    
    # 1. 测试公开API（无需认证）
    try:
        print("\n📡 测试公开API (ping)...")
        response = requests.get(f"{base_url}/api/v1/ping", timeout=10)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print("✅ 服务器连接正常")
        else:
            print(f"❌ 服务器连接失败: {response.text}")
            return
    except Exception as e:
        print(f"❌ 网络连接错误: {e}")
        return
    
    # 2. 测试服务器时间（无需认证）
    try:
        print("\n⏰ 测试服务器时间...")
        response = requests.get(f"{base_url}/api/v1/time", timeout=10)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            time_data = response.json()
            server_time = time_data['serverTime']
            print(f"✅ 服务器时间: {server_time}")
            print(f"本地时间: {int(time.time() * 1000)}")
            print(f"时间差: {abs(server_time - int(time.time() * 1000))}ms")
        else:
            print(f"❌ 获取服务器时间失败: {response.text}")
    except Exception as e:
        print(f"❌ 服务器时间错误: {e}")
    
    # 3. 测试交易对信息（无需认证）
    try:
        print("\n📊 测试交易对信息...")
        response = requests.get(f"{base_url}/api/v1/ticker/bookTicker?symbol=LISAUSDT", timeout=10)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            ticker_data = response.json()
            print(f"✅ 交易对信息获取成功")
            print(f"买一价: {ticker_data.get('bidPrice', 'N/A')}")
            print(f"卖一价: {ticker_data.get('askPrice', 'N/A')}")
        else:
            print(f"❌ 交易对信息失败: {response.text}")
    except Exception as e:
        print(f"❌ 交易对信息错误: {e}")
    
    # 4. 测试需要签名的API（账户信息）
    try:
        print("\n🔐 测试账户信息API...")
        
        # 获取服务器时间用于签名
        time_response = requests.get(f"{base_url}/api/v1/time", timeout=10)
        if time_response.status_code == 200:
            server_time = time_response.json()['serverTime']
        else:
            server_time = int(time.time() * 1000)
        
        # 构建签名参数
        params = {
            'timestamp': server_time,
            'recvWindow': 60000
        }
        
        # 生成签名
        query_string = f"timestamp={server_time}&recvWindow=60000"
        signature = hmac.new(
            secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        params['signature'] = signature
        
        # 发送请求
        response = requests.get(
            f"{base_url}/api/v1/account",
            params=params,
            headers={
                'X-MBX-APIKEY': api_key,
                'User-Agent': 'TestClient/1.0'
            },
            timeout=30
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✅ API认证成功！")
            account_data = response.json()
            balances = account_data.get('balances', [])
            print(f"账户余额种类: {len(balances)}")
            
            # 显示有余额的资产
            for balance in balances:
                free_amount = float(balance.get('free', 0))
                if free_amount > 0:
                    print(f"  {balance['asset']}: {free_amount}")
        else:
            print(f"❌ API认证失败")
            print(f"完整错误: {response.text}")
            
            # 尝试解析错误信息
            try:
                error_data = response.json()
                error_code = error_data.get('code', 'Unknown')
                error_msg = error_data.get('msg', 'Unknown')
                print(f"错误代码: {error_code}")
                print(f"错误信息: {error_msg}")
            except:
                pass
                
    except Exception as e:
        print(f"❌ 账户API测试异常: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 测试完成")

if __name__ == '__main__':
    test_basic_api()
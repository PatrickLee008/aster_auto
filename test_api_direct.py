#!/usr/bin/env python3
"""
测试API直连（不使用代理）
验证API密钥是否有效
"""

import requests
import hmac
import hashlib
import time

# 使用你的API凭证
api_key = '395f519b65a36d2b4e326abe8554af9b0e5745c5219b0863d0ab14818b0099eb'
secret_key = 'f272c49bc65b4375420e262497441b7a42991864e921ffb30cd0c449405da859'
host = 'https://sapi.asterdex.com'

def test_api_direct():
    """直连测试API"""
    print("🧪 测试API直连（不使用代理）")
    print("=" * 50)
    
    # 1. 测试公开API
    try:
        print("\n📡 测试公开API...")
        response = requests.get(f"{host}/api/v1/ping", timeout=10)
        if response.status_code == 200:
            print("✅ 公开API连接成功")
        else:
            print(f"❌ 公开API失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 公开API错误: {e}")
        return False
    
    # 2. 测试需要签名的API
    try:
        print("\n🔐 测试账户信息API...")
        server_time = int(time.time() * 1000)
        
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
        
        response = requests.get(
            f"{host}/api/v1/account",
            params=params,
            headers={'X-MBX-APIKEY': api_key},
            timeout=30
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text[:500]}...")
        
        if response.status_code == 200:
            print("✅ 账户API直连成功")
            data = response.json()
            balances = data.get('balances', [])
            print(f"账户余额数量: {len(balances)}")
            for balance in balances[:5]:  # 只显示前5个
                if float(balance['free']) > 0:
                    print(f"  {balance['asset']}: {balance['free']}")
            return True
        else:
            print(f"❌ 账户API失败: {response.status_code}")
            print(f"错误详情: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 账户API错误: {e}")
        return False

if __name__ == '__main__':
    success = test_api_direct()
    if success:
        print("\n✅ API凭证验证成功！问题可能在于代理IP限制")
    else:
        print("\n❌ API凭证本身有问题，需要检查密钥权限")
#!/usr/bin/env python3
"""
Bright Data 代理连接测试脚本
用于调试代理连接问题
"""

import sys
import os
import time
import requests
from config_env import get_env, get_env_bool

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_direct_connection():
    """测试直接连接（无代理）"""
    print("=== 直接连接测试 ===")
    try:
        start_time = time.time()
        response = requests.get('https://lumtest.com/myip.json', timeout=15)
        latency = round((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            ip_info = response.json()
            current_ip = ip_info.get('ip', ip_info.get('current_ip', 'unknown'))
            country = ip_info.get('country', 'Unknown')
            print(f"✅ 直接连接成功")
            print(f"   IP: {current_ip}")
            print(f"   位置: {country}")
            print(f"   延迟: {latency}ms")
        else:
            print(f"❌ 直接连接失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ 直接连接错误: {e}")


def test_bright_data_proxy():
    """测试 Bright Data 代理连接"""
    print("\n=== Bright Data 代理连接测试 ===")
    
    # 从环境变量读取配置
    enabled = get_env_bool('BRIGHTDATA_ENABLED', False)
    customer = get_env('BRIGHTDATA_CUSTOMER', '')
    password = get_env('BRIGHTDATA_PASSWORD', '')
    zone = get_env('BRIGHTDATA_ZONE', 'aster')
    country = get_env('BRIGHTDATA_COUNTRY', 'us')
    host = get_env('BRIGHTDATA_HOST', 'brd.superproxy.io')
    port = get_env('BRIGHTDATA_PORT', '33335')
    
    print(f"配置状态: enabled={enabled}")
    print(f"客户ID: {customer}")
    print(f"区域: {zone}")
    print(f"目标国家: {country}")
    print(f"代理服务器: {host}:{port}")
    
    if not enabled:
        print("❌ Bright Data 未启用，请先在 .env 文件中设置 BRIGHTDATA_ENABLED=true")
        return False
    
    if not customer or not password:
        print("❌ Bright Data 凭证未配置，请检查 BRIGHTDATA_CUSTOMER 和 BRIGHTDATA_PASSWORD")
        return False
    
    # 测试不同格式的用户名
    session_id = f"test{int(time.time())}"
    
    # 格式1: 住宅代理
    username1 = f"{customer}-country-{country}-session-{session_id}"
    print(f"\n--- 测试格式1: 住宅代理 ---")
    print(f"用户名: {username1}")
    test_proxy_connection(username1, password, host, port)
    
    # 格式2: 带zone的格式
    username2 = f"{customer}-zone-{zone}-country-{country}-session-{session_id}"
    print(f"\n--- 测试格式2: 带zone格式 ---")
    print(f"用户名: {username2}")
    test_proxy_connection(username2, password, host, port)
    
    # 格式3: 简单格式
    username3 = f"{customer}-session-{session_id}"
    print(f"\n--- 测试格式3: 简单格式 ---")
    print(f"用户名: {username3}")
    test_proxy_connection(username3, password, host, port)
    
    return True


def test_proxy_connection(username, password, host, port):
    """测试单个代理连接"""
    try:
        proxy_url = f"http://{username}:{password}@{host}:{port}"
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        print(f"   正在测试代理连接...")
        
        start_time = time.time()
        response = requests.get(
            'https://lumtest.com/myip.json',
            proxies=proxies,
            timeout=15,
            headers={'User-Agent': 'AsterAuto-ProxyTest/1.0'}
        )
        
        latency = round((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            ip_info = response.json()
            current_ip = ip_info.get('ip', ip_info.get('current_ip', 'unknown'))
            country = ip_info.get('country', ip_info.get('geo', {}).get('country', 'Unknown'))
            region = ip_info.get('region', ip_info.get('geo', {}).get('region', 'Unknown'))
            
            print(f"   ✅ 代理连接成功")
            print(f"   IP: {current_ip}")
            print(f"   位置: {region}, {country}")
            print(f"   延迟: {latency}ms")
            
            return True
        else:
            print(f"   ❌ 代理连接失败: HTTP {response.status_code}")
            print(f"   响应: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout as e:
        print(f"   ⏱️ 代理连接超时: {e}")
        return False
    except requests.exceptions.ProxyError as e:
        print(f"   🚫 代理错误: {e}")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"   🔌 连接错误: {e}")
        return False
    except Exception as e:
        print(f"   ❌ 代理连接错误: {type(e).__name__} - {e}")
        return False


def test_api_connection():
    """测试API连接"""
    print("\n=== API 连接测试 ===")
    try:
        start_time = time.time()
        response = requests.get('https://sapi.asterdex.com/api/v1/ping', timeout=10)
        latency = round((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            print(f"✅ API连接正常")
            print(f"   延迟: {latency}ms")
        else:
            print(f"❌ API连接失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ API连接错误: {e}")


def main():
    print("🔍 Bright Data 代理连接测试工具")
    print("=" * 50)
    
    # 测试直接连接
    test_direct_connection()
    
    # 测试代理连接
    test_bright_data_proxy()
    
    # 测试API连接
    test_api_connection()
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("\n常见问题排查:")
    print("1. 检查环境变量配置是否正确")
    print("2. 确认Bright Data账户是否有效")
    print("3. 验证代理凭据是否正确")
    print("4. 检查网络连接是否正常")
    print("5. 尝试使用不同的代理格式")


if __name__ == '__main__':
    main()
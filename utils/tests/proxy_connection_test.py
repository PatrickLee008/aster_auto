# -*- coding: utf-8 -*-
"""
代理连接测试工具
用于测试Smartproxy连接问题
"""

import requests
import sys
import os
import time

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config_env import get_env

def test_proxy_connection():
    """测试代理连接"""
    print("=== Smartproxy Connection Test ===")
    
    # 读取配置
    base_username = get_env('SMARTPROXY_BASE_USERNAME', '')
    password = get_env('SMARTPROXY_PASSWORD', '')
    host = get_env('SMARTPROXY_RESIDENTIAL_HOST', 'gate.decodo.com')
    port = int(get_env('SMARTPROXY_RESIDENTIAL_PORT', '10001'))
    
    if not base_username or not password:
        print("[ERROR] Missing Smartproxy configuration")
        print("Please set environment variables:")
        print("  SMARTPROXY_BASE_USERNAME")
        print("  SMARTPROXY_PASSWORD")
        return False
    
    print(f"Base username: {base_username}")
    print(f"Proxy host: {host}:{port}")
    print()
    
    # 测试不同的用户名格式
    test_cases = [
        {
            'name': 'Simple format (Recommended)',
            'username': f"user-{base_username}",
        },
        {
            'name': 'With session ID',
            'username': f"user-{base_username}-session-test001",
        },
        {
            'name': 'Country specified',
            'username': f"user-{base_username}-country-us",
        },
        {
            'name': 'Full format (City + Session)',
            'username': f"user-{base_username}-country-us-city-newyork-session-test002",
        }
    ]
    
    successful_format = None
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['name']}")
        print(f"Username: {test_case['username']}")
        
        result = test_single_proxy_format(
            username=test_case['username'],
            password=password,
            host=host,
            port=port
        )
        
        if result['success']:
            print(f"[SUCCESS] {test_case['name']}")
            print(f"IP: {result['ip']}")
            print(f"Location: {result['location']}")
            if not successful_format:
                successful_format = test_case['username']
        else:
            print(f"[FAILED] {result['error']}")
        
        print("-" * 50)
        time.sleep(1)  # 避免请求过快
    
    if successful_format:
        print(f"\n[RECOMMENDATION] Use this format: {successful_format}")
        return True
    else:
        print(f"\n[ERROR] All proxy formats failed")
        return False

def test_single_proxy_format(username: str, password: str, host: str, port: int) -> dict:
    """测试单个代理格式"""
    try:
        proxy_url = f"http://{username}:{password}@{host}:{port}"
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        # 使用官方测试URL
        test_url = 'https://ip.decodo.com/json'
        
        response = requests.get(
            test_url,
            proxies=proxies,
            timeout=15,
            headers={'User-Agent': 'AsterAuto-ProxyTest/1.0'}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # 解析IP信息
            ip = data.get('proxy', {}).get('ip', 'unknown')
            
            # 解析位置信息
            country = data.get('country', {})
            if isinstance(country, dict):
                country_name = country.get('name', 'Unknown')
            else:
                country_name = str(country)
            
            city = data.get('city', {})
            if isinstance(city, dict):
                city_name = city.get('name', 'Unknown')
                state_name = city.get('state', 'Unknown')
                location = f"{city_name}, {state_name}, {country_name}"
            else:
                location = f"{country_name}"
            
            return {
                'success': True,
                'ip': ip,
                'location': location,
                'response_data': data
            }
        else:
            return {
                'success': False,
                'error': f"HTTP {response.status_code}: {response.text[:100]}"
            }
            
    except requests.exceptions.ProxyError as e:
        return {'success': False, 'error': f"Proxy connection failed: {e}"}
    except requests.exceptions.Timeout as e:
        return {'success': False, 'error': f"Connection timeout: {e}"}
    except requests.exceptions.ConnectionError as e:
        return {'success': False, 'error': f"Connection error: {e}"}
    except Exception as e:
        return {'success': False, 'error': f"Unknown error: {e}"}

def test_direct_connection():
    """测试直接连接（无代理）"""
    print("=== Direct Connection Test (No Proxy) ===")
    try:
        response = requests.get(
            'https://ip.decodo.com/json',
            timeout=10,
            headers={'User-Agent': 'AsterAuto-DirectTest/1.0'}
        )
        
        if response.status_code == 200:
            data = response.json()
            ip = data.get('ip', 'unknown')
            
            country = data.get('country', {})
            if isinstance(country, dict):
                country_name = country.get('name', 'Unknown')
            else:
                country_name = str(country)
                
            print(f"[SUCCESS] Direct connection")
            print(f"Your IP: {ip}")
            print(f"Location: {country_name}")
            return True
        else:
            print(f"[ERROR] HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Direct connection failed: {e}")
        return False

if __name__ == '__main__':
    # 测试直接连接
    print("Step 1: Testing direct connection...")
    direct_ok = test_direct_connection()
    print()
    
    # 测试代理连接
    print("Step 2: Testing proxy connection...")
    proxy_ok = test_proxy_connection()
    
    print("\n=== Test Summary ===")
    print(f"Direct connection: {'OK' if direct_ok else 'FAILED'}")
    print(f"Proxy connection: {'OK' if proxy_ok else 'FAILED'}")
    
    if proxy_ok:
        print("\n[NEXT STEP] Proxy is working! You can now run the trading strategy.")
    else:
        print("\n[TROUBLESHOOTING] Check your Smartproxy configuration.")
    
    sys.exit(0 if proxy_ok else 1)
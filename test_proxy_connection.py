#!/usr/bin/env python3
"""
手动测试 Smartproxy 代理连接
"""

import sys
import requests
from config_env import load_environment, get_env

# 加载环境变量
load_environment()

def test_proxy():
    """测试代理连接"""
    print("=== Smartproxy 代理连接测试 ===\n")
    
    # 读取配置
    base_username = get_env('SMARTPROXY_BASE_USERNAME', '')
    password = get_env('SMARTPROXY_PASSWORD', '')
    host = get_env('SMARTPROXY_RESIDENTIAL_HOST', 'gate.decodo.com')
    port = int(get_env('SMARTPROXY_RESIDENTIAL_PORT', '10001'))
    
    if not base_username or not password:
        print("❌ 错误: 未配置 SMARTPROXY_BASE_USERNAME 或 SMARTPROXY_PASSWORD")
        return False
    
    print(f"📋 配置信息:")
    print(f"   用户名: {base_username[:3]}***{base_username[-3:]}")
    print(f"   密码: ***")
    print(f"   主机: {host}")
    print(f"   端口: {port}")
    print()
    
    # 构造代理URL（测试任务ID: 9999）
    session_id = "task9999"
    username_with_location = f"user-{base_username}-country-us-session-{session_id}"
    proxy_url = f"http://{username_with_location}:{password}@{host}:{port}"
    
    print(f"🔗 代理URL: http://{username_with_location}:***@{host}:{port}")
    print()
    
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    # 测试连接
    test_url = 'https://ip.decodo.com/json'
    
    print(f"🔍 测试连接: {test_url}")
    print(f"⏱️ 超时设置: 15秒")
    print()
    
    try:
        print("⏳ 正在连接...")
        response = requests.get(
            test_url,
            proxies=proxies,
            timeout=15,
            headers={'User-Agent': 'AsterAuto/1.0'}
        )
        
        if response.status_code == 200:
            print(f"✅ 连接成功! HTTP {response.status_code}")
            print()
            
            try:
                ip_info = response.json()
                
                # Decodo API 的 IP 在 proxy.ip 字段
                current_ip = ip_info.get('proxy', {}).get('ip', 'unknown')
                
                # 获取国家信息
                country = ip_info.get('country', {})
                if isinstance(country, dict):
                    country_name = country.get('name', 'Unknown')
                else:
                    country_name = str(country)
                
                # 获取城市和州信息
                city = ip_info.get('city', {})
                if isinstance(city, dict):
                    city_name = city.get('name', 'Unknown')
                    state_name = city.get('state', 'Unknown')
                    region = f"{city_name}, {state_name}"
                else:
                    region = ip_info.get('region', 'Unknown')
                
                # 获取ISP信息
                isp = ip_info.get('isp', {})
                isp_name = isp.get('isp', 'Unknown') if isinstance(isp, dict) else 'Unknown'
                
                print(f"📊 代理信息:")
                print(f"   IP地址: {current_ip}")
                print(f"   国家: {country_name}")
                print(f"   地区: {region}")
                print(f"   ISP: {isp_name}")
                print()
                print(f"📄 完整响应:")
                print(response.text)
                
                return True
            except Exception as e:
                print(f"⚠️ 解析响应失败: {e}")
                print(f"原始响应: {response.text}")
                return False
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            print(f"响应内容: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"⏱️ 连接超时(15秒)")
        print("可能原因:")
        print("  1. 代理服务器响应慢")
        print("  2. 网络连接问题")
        print("  3. 防火墙阻止")
        return False
        
    except requests.exceptions.ProxyError as e:
        print(f"🚫 代理错误: {e}")
        print("可能原因:")
        print("  1. 代理凭证不正确")
        print("  2. 代理服务器拒绝连接")
        print("  3. 账户余额不足")
        return False
        
    except requests.exceptions.ConnectionError as e:
        print(f"🔌 连接错误: {e}")
        print("可能原因:")
        print("  1. 无法连接到代理服务器")
        print("  2. DNS解析失败")
        print("  3. 网络不可达")
        return False
        
    except Exception as e:
        print(f"❌ 未知错误: {type(e).__name__}")
        print(f"详情: {e}")
        return False

if __name__ == "__main__":
    success = test_proxy()
    sys.exit(0 if success else 1)

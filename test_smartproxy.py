#!/usr/bin/env python3
"""
测试Smartproxy代理配置
验证代理连接和IP分配是否正常工作
"""

import requests
import json
import time
from utils.smartproxy_manager import SmartproxyManager

def test_direct_connection():
    """测试直接连接（不使用代理）"""
    print("=== 测试直接连接 ===")
    try:
        response = requests.get('https://ip.decodo.com/json', timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 直接连接成功")
            print(f"本地IP: {data.get('ip', 'unknown')}")
            print(f"国家: {data.get('country', 'unknown')}")
            return True
        else:
            print(f"❌ 直接连接失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 直接连接错误: {e}")
        return False

def test_smartproxy_direct():
    """测试使用你提供的Smartproxy配置"""
    print("\n=== 测试Smartproxy粘性会话配置 ===")
    
    # 新的粘性会话用户名格式
    sticky_username = 'user-sp9y3nhxbw-sessionduration-60'
    password = 'ez8m5F~gl6jG9snvPU'
    host = 'gate.decodo.com'
    
    # 测试不同端口（从截图看到的范围）
    test_ports = [10001, 10004, 10005, 10006]
    
    for port in test_ports:
        try:
            print(f"\n🔧 测试端口 {port} (粘性会话60分钟)...")
            proxy_url = f"http://{sticky_username}:{password}@{host}:{port}"
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            response = requests.get(
                'https://ip.decodo.com/json', 
                proxies=proxies, 
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 端口 {port} 连接成功")
                print(f"代理IP: {data.get('ip', 'unknown')}")
                print(f"国家: {data.get('country', 'unknown')}")
                print(f"城市: {data.get('city', 'unknown')}")
                
                # 测试粘性：再次请求相同端口，IP应该相同
                time.sleep(1)
                response2 = requests.get(
                    'https://ip.decodo.com/json', 
                    proxies=proxies, 
                    timeout=10
                )
                if response2.status_code == 200:
                    data2 = response2.json()
                    if data.get('ip') == data2.get('ip'):
                        print(f"✅ 粘性验证成功：IP保持一致")
                    else:
                        print(f"⚠️ 粘性验证失败：IP发生变化 {data.get('ip')} → {data2.get('ip')}")
                        
            else:
                print(f"❌ 端口 {port} 失败: HTTP {response.status_code}")
                print(f"响应内容: {response.text[:200]}...")
                
        except Exception as e:
            print(f"❌ 端口 {port} 错误: {e}")
        
        time.sleep(2)  # 稍长间隔避免请求过快

def test_proxy_manager():
    """测试代理管理器"""
    print("\n=== 测试代理管理器 ===")
    
    manager = SmartproxyManager()
    
    # 显示配置状态
    stats = manager.get_proxy_statistics()
    print(f"代理管理器状态: {stats}")
    
    if not manager.enabled:
        print("⚠️ Smartproxy未启用，请检查环境变量配置")
        return False
    
    # 测试为不同任务分配代理
    test_tasks = [1, 2, 3]
    
    for task_id in test_tasks:
        print(f"\n🔧 测试任务 {task_id} 的代理分配...")
        
        try:
            proxy_config = manager.get_proxy_for_task(task_id, 'residential')
            
            if proxy_config:
                print(f"✅ 任务 {task_id} 代理分配成功:")
                print(f"  主机: {proxy_config['host']}")
                print(f"  端口: {proxy_config['port']}")
                print(f"  类型: {proxy_config['proxy_type']}")
                print(f"  描述: {proxy_config['display_info']}")
                
                if 'current_ip' in proxy_config:
                    print(f"  当前IP: {proxy_config['current_ip']}")
            else:
                print(f"❌ 任务 {task_id} 代理分配失败")
                
        except Exception as e:
            print(f"❌ 任务 {task_id} 错误: {e}")
        
        time.sleep(1)

def test_asterdex_connection():
    """测试通过代理连接AsterDEX API"""
    print("\n=== 测试AsterDEX API连接 ===")
    
    username = 'sp9y3nhxbw'
    password = 'ez8m5F~gl6jG9snvPU'
    proxy_url = f"http://{username}:{password}@gate.decodo.com:10001"
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    # 测试AsterDEX公开API
    test_endpoints = [
        'https://sapi.asterdex.com/api/v1/ping',
        'https://sapi.asterdex.com/api/v1/time',
        'https://sapi.asterdex.com/api/v1/ticker/bookTicker?symbol=ASTERUSDT'
    ]
    
    for endpoint in test_endpoints:
        try:
            print(f"\n🔧 测试 {endpoint.split('/')[-1]}...")
            response = requests.get(endpoint, proxies=proxies, timeout=15)
            
            if response.status_code == 200:
                print(f"✅ 连接成功")
                data = response.json()
                if isinstance(data, dict) and len(data) < 10:  # 简单显示
                    print(f"响应: {data}")
            else:
                print(f"❌ 连接失败: HTTP {response.status_code}")
                print(f"响应: {response.text[:200]}...")
                
        except Exception as e:
            print(f"❌ 连接错误: {e}")
        
        time.sleep(1)

def main():
    print("🚀 Smartproxy代理测试工具")
    print("=" * 60)
    
    # 1. 测试直接连接
    test_direct_connection()
    
    # 2. 测试Smartproxy直接配置
    test_smartproxy_direct()
    
    # 3. 测试代理管理器
    test_proxy_manager()
    
    # 4. 测试AsterDEX连接
    test_asterdex_connection()
    
    print("\n" + "=" * 60)
    print("🎯 测试完成！")

if __name__ == '__main__':
    main()
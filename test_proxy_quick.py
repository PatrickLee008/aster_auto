#!/usr/bin/env python3
"""
快速代理测试脚本
直接测试你的Smartproxy配置是否能正常工作
"""

import requests
import time

def test_proxy_connection():
    print("🔧 快速Smartproxy连接测试")
    print("=" * 40)
    
    # 你的Smartproxy配置
    username = 'sp9y3nhxbw'
    password = 'ez8m5F~gl6jG9snvPU'
    proxy_host = 'gate.decodo.com'
    proxy_port = '10001'
    
    proxy_url = f"http://{username}:{password}@{proxy_host}:{proxy_port}"
    
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    print(f"代理地址: {username}:***@{proxy_host}:{proxy_port}")
    print(f"测试开始时间: {time.strftime('%H:%M:%S')}")
    
    # 测试连接
    test_cases = [
        ("IP检测", "https://ip.decodo.com/json"),
        ("Binance时间", "https://api.binance.com/api/v3/time"),
        ("HTTP测试", "http://httpbin.org/ip")
    ]
    
    success_count = 0
    
    for name, url in test_cases:
        print(f"\n🔄 {name}: {url}")
        try:
            start_time = time.time()
            response = requests.get(url, proxies=proxies, timeout=8)
            end_time = time.time()
            
            latency = int((end_time - start_time) * 1000)
            
            if response.status_code == 200:
                print(f"✅ 成功 ({latency}ms)")
                
                # 尝试解析JSON响应
                try:
                    data = response.json()
                    if 'ip' in data:
                        print(f"   🌐 IP: {data['ip']}")
                    if 'country' in data:
                        print(f"   📍 位置: {data.get('country', 'Unknown')}")
                    if 'serverTime' in data:
                        print(f"   🕐 服务器时间: {data['serverTime']}")
                except:
                    # 不是JSON响应，显示部分内容
                    content = response.text[:100].replace('\n', ' ')
                    print(f"   📄 响应: {content}...")
                    
                success_count += 1
            else:
                print(f"❌ HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("❌ 超时")
        except requests.exceptions.ProxyError:
            print("❌ 代理错误")
        except requests.exceptions.ConnectionError:
            print("❌ 连接错误")
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    print("\n" + "=" * 40)
    print(f"📊 测试结果: {success_count}/{len(test_cases)} 成功")
    
    if success_count == len(test_cases):
        print("🎉 代理配置完全正常!")
        return True
    elif success_count > 0:
        print("⚠️ 代理部分工作，可能有网络波动")
        return True
    else:
        print("❌ 代理配置有问题，请检查:")
        print("   1. 用户名密码是否正确")
        print("   2. 代理服务器是否可达")
        print("   3. 网络连接是否正常")
        return False

def test_without_proxy():
    print("\n🔧 无代理连接测试 (对比)")
    print("=" * 40)
    
    try:
        start_time = time.time()
        response = requests.get("https://ip.decodo.com/json", timeout=5)
        end_time = time.time()
        
        latency = int((end_time - start_time) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 直连成功 ({latency}ms)")
            print(f"   🌐 本地IP: {data.get('ip', 'Unknown')}")
            print(f"   📍 位置: {data.get('country', 'Unknown')}")
        else:
            print(f"❌ 直连失败: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ 直连错误: {e}")

if __name__ == "__main__":
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 测试代理连接
    proxy_ok = test_proxy_connection()
    
    # 测试直连（对比）
    test_without_proxy()
    
    print(f"\n测试完成: {time.strftime('%H:%M:%S')}")
    
    if proxy_ok:
        print("\n✅ 下一步: 检查应用为什么没有使用这个代理配置")
    else:
        print("\n❌ 下一步: 先解决代理连接问题")
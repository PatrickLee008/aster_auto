#!/usr/bin/env python3
"""
测试俄亥俄州IP分配脚本
验证Smartproxy是否正确分配俄亥俄州IP地址
"""

import requests
import time

def test_ohio_assignment():
    print("=== 俄亥俄州IP分配测试 ===")
    print("=" * 40)
    
    # 配置
    base_username = 'sp9y3nhxbw'
    password = 'ez8m5F~gl6jG9snvPU'
    proxy_host = 'gate.decodo.com'
    proxy_port = '10001'
    
    # 测试多个任务ID的俄亥俄州格式
    test_cases = [
        ("任务39", f"user-{base_username}-country-us-state-us_ohio-session-task0039"),
        ("任务40", f"user-{base_username}-country-us-state-us_ohio-session-task0040"),
        ("任务41", f"user-{base_username}-country-us-state-us_ohio-session-task0041")
    ]
    
    for task_name, username in test_cases:
        print(f"\n测试 {task_name}:")
        print(f"用户名: {username}")
        
        proxy_url = f"http://{username}:{password}@{proxy_host}:{proxy_port}"
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        try:
            start_time = time.time()
            response = requests.get(
                'https://ip.decodo.com/json',
                proxies=proxies,
                timeout=10,
                headers={'User-Agent': 'AsterAuto/1.0'}
            )
            end_time = time.time()
            
            latency = int((end_time - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                ip = data.get('ip', 'unknown')
                country = data.get('country', {})
                region = data.get('region', 'unknown')
                city = data.get('city', 'unknown')
                
                # 提取国家和地区信息
                if isinstance(country, dict):
                    country_name = country.get('name', 'Unknown')
                    country_code = country.get('code', 'Unknown')
                else:
                    country_name = str(country)
                    country_code = 'Unknown'
                
                print(f"  成功 ({latency}ms)")
                print(f"  IP: {ip}")
                print(f"  国家: {country_name} ({country_code})")
                print(f"  地区: {region}")
                print(f"  城市: {city}")
                
                # 检查是否为美国俄亥俄州
                if country_code.upper() == 'US':
                    # 检查城市信息中的州代码
                    if isinstance(city, dict) and city.get('code') == 'OH':
                        print(f"  俄亥俄州IP分配成功！城市: {city.get('name', 'unknown')}")
                    elif 'ohio' in region.lower() or 'oh' in region.lower():
                        print(f"  俄亥俄州IP分配成功！")
                    else:
                        print(f"  非俄亥俄州IP: {region}")
                else:
                    print(f"  非美国IP")
                    
            else:
                print(f"  HTTP错误: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"  连接超时")
        except requests.exceptions.ProxyError:
            print(f"  代理连接错误")
        except Exception as e:
            print(f"  错误: {e}")
            
        # 短暂等待避免请求过快
        time.sleep(2)
    
    print(f"\n测试完成: {time.strftime('%H:%M:%S')}")

if __name__ == "__main__":
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    test_ohio_assignment()
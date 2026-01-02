#!/usr/bin/env python3
"""
Smartproxy配置测试脚本
检查环境配置加载和代理连接状态
"""

import os
import sys
import requests
import time
from datetime import datetime

def print_header(title):
    print("=" * 60)
    print(f"🔧 {title}")
    print("=" * 60)

def print_section(title):
    print(f"\n📋 {title}")
    print("-" * 40)

def test_env_loading():
    """测试环境配置加载"""
    print_section("环境配置检查")
    
    # 检查环境文件
    env_files = ['.env', '.envProd', '.env.prod', '.env.production']
    found_files = []
    
    for env_file in env_files:
        if os.path.exists(env_file):
            found_files.append(env_file)
            print(f"✅ 发现配置文件: {env_file}")
    
    if not found_files:
        print("❌ 未发现任何环境配置文件")
        return False
    
    # 加载环境变量
    try:
        # 尝试加载 .envProd
        if '.envProd' in found_files:
            print(f"\n🔍 加载 .envProd 配置...")
            with open('.envProd', 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"📄 文件大小: {len(content)} 字符")
                
                # 查找Smartproxy相关配置
                smartproxy_lines = []
                for line_num, line in enumerate(content.split('\n'), 1):
                    if 'SMARTPROXY' in line.upper() and not line.strip().startswith('#'):
                        smartproxy_lines.append(f"第{line_num}行: {line}")
                
                if smartproxy_lines:
                    print(f"🎯 发现 {len(smartproxy_lines)} 行Smartproxy配置:")
                    for line in smartproxy_lines:
                        print(f"   {line}")
                else:
                    print("⚠️ 未发现Smartproxy配置")
                    
        return True
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        return False

def test_env_variables():
    """测试环境变量"""
    print_section("环境变量检查")
    
    smartproxy_vars = [
        'SMARTPROXY_ENABLED',
        'SMARTPROXY_BASE_USERNAME', 
        'SMARTPROXY_PASSWORD',
        'SMARTPROXY_RESIDENTIAL_HOST',
        'SMARTPROXY_RESIDENTIAL_PORT',
        'SMARTPROXY_DATACENTER_HOST',
        'SMARTPROXY_SESSION_DURATION'
    ]
    
    found_vars = {}
    missing_vars = []
    
    for var in smartproxy_vars:
        value = os.getenv(var)
        if value is not None:
            # 隐藏敏感信息
            if 'PASSWORD' in var or 'USERNAME' in var:
                display_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "****"
            else:
                display_value = value
            found_vars[var] = display_value
            print(f"✅ {var} = {display_value}")
        else:
            missing_vars.append(var)
            print(f"❌ {var} = 未设置")
    
    return len(missing_vars) == 0, found_vars

def test_smartproxy_direct():
    """直接测试Smartproxy连接"""
    print_section("Smartproxy直接连接测试")
    
    # 硬编码测试（使用你提供的配置）
    username = 'sp9y3nhxbw'
    password = 'ez8m5F~gl6jG9snvPU'
    proxy_host = 'gate.decodo.com'
    proxy_port = '10001'
    
    proxy_url = f"http://{username}:{password}@{proxy_host}:{proxy_port}"
    
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    test_urls = [
        'https://ip.decodo.com/json',
        'https://httpbin.org/ip',
        'https://api.binance.com/api/v3/time'
    ]
    
    for url in test_urls:
        try:
            print(f"\n🔄 测试URL: {url}")
            start_time = time.time()
            
            response = requests.get(
                url, 
                proxies=proxies, 
                timeout=10,
                headers={'User-Agent': 'AsterAuto-Test/1.0'}
            )
            
            end_time = time.time()
            latency = int((end_time - start_time) * 1000)
            
            if response.status_code == 200:
                print(f"✅ 连接成功 (延迟: {latency}ms)")
                
                try:
                    data = response.json()
                    if 'ip' in data:
                        print(f"🌐 代理IP: {data['ip']}")
                    if 'country' in data:
                        print(f"📍 位置: {data.get('city', 'Unknown')}, {data['country']}")
                except:
                    print(f"📄 响应内容: {response.text[:100]}...")
                    
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("❌ 连接超时")
        except requests.exceptions.ProxyError:
            print("❌ 代理连接错误")
        except requests.exceptions.ConnectionError:
            print("❌ 网络连接错误")
        except Exception as e:
            print(f"❌ 未知错误: {e}")

def test_smartproxy_manager():
    """测试Smartproxy管理器"""
    print_section("Smartproxy管理器测试")
    
    try:
        # 添加项目路径
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        from utils.smartproxy_manager import get_proxy_manager, get_task_proxy_config
        
        print("🔍 测试Smartproxy管理器...")
        
        # 测试管理器初始化
        manager = get_proxy_manager()
        print(f"✅ 管理器实例化成功")
        print(f"📊 管理器状态: {'启用' if manager.enabled else '禁用'}")
        
        if hasattr(manager, 'base_username'):
            print(f"👤 基础用户名: {manager.base_username}")
        if hasattr(manager, 'residential_host'):
            print(f"🏠 住宅代理主机: {manager.residential_host}")
        if hasattr(manager, 'residential_port'):
            print(f"🔌 住宅代理端口: {manager.residential_port}")
            
        # 测试任务代理配置
        print(f"\n🎯 测试任务代理配置 (任务ID: 999)...")
        task_config = get_task_proxy_config(999, 'residential')
        
        print(f"代理配置: {task_config}")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入Smartproxy管理器失败: {e}")
        return False
    except Exception as e:
        print(f"❌ Smartproxy管理器测试失败: {e}")
        return False

def test_no_proxy():
    """测试无代理连接"""
    print_section("无代理连接测试 (对比)")
    
    try:
        response = requests.get(
            'https://ip.decodo.com/json', 
            timeout=5,
            headers={'User-Agent': 'AsterAuto-Test/1.0'}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 直连成功")
            print(f"🌐 本地IP: {data.get('ip', 'Unknown')}")
            print(f"📍 位置: {data.get('city', 'Unknown')}, {data.get('country', 'Unknown')}")
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 直连测试失败: {e}")

def main():
    print_header(f"Smartproxy配置诊断 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 检查环境配置文件
    env_ok = test_env_loading()
    
    # 2. 检查环境变量
    vars_ok, found_vars = test_env_variables()
    
    # 3. 测试Smartproxy管理器
    manager_ok = test_smartproxy_manager()
    
    # 4. 测试直接代理连接
    test_smartproxy_direct()
    
    # 5. 测试无代理连接（对比）
    test_no_proxy()
    
    # 总结
    print_header("诊断总结")
    print(f"📄 环境配置文件: {'✅ 正常' if env_ok else '❌ 异常'}")
    print(f"🔧 环境变量: {'✅ 正常' if vars_ok else '❌ 异常'}")  
    print(f"⚙️ Smartproxy管理器: {'✅ 正常' if manager_ok else '❌ 异常'}")
    
    if not vars_ok:
        print(f"\n⚠️ 建议检查 .envProd 文件中的Smartproxy配置")
    
    print(f"\n🕐 测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
调试Smartproxy管理器状态
"""

import os
import sys

# 添加项目路径
sys.path.append('.')

def test_smartproxy_manager():
    print("=== 调试Smartproxy管理器状态 ===")
    print("=" * 50)
    
    # 1. 检查环境变量
    print("环境变量检查:")
    smartproxy_vars = [
        'SMARTPROXY_ENABLED',
        'SMARTPROXY_BASE_USERNAME',
        'SMARTPROXY_PASSWORD',
        'SMARTPROXY_RESIDENTIAL_HOST',
        'SMARTPROXY_RESIDENTIAL_PORT'
    ]
    
    for var in smartproxy_vars:
        value = os.getenv(var, 'NOT_SET')
        if 'PASSWORD' in var or 'USERNAME' in var:
            display = f"{value[:3]}***{value[-3:]}" if value != 'NOT_SET' else 'NOT_SET'
        else:
            display = value
        print(f"  {var} = {display}")
    
    # 2. 测试config_env加载
    print(f"\nconfig_env模块测试:")
    try:
        from config_env import get_env_bool, get_env
        enabled = get_env_bool('SMARTPROXY_ENABLED', False)
        username = get_env('SMARTPROXY_BASE_USERNAME', '')
        password = get_env('SMARTPROXY_PASSWORD', '')
        
        print(f"  get_env_bool('SMARTPROXY_ENABLED') = {enabled}")
        print(f"  get_env('SMARTPROXY_BASE_USERNAME') = {username[:3]}***{username[-3:] if username else ''}")
        print(f"  get_env('SMARTPROXY_PASSWORD') = {'***' if password else 'EMPTY'}")
        
    except Exception as e:
        print(f"  config_env导入失败: {e}")
    
    # 3. 测试Smartproxy管理器
    print(f"\nSmartproxy管理器测试:")
    try:
        from utils.smartproxy_manager import SmartproxyManager, get_proxy_manager, get_task_proxy_config
        
        # 创建管理器实例
        manager = SmartproxyManager()
        print(f"  管理器实例创建成功")
        print(f"  enabled = {manager.enabled}")
        print(f"  base_username = {manager.base_username[:3]}***{manager.base_username[-3:] if manager.base_username else ''}")
        print(f"  password = {'***' if manager.password else 'EMPTY'}")
        print(f"  residential_host = {manager.residential_endpoint}")
        print(f"  residential_port = {manager.residential_port}")
        
        # 测试获取代理配置
        print(f"\n测试获取任务代理配置 (任务ID: 999):")
        task_config = get_task_proxy_config(999, 'residential')
        print(f"  proxy_enabled = {task_config.get('proxy_enabled', False)}")
        
        if task_config.get('proxy_enabled'):
            print(f"  proxy_host = {task_config.get('proxy_host', 'None')}")
            print(f"  proxy_port = {task_config.get('proxy_port', 'None')}")
            print(f"  proxy_type = {task_config.get('proxy_type', 'None')}")
            print(f"  proxy_auth = {task_config.get('proxy_auth', 'None')[:20]}..." if task_config.get('proxy_auth') else "  proxy_auth = None")
            print(f"  country = {task_config.get('country', 'None')}")
            print(f"  current_ip = {task_config.get('current_ip', 'None')}")
            
            # 如果IP是unknown，说明测试失败
            if task_config.get('current_ip') == 'unknown':
                print("\n⚠️ 警告: 代理IP显示为 'unknown'，说明代理测试失败")
                print("可能原因:")
                print("  1. 代理凭证不正确")
                print("  2. 网络连接问题")
                print("  3. Smartproxy服务问题")
                print("  4. 代理测试URL被屏蔽")
                print("\n请检查日志中的详细错误信息")
        else:
            print("  代理未启用")
            
            # 检查为什么未启用
            if not manager.enabled:
                print("  原因: manager.enabled = False")
            elif not manager.base_username:
                print("  原因: base_username为空")
            elif not manager.password:
                print("  原因: password为空")
        
    except Exception as e:
        print(f"  Smartproxy管理器测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_smartproxy_manager()
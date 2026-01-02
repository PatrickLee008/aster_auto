#!/usr/bin/env python3
"""
简化环境配置测试脚本
专门检查.envProd文件加载情况
"""

import os
import sys

def test_envprod():
    print("=" * 50)
    print("🔍 .envProd 文件测试")
    print("=" * 50)
    
    # 检查文件是否存在
    if not os.path.exists('.envProd'):
        print("❌ .envProd 文件不存在")
        return
    
    print("✅ .envProd 文件存在")
    
    # 读取文件内容
    try:
        with open('.envProd', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"📄 文件行数: {len(lines)}")
        
        # 查找Smartproxy配置
        smartproxy_config = {}
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line and not line.startswith('#') and 'SMARTPROXY' in line:
                if '=' in line:
                    key, value = line.split('=', 1)
                    smartproxy_config[key.strip()] = value.strip()
                    print(f"第{i:2d}行: {key.strip()} = {value.strip()}")
        
        print(f"\n📊 发现 {len(smartproxy_config)} 个SMARTPROXY配置项")
        
        # 关键配置检查
        required_keys = [
            'SMARTPROXY_ENABLED',
            'SMARTPROXY_BASE_USERNAME', 
            'SMARTPROXY_PASSWORD',
            'SMARTPROXY_RESIDENTIAL_HOST',
            'SMARTPROXY_RESIDENTIAL_PORT'
        ]
        
        print("\n🎯 关键配置检查:")
        for key in required_keys:
            if key in smartproxy_config:
                value = smartproxy_config[key]
                if 'PASSWORD' in key or 'USERNAME' in key:
                    display = f"{value[:3]}***{value[-3:]}" if len(value) > 6 else "***"
                else:
                    display = value
                print(f"  ✅ {key} = {display}")
            else:
                print(f"  ❌ {key} = 缺失")
        
        # 测试直接设置环境变量
        print(f"\n⚙️ 手动设置环境变量测试:")
        for key, value in smartproxy_config.items():
            os.environ[key] = value
            print(f"  设置: {key}")
        
        # 验证环境变量
        print(f"\n✅ 环境变量验证:")
        for key in required_keys:
            env_value = os.getenv(key)
            if env_value:
                if 'PASSWORD' in key or 'USERNAME' in key:
                    display = f"{env_value[:3]}***{env_value[-3:]}"
                else:
                    display = env_value
                print(f"  ✅ {key} = {display}")
            else:
                print(f"  ❌ {key} = 未设置")
                
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")

def test_app_env_loading():
    print("\n" + "=" * 50)
    print("🔍 应用环境加载测试")
    print("=" * 50)
    
    try:
        # 尝试导入Flask应用的环境加载逻辑
        sys.path.append('.')
        
        # 检查是否有config模块
        try:
            from config import Config
            print("✅ 导入Config类成功")
            
            # 检查Config中的Smartproxy配置
            config_attrs = [attr for attr in dir(Config) if 'SMARTPROXY' in attr]
            print(f"📊 Config中的SMARTPROXY属性: {len(config_attrs)}个")
            for attr in config_attrs:
                value = getattr(Config, attr, None)
                if 'PASSWORD' in attr or 'USERNAME' in attr:
                    display = f"{str(value)[:3]}***{str(value)[-3:]}" if value else "None"
                else:
                    display = value
                print(f"  {attr} = {display}")
                
        except ImportError:
            print("⚠️ 无法导入Config类")
            
        # 检查是否有环境加载函数
        try:
            from utils.env_loader import load_env
            print("✅ 发现环境加载函数")
            load_env()  # 手动加载
            print("✅ 环境加载完成")
        except ImportError:
            print("⚠️ 未发现专用环境加载函数")
            
    except Exception as e:
        print(f"❌ 应用环境加载测试失败: {e}")

if __name__ == "__main__":
    test_envprod()
    test_app_env_loading()
    
    print("\n" + "=" * 50)
    print("🎯 建议下一步:")
    print("1. 确认.envProd中SMARTPROXY_ENABLED=True")  
    print("2. 运行完整测试: python test_smartproxy_config.py")
    print("3. 检查应用是否正确加载.envProd文件")
    print("=" * 50)
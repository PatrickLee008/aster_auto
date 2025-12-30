#!/usr/bin/env python3
"""
加密配置诊断工具
检查加密密钥配置和钱包凭证解密状态
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.wallet import Wallet
from utils.encryption import get_encryption_key, test_encryption
import base64


def main():
    print("=" * 60)
    print("加密配置诊断工具")
    print("=" * 60)
    
    # 检查环境变量
    print(f"当前环境: {os.getenv('ENVIRONMENT', 'development')}")
    
    # 检查加密密钥
    try:
        encryption_key = get_encryption_key()
        print(f"加密密钥长度: {len(encryption_key)}")
        print(f"加密密钥前16字节: {encryption_key[:16]}")
        print(f"加密密钥来源: config_env.SECURITY_CONFIG")
        
        # 测试加密功能
        test_result = test_encryption()
        print(f"加密功能测试: {test_result}")
        
    except Exception as e:
        print(f"❌ 获取加密密钥失败: {e}")
        return
    
    # 创建应用上下文并检查钱包
    app = create_app()
    
    with app.app_context():
        wallets = Wallet.query.all()
        print(f"\n找到 {len(wallets)} 个钱包:")
        
        for wallet in wallets:
            print(f"\n钱包: {wallet.id} - {wallet.name} ({wallet.wallet_type})")
            
            # 检查原始加密数据
            if wallet.api_key:
                print(f"  API密钥 (加密): 存在，长度 {len(wallet.api_key)}")
                print(f"  API密钥前32字符: {wallet.api_key[:32]}")
            else:
                print(f"  API密钥: 不存在")
            
            if wallet.secret_key:
                print(f"  Secret密钥 (加密): 存在，长度 {len(wallet.secret_key)}")
                print(f"  Secret密钥前32字符: {wallet.secret_key[:32]}")
            else:
                print(f"  Secret密钥: 不存在")
            
            # 尝试解密
            try:
                credentials = wallet.get_api_credentials()
                if credentials['api_key']:
                    print(f"  ✅ API密钥解密成功: {credentials['api_key'][:8]}...")
                else:
                    print(f"  ❌ API密钥解密失败或为空")
                
                if credentials['secret_key']:
                    print(f"  ✅ Secret密钥解密成功: {credentials['secret_key'][:8]}...")
                else:
                    print(f"  ❌ Secret密钥解密失败或为空")
                    
            except Exception as e:
                print(f"  ❌ 凭证解密异常: {e}")
    
    print(f"\n💡 如果解密失败，可能的原因:")
    print(f"1. 钱包凭证是在不同的环境下用不同的加密密钥创建的")
    print(f"2. 本地开发环境和生产环境的 ENCRYPTION_KEY 不一致")
    print(f"3. 环境变量 ENVIRONMENT 可能影响配置文件选择")
    
    print(f"\n🔧 建议检查:")
    print(f"1. 对比 .env 和 .envProd 中的 ENCRYPTION_KEY")
    print(f"2. 确认钱包凭证是在哪个环境下创建的")
    print(f"3. 统一加密密钥或重新加密凭证")


if __name__ == '__main__':
    main()
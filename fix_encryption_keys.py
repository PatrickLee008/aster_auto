#!/usr/bin/env python3
"""
钱包凭证加密密钥修复工具
用于在更改加密密钥后重新加密钱包凭证
"""

import os
import sys
from getpass import getpass

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.wallet import Wallet
from models.base import db


def decrypt_with_old_key(encrypted_data, old_key):
    """使用旧密钥解密数据"""
    if not encrypted_data:
        return None
    
    try:
        import base64
        from cryptography.fernet import Fernet
        cipher_suite = Fernet(base64.urlsafe_b64encode(old_key[:32]))
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        print(f"使用旧密钥解密失败: {e}")
        return None


def encrypt_with_new_key(data, new_key):
    """使用新密钥加密数据"""
    if not data:
        return None
    
    try:
        import base64
        from cryptography.fernet import Fernet
        cipher_suite = Fernet(base64.urlsafe_b64encode(new_key[:32]))
        return cipher_suite.encrypt(data.encode()).decode()
    except Exception as e:
        print(f"使用新密钥加密失败: {e}")
        return None


def main():
    print("=" * 60)
    print("钱包凭证加密密钥修复工具")
    print("=" * 60)
    
    # 获取旧加密密钥
    print("\n请输入原加密密钥（用于解密现有数据）:")
    old_key_input = getpass("原加密密钥: ").strip()
    
    if not old_key_input:
        print("❌ 原加密密钥不能为空")
        return
    
    # 获取新加密密钥
    print("\n请输入新加密密钥（用于重新加密）:")
    new_key_input = getpass("新加密密钥: ").strip()
    
    if not new_key_input:
        print("❌ 新加密密钥不能为空")
        return
    
    # 确保密钥长度
    old_key = old_key_input.encode()[:32].ljust(32, b'x')
    new_key = new_key_input.encode()[:32].ljust(32, b'x')
    
    # 创建应用上下文
    app = create_app()
    
    with app.app_context():
        wallets = Wallet.query.all()
        
        if not wallets:
            print("📭 没有找到需要处理的钱包")
            return
        
        print(f"\n🔍 找到 {len(wallets)} 个钱包需要处理:")
        
        updated_count = 0
        failed_count = 0
        
        for wallet in wallets:
            print(f"\n处理钱包: {wallet.name} ({wallet.wallet_type})")
            
            # 处理API密钥
            if wallet.api_key:
                old_api_key = decrypt_with_old_key(wallet.api_key, old_key)
                if old_api_key:
                    new_encrypted_api_key = encrypt_with_new_key(old_api_key, new_key)
                    if new_encrypted_api_key:
                        wallet.api_key = new_encrypted_api_key
                        print(f"  ✅ API密钥重新加密成功")
                    else:
                        print(f"  ❌ API密钥重新加密失败")
                        failed_count += 1
                        continue
                else:
                    print(f"  ❌ API密钥解密失败")
                    failed_count += 1
                    continue
            
            # 处理密钥
            if wallet.secret_key:
                old_secret_key = decrypt_with_old_key(wallet.secret_key, old_key)
                if old_secret_key:
                    new_encrypted_secret_key = encrypt_with_new_key(old_secret_key, new_key)
                    if new_encrypted_secret_key:
                        wallet.secret_key = new_encrypted_secret_key
                        print(f"  ✅ Secret密钥重新加密成功")
                    else:
                        print(f"  ❌ Secret密钥重新加密失败")
                        failed_count += 1
                        continue
                else:
                    print(f"  ❌ Secret密钥解密失败")
                    failed_count += 1
                    continue
            
            # 处理私钥（期货）
            if wallet.private_key:
                old_private_key = decrypt_with_old_key(wallet.private_key, old_key)
                if old_private_key:
                    new_encrypted_private_key = encrypt_with_new_key(old_private_key, new_key)
                    if new_encrypted_private_key:
                        wallet.private_key = new_encrypted_private_key
                        print(f"  ✅ 私钥重新加密成功")
                    else:
                        print(f"  ❌ 私钥重新加密失败")
                        failed_count += 1
                        continue
                else:
                    print(f"  ❌ 私钥解密失败")
                    failed_count += 1
                    continue
            
            updated_count += 1
        
        # 保存更改
        if updated_count > 0:
            try:
                db.session.commit()
                print(f"\n✅ 成功处理 {updated_count} 个钱包")
                if failed_count > 0:
                    print(f"❌ 失败 {failed_count} 个钱包")
                print("\n📝 请更新配置文件中的 ENCRYPTION_KEY 为新密钥")
            except Exception as e:
                db.session.rollback()
                print(f"\n❌ 保存失败: {e}")
        else:
            print(f"\n❌ 没有成功处理任何钱包")


if __name__ == '__main__':
    main()
"""
检查数据库中的钱包数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Wallet, User

with app.app_context():
    print("=" * 60)
    print("数据库钱包检查")
    print("=" * 60)
    
    # 检查所有钱包
    print("\n📋 所有钱包列表:")
    wallets = Wallet.query.all()
    if not wallets:
        print("  ❌ 数据库中没有任何钱包")
    else:
        print(f"  共有 {len(wallets)} 个钱包:\n")
        for wallet in wallets:
            user = User.query.get(wallet.user_id)
            user_name = user.username if user else "未知用户"
            print(f"  ID: {wallet.id}")
            print(f"    名称: {wallet.name}")
            print(f"    类型: {wallet.wallet_type}")
            print(f"    所属用户: {user_name} (ID: {wallet.user_id})")
            print(f"    是否激活: {'是' if wallet.is_active else '否'}")
            print(f"    创建时间: {wallet.created_at}")
            print()
    
    # 检查钱包ID 34
    print("\n🔍 检查钱包ID 34:")
    wallet_34 = Wallet.query.get(34)
    if wallet_34:
        user = User.query.get(wallet_34.user_id)
        print(f"  ✅ 钱包ID 34 存在")
        print(f"    名称: {wallet_34.name}")
        print(f"    类型: {wallet_34.wallet_type}")
        print(f"    所属用户: {user.username if user else '未知'} (ID: {wallet_34.user_id})")
        print(f"    是否激活: {'是' if wallet_34.is_active else '否'}")
        
        # 检查API配置
        credentials = wallet_34.get_api_credentials()
        has_spot = bool(credentials.get('api_key') and credentials.get('secret_key'))
        has_futures = bool(wallet_34.user_address and wallet_34.signer_address and credentials.get('private_key'))
        print(f"    现货API配置: {'是' if has_spot else '否'}")
        print(f"    期货API配置: {'是' if has_futures else '否'}")
    else:
        print(f"  ❌ 钱包ID 34 不存在")
    
    # 检查管理员用户的钱包
    print("\n👤 管理员用户的钱包:")
    admin_users = User.query.filter_by(role='admin').all()
    if not admin_users:
        print("  ❌ 没有管理员用户")
    else:
        for admin in admin_users:
            print(f"\n  管理员: {admin.username} (ID: {admin.id})")
            admin_wallets = Wallet.query.filter_by(user_id=admin.id).all()
            if not admin_wallets:
                print(f"    ❌ 该管理员没有钱包")
            else:
                print(f"    该管理员有 {len(admin_wallets)} 个钱包:")
                for w in admin_wallets:
                    print(f"      - ID: {w.id}, 名称: {w.name}, 类型: {w.wallet_type}")

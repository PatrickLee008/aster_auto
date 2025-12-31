#!/usr/bin/env python3
"""
数据库迁移脚本：增加钱包地址字段长度
从 VARCHAR(42) 增加到 VARCHAR(100)
"""

import sys
import os
sys.path.append('.')

from app import create_app
from models.base import db

def migrate_database():
    """执行数据库迁移"""
    
    app = create_app()
    
    with app.app_context():
        try:
            print("开始数据库迁移...")
            
            # 执行SQL命令来修改字段长度
            alter_sql = [
                "ALTER TABLE wallets MODIFY COLUMN user_address VARCHAR(100);",
                "ALTER TABLE wallets MODIFY COLUMN signer_address VARCHAR(100);"
            ]
            
            for sql in alter_sql:
                print(f"执行SQL: {sql}")
                db.engine.execute(sql)
            
            print("✅ 数据库迁移成功完成!")
            print("- user_address 字段长度已从 VARCHAR(42) 改为 VARCHAR(100)")
            print("- signer_address 字段长度已从 VARCHAR(42) 改为 VARCHAR(100)")
            
        except Exception as e:
            print(f"❌ 数据库迁移失败: {e}")
            print("\n如果是生产环境，请手动执行以下SQL:")
            print("ALTER TABLE wallets MODIFY COLUMN user_address VARCHAR(100);")
            print("ALTER TABLE wallets MODIFY COLUMN signer_address VARCHAR(100);")
            return False
    
    return True

if __name__ == '__main__':
    success = migrate_database()
    sys.exit(0 if success else 1)
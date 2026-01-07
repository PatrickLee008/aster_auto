"""
添加system_config表的数据库迁移脚本
运行方式：python add_system_config_table.py
"""

from app import create_app
from models.base import db
from models import SystemConfig

def migrate():
    """执行数据库迁移"""
    app = create_app()
    
    with app.app_context():
        print("正在创建 system_config 表...")
        
        try:
            # 创建表
            db.create_all()
            print("✅ system_config 表创建成功")
            
            # 初始化默认配置
            print("\n正在初始化默认配置...")
            
            # 从环境变量读取初始值
            from config_env import get_env_bool
            initial_smartproxy_enabled = get_env_bool('SMARTPROXY_ENABLED', False)
            
            SystemConfig.set_value(
                'smartproxy_enabled',
                initial_smartproxy_enabled,
                config_type='boolean',
                description='Smartproxy任务级代理开关'
            )
            
            print(f"✅ Smartproxy开关初始化为: {initial_smartproxy_enabled}")
            print("\n✨ 数据库迁移完成！")
            print("现在可以在管理后台的「系统设置」页面管理代理开关了")
            
        except Exception as e:
            print(f"❌ 迁移失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    migrate()

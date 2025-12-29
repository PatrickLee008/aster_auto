"""
AsterDEX多钱包管理系统 - 重构版
基于MVC架构的Flask应用
"""

import os
import sys


from flask import Flask
from flask_login import LoginManager

# 导入模型和配置
from models.base import db
from models import User
from controllers import auth_bp, wallet_bp, task_bp, main_bp
from services import AuthService, StrategyService


def create_app():
    """应用工厂函数"""
    app = Flask(__name__)
    
    # 配置应用
    configure_app(app)
    
    # 初始化扩展
    initialize_extensions(app)
    
    # 注册蓝图
    register_blueprints(app)
    
    # 初始化数据库
    initialize_database(app)
    
    return app


def configure_app(app):
    """配置应用"""
    try:
        from config_env import DATABASE_CONFIG, FLASK_CONFIG, SECURITY_CONFIG
        
        app.config['SECRET_KEY'] = FLASK_CONFIG['secret_key']
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            f"mysql+pymysql://{DATABASE_CONFIG['username']}:{DATABASE_CONFIG['password']}"
            f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
        )
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['WTF_CSRF_ENABLED'] = False  # 简化API调用
        
        print("环境配置文件加载成功")
        
    except ImportError:
        print("未找到环境配置文件，使用默认配置")
        app.config['SECRET_KEY'] = 'your-secret-key-change-this'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/aster_auto'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['WTF_CSRF_ENABLED'] = False


def initialize_extensions(app):
    """初始化Flask扩展"""
    # 初始化数据库
    db.init_app(app)
    
    # 初始化登录管理器
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from models.base import db
        return db.session.get(User, int(user_id))


def register_blueprints(app):
    """注册蓝图"""
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(task_bp)
    
    print("蓝图注册完成")


def initialize_database(app):
    """初始化数据库"""
    with app.app_context():
        try:
            # 创建所有表
            db.create_all()
            print("数据库表创建成功")
            
            # 创建默认管理员账户
            create_default_admin()
            
            # 初始化默认策略
            initialize_default_strategies()
            
        except Exception as e:
            print(f"数据库初始化失败: {e}")
            print("请确保MySQL服务正在运行，并且配置正确")
            sys.exit(1)


def create_default_admin():
    """创建默认管理员账户"""
    try:
        if not User.query.filter_by(username='admin').first():
            success, message, admin_user = AuthService.create_user(
                username='admin',
                email='admin@example.com',
                password='admin123',
                is_admin=True
            )
            
            if success:
                print("默认管理员账户创建成功: admin / admin123")
            else:
                print(f"创建默认管理员失败: {message}")
        else:
            print("管理员账户已存在")
            
    except Exception as e:
        print(f"创建管理员账户异常: {e}")


def initialize_default_strategies():
    """初始化默认策略"""
    try:
        success, message = StrategyService.initialize_default_strategies()
        if success:
            print("默认策略初始化成功")
        else:
            print(f"信息: {message}")
            
    except Exception as e:
        print(f"初始化默认策略异常: {e}")


def start_app():
    """启动应用"""
    try:
        from config_env import FLASK_CONFIG
        host = FLASK_CONFIG['host']
        port = FLASK_CONFIG['port']
        debug = FLASK_CONFIG['debug']
    except:
        host = '0.0.0.0'
        port = 5000
        debug = True
    
    print(f"\n{'='*60}")
    print("AsterDEX 多钱包管理系统")
    print(f"{'='*60}")
    print(f"访问地址: http://localhost:{port}")
    print(f"默认账户: admin / admin123")
    print("\n核心功能:")
    print("- 多钱包管理 (现货/合约)")
    print("- 交易任务管理")
    print("- 多进程策略执行")
    print("- 实时状态监控")
    print("- 安全的API密钥存储")
    print(f"{'='*60}\n")
    
    return host, port, debug


if __name__ == '__main__':
    # 创建应用实例
    app = create_app()
    
    # 启动应用
    host, port, debug = start_app()
    app.run(debug=debug, host=host, port=port)
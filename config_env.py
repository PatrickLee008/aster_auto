"""
环境配置加载器
使用 python-dotenv 从.env文件加载配置
"""

import os
from typing import Dict, Optional, Union
from dotenv import load_dotenv


def load_environment():
    """
    加载环境变量文件
    优先级：.env.local > .envProd (生产环境) > .env (开发环境)
    """
    # 检查环境类型
    environment = os.getenv('ENVIRONMENT', 'development')
    
    # 按优先级加载配置文件
    env_files = []
    
    if environment == 'production':
        # 生产环境：基础配置 -> 生产环境配置 -> 本地覆盖
        env_files = ['.env', '.envProd', '.env.local']
    else:
        # 开发环境：基础配置 -> 本地覆盖
        env_files = ['.env', '.env.local']
    
    loaded_files = []
    for env_file in env_files:
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
            loaded_files.append(env_file)
    
    if loaded_files:
        print(f"已加载配置文件: {', '.join(loaded_files)}")
        print(f"当前环境: {environment}")
        print(f"最终配置 - SMARTPROXY_ENABLED: {os.getenv('SMARTPROXY_ENABLED', 'undefined')}")
    else:
        print("警告: 未找到任何环境配置文件")


def get_env(key: str, default: Union[str, int, bool, None] = None) -> str:
    """获取环境变量"""
    return os.getenv(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    """获取布尔类型环境变量"""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')


def get_env_int(key: str, default: int = 0) -> int:
    """获取整数类型环境变量"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def get_env_float(key: str, default: float = 0.0) -> float:
    """获取浮点数类型环境变量"""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


# 加载环境变量
load_environment()

# 数据库配置
DATABASE_CONFIG = {
    'host': get_env('DB_HOST', 'localhost'),
    'port': get_env_int('DB_PORT', 3306),
    'username': get_env('DB_USERNAME', 'root'),
    'password': get_env('DB_PASSWORD', ''),
    'database': get_env('DB_DATABASE', 'aster_auto')
}

# Flask应用配置
FLASK_CONFIG = {
    'secret_key': get_env('FLASK_SECRET_KEY', 'dev-secret-key'),
    'host': get_env('FLASK_HOST', '0.0.0.0'),
    'port': get_env_int('FLASK_PORT', 5000),
    'debug': get_env_bool('FLASK_DEBUG', True)
}

# 安全配置
SECURITY_CONFIG = {
    'encryption_key': get_env('ENCRYPTION_KEY', 'dev-encryption-key-32-chars-here').encode()
}

# 日志配置
LOGGING_CONFIG = {
    'level': get_env('LOG_LEVEL', 'INFO'),
    'log_dir': get_env('LOG_DIR', 'logs'),
    'max_log_files': get_env_int('MAX_LOG_FILES', 10)
}

# 代理配置
PROXY_CONFIG = {
    'enabled': get_env_bool('PROXY_ENABLED', False),  # 默认禁用代理，生产环境安全
    'host': get_env('PROXY_HOST', '127.0.0.1'),
    'port': get_env_int('PROXY_PORT', 7890),
    'type': get_env('PROXY_TYPE', 'socks5')
}

# Smartproxy配置
SMARTPROXY_CONFIG = {
    'enabled': get_env_bool('SMARTPROXY_ENABLED', False),
    'base_username': get_env('SMARTPROXY_BASE_USERNAME', ''),
    'password': get_env('SMARTPROXY_PASSWORD', ''),
    'residential_host': get_env('SMARTPROXY_RESIDENTIAL_HOST', 'gate.decodo.com'),
    'residential_port': get_env_int('SMARTPROXY_RESIDENTIAL_PORT', 10001),
    'datacenter_host': get_env('SMARTPROXY_DATACENTER_HOST', 'gate.decodo.com'),
    'datacenter_port': get_env_int('SMARTPROXY_DATACENTER_PORT', 8001),
    'session_duration': get_env_int('SMARTPROXY_SESSION_DURATION', 60)
}

# 期货交易配置 (仅用作策略回退，钱包管理器使用数据库配置)
FUTURES_CONFIG = {
    'user_address': get_env('FUTURES_USER_ADDRESS', ''),
    'signer_address': get_env('FUTURES_SIGNER_ADDRESS', ''),
    'private_key': get_env('FUTURES_PRIVATE_KEY', '')
}

# 现货交易配置 (仅用作策略回退，钱包管理器使用数据库配置)
SPOT_CONFIG = {
    'api_key': get_env('SPOT_API_KEY', ''),
    'secret_key': get_env('SPOT_SECRET_KEY', '')
}

# API主机配置
HOSTS = {
    'futures': get_env('FUTURES_HOST', 'https://fapi.asterdex.com'),
    'spot': get_env('SPOT_HOST', 'https://sapi.asterdex.com'),
    'futures_testnet': get_env('FUTURES_TESTNET_HOST', 'https://testnet-fapi.asterdex.com'),
    'spot_testnet': get_env('SPOT_TESTNET_HOST', 'https://testnet-sapi.asterdex.com')
}


def get_proxy_dict() -> Optional[Dict[str, str]]:
    """
    获取代理配置字典
    
    Returns:
        dict or None: 代理配置字典，如果禁用代理则返回None
    """
    if not PROXY_CONFIG['enabled']:
        return None
    
    proxy_url = f"{PROXY_CONFIG['type']}://{PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}"
    return {
        'http': proxy_url,
        'https': proxy_url
    }


def print_config_status():
    """
    打印配置状态
    """
    print("=== AsterDEX 配置状态 ===")
    
    # 环境信息
    environment = os.getenv('ENVIRONMENT', 'development')
    print(f"当前环境: {environment}")
    
    # 配置文件状态
    config_files_exist = {
        '.env': os.path.exists('.env'),
        '.envProd': os.path.exists('.envProd'),
        '.env.local': os.path.exists('.env.local')
    }
    existing_files = [f for f, exists in config_files_exist.items() if exists]
    print(f"配置文件: {', '.join(existing_files) if existing_files else '无'}")
    
    # 期货配置检查 (仅作回退使用)
    futures_ready = all([
        FUTURES_CONFIG['user_address'],
        FUTURES_CONFIG['signer_address'], 
        FUTURES_CONFIG['private_key']
    ]) and not FUTURES_CONFIG['private_key'].endswith('_HERE')
    
    print(f"期货回退配置: {'配置' if futures_ready else '未配置'} (策略回退用)")
    if futures_ready:
        print(f"  用户地址: {FUTURES_CONFIG['user_address']}")
        print(f"  签名地址: {FUTURES_CONFIG['signer_address']}")
        print(f"  私钥: {FUTURES_CONFIG['private_key'][:10]}...{FUTURES_CONFIG['private_key'][-8:]}")
    
    # 现货配置检查 (仅作回退使用)
    spot_ready = all([
        SPOT_CONFIG['api_key'],
        SPOT_CONFIG['secret_key']
    ]) and not SPOT_CONFIG['api_key'].endswith('_HERE')
    
    print(f"现货回退配置: {'配置' if spot_ready else '未配置'} (策略回退用)")
    if spot_ready:
        print(f"  API密钥: {SPOT_CONFIG['api_key'][:10]}...{SPOT_CONFIG['api_key'][-8:]}")
        print(f"  密钥: {SPOT_CONFIG['secret_key'][:10]}...{SPOT_CONFIG['secret_key'][-8:]}")
    
    # 代理配置
    proxy_dict = get_proxy_dict()
    print(f"代理设置: {'启用' if proxy_dict else '禁用'}")
    if proxy_dict:
        print(f"  代理地址: {proxy_dict['https']}")
    
    # Smartproxy配置
    smartproxy_ready = SMARTPROXY_CONFIG['enabled'] and SMARTPROXY_CONFIG['base_username'] and SMARTPROXY_CONFIG['password']
    print(f"Smartproxy设置: {'启用' if smartproxy_ready else '禁用'}")
    if smartproxy_ready:
        print(f"  用户名: {SMARTPROXY_CONFIG['base_username']}")
        print(f"  主机: {SMARTPROXY_CONFIG['residential_host']}:{SMARTPROXY_CONFIG['residential_port']}")
        print(f"  会话时长: {SMARTPROXY_CONFIG['session_duration']}分钟")
    
    # 数据库配置
    print(f"数据库: {DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}")
    
    # Flask配置
    debug_status = "开启" if FLASK_CONFIG['debug'] else "关闭"
    print(f"调试模式: {debug_status}")
    
    print("\n注意: 主要API配置现在通过钱包管理器存储在数据库中")


if __name__ == '__main__':
    print_config_status()
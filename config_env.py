"""
环境配置加载器
支持从.env或.envProd文件加载配置
"""

import os
from typing import Dict, Optional, Union


def load_env_file(env_file: str = None) -> None:
    """
    加载环境变量文件
    
    Args:
        env_file: 环境文件路径，默认根据ENVIRONMENT环境变量选择
    """
    if env_file is None:
        environment = os.getenv('ENVIRONMENT', 'development')
        if environment == 'production':
            env_file = '.envProd'
        else:
            env_file = '.env'
    
    if not os.path.exists(env_file):
        print(f"警告: 环境配置文件 {env_file} 不存在")
        return
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


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


# 加载环境变量
load_env_file()

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
    'enabled': get_env_bool('PROXY_ENABLED', True),
    'host': get_env('PROXY_HOST', '127.0.0.1'),
    'port': get_env_int('PROXY_PORT', 7890),
    'type': get_env('PROXY_TYPE', 'socks5')
}

# 期货交易配置
FUTURES_CONFIG = {
    'user_address': get_env('FUTURES_USER_ADDRESS', ''),
    'signer_address': get_env('FUTURES_SIGNER_ADDRESS', ''),
    'private_key': get_env('FUTURES_PRIVATE_KEY', '')
}

# 现货交易配置
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
    
    # 期货配置检查
    futures_ready = all([
        FUTURES_CONFIG['user_address'],
        FUTURES_CONFIG['signer_address'], 
        FUTURES_CONFIG['private_key']
    ]) and not FUTURES_CONFIG['private_key'].endswith('_HERE')
    
    print(f"期货交易: {'OK' if futures_ready else 'NOT_CONFIGURED'}")
    if futures_ready:
        print(f"  用户地址: {FUTURES_CONFIG['user_address']}")
        print(f"  签名地址: {FUTURES_CONFIG['signer_address']}")
        print(f"  私钥: {FUTURES_CONFIG['private_key'][:10]}...{FUTURES_CONFIG['private_key'][-8:]}")
    else:
        print(f"  用户地址: {FUTURES_CONFIG['user_address']}")
        print(f"  签名地址: {FUTURES_CONFIG['signer_address']}")
        print(f"  私钥: {FUTURES_CONFIG['private_key']}")
    
    # 现货配置检查
    spot_ready = all([
        SPOT_CONFIG['api_key'],
        SPOT_CONFIG['secret_key']
    ]) and not SPOT_CONFIG['api_key'].endswith('_HERE')
    
    print(f"现货交易: {'OK' if spot_ready else 'NOT_CONFIGURED'}")
    if spot_ready:
        print(f"  API密钥: {SPOT_CONFIG['api_key'][:10]}...{SPOT_CONFIG['api_key'][-8:]}")
        print(f"  密钥: {SPOT_CONFIG['secret_key'][:10]}...{SPOT_CONFIG['secret_key'][-8:]}")
    else:
        print(f"  API密钥: {SPOT_CONFIG['api_key']}")
        print(f"  密钥: {SPOT_CONFIG['secret_key']}")
    
    # 代理配置
    proxy_dict = get_proxy_dict()
    print(f"代理设置: {'ENABLED' if proxy_dict else 'DISABLED'}")
    if proxy_dict:
        print(f"  代理地址: {proxy_dict['https']}")
    
    # 数据库配置
    print(f"数据库: {DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}")
    
    # Flask配置
    debug_status = "ENABLED" if FLASK_CONFIG['debug'] else "DISABLED"
    print(f"调试模式: {debug_status}")


if __name__ == '__main__':
    print_config_status()
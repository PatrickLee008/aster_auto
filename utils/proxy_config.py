"""
全局代理配置工具
统一管理代理设置
"""

def get_proxy_config():
    """
    获取代理配置
    
    Returns:
        dict or None: 代理配置字典，如果禁用代理则返回None
    """
    try:
        from config_env import PROXY_CONFIG
        
        if not PROXY_CONFIG['enabled']:
            return None
        
        proxy_url = f"{PROXY_CONFIG['type']}://{PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}"
        return {
            'http': proxy_url,
            'https': proxy_url
        }
        
    except ImportError:
        # 如果没有配置文件，使用默认配置（本地开发）
        return {
            'http': 'socks5://127.0.0.1:7890',
            'https': 'socks5://127.0.0.1:7890'
        }
    except Exception as e:
        print(f"获取代理配置失败: {e}")
        return None


def is_proxy_enabled():
    """
    检查代理是否启用
    
    Returns:
        bool: 代理是否启用
    """
    try:
        from config_env import PROXY_CONFIG
        return PROXY_CONFIG.get('enabled', False)
    except ImportError:
        return True  # 默认启用代理（本地开发）
    except Exception:
        return False


def get_proxy_info():
    """
    获取代理信息用于显示
    
    Returns:
        dict: 包含代理信息的字典
    """
    try:
        from config_env import PROXY_CONFIG
        return {
            'enabled': PROXY_CONFIG.get('enabled', False),
            'host': PROXY_CONFIG.get('host', '127.0.0.1'),
            'port': PROXY_CONFIG.get('port', 7890),
            'type': PROXY_CONFIG.get('type', 'socks5')
        }
    except ImportError:
        return {
            'enabled': True,
            'host': '127.0.0.1',
            'port': 7890,
            'type': 'socks5'
        }
    except Exception:
        return {
            'enabled': False,
            'host': None,
            'port': None,
            'type': None
        }
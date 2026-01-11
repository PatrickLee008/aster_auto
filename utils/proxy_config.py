"""
全局代理配置工具
统一管理代理设置
"""

def is_proxy_enabled():
    """
    检查Bright Data代理是否启用
    
    Returns:
        bool: 代理是否启用
    """
    try:
        from models.system_config import SystemConfig
        return SystemConfig.get_value('brightdata_enabled', False)
    except Exception as e:
        print(f"检查代理状态失败: {e}")
        return False


def get_proxy_info():
    """
    获取代理信息用于显示
    
    Returns:
        dict: 包含代理信息的字典
    """
    try:
        from models.system_config import SystemConfig
        enabled = SystemConfig.get_value('brightdata_enabled', False)
        
        if enabled:
            # 从环境变量获取Bright Data配置信息
            from config_env import get_env
            host = get_env('BRIGHTDATA_HOST', 'brd.superproxy.io')
            port = get_env('BRIGHTDATA_PORT', '33335')
            
            return {
                'enabled': enabled,
                'host': host,
                'port': port,
                'type': 'http'
            }
        else:
            return {
                'enabled': enabled,
                'host': None,
                'port': None,
                'type': None
            }
    except Exception as e:
        print(f"获取代理信息失败: {e}")
        return {
            'enabled': False,
            'host': None,
            'port': None,
            'type': None
        }

def get_proxy_config():
    """
    获取代理配置（此函数现在主要用于向后兼容）
    
    Returns:
        dict or None: 代理配置字典，如果禁用代理则返回None
    """
    # 对于任务级代理，此函数不再主要使用，因为每个任务会有独立的代理配置
    # 保留此函数用于向后兼容
    try:
        from models.system_config import SystemConfig
        enabled = SystemConfig.get_value('brightdata_enabled', False)
        
        if not enabled:
            return None
        
        # 从环境变量获取Bright Data配置
        from config_env import get_env
        host = get_env('BRIGHTDATA_HOST', 'brd.superproxy.io')
        port = get_env('BRIGHTDATA_PORT', '33335')
        username = get_env('BRIGHTDATA_USERNAME', '')
        password = get_env('BRIGHTDATA_PASSWORD', '')
        
        if username and password:
            proxy_url = f"http://{username}:{password}@{host}:{port}"
            return {
                'http': proxy_url,
                'https': proxy_url
            }
        
    except Exception as e:
        print(f"获取代理配置失败: {e}")
        return None
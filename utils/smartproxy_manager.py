"""
Smartproxy代理管理器
为每个任务分配独立的美国IP地址
"""

import requests
import time
from typing import Dict, Optional, List
from config_env import get_env, get_env_bool
import logging

class SmartproxyManager:
    """Smartproxy代理管理器 - 支持任务级IP隔离"""
    
    def __init__(self):
        # 从环境变量读取配置
        self.enabled = get_env_bool('SMARTPROXY_ENABLED', False)
        self.base_username = get_env('SMARTPROXY_BASE_USERNAME', '')  # user-sp9y3nhxbw-sessionduration-60
        self.password = get_env('SMARTPROXY_PASSWORD', '')
        self.session_duration = get_env('SMARTPROXY_SESSION_DURATION', '60')
        
        # 住宅代理配置
        self.residential_endpoint = get_env('SMARTPROXY_RESIDENTIAL_HOST', 'rotating-residential.smartproxy.com')
        self.residential_port = int(get_env('SMARTPROXY_RESIDENTIAL_PORT', '10000'))
        
        # 数据中心代理配置
        self.datacenter_endpoint = get_env('SMARTPROXY_DATACENTER_HOST', 'datacenter.smartproxy.com')
        self.datacenter_port_range = range(10001, 10101)  # 100个端口
        
        # 任务代理映射缓存
        self.task_proxy_cache = {}
        
        # 日志
        self.logger = logging.getLogger(__name__)
        
    def get_proxy_for_task(self, task_id: int, proxy_type: str = 'residential') -> Optional[Dict]:
        """
        为任务获取专用美国代理
        
        Args:
            task_id: 任务ID
            proxy_type: 'residential' 或 'datacenter'
        
        Returns:
            代理配置字典 or None
        """
        if not self.enabled:
            return None
            
        if not self.base_username or not self.password:
            self.logger.error("Smartproxy凭证未配置")
            return None
            
        # 检查缓存
        cache_key = f"{task_id}_{proxy_type}"
        if cache_key in self.task_proxy_cache:
            return self.task_proxy_cache[cache_key]
        
        try:
            if proxy_type == 'residential':
                proxy_config = self._create_residential_proxy(task_id)
            elif proxy_type == 'datacenter':
                proxy_config = self._create_datacenter_proxy(task_id)
            else:
                raise ValueError(f"不支持的代理类型: {proxy_type}")
                
            # 可选的代理连接测试（不影响代理分配）
            test_success = self._test_proxy_connection(proxy_config)
            
            if test_success:
                # 测试成功，记录IP信息
                current_ip = proxy_config.get('current_ip', 'unknown')
                actual_country = proxy_config.get('actual_country', 'Unknown')
                actual_region = proxy_config.get('actual_region', 'Unknown')
                
                self.logger.info(f"✅ 任务 {task_id} 代理连接测试成功")
                self.logger.info(f"   代理类型: {proxy_type}")
                self.logger.info(f"   代理IP: {current_ip}")
                self.logger.info(f"   位置: {actual_region}, {actual_country}")
            else:
                self.logger.warning(f"⚠️ 任务 {task_id} 代理连接测试失败，但仍分配代理（可能是网络波动）")
                # 设置默认值
                proxy_config['current_ip'] = 'unknown'
                proxy_config['actual_country'] = 'Unknown'
                proxy_config['actual_region'] = 'Unknown'
            
            # 无论测试结果如何都分配代理
            self.task_proxy_cache[cache_key] = proxy_config
            return proxy_config
                
        except Exception as e:
            self.logger.error(f"为任务 {task_id} 创建代理失败: {e}")
            return None
    
    def _create_residential_proxy(self, task_id: int) -> Dict:
        """创建住宅代理（美国自动选择最优位置的粘性会话）"""
        # 基于decodo官方格式，动态创建美国IP（不指定州，自动选择网络最优位置）
        # 格式：username-country-session-sessionID
        session_id = f"task{task_id:04d}"
        
        # Smartproxy官方格式：user-username-country-us-session-sessionid
        # 移除state参数，让系统自动选择美国内网络最优的位置
        username_with_location = f"user-{self.base_username}-country-us-session-{session_id}"
        
        return {
            'proxy_type': 'residential',
            'protocol': 'http',
            'host': self.residential_endpoint,  # gate.decodo.com
            'port': self.residential_port,      # 10001
            'username': username_with_location,  # user-sp9y3nhxbw-country-us-session-taskXXXX
            'password': self.password,          # ez8m5F~gl6jG9snvPU
            'country': 'US',
            'state': None,  # 不指定州，自动选择最优位置
            'task_id': task_id,
            'session_id': session_id,
            'sticky_duration': f'{self.session_duration}min',
            'display_info': f"美国住宅IP (会话: {session_id}, {self.session_duration}分钟, 自动最优位置)"
        }
    
    def _create_datacenter_proxy(self, task_id: int) -> Dict:
        """创建数据中心代理"""
        # 根据任务ID分配固定端口
        port_index = task_id % len(self.datacenter_port_range)
        assigned_port = self.datacenter_port_range[port_index]
        
        return {
            'proxy_type': 'datacenter',
            'protocol': 'http',
            'host': self.datacenter_endpoint,
            'port': assigned_port,
            'username': self.username,
            'password': self.password,
            'country': 'US',
            'assigned_port': assigned_port,
            'display_info': f"美国数据中心IP (端口: {assigned_port})"
        }
    
    def _test_proxy_connection(self, proxy_config: Dict) -> bool:
        """测试代理连接（基于decodo官方格式）"""
        try:
            # 使用decodo官方推荐的格式和测试URL
            username = proxy_config['username']
            password = proxy_config['password'] 
            host = proxy_config['host']
            port = proxy_config['port']
            
            proxy_url = f"http://{username}:{password}@{host}:{port}"
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            # 使用decodo官方推荐的测试URL
            test_url = 'https://ip.decodo.com/json'
            
            response = requests.get(
                test_url,
                proxies=proxies,
                timeout=8,  # 稍微缩短超时时间
                headers={'User-Agent': 'AsterAuto/1.0'}
            )
            
            if response.status_code == 200:
                ip_info = response.json()
                current_ip = ip_info.get('ip', 'unknown')
                country = ip_info.get('country', {}).get('name', 'Unknown') if isinstance(ip_info.get('country'), dict) else str(ip_info.get('country', 'Unknown'))
                region = ip_info.get('region', 'Unknown')
                
                proxy_config['current_ip'] = current_ip
                proxy_config['actual_country'] = country  
                proxy_config['actual_region'] = region
                
                self.logger.info(f"代理测试成功 - IP: {current_ip}, 位置: {region}, {country}")
                return True
            else:
                self.logger.warning(f"代理测试HTTP错误: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"代理连接测试失败: {e}")
            return False
    
    def get_proxy_dict_for_requests(self, proxy_config: Dict) -> Dict[str, str]:
        """
        生成适用于requests库的代理配置
        
        Returns:
            {'http': 'http://user:pass@host:port', 'https': 'http://user:pass@host:port'}
        """
        if not proxy_config:
            return {}
            
        proxy_url = f"http://{proxy_config['username']}:{proxy_config['password']}@{proxy_config['host']}:{proxy_config['port']}"
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def release_proxy_for_task(self, task_id: int):
        """释放任务的代理资源"""
        # 住宅代理的粘性会话会自动过期，无需手动释放
        # 清理本地缓存即可
        keys_to_remove = [k for k in self.task_proxy_cache.keys() if k.startswith(f"{task_id}_")]
        for key in keys_to_remove:
            del self.task_proxy_cache[key]
            
        self.logger.info(f"任务 {task_id} 代理资源已释放")
    
    def get_proxy_statistics(self) -> Dict:
        """获取代理使用统计"""
        return {
            'enabled': self.enabled,
            'active_tasks': len(self.task_proxy_cache),
            'cached_proxies': list(self.task_proxy_cache.keys()),
            'residential_endpoint': self.residential_endpoint,
            'datacenter_endpoint': self.datacenter_endpoint
        }


# 全局代理管理器实例
_proxy_manager = None

def get_proxy_manager() -> SmartproxyManager:
    """获取全局代理管理器实例"""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = SmartproxyManager()
    return _proxy_manager


def get_task_proxy_config(task_id: int, proxy_type: str = 'residential') -> Dict:
    """
    便捷函数：获取任务的代理配置
    
    Args:
        task_id: 任务ID
        proxy_type: 代理类型 ('residential' 或 'datacenter')
        
    Returns:
        适用于任务运行器的代理配置
    """
    manager = get_proxy_manager()
    proxy_config = manager.get_proxy_for_task(task_id, proxy_type)
    
    if proxy_config:
        # 转换为任务运行器期望的格式
        return {
            'proxy_enabled': True,
            'proxy_host': proxy_config['host'],
            'proxy_port': proxy_config['port'],
            'proxy_auth': f"{proxy_config['username']}:{proxy_config['password']}",
            'proxy_type': proxy_config['proxy_type'],
            'country': proxy_config.get('country', 'US'),
            'current_ip': proxy_config.get('current_ip', 'unknown')
        }
    else:
        return {
            'proxy_enabled': False,
            'proxy_host': None,
            'proxy_port': None
        }


if __name__ == '__main__':
    # 测试代码
    manager = SmartproxyManager()
    
    if manager.enabled:
        print("=== Smartproxy 代理管理器测试 ===")
        
        # 测试为任务1创建住宅代理
        proxy1 = manager.get_proxy_for_task(1, 'residential')
        print(f"任务1住宅代理: {proxy1}")
        
        # 测试为任务2创建数据中心代理
        proxy2 = manager.get_proxy_for_task(2, 'datacenter')
        print(f"任务2数据中心代理: {proxy2}")
        
        # 显示统计信息
        stats = manager.get_proxy_statistics()
        print(f"代理统计: {stats}")
    else:
        print("Smartproxy未启用，请配置环境变量")
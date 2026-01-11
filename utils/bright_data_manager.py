"""
Bright Data代理管理器
为每个任务分配独立的代理IP，替换现有的Decodo代理系统
"""
import requests
import time
from typing import Dict, Optional, List
from config_env import get_env, get_env_bool
import logging


class BrightDataManager:
    """Bright Data代理管理器 - 支持任务级IP隔离"""
    
    def __init__(self):
        # 从环境变量读取配置
        self.enabled = get_env_bool('BRIGHTDATA_ENABLED', False)
        self.customer = get_env('BRIGHTDATA_CUSTOMER', '')  # brd-customer-hl_5e1f2ce5-zone-aster
        self.password = get_env('BRIGHTDATA_PASSWORD', '')
        self.zone = get_env('BRIGHTDATA_ZONE', 'aster')  # 代理区域
        self.country = get_env('BRIGHTDATA_COUNTRY', 'us')  # 目标国家
        
        # 代理目标国家设置 - 为避免区域限制，可自定义国家
        self.target_country = get_env('BRIGHTDATA_TARGET_COUNTRY', self.country)  # 使用BRIGHTDATA_COUNTRY作为默认值
        self.session_duration = get_env('BRIGHTDATA_SESSION_DURATION', '60')
        
        # Bright Data代理配置
        self.proxy_endpoint = get_env('BRIGHTDATA_HOST', 'brd.superproxy.io')
        self.proxy_port = int(get_env('BRIGHTDATA_PORT', '33335'))  # 根据您的配置使用33335端口
        

        
        # 任务代理映射缓存
        self.task_proxy_cache = {}
        
        # 日志
        self.logger = logging.getLogger(__name__)
        
    def get_proxy_for_task(self, task_id: int, proxy_type: str = 'isp') -> Optional[Dict]:
        """
        为任务获取专用代理

        Args:
            task_id: 任务ID
            proxy_type: 'residential', 'datacenter', 'mobile' 或 'isp'

        Returns:
            代理配置字典 or None
        """
        if not self.enabled:
            return None
            
        if not self.customer or not self.password:
            self.logger.error("Bright Data凭证未配置")
            return None
            
        # 检查缓存，但如果IP未知则重新获取
        cache_key = f"{task_id}_{proxy_type}"
        if cache_key in self.task_proxy_cache:
            cached_proxy = self.task_proxy_cache[cache_key]
            # 如果缓存的IP是unknown，则重新获取代理配置
            if cached_proxy.get('current_ip') == 'unknown':
                self.logger.info(f"缓存的IP为unknown，重新获取任务 {task_id} 的代理配置")
            else:
                # 返回缓存的代理配置
                return cached_proxy
        
        try:
            proxy_config = self._create_proxy_config(task_id, proxy_type)
            
            # 测试代理连接并测量延迟
            test_success, latency = self._test_proxy_connection_with_latency(proxy_config)
            
            if test_success:
                # 测试成功，记录IP信息
                current_ip = proxy_config.get('current_ip', 'unknown')
                actual_country = proxy_config.get('actual_country', 'Unknown')
                actual_region = proxy_config.get('actual_region', 'Unknown')
                
                self.logger.info(f"✅ 任务 {task_id} 代理连接测试成功")
                self.logger.info(f"   代理类型: {proxy_type}")
                self.logger.info(f"   代理IP: {current_ip}")
                self.logger.info(f"   位置: {actual_region}, {actual_country}")
                self.logger.info(f"   延迟: {latency}ms")
            else:
                self.logger.warning(f"⚠️ 任务 {task_id} 代理连接测试失败，但仍分配代理（可能是网络波动）")
                # 设置默认值
                proxy_config['current_ip'] = 'unknown'
                proxy_config['actual_country'] = 'Unknown'
                proxy_config['actual_region'] = 'Unknown'
                proxy_config['latency'] = 9999  # 高延迟标记
            
            # 无论测试结果如何都分配代理
            self.task_proxy_cache[cache_key] = proxy_config
            return proxy_config
                
        except Exception as e:
            self.logger.error(f"为任务 {task_id} 创建代理失败: {e}")
            return None
    
    def _create_proxy_config(self, task_id: int, proxy_type: str) -> Dict:
        """创建代理配置"""
        session_id = f"task{task_id:04d}"
        
        # 根据代理类型创建不同的用户名格式
        # 使用官方格式: brd-customer-hl_5e1f2ce5-zone-aster-country-us
        # 例如: brd-customer-hl_5e1f2ce5-zone-aster-country-us:jlfm7ayb6puo@brd.superproxy.io:33335
        base_username = f"{self.customer}-country-{self.target_country}"
        if proxy_type == 'residential':
            # 住宅代理格式
            username = f"{base_username}-session-{session_id}"
        elif proxy_type == 'datacenter':
            # 数据中心代理格式
            username = f"{base_username}-session-{session_id}"
        elif proxy_type == 'mobile':
            # 移动代理格式
            username = f"{base_username}-session-{session_id}"
        elif proxy_type == 'isp':
            # ISP代理格式 - 使用基础国家格式，代理类型在测试URL中指定
            username = f"{base_username}-session-{session_id}"
        else:
            # 默认使用住宅代理
            username = f"{base_username}-session-{session_id}"
        
        return {
            'proxy_type': proxy_type,
            'protocol': 'http',
            'host': self.proxy_endpoint,
            'port': self.proxy_port,
            'username': username,
            'password': self.password,
            'country': 'Auto',  # 自动分配
            'task_id': task_id,
            'session_id': session_id,
            'sticky_duration': f'{self.session_duration}min',
            'display_info': f"{proxy_type.title()} IP (会话: {session_id}, {self.session_duration}分钟)"
        }
    
    def _test_proxy_connection_with_latency(self, proxy_config: Dict) -> tuple[bool, int]:
        """测试代理连接并返回延迟"""
        try:
            # 使用Bright Data官方推荐的测试URL
            username = proxy_config['username']
            password = proxy_config['password'] 
            host = proxy_config['host']
            port = proxy_config['port']
                
            proxy_url = f"http://{username}:{password}@{host}:{port}"
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
                
            # 使用可靠的IP检测服务，同时保留位置信息获取
            # 结合使用httpbin.org获取IP和geo.brdtest.com获取位置信息
            test_url = 'https://geo.brdtest.com/welcome.txt?product=isp&method=native'
                
            # 记录开始测试时间以计算延迟
            import time
            start_time = time.time()
                
            self.logger.info(f"🔍 开始测试代理连接: {host}:{port}")
                
            response = requests.get(
                test_url,
                proxies=proxies,
                timeout=15,  # 增加超时时间到15秒
                headers={'User-Agent': 'AsterAuto/1.0'}
            )
                
            # 计算延迟（毫秒）
            end_time = time.time()
            latency_ms = round((end_time - start_time) * 1000)
                
            if response.status_code == 200:
                # geo.brdtest.com返回文本格式响应，需要解析IP和位置信息
                content = response.text
                current_ip = 'unknown'
                country = 'Unknown'
                region = 'Unknown'
                city = 'Unknown'
                            
                # 从文本内容中提取位置信息
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('Country:'):
                        country = line.replace('Country:', '').strip()
                    elif line.startswith('Region:'):
                        region = line.replace('Region:', '').strip()
                    elif line.startswith('City:'):
                        city = line.replace('City:', '').strip()
                            
                # 尝试从文本中提取IP地址，但避免提取1.1.1.1这类公共IP
                import re
                ip_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
                ip_matches = re.findall(ip_pattern, content)
                            
                # 过滤掉公共IP地址
                for ip_match in ip_matches:
                    if not ip_match.startswith('1.1.1.') and ip_match != '1.1.1.1' and not ip_match.startswith('8.8.8') and not ip_match.startswith('208.67'):
                        current_ip = ip_match
                        break
                            
                proxy_config['current_ip'] = current_ip
                proxy_config['actual_country'] = country
                proxy_config['actual_region'] = f"{city}, {region}" if city != 'Unknown' and region != 'Unknown' else region
                proxy_config['latency'] = latency_ms  # 添加延迟信息
                            
                self.logger.info(f"✅ 代理测试成功 - IP: {current_ip}, 位置: {proxy_config['actual_region']}, {country}, 延迟: {latency_ms}ms")
                return True, latency_ms
            else:
                self.logger.warning(f"❌ 代理测试HTTP错误: {response.status_code}")
                self.logger.warning(f"响应内容: {response.text[:200]}")
                return False, 9999
                    
        except requests.exceptions.Timeout as e:
            self.logger.warning(f"⏱️ 代理连接测试超时(15秒): {e}")
            return False, 9999
        except requests.exceptions.ProxyError as e:
            self.logger.warning(f"🚫 代理连接错误: {e}")
            return False, 9999
        except requests.exceptions.ConnectionError as e:
            self.logger.warning(f"🔌 网络连接错误: {e}")
            return False, 9999
        except Exception as e:
            self.logger.warning(f"❌ 代理连接测试失败: {type(e).__name__} - {e}")
            return False, 9999
    
    def _test_proxy_connection(self, proxy_config: Dict) -> bool:
        """兼容旧方法：测试代理连接"""
        success, _ = self._test_proxy_connection_with_latency(proxy_config)
        return success
    
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
        # Bright Data的会话会在一段时间不活动后自动过期，无需手动释放
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
            'proxy_endpoint': self.proxy_endpoint,
            'proxy_port': self.proxy_port
        }


# 全局代理管理器实例
_proxy_manager = None


def get_bright_data_manager() -> BrightDataManager:
    """获取全局Bright Data代理管理器实例"""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = BrightDataManager()
    return _proxy_manager


def get_task_bright_data_config(task_id: int, proxy_type: str = 'isp') -> Dict:
    """
    便捷函数：获取任务的Bright Data代理配置

    Args:
        task_id: 任务ID
        proxy_type: 代理类型 ('residential', 'datacenter', 'mobile', 'isp')

    Returns:
        适用于任务运行器的代理配置
    """
    manager = get_bright_data_manager()
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
            'current_ip': proxy_config.get('current_ip', 'unknown'),
            'actual_country': proxy_config.get('actual_country', 'Unknown'),
            'actual_region': proxy_config.get('actual_region', 'Unknown'),
            'latency': proxy_config.get('latency', 'N/A'),  # 延迟信息
            'session_id': proxy_config.get('session_id', 'N/A')
        }
    else:
        return {
            'proxy_enabled': False,
            'proxy_host': None,
            'proxy_port': None
        }


if __name__ == '__main__':
    # 测试代码
    manager = BrightDataManager()
    
    if manager.enabled:
        print("=== Bright Data 代理管理器测试 ===")
        
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
        print("Bright Data未启用，请配置环境变量")
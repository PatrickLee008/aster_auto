"""
Bright Data 代理客户端
基于您的实际账户信息实现的代理客户端
"""
import requests
import time
from typing import Dict, Optional
from config_env import get_env, get_env_bool
import logging


class BrightDataClient:
    """Bright Data 代理客户端 - 基于实际账户信息"""

    def __init__(self, customer: str = None, password: str = None, zone: str = None, 
                 host: str = None, port: int = None):
        """
        初始化客户端
        
        Args:
            customer: 客户名 (例如: brd-customer-hl_5e1f2ce5-zone-aster)
            password: 密码
            zone: 代理区域 (默认: aster)
            host: 代理主机 (默认: brd.superproxy.io)
            port: 代理端口 (默认: 33335)
        """
        # 如果没有传入参数，则从环境变量获取
        self.customer = customer or get_env('BRIGHTDATA_CUSTOMER', '')
        self.password = password or get_env('BRIGHTDATA_PASSWORD', '')
        self.zone = zone or get_env('BRIGHTDATA_ZONE', 'aster')
        self.host = host or get_env('BRIGHTDATA_HOST', 'brd.superproxy.io')
        self.port = port or int(get_env('BRIGHTDATA_PORT', '33335'))

        # 验证必要参数
        if not self.customer or not self.password:
            raise ValueError("必须提供客户名和密码")

        self.logger = logging.getLogger(__name__)

    def get_proxy_url(self, session_id: str = None, country: str = 'auto') -> str:
        """
        生成代理URL
        
        Args:
            session_id: 会话ID (可选，如果不提供则使用时间戳)
            country: 目标国家 (默认: auto)
            
        Returns:
            代理URL字符串
        """
        if not session_id:
            session_id = f"sess{int(time.time())}"
        
        # 根据您的实际格式构建用户名
        # 例如: brd-customer-hl_5e1f2ce5-zone-aster-country-us:jlfm7ayb6puo@brd.superproxy.io:33335
        username = f"{self.customer}-country-{country}-session-{session_id}"
        proxy_url = f"http://{username}:{self.password}@{self.host}:{self.port}"
        
        return proxy_url

    def get_proxy_config(self, session_id: str = None, country: str = 'auto') -> Dict[str, str]:
        """
        获取适用于requests的代理配置
        
        Args:
            session_id: 会话ID
            country: 目标国家
            
        Returns:
            代理配置字典
        """
        proxy_url = self.get_proxy_url(session_id, country)
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def test_proxy_connection(self, session_id: str = None, country: str = 'auto') -> Dict:
        """
        测试代理连接
        
        Args:
            session_id: 会话ID
            country: 目标国家
            
        Returns:
            测试结果字典
        """
        try:
            proxy_config = self.get_proxy_config(session_id, country)
            
            # 使用Bright Data官方测试URL
            test_url = 'https://geo.brdtest.com/myip.json'
            
            response = requests.get(
                test_url,
                proxies=proxy_config,
                timeout=15,
                headers={'User-Agent': 'BrightData-Client/1.0'}
            )
            
            if response.status_code == 200:
                ip_info = response.json()
                
                result = {
                    'success': True,
                    'ip': ip_info.get('ip', 'unknown'),
                    'country': ip_info.get('country', 'unknown'),
                    'region': ip_info.get('region', 'unknown'),
                    'city': ip_info.get('city', 'unknown'),
                    'isp': ip_info.get('isp', 'unknown'),
                    'user_agent': ip_info.get('user_agent', 'unknown'),
                    'proxy_config': proxy_config
                }
                
                self.logger.info(f"✅ 代理连接测试成功 - IP: {result['ip']}, 国家: {result['country']}")
                return result
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'response_text': response.text[:200]
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def make_request_through_proxy(self, url: str, session_id: str = None, 
                                 country: str = 'auto', **kwargs) -> Optional[requests.Response]:
        """
        通过代理发送请求
        
        Args:
            url: 目标URL
            session_id: 会话ID
            country: 目标国家
            **kwargs: 传递给requests的其他参数
            
        Returns:
            Response对象或None
        """
        try:
            proxy_config = self.get_proxy_config(session_id, country)
            
            # 合并用户提供的参数
            request_kwargs = {
                'proxies': proxy_config,
                'timeout': kwargs.pop('timeout', 30),
                'headers': kwargs.pop('headers', {}),
            }
            request_kwargs.update(kwargs)
            
            # 设置默认User-Agent
            if 'User-Agent' not in request_kwargs['headers']:
                request_kwargs['headers']['User-Agent'] = 'BrightData-Client/1.0'
            
            response = requests.get(url, **request_kwargs)
            return response
            
        except Exception as e:
            self.logger.error(f"通过代理请求失败: {e}")
            return None


# 便捷函数
def create_bright_data_client() -> BrightDataClient:
    """根据环境变量创建Bright Data客户端"""
    customer = get_env('BRIGHTDATA_CUSTOMER', '')
    password = get_env('BRIGHTDATA_PASSWORD', '')
    
    if not customer or not password:
        raise ValueError("请在环境变量中配置 BRIGHTDATA_CUSTOMER 和 BRIGHTDATA_PASSWORD")
    
    return BrightDataClient(customer=customer, password=password)


if __name__ == '__main__':
    # 示例用法
    print("=== Bright Data 客户端测试 ===")
    
    try:
        # 从环境变量创建客户端
        client = create_bright_data_client()
        
        print(f"客户名: {client.customer}")
        print(f"主机: {client.host}:{client.port}")
        
        # 测试代理连接
        print("\n🔍 测试代理连接...")
        result = client.test_proxy_connection()
        
        if result['success']:
            print(f"✅ 连接成功!")
            print(f"   IP: {result['ip']}")
            print(f"   国家: {result['country']}")
            print(f"   区域: {result['region']}")
            print(f"   城市: {result['city']}")
            print(f"   ISP: {result['isp']}")
        else:
            print(f"❌ 连接失败: {result['error']}")
            
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        print("请在 .env 文件中配置以下变量:")
        print("  BRIGHTDATA_CUSTOMER=brd-customer-hl_5e1f2ce5-zone-aster")
        print("  BRIGHTDATA_PASSWORD=jlfm7ayb6puo")
        print("  BRIGHTDATA_HOST=brd.superproxy.io")
        print("  BRIGHTDATA_PORT=33335")
        print("  BRIGHTDATA_ZONE=aster")
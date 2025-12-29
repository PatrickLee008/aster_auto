"""
钱包服务
"""

from typing import Optional, List, Tuple
from datetime import datetime

from models import Wallet, Task
from models.base import db


class WalletService:
    """钱包服务类"""
    
    @staticmethod
    def create_wallet(user_id: int, name: str, wallet_type: str, **kwargs) -> Tuple[bool, str, Optional[Wallet]]:
        """
        创建钱包
        
        Returns:
            (success, message, wallet)
        """
        try:
            # 验证钱包类型
            if wallet_type not in ['spot', 'futures']:
                return False, "不支持的钱包类型", None
            
            # 创建钱包对象
            wallet = Wallet(
                name=name,
                wallet_type=wallet_type,
                description=kwargs.get('description'),
                user_address=kwargs.get('user_address'),
                signer_address=kwargs.get('signer_address'),
                user_id=user_id
            )
            
            # 设置API凭证
            wallet.set_api_credentials(
                api_key=kwargs.get('api_key'),
                secret_key=kwargs.get('secret_key'),
                private_key=kwargs.get('private_key')
            )
            
            db.session.add(wallet)
            db.session.commit()
            
            return True, "钱包创建成功", wallet
            
        except Exception as e:
            db.session.rollback()
            return False, f"创建钱包失败: {str(e)}", None
    
    @staticmethod
    def update_wallet(wallet_id: int, user_id: int, **kwargs) -> Tuple[bool, str]:
        """
        更新钱包信息
        
        Returns:
            (success, message)
        """
        try:
            wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
            if not wallet:
                return False, "钱包不存在"
            
            # 更新基本信息
            if 'name' in kwargs:
                wallet.name = kwargs['name']
            if 'description' in kwargs:
                wallet.description = kwargs['description']
            if 'is_active' in kwargs:
                wallet.is_active = kwargs['is_active']
            
            # 更新API凭证（如果提供）
            api_key = kwargs.get('api_key')
            secret_key = kwargs.get('secret_key')
            private_key = kwargs.get('private_key')
            
            if api_key or secret_key or private_key:
                wallet.set_api_credentials(
                    api_key=api_key,
                    secret_key=secret_key,
                    private_key=private_key
                )
            
            wallet.updated_at = datetime.utcnow()
            db.session.commit()
            
            return True, "钱包更新成功"
            
        except Exception as e:
            db.session.rollback()
            return False, f"更新钱包失败: {str(e)}"
    
    @staticmethod
    def delete_wallet(wallet_id: int, user_id: int) -> Tuple[bool, str]:
        """
        删除钱包
        
        Returns:
            (success, message)
        """
        try:
            wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
            if not wallet:
                return False, "钱包不存在"
            
            # 检查是否有关联的运行中任务
            running_tasks = Task.query.filter_by(wallet_id=wallet_id, status='running').count()
            if running_tasks > 0:
                return False, "请先停止关联的运行中任务"
            
            db.session.delete(wallet)
            db.session.commit()
            
            return True, "钱包删除成功"
            
        except Exception as e:
            db.session.rollback()
            return False, f"删除钱包失败: {str(e)}"
    
    @staticmethod
    def test_wallet_connection(wallet_id: int, user_id: int) -> Tuple[bool, str]:
        """
        测试钱包连接
        
        Returns:
            (success, message)
        """
        try:
            wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
            if not wallet:
                return False, "钱包不存在"
            
            # 更新最后使用时间
            wallet.update_last_used()
            
            # 根据钱包类型测试连接
            if wallet.wallet_type == 'spot':
                success = WalletService._test_spot_connection(wallet)
            elif wallet.wallet_type == 'futures':
                success = WalletService._test_futures_connection(wallet)
            else:
                return False, "不支持的钱包类型"
            
            if success:
                return True, "连接测试成功"
            else:
                return False, "连接测试失败"
                
        except Exception as e:
            return False, f"连接测试异常: {str(e)}"
    
    @staticmethod
    def _test_spot_connection(wallet: Wallet) -> bool:
        """测试现货钱包连接"""
        try:
            from spot_client import AsterSpotClient
            
            credentials = wallet.get_api_credentials()
            if not credentials['api_key'] or not credentials['secret_key']:
                return False
            
            from utils.proxy_config import is_proxy_enabled, get_proxy_info
            
            proxy_enabled = is_proxy_enabled()
            proxy_info = get_proxy_info() if proxy_enabled else {}
            
            client = AsterSpotClient(
                api_key=credentials['api_key'],
                secret_key=credentials['secret_key'],
                proxy_host=proxy_info.get('host', '127.0.0.1') if proxy_enabled else None,
                proxy_port=proxy_info.get('port', 7890) if proxy_enabled else None,
                use_proxy=proxy_enabled
            )
            
            return client.test_connection()
        except Exception as e:
            print(f"现货连接测试失败: {e}")
            return False
    
    @staticmethod
    def _test_futures_connection(wallet: Wallet) -> bool:
        """测试期货钱包连接"""
        try:
            from futures_client import AsterFuturesClient
            
            credentials = wallet.get_api_credentials()
            if not wallet.user_address or not wallet.signer_address or not credentials['private_key']:
                return False
                
            from utils.proxy_config import is_proxy_enabled, get_proxy_info
            
            proxy_enabled = is_proxy_enabled()
            proxy_info = get_proxy_info() if proxy_enabled else {}
            
            client = AsterFuturesClient(
                user_address=wallet.user_address,
                signer_address=wallet.signer_address,
                private_key=credentials['private_key'],
                proxy_host=proxy_info.get('host', '127.0.0.1') if proxy_enabled else None,
                proxy_port=proxy_info.get('port', 7890) if proxy_enabled else None,
                use_proxy=proxy_enabled
            )
            
            return client.test_connection()
        except Exception as e:
            print(f"期货连接测试失败: {e}")
            return False
    
    @staticmethod
    def get_user_wallets(user_id: int, include_inactive: bool = False) -> List[Wallet]:
        """获取用户钱包列表"""
        try:
            query = Wallet.query.filter_by(user_id=user_id)
            if not include_inactive:
                query = query.filter_by(is_active=True)
            return query.order_by(Wallet.created_at.desc()).all()
        except Exception as e:
            print(f"获取钱包列表失败: {e}")
            return []
    
    @staticmethod
    def get_wallet_by_id(wallet_id: int, user_id: int) -> Optional[Wallet]:
        """根据ID获取钱包"""
        try:
            return Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
        except Exception as e:
            print(f"获取钱包失败: {e}")
            return None
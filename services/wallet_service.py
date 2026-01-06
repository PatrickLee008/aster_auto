"""
钱包服务
"""

from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from models import Wallet, Task
from models.base import db


class WalletService:
    """钱包服务类"""
    
    @staticmethod
    def create_unified_wallet(user_id: int, name: str, description: str, is_active: bool, **kwargs) -> Tuple[bool, str, List[Wallet]]:
        """
        创建统一钱包配置（可同时创建现货和合约钱包）
        
        Returns:
            (success, message, wallet_list)
        """
        try:
            created_wallets = []
            wallet_type = kwargs.get('wallet_type', 'auto')
            
            # 检查配置
            spot_api_key = kwargs.get('spot_api_key')
            spot_secret_key = kwargs.get('spot_secret_key')
            spot_api_type = kwargs.get('spot_api_type', 'normal')
            
            user_address = kwargs.get('user_address')
            signer_address = kwargs.get('signer_address')
            private_key = kwargs.get('private_key')
            futures_api_type = kwargs.get('futures_api_type', 'normal')
            
            has_spot_config = spot_api_key and spot_secret_key
            has_futures_config = user_address and signer_address and private_key
            
            if wallet_type == 'unified' and has_spot_config and has_futures_config:
                # 创建统一钱包（单个钱包包含现货和合约配置）
                unified_wallet = Wallet(
                    name=name,
                    wallet_type='unified',
                    description=f"{description} (统一钱包：现货+合约)",
                    user_address=user_address,
                    signer_address=signer_address,
                    user_id=user_id,
                    is_active=is_active
                )
                unified_wallet.set_api_credentials(
                    api_key=spot_api_key,
                    secret_key=spot_secret_key,
                    private_key=private_key
                )
                db.session.add(unified_wallet)
                created_wallets.append(unified_wallet)
                
            else:
                # 分别创建现货和合约钱包（原有逻辑）
                if has_spot_config:
                    spot_wallet = Wallet(
                        name=f"{name} - 现货",
                        wallet_type='spot',
                        description=f"{description} (现货API - {spot_api_type})",
                        user_id=user_id,
                        is_active=is_active
                    )
                    spot_wallet.set_api_credentials(
                        api_key=spot_api_key,
                        secret_key=spot_secret_key
                    )
                    db.session.add(spot_wallet)
                    created_wallets.append(spot_wallet)
                
                if has_futures_config:
                    futures_wallet = Wallet(
                        name=f"{name} - 合约",
                        wallet_type='futures',
                        description=f"{description} (合约API - {futures_api_type})",
                        user_address=user_address,
                        signer_address=signer_address,
                        user_id=user_id,
                        is_active=is_active
                    )
                    futures_wallet.set_api_credentials(private_key=private_key)
                    db.session.add(futures_wallet)
                    created_wallets.append(futures_wallet)
            
            if not created_wallets:
                return False, "请至少配置一种API（现货或合约）", []
            
            db.session.commit()
            
            wallet_types = [w.wallet_type for w in created_wallets]
            return True, f"成功创建 {len(created_wallets)} 个钱包配置：{', '.join(wallet_types)}", created_wallets
            
        except Exception as e:
            db.session.rollback()
            return False, f"创建钱包失败: {str(e)}", []

    @staticmethod
    def create_wallet(user_id: int, name: str, wallet_type: str, **kwargs) -> Tuple[bool, str, Optional[Wallet]]:
        """
        创建钱包（保留原有方法以兼容现有代码）
        
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
    def delete_wallet(wallet_id: int, user_id: int = None) -> Tuple[bool, str]:
        """
        删除钱包及其关联的任务
        
        Returns:
            (success, message)
        """
        try:
            from models.task import Task
            
            if user_id is None:
                # 管理员权限，可以删除任意钱包
                wallet = Wallet.query.filter_by(id=wallet_id).first()
            else:
                # 普通用户权限，只能删除自己的钱包
                wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
                
            if not wallet:
                return False, "钱包不存在"
            
            # 检查是否有关联的运行中任务
            running_tasks = Task.query.filter_by(wallet_id=wallet_id).filter(
                Task.status.in_(['running', 'pending'])
            ).count()
            if running_tasks > 0:
                return False, "请先停止关联的运行中或等待中的任务"
            
            # 获取关联任务数量用于反馈
            related_tasks_count = Task.query.filter_by(wallet_id=wallet_id).count()
            
            # 删除所有关联任务
            Task.query.filter_by(wallet_id=wallet_id).delete()
            
            # 删除钱包
            db.session.delete(wallet)
            db.session.commit()
            
            # 构造反馈消息
            message = "钱包删除成功"
            if related_tasks_count > 0:
                message += f"，同时删除了 {related_tasks_count} 个关联任务"
            
            return True, message
            
        except Exception as e:
            db.session.rollback()
            return False, f"删除钱包失败: {str(e)}"
    
    @staticmethod
    def test_wallet_connection(wallet_id: int, user_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        测试钱包连接并获取USDT余额
        
        Returns:
            (success, message, balance_info)
        """
        try:
            wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
            if not wallet:
                return False, "钱包不存在", None
            
            # 更新最后使用时间
            wallet.update_last_used()
            
            # 根据钱包配置的API类型测试连接并获取余额
            credentials = wallet.get_api_credentials()
            
            # 检查配置了哪些API
            has_spot_api = credentials.get('api_key') and credentials.get('secret_key')
            has_futures_api = wallet.user_address and wallet.signer_address and credentials.get('private_key')
            
            print(f"🔍 [钱包测试] 钱包ID: {wallet.id}, 类型: {wallet.wallet_type}")
            print(f"📊 现货API配置: {'是' if has_spot_api else '否'}")
            print(f"📈 期货API配置: {'是' if has_futures_api else '否'}")
            
            # 添加代理连接测试
            from utils.proxy_config import is_proxy_enabled, get_proxy_info
            proxy_enabled = is_proxy_enabled()
            if proxy_enabled:
                proxy_info = get_proxy_info()
                print(f"🌐 使用代理: {proxy_info}")
            else:
                print(f"🌐 未使用代理")
            
            if has_spot_api and has_futures_api:
                # 两种API都配置了，统一测试
                return WalletService._test_unified_connection(wallet)
                
            elif has_spot_api:
                # 只配置了现货API，测试现货
                print(f"🎯 测试现货API连接...")
                success, balance_info = WalletService._test_spot_connection(wallet)
                if success:
                    balance_msg = f" | 现货USDT: {balance_info.get('usdt_balance', 'N/A')}"
                    return True, f"现货连接测试成功{balance_msg}", balance_info
                else:
                    return False, "现货连接测试失败", None
                    
            elif has_futures_api:
                # 只配置了期货API，测试期货
                print(f"🎯 测试期货API连接...")
                success, balance_info = WalletService._test_futures_connection(wallet)
                if success:
                    balance_msg = f" | 合约USDT: {balance_info.get('usdt_balance', 'N/A')} | 可用保证金: {balance_info.get('available_balance', 'N/A')}"
                    return True, f"期货连接测试成功{balance_msg}", balance_info
                else:
                    return False, "期货连接测试失败", None
                    
            else:
                return False, "未配置任何API，请检查钱包配置", None
                
        except Exception as e:
            return False, f"连接测试异常: {str(e)}", None
    
    @staticmethod
    def _test_spot_connection(wallet: Wallet) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """测试现货钱包连接并获取余额"""
        try:
            from spot_client import AsterSpotClient
            
            credentials = wallet.get_api_credentials()
            if not credentials['api_key'] or not credentials['secret_key']:
                return False, None
            
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
            
            # 测试连接
            if not client.test_connection():
                return False, None
            
            # 获取账户信息和USDT余额
            account_info = client.get_account_info()
            balance_info = {}
            
            if account_info and 'balances' in account_info:
                # 查找USDT余额
                for balance in account_info['balances']:
                    if balance.get('asset') == 'USDT':
                        balance_info = {
                            'usdt_balance': float(balance.get('free', '0')),
                            'usdt_locked': float(balance.get('locked', '0')),
                            'total_usdt': float(balance.get('free', '0')) + float(balance.get('locked', '0'))
                        }
                        break
                
                if not balance_info:
                    balance_info = {'usdt_balance': 0.0, 'usdt_locked': 0.0, 'total_usdt': 0.0}
            else:
                balance_info = {'usdt_balance': 'N/A', 'usdt_locked': 'N/A', 'total_usdt': 'N/A'}
            
            return True, balance_info
            
        except Exception as e:
            print(f"现货连接测试失败: {e}")
            return False, None
    
    @staticmethod
    def _test_futures_connection(wallet: Wallet) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """测试期货钱包连接并获取余额"""
        try:
            from futures_client import AsterFuturesClient
            
            credentials = wallet.get_api_credentials()
            
            if not wallet.user_address or not wallet.signer_address or not credentials['private_key']:
                return False, None
                
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
            
            # 测试连接
            if not client.test_connection():
                return False, None
            
            
            # 获取账户余额信息
            # 根据API文档，期货账户信息端点是 /fapi/v3/balance
            balance_result = client._make_request('GET', '/fapi/v3/balance', {}, need_signature=True)
            balance_info = {}
            
            print(f"📊 期货余额信息: {balance_result}")
            
            if balance_result and isinstance(balance_result, list):
                # 查找USDT余额
                for asset in balance_result:
                    if asset.get('asset') == 'USDT':
                        balance_info = {
                            'usdt_balance': float(asset.get('balance', '0')),
                            'available_balance': float(asset.get('availableBalance', '0')),
                            'cross_wallet_balance': float(asset.get('crossWalletBalance', '0')),
                            'unrealized_pnl': float(asset.get('crossUnPnl', '0'))
                        }
                        break
                
                if not balance_info:
                    # 如果没找到USDT，使用默认值
                    balance_info = {
                        'usdt_balance': 0.0, 
                        'available_balance': 0.0,
                        'cross_wallet_balance': 0.0,
                        'unrealized_pnl': 0.0
                    }
            else:
                # API调用失败，返回N/A
                balance_info = {
                    'usdt_balance': 'N/A', 
                    'available_balance': 'N/A',
                    'cross_wallet_balance': 'N/A',
                    'unrealized_pnl': 'N/A'
                }
            
            return True, balance_info
            
        except Exception as e:
            print(f"期货连接测试失败: {e}")
            return False, None
    
    @staticmethod
    def _test_unified_connection(wallet: Wallet) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """测试统一钱包的现货和期货连接并获取余额"""
        try:
            combined_balance = {
                'spot': {'status': 'failed', 'usdt_balance': 'N/A'},
                'futures': {'status': 'failed', 'usdt_balance': 'N/A', 'available_balance': 'N/A'}
            }
            
            success_count = 0
            total_tests = 2
            
            # 测试现货连接
            try:
                spot_success, spot_balance = WalletService._test_spot_connection(wallet)
                if spot_success and spot_balance:
                    combined_balance['spot'] = {
                        'status': 'success',
                        'usdt_balance': spot_balance.get('usdt_balance', 0),
                        'usdt_locked': spot_balance.get('usdt_locked', 0),
                        'total_usdt': spot_balance.get('total_usdt', 0)
                    }
                    success_count += 1
                else:
                    combined_balance['spot']['status'] = 'failed'
            except Exception as e:
                print(f"现货测试失败: {e}")
                combined_balance['spot']['status'] = 'error'
            
            # 测试期货连接
            try:
                futures_success, futures_balance = WalletService._test_futures_connection(wallet)
                if futures_success and futures_balance:
                    combined_balance['futures'] = {
                        'status': 'success',
                        'usdt_balance': futures_balance.get('usdt_balance', 0),
                        'available_balance': futures_balance.get('available_balance', 0),
                        'cross_wallet_balance': futures_balance.get('cross_wallet_balance', 0),
                        'unrealized_pnl': futures_balance.get('unrealized_pnl', 0)
                    }
                    success_count += 1
                else:
                    combined_balance['futures']['status'] = 'failed'
            except Exception as e:
                print(f"期货测试失败: {e}")
                combined_balance['futures']['status'] = 'error'
            
            # 构造返回消息
            if success_count == 0:
                return False, "现货和期货连接均失败", None
            elif success_count == 1:
                spot_status = "成功" if combined_balance['spot']['status'] == 'success' else "失败"
                futures_status = "成功" if combined_balance['futures']['status'] == 'success' else "失败"
                
                # 构造余额消息
                balance_parts = []
                if combined_balance['spot']['status'] == 'success':
                    balance_parts.append(f"现货USDT: {combined_balance['spot']['usdt_balance']}")
                if combined_balance['futures']['status'] == 'success':
                    balance_parts.append(f"合约USDT: {combined_balance['futures']['usdt_balance']}")
                    balance_parts.append(f"可用保证金: {combined_balance['futures']['available_balance']}")
                
                balance_msg = " | " + " | ".join(balance_parts) if balance_parts else ""
                message = f"部分连接成功 (现货:{spot_status}, 期货:{futures_status}){balance_msg}"
                return True, message, combined_balance
            else:
                # 两个都成功
                balance_msg = (f" | 现货USDT: {combined_balance['spot']['usdt_balance']} | "
                              f"合约USDT: {combined_balance['futures']['usdt_balance']} | "
                              f"可用保证金: {combined_balance['futures']['available_balance']}")
                return True, f"现货和期货连接均成功{balance_msg}", combined_balance
                
        except Exception as e:
            print(f"统一钱包连接测试失败: {e}")
            return False, f"连接测试异常: {str(e)}", None
    
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
    def get_all_wallets(include_inactive: bool = False) -> List[Wallet]:
        """获取所有钱包列表（管理员用）"""
        try:
            query = Wallet.query
            if not include_inactive:
                query = query.filter_by(is_active=True)
            return query.order_by(Wallet.created_at.desc()).all()
        except Exception as e:
            print(f"获取所有钱包失败: {e}")
            return []
    
    @staticmethod
    def get_wallet_by_id(wallet_id: int, user_id: int = None) -> Optional[Wallet]:
        """根据ID获取钱包"""
        try:
            if user_id is None:
                # 管理员权限，可以查看任意钱包
                return Wallet.query.filter_by(id=wallet_id).first()
            else:
                # 普通用户权限，只能查看自己的钱包
                return Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
        except Exception as e:
            print(f"获取钱包失败: {e}")
            return None
"""
策略服务
"""

from typing import Optional, List, Tuple
import json

from models import Strategy
from models.base import db


class StrategyService:
    """策略服务类"""
    
    @staticmethod
    def create_strategy(name: str, description: str, strategy_type: str,
                       supported_wallet_types: str, module_path: str, 
                       class_name: str, default_parameters: dict = None) -> Tuple[bool, str, Optional[Strategy]]:
        """
        创建策略
        
        Returns:
            (success, message, strategy)
        """
        try:
            # 检查策略名称是否已存在
            if Strategy.query.filter_by(name=name).first():
                return False, "策略名称已存在", None
            
            strategy = Strategy(
                name=name,
                description=description,
                strategy_type=strategy_type,
                supported_wallet_types=supported_wallet_types,
                module_path=module_path,
                class_name=class_name
            )
            
            if default_parameters:
                strategy.set_default_parameters(default_parameters)
            
            db.session.add(strategy)
            db.session.commit()
            
            return True, "策略创建成功", strategy
            
        except Exception as e:
            db.session.rollback()
            return False, f"创建策略失败: {str(e)}", None
    
    @staticmethod
    def update_strategy(strategy_id: int, **kwargs) -> Tuple[bool, str]:
        """
        更新策略信息
        
        Returns:
            (success, message)
        """
        try:
            strategy = db.session.get(Strategy, strategy_id)
            if not strategy:
                return False, "策略不存在"
            
            # 更新字段
            if 'name' in kwargs:
                strategy.name = kwargs['name']
            if 'description' in kwargs:
                strategy.description = kwargs['description']
            if 'supported_wallet_types' in kwargs:
                strategy.supported_wallet_types = kwargs['supported_wallet_types']
            if 'is_active' in kwargs:
                strategy.is_active = kwargs['is_active']
            if 'default_parameters' in kwargs:
                strategy.set_default_parameters(kwargs['default_parameters'])
            
            db.session.commit()
            return True, "策略更新成功"
            
        except Exception as e:
            db.session.rollback()
            return False, f"更新策略失败: {str(e)}"
    
    @staticmethod
    def delete_strategy(strategy_id: int) -> Tuple[bool, str]:
        """
        删除策略
        
        Returns:
            (success, message)
        """
        try:
            strategy = db.session.get(Strategy, strategy_id)
            if not strategy:
                return False, "策略不存在"
            
            # 检查是否有关联的任务
            from models import Task
            related_tasks = Task.query.filter_by(strategy_id=strategy_id).count()
            if related_tasks > 0:
                return False, "存在关联任务，无法删除"
            
            db.session.delete(strategy)
            db.session.commit()
            
            return True, "策略删除成功"
            
        except Exception as e:
            db.session.rollback()
            return False, f"删除策略失败: {str(e)}"
    
    @staticmethod
    def get_active_strategies() -> List[Strategy]:
        """获取活跃策略列表"""
        try:
            return Strategy.query.filter_by(is_active=True)\
                                .order_by(Strategy.created_at.desc()).all()
        except Exception as e:
            print(f"获取策略列表失败: {e}")
            return []
    
    @staticmethod
    def get_all_strategies() -> List[Strategy]:
        """获取所有策略列表"""
        try:
            return Strategy.query.order_by(Strategy.created_at.desc()).all()
        except Exception as e:
            print(f"获取策略列表失败: {e}")
            return []
    
    @staticmethod
    def get_strategy_by_id(strategy_id: int) -> Optional[Strategy]:
        """根据ID获取策略"""
        try:
            return db.session.get(Strategy, strategy_id)
        except Exception as e:
            print(f"获取策略失败: {e}")
            return None
    
    @staticmethod
    def get_compatible_strategies(wallet_type: str) -> List[Strategy]:
        """获取与指定钱包类型兼容的策略"""
        try:
            return [strategy for strategy in StrategyService.get_active_strategies()
                   if strategy.is_compatible_with_wallet(wallet_type)]
        except Exception as e:
            print(f"获取兼容策略失败: {e}")
            return []
    
    @staticmethod
    def validate_strategy_module(module_path: str, class_name: str) -> Tuple[bool, str]:
        """
        验证策略模块是否存在和有效
        
        Returns:
            (success, message)
        """
        try:
            import importlib
            
            # 尝试导入模块
            module = importlib.import_module(module_path)
            
            # 检查类是否存在
            if not hasattr(module, class_name):
                return False, f"模块 {module_path} 中不存在类 {class_name}"
            
            # 获取类
            strategy_class = getattr(module, class_name)
            
            # 检查是否有run方法
            if not hasattr(strategy_class, 'run'):
                return False, f"策略类 {class_name} 缺少 run 方法"
            
            return True, "策略模块验证成功"
            
        except ImportError as e:
            return False, f"无法导入模块 {module_path}: {str(e)}"
        except Exception as e:
            return False, f"验证策略模块失败: {str(e)}"
    
    @staticmethod
    def initialize_default_strategies():
        """初始化默认策略"""
        try:
            # 检查是否已有策略
            if Strategy.query.count() > 0:
                return True, "策略已存在"
            
            default_strategies = [
                {
                    'name': '现货刷量策略',
                    'description': '现货刷量交易策略，通过买卖相同数量和价格的现货来刷交易量',
                    'strategy_type': 'volume',
                    'supported_wallet_types': 'spot,unified',
                    'module_path': 'strategies.volume_strategy',
                    'class_name': 'VolumeStrategy',
                    'default_parameters': {
                        'symbol': 'SENTISUSDT',
                        'quantity': '101.0', 
                        'interval': 5,
                        'rounds': 3
                    }
                },
                {
                    'name': '合约HIDDEN自成交策略',
                    'description': '使用HIDDEN隐藏订单实现合约自成交，零风险策略',
                    'strategy_type': 'hidden_futures',
                    'supported_wallet_types': 'futures,unified',
                    'module_path': 'strategies.hidden_futures_strategy',
                    'class_name': 'HiddenFuturesStrategy',
                    'default_parameters': {
                        'symbol': 'SKYUSDT',
                        'quantity': '3249.0',
                        'leverage': 20,
                        'rounds': 5,
                        'interval': 3
                    }
                }
            ]
            
            for strategy_data in default_strategies:
                strategy = Strategy(
                    name=strategy_data['name'],
                    description=strategy_data['description'],
                    strategy_type=strategy_data['strategy_type'],
                    supported_wallet_types=strategy_data['supported_wallet_types'],
                    module_path=strategy_data['module_path'],
                    class_name=strategy_data['class_name']
                )
                strategy.set_default_parameters(strategy_data['default_parameters'])
                
                db.session.add(strategy)
            
            db.session.commit()
            return True, "默认策略初始化成功"
            
        except Exception as e:
            db.session.rollback()
            return False, f"初始化默认策略失败: {str(e)}"
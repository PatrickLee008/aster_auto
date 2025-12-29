"""
任务模型
"""

from datetime import datetime
import json
import psutil
from decimal import Decimal as PyDecimal

from sqlalchemy import Numeric
from .base import db, BaseModel


class Task(db.Model, BaseModel):
    """交易任务模型"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # 任务名称必须唯一，用于生成日志文件
    description = db.Column(db.Text)
    
    # 任务配置 - 交易参数
    symbol = db.Column(db.String(20), nullable=False)  # 交易品种，如 BTCUSDT
    quantity = db.Column(Numeric(20, 8), nullable=False)  # 每次交易数量
    interval = db.Column(db.Integer, nullable=False)  # 间隔秒数
    rounds = db.Column(db.Integer, nullable=False)  # 循环次数
    leverage = db.Column(db.Integer, default=1)  # 杠杆倍数（合约交易用）
    side = db.Column(db.String(10), default='buy')  # 交易方向：buy, sell, both
    order_type = db.Column(db.String(10), default='market')  # 订单类型：market, limit
    
    # 保留原有的strategy_parameters字段用于其他扩展参数
    strategy_parameters = db.Column(db.Text)  # JSON格式的其他策略参数
    
    # 任务状态
    status = db.Column(db.String(20), default='stopped')  # 'stopped', 'running', 'paused', 'error'
    process_id = db.Column(db.Integer)  # 进程ID
    
    # 执行统计
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    total_rounds = db.Column(db.Integer, default=0)
    successful_rounds = db.Column(db.Integer, default=0)
    failed_rounds = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text)
    
    # 新增统计字段
    supplement_orders = db.Column(db.Integer, default=0, comment='补单数')
    total_cost_diff = db.Column(Numeric(20, 8), default=0, comment='总损耗')
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 外键
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallets.id'), nullable=False)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=False)
    
    def get_trading_parameters(self):
        """获取交易参数"""
        return {
            'symbol': self.symbol,
            'quantity': float(self.quantity),
            'interval': self.interval,
            'rounds': self.rounds,
            'leverage': self.leverage,
            'side': self.side,
            'order_type': self.order_type
        }
    
    def get_parameters(self):
        """获取所有参数（包括交易参数和其他参数）"""
        params = self.get_trading_parameters()
        if self.strategy_parameters:
            params.update(json.loads(self.strategy_parameters))
        return params
    
    def set_parameters(self, params_dict):
        """设置策略参数"""
        self.strategy_parameters = json.dumps(params_dict)
    
    def is_running(self):
        """检查任务是否正在运行"""
        if self.process_id and self.status == 'running':
            try:
                process = psutil.Process(self.process_id)
                return process.is_running()
            except psutil.NoSuchProcess:
                return False
        return False
    
    def update_status(self, status, error_message=None, process_id=None):
        """更新任务状态"""
        self.status = status
        if error_message:
            self.last_error = error_message
        if process_id is not None:
            self.process_id = process_id
        if status == 'running':
            self.start_time = datetime.utcnow()
            self.last_error = None
        elif status in ['stopped', 'error']:
            self.end_time = datetime.utcnow()
            self.process_id = None
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def update_statistics(self, total_rounds=0, successful_rounds=0, failed_rounds=0, 
                         supplement_orders=0, total_cost_diff=0):
        """更新执行统计"""
        if total_rounds > 0:
            self.total_rounds += total_rounds
        if successful_rounds > 0:
            self.successful_rounds += successful_rounds
        if failed_rounds > 0:
            self.failed_rounds += failed_rounds
        if supplement_orders > 0:
            self.supplement_orders += supplement_orders
        if total_cost_diff > 0:
            self.total_cost_diff += PyDecimal(str(total_cost_diff))
        db.session.commit()
    
    def get_success_rate(self):
        """获取成功率"""
        if self.total_rounds > 0:
            return (self.successful_rounds / self.total_rounds) * 100
        return 0.0
    
    def get_duration(self):
        """获取运行时长"""
        if self.start_time:
            end_time = self.end_time if self.end_time else datetime.utcnow()
            return end_time - self.start_time
        return None
    
    def __repr__(self):
        return f'<Task {self.name}({self.status})>'
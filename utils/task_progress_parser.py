"""
任务进度解析器 - 从日志文件中提取实时统计数据
"""

import os
import re
from datetime import datetime
from typing import Dict, Optional, List
from collections import defaultdict


class TaskProgressParser:
    """任务进度解析器"""
    
    def __init__(self, log_dir: str = "task_logs"):
        self.log_dir = log_dir
        
    def parse_task_progress(self, task_name: str, task_id: int) -> Dict:
        """解析单个任务的进度信息"""
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(self.log_dir, f"{task_name}_{today}.log")
        
        if not os.path.exists(log_file):
            return self._get_default_progress(task_id, task_name)
        
        try:
            # 读取最新的日志内容
            progress_data = self._parse_log_file(log_file)
            progress_data['task_id'] = task_id
            progress_data['task_name'] = task_name
            progress_data['last_update'] = datetime.now().isoformat()
            return progress_data
            
        except Exception as e:
            print(f"解析任务 {task_name} 进度失败: {e}")
            return self._get_default_progress(task_id, task_name)
    
    def _parse_log_file(self, log_file: str) -> Dict:
        """解析日志文件内容"""
        progress_data = {
            'current_round': 0,
            'total_rounds': 0,
            'completed_rounds': 0,
            'percentage': 0,
            'buy_volume': 0.0,
            'sell_volume': 0.0,
            'total_fees': 0.0,
            'supplement_orders': 0,
            'success_orders': 0,
            'failed_orders': 0,
            'usdt_balance': 0.0,
            'net_profit': 0.0,
            'estimated_cost': 0.0,
            'status': 'unknown'
        }
        
        try:
            # 读取文件最后几百行以提高性能
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = self._get_recent_lines(f, 500)
            
            # 解析各种统计数据
            self._extract_round_info(lines, progress_data)
            self._extract_volume_info(lines, progress_data)
            self._extract_order_statistics(lines, progress_data)
            self._extract_balance_info(lines, progress_data)
            self._extract_task_status(lines, progress_data)
            
            # 计算进度百分比
            if progress_data['total_rounds'] > 0:
                progress_data['percentage'] = round(
                    (progress_data['completed_rounds'] / progress_data['total_rounds']) * 100, 1
                )
                
        except Exception as e:
            print(f"解析日志文件失败: {e}")
        
        return progress_data
    
    def _get_recent_lines(self, file_obj, max_lines: int = 500) -> List[str]:
        """获取文件的最后N行"""
        lines = []
        try:
            # 简单实现：读取全部然后取最后N行
            all_lines = file_obj.readlines()
            lines = all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines
        except Exception:
            pass
        return lines
    
    def _extract_round_info(self, lines: List[str], data: Dict):
        """提取轮次信息"""
        for line in lines:
            # 提取总轮次数 
            match = re.search(r'rounds:\s*(\d+)', line)
            if match:
                data['total_rounds'] = int(match.group(1))
            
            # 提取当前轮次 - 支持格式：第 156/200 轮交易 或 第156轮
            match = re.search(r'第\s*(\d+)/(\d+)\s*轮交易', line)
            if match:
                data['current_round'] = max(data['current_round'], int(match.group(1)))
                data['total_rounds'] = int(match.group(2))
            else:
                match = re.search(r'第\s*(\d+)\s*轮', line)
                if match:
                    data['current_round'] = max(data['current_round'], int(match.group(1)))
            
            # 提取完成轮次
            if '轮交易完成' in line or '轮交易双向成交完成' in line:
                match = re.search(r'第\s*(\d+)\s*轮', line)
                if match:
                    data['completed_rounds'] = max(data['completed_rounds'], int(match.group(1)))
    
    def _extract_volume_info(self, lines: List[str], data: Dict):
        """提取交易量信息"""
        for line in lines:
            # 提取买卖交易量
            if '买单总交易量' in line:
                match = re.search(r'买单总交易量.*?(\d+\.?\d*)', line)
                if match:
                    data['buy_volume'] = float(match.group(1))
            
            if '卖单总交易量' in line:
                match = re.search(r'卖单总交易量.*?(\d+\.?\d*)', line)
                if match:
                    data['sell_volume'] = float(match.group(1))
            
            # 提取手续费 - 支持格式：总手续费: 0.2183 USDT
            if '总手续费:' in line:
                match = re.search(r'总手续费:\s*(\d+\.?\d*)\s*USDT', line)
                if match:
                    data['total_fees'] = float(match.group(1))
            
            # 估算交易量 - 从轮次和数量计算
            if data['completed_rounds'] > 0:
                quantity_match = re.search(r'quantity:\s*(\d+\.?\d*)', line)
                if quantity_match:
                    quantity = float(quantity_match.group(1))
                    data['buy_volume'] = data['completed_rounds'] * quantity
                    data['sell_volume'] = data['completed_rounds'] * quantity
    
    def _extract_order_statistics(self, lines: List[str], data: Dict):
        """提取订单统计"""
        for line in lines:
            # 统计补单次数 - 更精确的模式匹配
            if ('买入补单完成' in line or '卖出补单完成' in line or 
                '市价买入补单成功' in line or '市价卖出补单成功' in line):
                data['supplement_orders'] += 1
            
            # 统计成功订单 - 完成的轮次
            if '✅' in line and '轮交易完成' in line:
                data['success_orders'] += 1
            
            # 统计失败订单 - 需要补单的情况
            if '❌' in line and ('未成交' in line or '先取消未成交' in line):
                data['failed_orders'] += 1
                
    def _extract_balance_info(self, lines: List[str], data: Dict):
        """提取余额和盈亏信息"""
        for line in lines:
            # 提取USDT余额 - 格式：USDT余额: 264.15
            if 'USDT余额:' in line:
                match = re.search(r'USDT余额:\s*(\d+\.?\d*)', line)
                if match:
                    data['usdt_balance'] = float(match.group(1))
            
            # 从初始余额获取
            if '初始USDT余额:' in line:
                match = re.search(r'初始USDT余额:\s*(\d+\.?\d*)', line)
                if match:
                    initial_balance = float(match.group(1))
                    # 计算净损益（当前余额 - 初始余额 - 手续费）
                    if data['usdt_balance'] > 0:
                        data['net_profit'] = data['usdt_balance'] - initial_balance - data['total_fees']
            
            # 估算成本（手续费）
            data['estimated_cost'] = data['total_fees']
    
    def _extract_task_status(self, lines: List[str], data: Dict):
        """提取任务状态"""
        # 从最新的几行判断任务状态
        recent_lines = lines[-20:] if len(lines) >= 20 else lines
        
        task_completed = False
        task_failed = False
        task_started = False
        
        for line in reversed(recent_lines):
            # 检查任务完成状态
            if any(keyword in line for keyword in ['策略执行完成', '所有轮次已完成', '任务执行完成']):
                task_completed = True
                break
            elif any(keyword in line for keyword in ['策略执行失败', '任务异常终止', '执行失败']):
                task_failed = True
                break
            elif '任务结束' in line and '状态: stopped' in line:
                # 检查是否是正常结束还是异常结束
                if data['completed_rounds'] >= data['total_rounds'] and data['total_rounds'] > 0:
                    task_completed = True
                else:
                    task_failed = True
                break
            elif '任务开始' in line:
                task_started = True
                break
        
        # 根据分析结果设置状态
        if task_completed:
            data['status'] = 'completed'
            data['percentage'] = 100
        elif task_failed:
            data['status'] = 'failed'
        elif task_started or data['current_round'] > 0:
            data['status'] = 'running'
        else:
            data['status'] = 'pending'
    
    def _get_default_progress(self, task_id: int, task_name: str) -> Dict:
        """获取默认进度数据"""
        return {
            'task_id': task_id,
            'task_name': task_name,
            'current_round': 0,
            'total_rounds': 0,
            'completed_rounds': 0,
            'percentage': 0,
            'buy_volume': 0.0,
            'sell_volume': 0.0,
            'total_fees': 0.0,
            'supplement_orders': 0,
            'success_orders': 0,
            'failed_orders': 0,
            'usdt_balance': 0.0,
            'net_profit': 0.0,
            'estimated_cost': 0.0,
            'status': 'unknown',  # 改为unknown，让上层逻辑决定状态
            'last_update': datetime.now().isoformat()
        }
    
    def get_all_running_tasks_progress(self, task_ids: List[int], task_names: List[str]) -> List[Dict]:
        """获取所有运行中任务的进度"""
        progress_list = []
        
        for task_id, task_name in zip(task_ids, task_names):
            progress = self.parse_task_progress(task_name, task_id)
            progress_list.append(progress)
        
        return progress_list


# 全局实例
task_progress_parser = TaskProgressParser()
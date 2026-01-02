#!/usr/bin/env python3
"""
交易日志分析脚本
分析LISA交易策略的执行日志，计算损耗和性能指标
"""

import re
import os
from datetime import datetime
from typing import Dict, List, Tuple

class TradingLogAnalyzer:
    """交易日志分析器"""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.log_content = ""
        self.analysis_result = {}
        
    def load_log_file(self) -> bool:
        """加载日志文件"""
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                self.log_content = f.read()
            print(f"[OK] 成功加载日志文件: {self.log_file_path}")
            print(f"[INFO] 文件大小: {len(self.log_content)/1024:.1f}KB")
            return True
        except Exception as e:
            print(f"[ERROR] 加载日志文件失败: {e}")
            return False
    
    def extract_basic_info(self) -> Dict:
        """提取基本信息"""
        info = {}
        
        # 提取交易对
        symbol_match = re.search(r'交易对.*?(\w+USDT)', self.log_content)
        if symbol_match:
            info['symbol'] = symbol_match.group(1)
        
        # 提取策略参数
        rounds_match = re.search(r'轮次:\s*(\d+)', self.log_content)
        if rounds_match:
            info['total_rounds'] = int(rounds_match.group(1))
            
        quantity_match = re.search(r'单次数量:\s*([\d.]+)', self.log_content)
        if quantity_match:
            info['quantity_per_round'] = float(quantity_match.group(1))
            
        # 提取手续费率
        maker_fee_match = re.search(r'Maker费率:\s*([\d.]+)%', self.log_content)
        taker_fee_match = re.search(r'Taker费率:\s*([\d.]+)%', self.log_content)
        if maker_fee_match:
            info['maker_fee_rate'] = float(maker_fee_match.group(1)) / 100
        if taker_fee_match:
            info['taker_fee_rate'] = float(taker_fee_match.group(1)) / 100
            
        return info
    
    def extract_balance_info(self) -> Dict:
        """提取余额信息"""
        balance_info = {}
        
        # 提取初始余额
        initial_usdt_match = re.search(r'初始USDT余额:\s*([\d.]+)', self.log_content)
        if initial_usdt_match:
            balance_info['initial_usdt'] = float(initial_usdt_match.group(1))
            
        # 提取最终余额
        final_usdt_match = re.search(r'最终USDT余额:\s*([\d.]+)', self.log_content)
        if final_usdt_match:
            balance_info['final_usdt'] = float(final_usdt_match.group(1))
            
        # 提取USDT余额差值
        usdt_diff_match = re.search(r'USDT余额差值:\s*([-\d.]+)', self.log_content)
        if usdt_diff_match:
            balance_info['usdt_difference'] = float(usdt_diff_match.group(1))
            
        # 提取LISA余额
        initial_lisa_matches = re.findall(r'初始余额:\s*([\d.]+)', self.log_content)
        final_lisa_match = re.search(r'最终余额:\s*([\d.]+)', self.log_content)
        
        if initial_lisa_matches:
            balance_info['initial_lisa'] = float(initial_lisa_matches[0])
        if final_lisa_match:
            balance_info['final_lisa'] = float(final_lisa_match.group(1))
            
        return balance_info
    
    def extract_trading_stats(self) -> Dict:
        """提取交易统计信息"""
        stats = {}
        
        # 提取总交易量
        total_volume_match = re.search(r'总交易量:\s*([\d.]+)\s*USDT', self.log_content)
        if total_volume_match:
            stats['total_volume'] = float(total_volume_match.group(1))
            
        # 提取买单和卖单交易量
        buy_volume_match = re.search(r'买单总交易量:\s*([\d.]+)\s*USDT', self.log_content)
        sell_volume_match = re.search(r'卖单总交易量:\s*([\d.]+)\s*USDT', self.log_content)
        
        if buy_volume_match:
            stats['buy_volume'] = float(buy_volume_match.group(1))
        if sell_volume_match:
            stats['sell_volume'] = float(sell_volume_match.group(1))
            
        # 提取总手续费
        total_fees_match = re.search(r'总手续费:\s*([\d.]+)\s*USDT', self.log_content)
        if total_fees_match:
            stats['total_fees'] = float(total_fees_match.group(1))
            
        # 提取净损耗
        net_loss_match = re.search(r'净损耗.*?:\s*([-\d.]+)\s*USDT', self.log_content)
        if net_loss_match:
            stats['net_loss'] = float(net_loss_match.group(1))
            
        # 提取完成轮次和补单数
        completed_rounds_match = re.search(r'完成轮次:\s*(\d+)', self.log_content)
        supplement_orders_match = re.search(r'补单数:\s*(\d+)', self.log_content)
        
        if completed_rounds_match:
            stats['completed_rounds'] = int(completed_rounds_match.group(1))
        if supplement_orders_match:
            stats['supplement_orders'] = int(supplement_orders_match.group(1))
            
        return stats
    
    def extract_round_details(self) -> List[Dict]:
        """提取每轮交易详情"""
        rounds = []
        
        # 匹配每轮交易的模式
        round_pattern = r'=== 第 (\d+)/\d+ 轮交易 ==='
        round_matches = re.finditer(round_pattern, self.log_content)
        
        for match in round_matches:
            round_num = int(match.group(1))
            round_start = match.start()
            
            # 找到下一轮的开始位置
            next_match = None
            for next_round in round_matches:
                if next_round.start() > round_start:
                    next_match = next_round
                    break
                    
            round_end = next_match.start() if next_match else len(self.log_content)
            round_content = self.log_content[round_start:round_end]
            
            # 提取该轮的关键信息
            round_info = {
                'round_num': round_num,
                'success': '✅' in round_content,
                'has_errors': '❌' in round_content,
                'has_supplements': '补单' in round_content
            }
            
            rounds.append(round_info)
            
        return rounds
    
    def calculate_loss_metrics(self) -> Dict:
        """计算损耗指标"""
        metrics = {}
        
        balance_info = self.extract_balance_info()
        trading_stats = self.extract_trading_stats()
        basic_info = self.extract_basic_info()
        
        # 计算各种损耗指标
        if 'total_volume' in trading_stats and 'total_fees' in trading_stats:
            # 手续费率实际值
            actual_fee_rate = trading_stats['total_fees'] / trading_stats['total_volume']
            metrics['actual_fee_rate'] = actual_fee_rate * 100  # 转换为百分比
            
        if 'usdt_difference' in balance_info and 'total_fees' in trading_stats:
            # 净损耗 = USDT余额差值 - 手续费
            net_loss = balance_info['usdt_difference'] - trading_stats['total_fees']
            metrics['calculated_net_loss'] = net_loss
            
        if 'total_volume' in trading_stats and 'usdt_difference' in balance_info:
            # 损耗率 = 总损耗 / 总交易量
            total_loss_rate = abs(balance_info['usdt_difference']) / trading_stats['total_volume']
            metrics['total_loss_rate'] = total_loss_rate * 100
            
        if 'net_loss' in trading_stats and 'total_volume' in trading_stats:
            # 净损耗率
            net_loss_rate = abs(trading_stats['net_loss']) / trading_stats['total_volume']
            metrics['net_loss_rate'] = net_loss_rate * 100
            
        return metrics
    
    def analyze_problems(self) -> List[str]:
        """分析潜在问题"""
        problems = []
        
        balance_info = self.extract_balance_info()
        trading_stats = self.extract_trading_stats()
        metrics = self.calculate_loss_metrics()
        
        # 检查高损耗
        if 'net_loss_rate' in metrics and metrics['net_loss_rate'] > 0.1:
            problems.append(f"⚠️ 净损耗率过高: {metrics['net_loss_rate']:.3f}% (>0.1%)")
            
        # 检查买卖量不平衡
        if 'buy_volume' in trading_stats and 'sell_volume' in trading_stats:
            volume_diff = abs(trading_stats['buy_volume'] - trading_stats['sell_volume'])
            volume_diff_rate = volume_diff / trading_stats['total_volume'] * 100
            if volume_diff_rate > 1.0:
                problems.append(f"⚠️ 买卖量不平衡: 差异{volume_diff:.2f} USDT ({volume_diff_rate:.2f}%)")
                
        # 检查LISA余额异常
        if 'initial_lisa' in balance_info and 'final_lisa' in balance_info:
            lisa_diff = balance_info['final_lisa'] - balance_info['initial_lisa']
            if abs(lisa_diff) > 1.0:
                problems.append(f"⚠️ LISA余额变化异常: {lisa_diff:+.2f} LISA")
                
        # 检查补单次数
        if 'supplement_orders' in trading_stats and trading_stats['supplement_orders'] > 0:
            problems.append(f"⚠️ 策略执行中有补单: {trading_stats['supplement_orders']}次")
            
        return problems
    
    def generate_report(self) -> None:
        """生成分析报告"""
        print("\n" + "="*60)
        print("交易日志分析报告")
        print("="*60)
        
        # 基本信息
        basic_info = self.extract_basic_info()
        print(f"\n[基本信息]:")
        for key, value in basic_info.items():
            print(f"   {key}: {value}")
            
        # 余额信息
        balance_info = self.extract_balance_info()
        print(f"\n[余额分析]:")
        for key, value in balance_info.items():
            if 'usdt' in key.lower():
                print(f"   {key}: {value:.4f} USDT")
            else:
                print(f"   {key}: {value:.2f}")
                
        # 交易统计
        trading_stats = self.extract_trading_stats()
        print(f"\n[交易统计]:")
        for key, value in trading_stats.items():
            if isinstance(value, float):
                print(f"   {key}: {value:.4f}")
            else:
                print(f"   {key}: {value}")
                
        # 损耗指标
        metrics = self.calculate_loss_metrics()
        print(f"\n[损耗分析]:")
        for key, value in metrics.items():
            if 'rate' in key:
                print(f"   {key}: {value:.6f}%")
            else:
                print(f"   {key}: {value:.6f}")
                
        # 问题分析
        problems = self.analyze_problems()
        if problems:
            print(f"\n[发现的问题]:")
            for problem in problems:
                clean_problem = problem.replace('⚠️', '[WARNING]').replace('✅', '[OK]').replace('❌', '[ERROR]')
                print(f"   {clean_problem}")
        else:
            print(f"\n[OK] 未发现明显问题")
            
        print("\n" + "="*60)

def main():
    """主函数"""
    log_file_path = r"D:\Projects\aster_auto\task_logs\LISA_2026-01-02.log"
    
    if not os.path.exists(log_file_path):
        print(f"[ERROR] 日志文件不存在: {log_file_path}")
        return
        
    analyzer = TradingLogAnalyzer(log_file_path)
    
    if analyzer.load_log_file():
        analyzer.generate_report()
    else:
        print("[ERROR] 日志分析失败")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
分析新LISA交易日志 - 对比智能定价策略效果
"""

import re
import os
from datetime import datetime

class NewLisaLogAnalyzer:
    """新LISA日志分析器"""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.log_content = ""
        
    def load_log_file(self) -> bool:
        """加载日志文件"""
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                self.log_content = f.read()
            print(f"[OK] 加载日志文件: {self.log_file_path}")
            print(f"[INFO] 文件大小: {len(self.log_content)/1024:.1f}KB")
            return True
        except Exception as e:
            print(f"[ERROR] 加载失败: {e}")
            return False
    
    def analyze_round_success_rate(self) -> dict:
        """分析轮次成功率"""
        stats = {
            'total_rounds': 0,
            'completed_rounds': 0,
            'failed_rounds': 0,
            'success_rate': 0.0,
            'round_details': []
        }
        
        # 统计轮次结果
        completed_pattern = r'第 (\d+) 轮交易完成'
        failed_pattern = r'第 (\d+) 轮交易结束 \(未完成\)'
        
        completed_matches = re.findall(completed_pattern, self.log_content)
        failed_matches = re.findall(failed_pattern, self.log_content)
        
        stats['completed_rounds'] = len(completed_matches)
        stats['failed_rounds'] = len(failed_matches)
        stats['total_rounds'] = stats['completed_rounds'] + stats['failed_rounds']
        
        if stats['total_rounds'] > 0:
            stats['success_rate'] = (stats['completed_rounds'] / stats['total_rounds']) * 100
            
        return stats
    
    def analyze_pricing_strategy(self) -> dict:
        """分析定价策略使用情况"""
        pricing_stats = {
            'narrow_spread_count': 0,
            'buy_priority_count': 0,
            'sell_priority_count': 0,
            'mid_strategy_count': 0,
            'normal_spread_count': 0,
            'total_pricing': 0
        }
        
        # 统计各种定价策略
        narrow_patterns = [
            r'极小价差-买单优先',
            r'极小价差-卖单优先', 
            r'极小价差-中位策略'
        ]
        
        for pattern in narrow_patterns:
            matches = re.findall(pattern, self.log_content)
            if '买单优先' in pattern:
                pricing_stats['buy_priority_count'] = len(matches)
            elif '卖单优先' in pattern:
                pricing_stats['sell_priority_count'] = len(matches) 
            elif '中位策略' in pattern:
                pricing_stats['mid_strategy_count'] = len(matches)
                
        pricing_stats['narrow_spread_count'] = (
            pricing_stats['buy_priority_count'] + 
            pricing_stats['sell_priority_count'] + 
            pricing_stats['mid_strategy_count']
        )
        
        # 统计正常价差策略
        normal_matches = re.findall(r'平衡定价策略', self.log_content)
        pricing_stats['normal_spread_count'] = len(normal_matches)
        
        pricing_stats['total_pricing'] = (
            pricing_stats['narrow_spread_count'] + 
            pricing_stats['normal_spread_count']
        )
        
        return pricing_stats
    
    def analyze_order_status(self) -> dict:
        """分析订单成交情况"""
        order_stats = {
            'total_orders': 0,
            'filled_orders': 0,
            'new_orders': 0,
            'canceled_orders': 0,
            'fill_rate': 0.0,
            'both_filled': 0,
            'one_side_filled': 0,
            'both_failed': 0
        }
        
        # 统计订单状态
        filled_matches = re.findall(r'订单状态.*?FILLED', self.log_content)
        new_matches = re.findall(r'订单状态.*?NEW', self.log_content)
        
        order_stats['filled_orders'] = len(filled_matches)
        order_stats['new_orders'] = len(new_matches)
        order_stats['total_orders'] = order_stats['filled_orders'] + order_stats['new_orders']
        
        if order_stats['total_orders'] > 0:
            order_stats['fill_rate'] = (order_stats['filled_orders'] / order_stats['total_orders']) * 100
            
        # 分析成交模式
        both_filled_matches = re.findall(r'双向订单都已成交', self.log_content)
        one_side_matches = re.findall(r'(买单成交，卖单未成交|卖单成交，买单未成交)', self.log_content)
        both_failed_matches = re.findall(r'双向订单都未成交', self.log_content)
        
        order_stats['both_filled'] = len(both_filled_matches)
        order_stats['one_side_filled'] = len(one_side_matches)
        order_stats['both_failed'] = len(both_failed_matches)
        
        return order_stats
    
    def analyze_supplement_orders(self) -> dict:
        """分析补单情况"""
        supplement_stats = {
            'buy_supplements': 0,
            'sell_supplements': 0,
            'total_supplements': 0,
            'supplement_rate': 0.0
        }
        
        buy_matches = re.findall(r'买入补单成功', self.log_content)
        sell_matches = re.findall(r'卖出补单成功', self.log_content)
        
        supplement_stats['buy_supplements'] = len(buy_matches)
        supplement_stats['sell_supplements'] = len(sell_matches)
        supplement_stats['total_supplements'] = supplement_stats['buy_supplements'] + supplement_stats['sell_supplements']
        
        return supplement_stats
    
    def analyze_final_results(self) -> dict:
        """分析最终结果"""
        results = {
            'initial_usdt': 0.0,
            'final_usdt': 0.0,
            'usdt_difference': 0.0,
            'total_fees': 0.0,
            'net_loss': 0.0,
            'total_volume': 0.0,
            'loss_rate': 0.0
        }
        
        # 提取最终数据
        initial_match = re.search(r'初始USDT余额:\s*([\d.]+)', self.log_content)
        final_match = re.search(r'最终USDT余额:\s*([\d.]+)', self.log_content)
        diff_match = re.search(r'USDT余额差值:\s*([-\d.]+)', self.log_content)
        fees_match = re.search(r'总手续费:\s*([\d.]+)', self.log_content)
        volume_match = re.search(r'总交易量:\s*([\d.]+)', self.log_content)
        
        if initial_match:
            results['initial_usdt'] = float(initial_match.group(1))
        if final_match:
            results['final_usdt'] = float(final_match.group(1))
        if diff_match:
            results['usdt_difference'] = float(diff_match.group(1))
        if fees_match:
            results['total_fees'] = float(fees_match.group(1))
        if volume_match:
            results['total_volume'] = float(volume_match.group(1))
            
        # 计算净损耗
        if results['usdt_difference'] != 0 and results['total_fees'] != 0:
            results['net_loss'] = abs(results['usdt_difference']) - results['total_fees']
            
        # 计算损耗率
        if results['total_volume'] > 0:
            results['loss_rate'] = abs(results['net_loss']) / results['total_volume'] * 100
            
        return results
    
    def generate_comparison_report(self):
        """生成对比分析报告"""
        print("\n" + "="*60)
        print("智能定价策略效果分析报告")
        print("="*60)
        
        # 轮次成功率分析
        round_stats = self.analyze_round_success_rate()
        print(f"\n[轮次成功率]:")
        print(f"   总轮次: {round_stats['total_rounds']}")
        print(f"   成功轮次: {round_stats['completed_rounds']}")
        print(f"   失败轮次: {round_stats['failed_rounds']}")
        print(f"   成功率: {round_stats['success_rate']:.1f}%")
        
        # 定价策略分析
        pricing_stats = self.analyze_pricing_strategy()
        print(f"\n[定价策略使用]:")
        print(f"   极小价差策略: {pricing_stats['narrow_spread_count']} 次")
        print(f"     - 买单优先: {pricing_stats['buy_priority_count']} 次")
        print(f"     - 卖单优先: {pricing_stats['sell_priority_count']} 次")
        print(f"     - 中位策略: {pricing_stats['mid_strategy_count']} 次")
        print(f"   正常价差策略: {pricing_stats['normal_spread_count']} 次")
        print(f"   总定价次数: {pricing_stats['total_pricing']} 次")
        
        # 订单成交分析
        order_stats = self.analyze_order_status()
        print(f"\n[订单成交情况]:")
        print(f"   总订单数: {order_stats['total_orders']}")
        print(f"   成交订单: {order_stats['filled_orders']}")
        print(f"   未成交订单: {order_stats['new_orders']}")
        print(f"   订单成交率: {order_stats['fill_rate']:.1f}%")
        print(f"\n[成交模式]:")
        print(f"   双向成交: {order_stats['both_filled']} 次")
        print(f"   单边成交: {order_stats['one_side_filled']} 次")
        print(f"   双边失败: {order_stats['both_failed']} 次")
        
        # 补单分析
        supplement_stats = self.analyze_supplement_orders()
        print(f"\n[补单情况]:")
        print(f"   买入补单: {supplement_stats['buy_supplements']} 次")
        print(f"   卖出补单: {supplement_stats['sell_supplements']} 次")
        print(f"   总补单: {supplement_stats['total_supplements']} 次")
        
        # 最终结果
        results = self.analyze_final_results()
        print(f"\n[损耗分析]:")
        print(f"   初始USDT: {results['initial_usdt']:.4f}")
        print(f"   最终USDT: {results['final_usdt']:.4f}")
        print(f"   USDT差值: {results['usdt_difference']:.4f}")
        print(f"   总手续费: {results['total_fees']:.4f}")
        print(f"   净损耗: {results['net_loss']:.4f}")
        print(f"   总交易量: {results['total_volume']:.2f}")
        print(f"   损耗率: {results['loss_rate']:.6f}%")
        
        # 评估结论
        print(f"\n[策略评估]:")
        if round_stats['success_rate'] >= 80:
            print("   [优秀] 成功率优秀 (>=80%)")
        elif round_stats['success_rate'] >= 60:
            print("   [一般] 成功率一般 (60-80%)")
        else:
            print("   [较差] 成功率较差 (<60%)")
            
        if results['loss_rate'] <= 0.05:
            print("   [达标] 损耗率达标 (<=0.05%)")
        elif results['loss_rate'] <= 0.1:
            print("   [偏高] 损耗率偏高 (0.05-0.1%)")
        else:
            print("   [过高] 损耗率过高 (>0.1%)")
            
        print("\n" + "="*60)

def main():
    """主函数"""
    log_file_path = r"D:\Projects\aster_auto\task_logs\lisa_2026-01-03.log"
    
    if not os.path.exists(log_file_path):
        print(f"[ERROR] 日志文件不存在: {log_file_path}")
        return
        
    analyzer = NewLisaLogAnalyzer(log_file_path)
    
    if analyzer.load_log_file():
        analyzer.generate_comparison_report()
    else:
        print("[ERROR] 分析失败")

if __name__ == "__main__":
    main()
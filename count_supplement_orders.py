#!/usr/bin/env python3
"""
统计实际的补单次数
"""

log_file = r"D:\Projects\aster_auto\task_logs\LISA_2026-01-02.log"

try:
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 统计各种补单类型
    buy_supplement = content.count("买入补单成功")
    sell_supplement = content.count("卖出补单成功") 
    total_supplement = buy_supplement + sell_supplement
    
    print("=== 补单次数统计 ===")
    print(f"买入补单成功: {buy_supplement} 次")
    print(f"卖出补单成功: {sell_supplement} 次")
    print(f"总补单次数: {total_supplement} 次")
    
    # 统计其他相关信息
    failed_buy = content.count("买入补单失败")
    failed_sell = content.count("卖出补单失败")
    
    print(f"\n补单失败统计:")
    print(f"买入补单失败: {failed_buy} 次")
    print(f"卖出补单失败: {failed_sell} 次")
    
    # 统计补单相关的日志条目
    supplement_mentions = content.count("补单")
    print(f"\n总共提及'补单': {supplement_mentions} 次")
    
    # 分析买卖比例
    if total_supplement > 0:
        buy_ratio = buy_supplement / total_supplement * 100
        sell_ratio = sell_supplement / total_supplement * 100
        print(f"\n补单类型分析:")
        print(f"买入补单占比: {buy_ratio:.1f}%")
        print(f"卖出补单占比: {sell_ratio:.1f}%")
        
        if buy_supplement > sell_supplement:
            print("结论: 买入补单较多，说明卖单更容易成交，买单容易失败")
        elif sell_supplement > buy_supplement:
            print("结论: 卖出补单较多，说明买单更容易成交，卖单容易失败")
        else:
            print("结论: 买入和卖出补单基本平衡")
    
except Exception as e:
    print(f"错误: {e}")
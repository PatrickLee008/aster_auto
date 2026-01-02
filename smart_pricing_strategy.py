#!/usr/bin/env python3
"""
智能价格策略设计方案
解决买卖不平衡问题
"""

import random

class SmartPricingStrategy:
    """智能价格策略"""
    
    def __init__(self):
        # 策略参数
        self.buy_bias = 0.3   # 买单偏向买一价 (30%靠近买一)
        self.sell_bias = 0.7  # 卖单偏向卖一价 (70%靠近卖一)
        self.tick_size = 0.000100  # 最小价格变动
        
    def generate_balanced_prices(self, bid_price: float, ask_price: float) -> tuple:
        """
        生成平衡的买卖价格
        返回: (buy_price, sell_price)
        """
        spread = ask_price - bid_price
        
        if spread <= self.tick_size:
            # 极小价差处理
            return self._handle_narrow_spread(bid_price, ask_price)
        else:
            # 正常价差处理
            return self._handle_normal_spread(bid_price, ask_price, spread)
    
    def _handle_narrow_spread(self, bid_price: float, ask_price: float) -> tuple:
        """处理极小价差情况"""
        # 窄价差时，使用错位策略
        buy_price = bid_price - self.tick_size   # 买单更保守，低于买一
        sell_price = ask_price + self.tick_size  # 卖单更保守，高于卖一
        return (buy_price, sell_price)
    
    def _handle_normal_spread(self, bid_price: float, ask_price: float, spread: float) -> tuple:
        """处理正常价差情况"""
        # 买单策略：偏向买一价，提高成交率
        buy_offset = random.uniform(0.2, 0.4)  # 20%-40%，靠近买一
        buy_price = bid_price + (spread * buy_offset)
        
        # 卖单策略：偏向卖一价，提高成交率  
        sell_offset = random.uniform(0.6, 0.8)  # 60%-80%，靠近卖一
        sell_price = bid_price + (spread * sell_offset)
        
        return (buy_price, sell_price)
    
    def generate_adaptive_prices(self, bid_price: float, ask_price: float, 
                               recent_fill_ratio: dict) -> tuple:
        """
        根据最近成交情况自适应调整
        recent_fill_ratio: {'buy': 0.8, 'sell': 0.6} 最近买卖成交率
        """
        spread = ask_price - bid_price
        
        # 根据成交率动态调整偏向程度
        buy_fill_rate = recent_fill_ratio.get('buy', 0.5)
        sell_fill_rate = recent_fill_ratio.get('sell', 0.5)
        
        # 成交率低的方向更激进
        if buy_fill_rate < 0.5:
            # 买单成交率低，更激进（更靠近卖一）
            buy_offset = random.uniform(0.4, 0.6)
        else:
            # 买单成交率高，更保守（更靠近买一）
            buy_offset = random.uniform(0.2, 0.4)
            
        if sell_fill_rate < 0.5:
            # 卖单成交率低，更激进（更靠近买一）
            sell_offset = random.uniform(0.4, 0.6) 
        else:
            # 卖单成交率高，更保守（更靠近卖一）
            sell_offset = random.uniform(0.6, 0.8)
            
        buy_price = bid_price + (spread * buy_offset)
        sell_price = bid_price + (spread * sell_offset)
        
        return (buy_price, sell_price)
    
    def generate_market_making_prices(self, bid_price: float, ask_price: float, 
                                    volatility: float = 0.001) -> tuple:
        """
        做市商策略：确保买卖价格有足够利润空间
        """
        spread = ask_price - bid_price
        mid_price = (bid_price + ask_price) / 2
        
        # 基于波动率调整价差
        min_profit_spread = mid_price * volatility  # 最小利润价差
        
        if spread < min_profit_spread:
            # 价差太小，扩大价差
            buy_price = mid_price - min_profit_spread / 2
            sell_price = mid_price + min_profit_spread / 2
        else:
            # 价差足够，使用保守策略
            buy_price = bid_price + spread * 0.3   # 30%位置
            sell_price = bid_price + spread * 0.7   # 70%位置
            
        return (buy_price, sell_price)


def demo_pricing_strategies():
    """演示不同定价策略"""
    
    # 模拟市场数据
    bid_price = 1.45235
    ask_price = 1.45255
    spread = ask_price - bid_price
    
    print("=== 智能定价策略演示 ===")
    print(f"买一: {bid_price:.5f}, 卖一: {ask_price:.5f}, 价差: {spread:.5f}")
    print()
    
    strategy = SmartPricingStrategy()
    
    # 1. 平衡策略
    buy_price, sell_price = strategy.generate_balanced_prices(bid_price, ask_price)
    print("1. 平衡策略:")
    print(f"   买单价格: {buy_price:.5f} (距买一: {(buy_price-bid_price)*100000:.1f} ticks)")
    print(f"   卖单价格: {sell_price:.5f} (距卖一: {(ask_price-sell_price)*100000:.1f} ticks)")
    print()
    
    # 2. 自适应策略
    recent_fill_ratio = {'buy': 0.8, 'sell': 0.4}  # 买单成交率高，卖单成交率低
    buy_price, sell_price = strategy.generate_adaptive_prices(bid_price, ask_price, recent_fill_ratio)
    print("2. 自适应策略 (卖单成交率低):")
    print(f"   买单价格: {buy_price:.5f}")
    print(f"   卖单价格: {sell_price:.5f}")
    print()
    
    # 3. 做市商策略
    buy_price, sell_price = strategy.generate_market_making_prices(bid_price, ask_price)
    print("3. 做市商策略:")
    print(f"   买单价格: {buy_price:.5f}")
    print(f"   卖单价格: {sell_price:.5f}")
    print(f"   预期利润: {(sell_price - buy_price) / buy_price * 100:.4f}%")

if __name__ == "__main__":
    demo_pricing_strategies()
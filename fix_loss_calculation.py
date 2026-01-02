#!/usr/bin/env python3
"""
修正净损耗计算
"""

# 从日志中提取的数据
usdt_difference = -10.9369  # USDT余额差值
total_fees = 3.5172         # 总手续费

print("=== 净损耗计算修正 ===")
print(f"USDT余额差值: {usdt_difference:.4f} USDT")
print(f"总手续费: {total_fees:.4f} USDT")

# 正确的计算方式：
# 净损耗 = 余额差值 - 手续费
# 但是余额差值是负数，表示亏损
# 所以实际损耗 = |余额差值| - 手续费
actual_loss = abs(usdt_difference) - total_fees

print(f"\n正确计算:")
print(f"实际损耗 = |{usdt_difference:.4f}| - {total_fees:.4f}")
print(f"实际损耗 = {abs(usdt_difference):.4f} - {total_fees:.4f}")
print(f"实际损耗 = {actual_loss:.4f} USDT")

print(f"\n损耗分析:")
print(f"总亏损: {abs(usdt_difference):.4f} USDT")
print(f"其中手续费: {total_fees:.4f} USDT ({total_fees/abs(usdt_difference)*100:.1f}%)")
print(f"其中净损耗: {actual_loss:.4f} USDT ({actual_loss/abs(usdt_difference)*100:.1f}%)")

# 原来错误的计算
wrong_calculation = usdt_difference - total_fees
print(f"\n原来错误的计算:")
print(f"错误结果: {usdt_difference:.4f} - {total_fees:.4f} = {wrong_calculation:.4f} USDT")
print(f"这个计算是错误的，因为余额差值本身已经是负数")
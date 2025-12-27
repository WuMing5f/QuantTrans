#!/usr/bin/env python
"""
批量同步所有ETF的完整历史数据
"""
import os
import sys
import django
import time

# 设置Django环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command
from apps.data_master.models import Instrument

# 获取所有A股ETF
etfs = Instrument.objects.filter(market='CN').order_by('symbol')
total = etfs.count()
print(f'开始同步 {total} 个ETF的完整历史数据（2024-01-01 到 2025-12-23）...')

success = 0
failed = []

for i, etf in enumerate(etfs, 1):
    print(f'\n[{i}/{total}] 同步 {etf.symbol} ({etf.name})...')
    try:
        call_command(
            'sync_data',
            symbol=etf.symbol,
            market='CN',
            start='2024-01-01',
            end='2025-12-23',
            name=etf.name,
            verbosity=0
        )
        success += 1
        print(f'  ✓ {etf.symbol} 同步成功')
    except Exception as e:
        failed.append((etf.symbol, str(e)))
        print(f'  ✗ {etf.symbol} 同步失败: {e}')
    
    # 延迟避免请求过快
    if i < total:
        time.sleep(1)

print(f'\n=== 同步完成 ===')
print(f'成功: {success} 个')
print(f'失败: {len(failed)} 个')
if failed:
    print('失败的标的:')
    for symbol, error in failed:
        print(f'  {symbol}: {error}')


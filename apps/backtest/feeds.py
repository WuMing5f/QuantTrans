"""
Backtrader数据源适配器
将Django ORM查询的DataFrame转换为Backtrader可用的数据源
"""
import backtrader as bt
import pandas as pd
from datetime import datetime


class DjangoPandasData(bt.feeds.PandasData):
    """
    将Django ORM查询的DataFrame转换为Backtrader数据源
    
    要求DataFrame必须包含以下列：
    - date (datetime类型)
    - open, high, low, close (价格)
    - volume (成交量)
    - amount (成交额，可选)
    """
    
    # 定义数据列映射
    lines = ('amount',)  # 如果需要使用成交额
    
    params = (
        ('datetime', None),  # 自动检测date列
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('amount', 'amount'),  # 成交额
        ('openinterest', None),  # 持仓量（期货用，这里不用）
    )


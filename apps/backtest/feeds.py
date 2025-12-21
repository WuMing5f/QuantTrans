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
    
    def __init__(self, dataframe: pd.DataFrame):
        """
        初始化数据源
        
        Args:
            dataframe: 包含OHLCV数据的DataFrame
        """
        # 确保date列是datetime类型
        if 'date' in dataframe.columns:
            dataframe = dataframe.set_index('date')
        elif not isinstance(dataframe.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have 'date' column or DatetimeIndex")
        
        # 确保索引是DatetimeIndex
        if not isinstance(dataframe.index, pd.DatetimeIndex):
            dataframe.index = pd.to_datetime(dataframe.index)
        
        # 排序
        dataframe = dataframe.sort_index()
        
        # 调用父类初始化
        super(DjangoPandasData, self).__init__(dataname=dataframe)


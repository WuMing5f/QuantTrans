from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Union
import pandas as pd


class DataProvider(ABC):
    """数据提供者抽象基类"""
    
    @abstractmethod
    def fetch_history(
        self,
        symbol: str,
        start: Union[str, datetime],
        end: Union[str, datetime],
        **kwargs
    ) -> pd.DataFrame:
        """
        获取历史K线数据
        
        Args:
            symbol: 股票代码
            start: 开始日期
            end: 结束日期
            **kwargs: 其他参数
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount, turnover
        """
        pass
    
    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化DataFrame格式
        确保列名为标准格式：date, open, high, low, close, volume, amount, turnover
        """
        # 确保date列是datetime类型
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        elif df.index.name == 'date' or isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            if 'Date' in df.columns:
                df['date'] = pd.to_datetime(df['Date'])
                df = df.drop('Date', axis=1)
        
        # 确保date是索引或列
        if 'date' not in df.columns and isinstance(df.index, pd.DatetimeIndex):
            df['date'] = df.index
            df = df.reset_index(drop=True)
        
        # 标准化列名（转为小写）
        df.columns = df.columns.str.lower()
        
        # 确保必需的列存在
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # 确保数值列为数值类型
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turnover']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 确保amount列存在（如果没有则计算）
        if 'amount' not in df.columns:
            if 'close' in df.columns and 'volume' in df.columns:
                df['amount'] = df['close'] * df['volume']
        
        # 按日期排序
        df = df.sort_values('date').reset_index(drop=True)
        
        return df


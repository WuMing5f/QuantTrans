from datetime import datetime
from typing import Optional, Union
import pandas as pd
import yfinance as yf
from .base import DataProvider


class YahooUSProvider(DataProvider):
    """Yahoo Finance 美股数据提供者"""
    
    def fetch_history(
        self,
        symbol: str,
        start: Union[str, datetime],
        end: Union[str, datetime],
        **kwargs
    ) -> pd.DataFrame:
        """
        从 Yahoo Finance 获取美股历史数据
        
        Args:
            symbol: 股票代码 (如 'AAPL')
            start: 开始日期
            end: 结束日期
        """
        # 转换为字符串格式
        if isinstance(start, datetime):
            start = start.strftime('%Y-%m-%d')
        if isinstance(end, datetime):
            end = end.strftime('%Y-%m-%d')
        
        # 下载数据，auto_adjust=True 自动复权
        # 添加重试机制处理速率限制
        import time
        max_retries = 3
        retry_delay = 5  # 秒
        
        for attempt in range(max_retries):
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(
                    start=start,
                    end=end,
                    auto_adjust=True,
                    prepost=False
                )
                break  # 成功则跳出循环
            except Exception as e:
                if "Rate" in str(e) or "rate" in str(e).lower() or attempt < max_retries - 1:
                    if attempt < max_retries - 1:
                        print(f"遇到速率限制，等待 {retry_delay} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                        continue
                raise  # 其他错误或最后一次重试失败则抛出
        
        if df.empty:
            raise ValueError(f"No data found for {symbol} from {start} to {end}")
        
        # 重置索引，将Date转为列
        df = df.reset_index()
        
        # 重命名列
        df = df.rename(columns={
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        
        # 计算成交额
        df['amount'] = df['close'] * df['volume']
        
        # 计算换手率（需要获取流通股本）
        try:
            info = ticker.info
            shares_outstanding = info.get('sharesOutstanding', None)
            if shares_outstanding and shares_outstanding > 0:
                # 换手率 = (成交量 / 流通股本) * 100
                df['turnover'] = (df['volume'] / shares_outstanding) * 100
            else:
                df['turnover'] = None
        except Exception:
            # 如果获取失败，设为None
            df['turnover'] = None
        
        # 标准化数据格式
        df = self.normalize_dataframe(df)
        
        # 只保留需要的列
        columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover']
        df = df[[col for col in columns if col in df.columns]]
        
        return df


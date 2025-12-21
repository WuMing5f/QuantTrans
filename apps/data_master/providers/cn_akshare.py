from datetime import datetime, timedelta
from typing import Optional, Union
import pandas as pd
import akshare as ak
from .base import DataProvider


class AkShareCNProvider(DataProvider):
    """AkShare A股数据提供者（ETF数据）"""
    
    def fetch_history(
        self,
        symbol: str,
        start: Union[str, datetime],
        end: Union[str, datetime],
        **kwargs
    ) -> pd.DataFrame:
        """
        从 AkShare 获取A股ETF历史数据
        
        Args:
            symbol: ETF代码 (如 '510300')
            start: 开始日期 (格式: 'YYYYMMDD' 或 datetime)
            end: 结束日期 (格式: 'YYYYMMDD' 或 datetime)
        """
        # 转换为AkShare需要的格式 YYYYMMDD
        if isinstance(start, datetime):
            start_str = start.strftime('%Y%m%d')
        else:
            start_str = start.replace('-', '')
        
        if isinstance(end, datetime):
            end_str = end.strftime('%Y%m%d')
        else:
            end_str = end.replace('-', '')
        
        # 使用AkShare获取ETF历史数据
        # period参数应为 'daily', 'weekly', 'monthly'
        # start_date 和 end_date 格式为 'YYYYMMDD'
        try:
            df = ak.fund_etf_hist_em(
                symbol=symbol,
                period='daily',  # 日线数据
                start_date=start_str,
                end_date=end_str,
                adjust="qfq"  # 前复权
            )
        except Exception as e:
            raise ValueError(f"Failed to fetch data for {symbol}: {str(e)}")
        
        if df.empty:
            raise ValueError(f"No data found for {symbol}")
        
        # 重命名列（AkShare返回的是中文列名）
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '换手率': 'turnover',
        }
        
        # 只重命名存在的列
        rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=rename_dict)
        
        # 日期范围已在API调用时过滤，但再次确认
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            # 可以再次过滤确保精确范围
            df = df[(df['date'] >= pd.to_datetime(start_str)) & 
                    (df['date'] <= pd.to_datetime(end_str))]
        
        if df.empty:
            raise ValueError(f"No data in range {start} to {end} for {symbol}")
        
        # 标准化数据格式
        df = self.normalize_dataframe(df)
        
        # 处理换手率（AkShare返回的可能是字符串，需要转换）
        if 'turnover' in df.columns:
            df['turnover'] = pd.to_numeric(
                df['turnover'].astype(str).str.replace('%', '').str.strip(),
                errors='coerce'
            )
        
        # 确保amount列存在
        if 'amount' not in df.columns and 'close' in df.columns and 'volume' in df.columns:
            df['amount'] = df['close'] * df['volume']
        
        # 只保留需要的列
        columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover']
        df = df[[col for col in columns if col in df.columns]]
        
        return df
    
    def fetch_history_minute(
        self,
        symbol: str,
        start: Union[str, datetime],
        end: Union[str, datetime],
        interval: str = '5',
        **kwargs
    ) -> pd.DataFrame:
        """
        从 AkShare 获取A股ETF分钟级别历史数据
        
        Args:
            symbol: ETF代码 (如 '510300')
            start: 开始日期时间 (格式: 'YYYY-MM-DD HH:MM:SS' 或 datetime)
            end: 结束日期时间 (格式: 'YYYY-MM-DD HH:MM:SS' 或 datetime)
            interval: 时间间隔 ('1', '5', '15', '30', '60')
        """
        # 转换为AkShare需要的格式
        if isinstance(start, datetime):
            start_str = start.strftime('%Y-%m-%d %H:%M:%S')
        else:
            start_str = start
        
        if isinstance(end, datetime):
            end_str = end.strftime('%Y-%m-%d %H:%M:%S')
        else:
            end_str = end
        
        try:
            # akshare的分钟数据接口可能需要按天获取，尝试分段获取
            start_dt = pd.to_datetime(start_str)
            end_dt = pd.to_datetime(end_str)
            
            # 如果时间范围超过1天，尝试按天获取
            if (end_dt - start_dt).days > 1:
                all_dfs = []
                current_date = start_dt.date()
                end_date = end_dt.date()
                
                while current_date <= end_date:
                    day_start = datetime.combine(current_date, datetime.min.time()).replace(hour=9, minute=30)
                    day_end = datetime.combine(current_date, datetime.min.time()).replace(hour=15, minute=0)
                    
                    # 确保不超过end_dt
                    if day_start > end_dt:
                        break
                    if day_end > end_dt:
                        day_end = end_dt
                    
                    try:
                        day_df = ak.fund_etf_hist_min_em(
                            symbol=symbol,
                            start_date=day_start.strftime('%Y-%m-%d %H:%M:%S'),
                            end_date=day_end.strftime('%Y-%m-%d %H:%M:%S'),
                            period=interval,
                            adjust="qfq"
                        )
                        if not day_df.empty:
                            all_dfs.append(day_df)
                    except Exception:
                        # 某一天失败，继续下一天
                        pass
                    
                    current_date += timedelta(days=1)
                    # 避免请求过快
                    import time
                    time.sleep(0.5)
                
                if all_dfs:
                    df = pd.concat(all_dfs, ignore_index=True)
                    df = df.drop_duplicates()
                else:
                    df = pd.DataFrame()
            else:
                # 单天数据，直接获取
                df = ak.fund_etf_hist_min_em(
                    symbol=symbol,
                    start_date=start_str,
                    end_date=end_str,
                    period=interval,  # '1', '5', '15', '30', '60'
                    adjust="qfq"  # 前复权
                )
        except Exception as e:
            raise ValueError(f"Failed to fetch minute data for {symbol}: {str(e)}")
        
        if df.empty:
            raise ValueError(f"No minute data found for {symbol}")
        
        # 重命名列（AkShare返回的是中文列名）
        column_mapping = {
            '时间': 'datetime',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
        }
        
        # 只重命名存在的列
        rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=rename_dict)
        
        # 确保datetime列是datetime类型
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            # 转换为带时区的datetime（Django要求）
            from django.utils import timezone
            # akshare返回的是北京时间（UTC+8），但Django需要aware datetime
            # 将naive datetime转换为UTC+8的aware datetime
            if df['datetime'].dt.tz is None:
                import pytz
                beijing_tz = pytz.timezone('Asia/Shanghai')
                df['datetime'] = df['datetime'].dt.tz_localize(beijing_tz)
        else:
            raise ValueError("DataFrame must contain '时间' column")
        
        # 确保数值列为数值类型
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 修复异常的开盘价：如果开盘价为0或异常，使用收盘价替代
        # 这可能是akshare数据源的问题
        if 'open' in df.columns and 'close' in df.columns:
            mask = (df['open'] == 0) | (df['open'] < 0.1) | df['open'].isna()
            df.loc[mask, 'open'] = df.loc[mask, 'close']
        
        # 确保amount列存在
        if 'amount' not in df.columns and 'close' in df.columns and 'volume' in df.columns:
            df['amount'] = df['close'] * df['volume']
        
        # 按时间排序
        df = df.sort_values('datetime').reset_index(drop=True)
        
        # 只保留需要的列
        columns = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'amount']
        df = df[[col for col in columns if col in df.columns]]
        
        return df


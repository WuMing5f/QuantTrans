"""
技术指标计算引擎
优先使用 pandas_ta 库计算技术指标，如果不可用则使用 pandas/numpy 手动计算
"""
import pandas as pd
import numpy as np
from typing import Optional

# 尝试导入 pandas_ta，如果不可用则使用手动计算
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False


class IndicatorEngine:
    """指标计算引擎（静态工具类）"""
    
    @staticmethod
    def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def _calc_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """计算MACD指标"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return macd, signal_line, histogram
    
    @staticmethod
    def _calc_bbands(series: pd.Series, period: int = 20, std_dev: int = 2):
        """计算布林带"""
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        bandwidth = (upper - lower) / sma
        bb_percent = (series - lower) / (upper - lower)
        return {
            'BBL_20_2.0': lower,
            'BBM_20_2.0': sma,
            'BBU_20_2.0': upper,
            'BBB_20_2.0': bandwidth * 100,
            'BBP_20_2.0': bb_percent * 100
        }
    
    @staticmethod
    def _calc_stoch(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 9, d_period: int = 3):
        """计算随机指标（KDJ）"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        k_smooth = k_percent.rolling(window=d_period).mean()
        d_smooth = k_smooth.rolling(window=d_period).mean()
        return k_smooth, d_smooth
    
    @staticmethod
    def inject_indicators(df: pd.DataFrame, market: str = 'US') -> pd.DataFrame:
        """
        向DataFrame注入技术指标
        
        Args:
            df: 包含OHLCV数据的DataFrame，必须包含列：date, open, high, low, close, volume
            market: 市场类型 ('US' 或 'CN')
            
        Returns:
            包含原始数据和计算指标的DataFrame
        """
        # 确保有date列或索引是日期
        if 'date' not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()
                if df.index.name == 'date':
                    df.rename(columns={df.index.name: 'date'}, inplace=True)
        
        # 确保date是datetime类型
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
        
        if HAS_PANDAS_TA:
            # 使用 pandas_ta 计算（更快更准确）
            # 计算移动平均线 (MA)
            df['SMA_5'] = ta.sma(df['close'], length=5)
            df['SMA_20'] = ta.sma(df['close'], length=20)
            df['SMA_60'] = ta.sma(df['close'], length=60)
            
            # 计算布林带 (Bollinger Bands)
            bbands = ta.bbands(df['close'], length=20, std=2)
            if bbands is not None:
                df['BBL_20_2.0'] = bbands['BBL_20_2.0']
                df['BBM_20_2.0'] = bbands['BBM_20_2.0']
                df['BBU_20_2.0'] = bbands['BBU_20_2.0']
                df['BBB_20_2.0'] = bbands['BBB_20_2.0']
                df['BBP_20_2.0'] = bbands['BBP_20_2.0']
            
            # 计算MACD
            macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
            if macd is not None:
                df['MACD_12_26_9'] = macd['MACD_12_26_9']
                df['MACDs_12_26_9'] = macd['MACDs_12_26_9']
                df['MACDh_12_26_9'] = macd['MACDh_12_26_9']
            
            # 计算RSI
            df['RSI_14'] = ta.rsi(df['close'], length=14)
            
            # KDJ指标
            if market.upper() == 'CN' or True:
                stoch = ta.stoch(df['high'], df['low'], df['close'], k=9, d=3, smooth_k=3)
                if stoch is not None:
                    df['STOCHk_9_3_3'] = stoch['STOCHk_9_3_3']
                    df['STOCHd_9_3_3'] = stoch['STOCHd_9_3_3']
                    df['KDJ_J'] = 3 * df['STOCHk_9_3_3'] - 2 * df['STOCHd_9_3_3']
        else:
            # 使用 pandas/numpy 手动计算（兼容模式）
            # 计算移动平均线 (MA)
            df['SMA_5'] = df['close'].rolling(window=5).mean()
            df['SMA_20'] = df['close'].rolling(window=20).mean()
            df['SMA_60'] = df['close'].rolling(window=60).mean()
            
            # 计算布林带
            bbands = IndicatorEngine._calc_bbands(df['close'], period=20, std_dev=2)
            for key, value in bbands.items():
                df[key] = value
            
            # 计算MACD
            macd, signal, histogram = IndicatorEngine._calc_macd(df['close'], fast=12, slow=26, signal=9)
            df['MACD_12_26_9'] = macd
            df['MACDs_12_26_9'] = signal
            df['MACDh_12_26_9'] = histogram
            
            # 计算RSI
            df['RSI_14'] = IndicatorEngine._calc_rsi(df['close'], period=14)
            
            # KDJ指标
            if market.upper() == 'CN' or True:
                k, d = IndicatorEngine._calc_stoch(df['high'], df['low'], df['close'], k_period=9, d_period=3)
                df['STOCHk_9_3_3'] = k
                df['STOCHd_9_3_3'] = d
                df['KDJ_J'] = 3 * k - 2 * d
        
        # 重置索引，将date转为列
        df = df.reset_index()
        
        return df


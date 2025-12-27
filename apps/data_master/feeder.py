"""
统一数据源适配器 (DataFeeder)
封装 AkShare 和 uSmart SDK，对外输出统一格式
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pandas as pd
from decimal import Decimal
from django.utils import timezone

from apps.data_master.models import MarketData, Instrument
from apps.data_master.providers import get_provider
from apps.data_master.volume_estimator import VolumeEstimator


class DataFeeder:
    """
    统一数据源适配器
    功能：
    1. 封装不同数据源（AkShare、uSmart SDK等）
    2. 统一数据格式输出
    3. 自动估算成交量方向（当数据源不含taker_buy_volume时）
    """
    
    def __init__(self):
        self.volume_estimator = VolumeEstimator()
    
    def fetch_etf_bars(
        self,
        symbol: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        interval: str = '1d',
        exchange: str = 'SH'
    ) -> List[MarketData]:
        """
        获取A股ETF数据并存入MarketData表
        
        Args:
            symbol: ETF代码，如 "510300"
            start_date: 开始日期
            end_date: 结束日期，默认为当前时间
            interval: 时间间隔，默认'1d'（日线）
            exchange: 交易所代码，默认'SH'（上海）
            
        Returns:
            List[MarketData]: 保存的MarketData对象列表
        """
        if end_date is None:
            end_date = timezone.now()
        
        # 获取数据提供者
        provider = get_provider('CN')
        
        # 转换为字符串格式
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # 获取历史数据
        df = provider.fetch_history(symbol, start_str, end_str)
        
        if df.empty:
            return []
        
        # 转换为MarketData对象列表
        market_data_list = []
        for _, row in df.iterrows():
            # 转换日期为datetime（UTC）
            if isinstance(row['date'], pd.Timestamp):
                dt = row['date'].to_pydatetime()
            else:
                dt = pd.to_datetime(row['date']).to_pydatetime()
            
            # 确保是UTC时间
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            dt = timezone.localtime(dt, timezone.utc)
            
            # 创建或更新MarketData
            market_data, created = MarketData.objects.update_or_create(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
                interval=interval,
                defaults={
                    'open_price': Decimal(str(row['open'])),
                    'high_price': Decimal(str(row['high'])),
                    'low_price': Decimal(str(row['low'])),
                    'close_price': Decimal(str(row['close'])),
                    'volume': Decimal(str(row['volume'])),
                    'amount': Decimal(str(row.get('amount', row['close'] * row['volume']))),
                    'taker_buy_volume': None,  # AkShare不提供此字段，后续通过VolumeEstimator估算
                    'volume_direction': 0,
                }
            )
            market_data_list.append(market_data)
        
        # 如果有数据，使用VolumeEstimator估算成交量方向
        if market_data_list:
            self._estimate_volume_direction(market_data_list)
        
        return market_data_list
    
    def fetch_minute_bars(
        self,
        symbol: str,
        exchange: str,
        start_datetime: datetime,
        end_datetime: Optional[datetime] = None,
        interval: str = '1m'
    ) -> List[MarketData]:
        """
        获取分钟级K线数据
        
        Args:
            symbol: 代码
            exchange: 交易所
            start_datetime: 开始时间
            end_datetime: 结束时间
            interval: 时间间隔，默认'1m'
            
        Returns:
            List[MarketData]: 保存的MarketData对象列表
        """
        if end_datetime is None:
            end_datetime = timezone.now()
        
        # 这里可以根据exchange选择不同的数据源
        # 目前先使用现有的分钟数据同步逻辑
        from apps.data_master.models import CandleMinute, Instrument
        
        try:
            instrument = Instrument.objects.get(symbol=symbol)
        except Instrument.DoesNotExist:
            return []
        
        # 查询分钟数据
        minute_candles = CandleMinute.objects.filter(
            instrument=instrument,
            interval=interval,
            datetime__gte=start_datetime,
            datetime__lte=end_datetime
        ).order_by('datetime')
        
        # 转换为MarketData
        market_data_list = []
        for candle in minute_candles:
            # 确保是UTC时间
            dt = candle.datetime
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            dt = timezone.localtime(dt, timezone.utc)
            
            market_data, created = MarketData.objects.update_or_create(
                symbol=symbol,
                exchange=exchange or instrument.exchange or 'SH',
                datetime=dt,
                interval=interval,
                defaults={
                    'open_price': Decimal(str(candle.open)),
                    'high_price': Decimal(str(candle.high)),
                    'low_price': Decimal(str(candle.low)),
                    'close_price': Decimal(str(candle.close)),
                    'volume': Decimal(str(candle.volume)),
                    'amount': Decimal(str(candle.amount)),
                    'taker_buy_volume': None,
                    'volume_direction': 0,
                }
            )
            market_data_list.append(market_data)
        
        # 估算成交量方向
        if market_data_list:
            self._estimate_volume_direction(market_data_list)
        
        return market_data_list
    
    def _estimate_volume_direction(self, market_data_list: List[MarketData]):
        """
        使用VolumeEstimator估算成交量方向
        """
        # 按时间排序
        sorted_data = sorted(market_data_list, key=lambda x: x.datetime)
        
        # 使用VolumeEstimator估算
        for i, market_data in enumerate(sorted_data):
            if i == 0:
                # 第一条数据无法估算，设为中性
                market_data.volume_direction = 0
            else:
                prev_data = sorted_data[i - 1]
                # 使用Tick Rule算法估算
                direction, taker_buy_vol = self.volume_estimator.estimate(
                    current_price=float(market_data.close_price),
                    prev_price=float(prev_data.close_price),
                    volume=float(market_data.volume)
                )
                
                market_data.volume_direction = direction
                if taker_buy_vol is not None:
                    market_data.taker_buy_volume = Decimal(str(taker_buy_vol))
            
            market_data.save()
    
    def get_latest_bars(
        self,
        symbol: str,
        exchange: str,
        limit: int = 100,
        interval: str = '1m'
    ) -> List[MarketData]:
        """
        获取最新的K线数据
        
        Args:
            symbol: 代码
            exchange: 交易所
            limit: 返回条数
            interval: 时间间隔
            
        Returns:
            List[MarketData]: MarketData对象列表
        """
        return list(
            MarketData.objects.filter(
                symbol=symbol,
                exchange=exchange,
                interval=interval
            ).order_by('-datetime')[:limit]
        )


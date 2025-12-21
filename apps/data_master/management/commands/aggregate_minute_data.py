"""
从1分钟K线数据聚合生成5分钟和1小时K线数据
使用方法：
    python manage.py aggregate_minute_data --interval 5m  # 生成5分钟K线
    python manage.py aggregate_minute_data --interval 60m  # 生成1小时K线
    python manage.py aggregate_minute_data --interval all  # 生成所有间隔
"""
from django.core.management.base import BaseCommand
from apps.data_master.models import Instrument, CandleMinute
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd
import pytz


class Command(BaseCommand):
    help = '从1分钟K线数据聚合生成更长周期的K线数据'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=str,
            default='all',
            choices=['5m', '60m', 'all'],
            help='要生成的K线周期: 5m (5分钟), 60m (1小时), all (全部)'
        )
        parser.add_argument(
            '--symbol',
            type=str,
            help='指定标的代码（可选，不指定则处理所有有1分钟数据的标的）'
        )
    
    def aggregate_kline(self, df_1m, interval_minutes):
        """
        从1分钟K线数据聚合生成指定周期的K线数据
        
        Args:
            df_1m: 1分钟K线DataFrame，包含datetime, open, high, low, close, volume, amount
            interval_minutes: 聚合的分钟数（5或60）
        
        Returns:
            聚合后的DataFrame
        """
        # 设置datetime为索引
        df = df_1m.set_index('datetime').copy()
        
        # 按时间间隔分组
        if interval_minutes == 5:
            # 5分钟：按5分钟分组
            grouped = df.resample('5min').agg({
                'open': 'first',      # 第一个开盘价
                'high': 'max',        # 最高价
                'low': 'min',         # 最低价
                'close': 'last',      # 最后一个收盘价
                'volume': 'sum',      # 成交量求和
                'amount': 'sum'       # 成交额求和
            })
        elif interval_minutes == 60:
            # 1小时：按1小时分组
            grouped = df.resample('1h').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'amount': 'sum'
            })
        else:
            raise ValueError(f"不支持的间隔: {interval_minutes}分钟")
        
        # 重置索引
        grouped = grouped.reset_index()
        
        # 过滤掉没有数据的行（非交易时间）
        grouped = grouped.dropna()
        
        return grouped
    
    def handle(self, *args, **options):
        interval = options['interval']
        symbol = options.get('symbol')
        
        self.stdout.write(f'开始聚合分钟K线数据...')
        
        # 确定要处理的间隔
        intervals_to_process = []
        if interval == 'all':
            intervals_to_process = [('5m', 5), ('60m', 60)]
        elif interval == '5m':
            intervals_to_process = [('5m', 5)]
        elif interval == '60m':
            intervals_to_process = [('60m', 60)]
        
        # 获取要处理的标的
        if symbol:
            instruments = Instrument.objects.filter(symbol=symbol, market='CN')
        else:
            # 获取所有有1分钟数据的A股ETF
            instruments = Instrument.objects.filter(
                market='CN',
                minute_candles__interval='1m'
            ).distinct()
        
        if not instruments.exists():
            self.stdout.write(self.style.WARNING('没有找到需要处理的标的'))
            return
        
        total_instruments = instruments.count()
        self.stdout.write(f'找到 {total_instruments} 个标的需要处理')
        
        for interval_name, interval_minutes in intervals_to_process:
            self.stdout.write(f'\n处理 {interval_name} K线数据...')
            
            for idx, instrument in enumerate(instruments, 1):
                self.stdout.write(f'[{idx}/{total_instruments}] 处理 {instrument.symbol} ({instrument.name})...')
                
                try:
                    # 获取1分钟数据
                    candles_1m = CandleMinute.objects.filter(
                        instrument=instrument,
                        interval='1m'
                    ).order_by('datetime')
                    
                    if not candles_1m.exists():
                        self.stdout.write(f'  ⚠️ 没有1分钟数据，跳过')
                        continue
                    
                    # 转换为DataFrame
                    data_list = []
                    for candle in candles_1m:
                        data_list.append({
                            'datetime': candle.datetime,
                            'open': float(candle.open),
                            'high': float(candle.high),
                            'low': float(candle.low),
                            'close': float(candle.close),
                            'volume': int(candle.volume),
                            'amount': float(candle.amount),
                        })
                    
                    df_1m = pd.DataFrame(data_list)
                    df_1m['datetime'] = pd.to_datetime(df_1m['datetime'])
                    
                    # 聚合数据
                    df_aggregated = self.aggregate_kline(df_1m, interval_minutes)
                    
                    if df_aggregated.empty:
                        self.stdout.write(f'  ⚠️ 聚合后没有数据，跳过')
                        continue
                    
                    # 保存聚合后的数据
                    candles_to_create = []
                    candles_to_update = []
                    
                    for _, row in df_aggregated.iterrows():
                        # 确保datetime是aware datetime
                        dt = row['datetime']
                        if dt.tzinfo is None:
                            beijing_tz = pytz.timezone('Asia/Shanghai')
                            dt = beijing_tz.localize(dt)
                        
                        candle_data = {
                            'instrument': instrument,
                            'datetime': dt,
                            'interval': interval_name,
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': int(row['volume']),
                            'amount': float(row['amount']),
                        }
                        
                        # 检查是否已存在
                        existing = CandleMinute.objects.filter(
                            instrument=instrument,
                            datetime=dt,
                            interval=interval_name
                        ).first()
                        
                        if existing:
                            # 更新现有记录
                            for key, value in candle_data.items():
                                if key not in ['instrument', 'datetime', 'interval']:
                                    setattr(existing, key, value)
                            candles_to_update.append(existing)
                        else:
                            candles_to_create.append(CandleMinute(**candle_data))
                    
                    # 批量创建
                    if candles_to_create:
                        CandleMinute.objects.bulk_create(candles_to_create, ignore_conflicts=True)
                        self.stdout.write(self.style.SUCCESS(f'  ✓ 创建 {len(candles_to_create)} 条{interval_name}数据'))
                    
                    # 批量更新
                    if candles_to_update:
                        CandleMinute.objects.bulk_update(
                            candles_to_update,
                            ['open', 'high', 'low', 'close', 'volume', 'amount']
                        )
                        self.stdout.write(self.style.SUCCESS(f'  ✓ 更新 {len(candles_to_update)} 条{interval_name}数据'))
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ 处理失败: {str(e)}'))
                    import traceback
                    self.stdout.write(traceback.format_exc())
            
            self.stdout.write(self.style.SUCCESS(f'\n{interval_name} K线数据处理完成！'))
        
        self.stdout.write(self.style.SUCCESS('\n全部处理完成！'))


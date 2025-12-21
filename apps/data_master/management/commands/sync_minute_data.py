"""
分钟数据同步管理命令
使用方法：
    python manage.py sync_minute_data --symbol 510300 --market CN --interval 1m --days 7
    python manage.py sync_minute_data --symbol 510300 --market CN --interval 1m --start 2024-01-01 --end 2024-01-07
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from apps.data_master.models import Instrument, CandleMinute
from apps.data_master.providers import get_provider
import pandas as pd


class Command(BaseCommand):
    help = '从数据源同步股票分钟K线数据到数据库'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            required=True,
            help='股票代码 (如: AAPL, 510300)'
        )
        parser.add_argument(
            '--market',
            type=str,
            required=True,
            choices=['US', 'CN'],
            help='市场类型: US (美股) 或 CN (A股)'
        )
        parser.add_argument(
            '--interval',
            type=str,
            required=True,
            choices=['1m', '5m', '15m', '30m', '60m'],
            help='时间间隔: 1m, 5m, 15m, 30m, 60m'
        )
        parser.add_argument(
            '--start',
            type=str,
            help='开始日期时间 (格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)'
        )
        parser.add_argument(
            '--end',
            type=str,
            help='结束日期时间 (格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)'
        )
        parser.add_argument(
            '--days',
            type=int,
            help='同步最近多少天的数据（与start/end二选一）'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='标的名称（可选）'
        )
    
    def handle(self, *args, **options):
        symbol = options['symbol']
        market = options['market']
        interval = options['interval']
        start = options.get('start')
        end = options.get('end')
        days = options.get('days')
        name = options.get('name')
        
        # 确定时间范围
        if days:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days)
            start = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            end = end_dt.strftime('%Y-%m-%d %H:%M:%S')
        elif not start or not end:
            raise ValueError("必须提供 --days 或 --start 和 --end 参数")
        else:
            # 如果没有时间部分，添加默认时间
            if ' ' not in start:
                start = f"{start} 09:30:00"
            if ' ' not in end:
                end = f"{end} 15:00:00"
        
        self.stdout.write(f"开始同步 {market}:{symbol} 的{interval}分钟数据...")
        self.stdout.write(f"时间范围: {start} 到 {end}")
        
        try:
            # 获取或创建Instrument
            instrument, created = Instrument.objects.get_or_create(
                symbol=symbol,
                defaults={
                    'market': market,
                    'name': name or symbol
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'创建新标的: {instrument}'))
            else:
                self.stdout.write(f'使用现有标的: {instrument}')
            
            # 获取数据提供者
            provider = get_provider(market)
            
            # 检查是否支持分钟数据
            if not hasattr(provider, 'fetch_history_minute'):
                raise ValueError(f"Provider {type(provider).__name__} 不支持分钟数据获取")
            
            # 转换interval格式（1m -> '1', 5m -> '5'等）
            interval_map = {
                '1m': '1',
                '5m': '5',
                '15m': '15',
                '30m': '30',
                '60m': '60',
            }
            interval_value = interval_map[interval]
            
            # 获取历史数据
            self.stdout.write(f'正在从数据源获取分钟数据...')
            df = provider.fetch_history_minute(symbol, start, end, interval=interval_value)
            
            self.stdout.write(f'获取到 {len(df)} 条记录')
            
            if df.empty:
                self.stdout.write(self.style.WARNING('没有获取到数据'))
                return
            
            # 批量保存到数据库
            candles_to_create = []
            candles_to_update = []
            
            from django.utils import timezone
            
            for _, row in df.iterrows():
                # 处理datetime，确保是aware datetime
                dt = row['datetime']
                if isinstance(dt, pd.Timestamp):
                    if dt.tzinfo is None:
                        # naive datetime，需要添加时区
                        import pytz
                        beijing_tz = pytz.timezone('Asia/Shanghai')
                        dt = dt.tz_localize(beijing_tz)
                    dt = dt.to_pydatetime()
                elif isinstance(dt, datetime) and dt.tzinfo is None:
                    import pytz
                    beijing_tz = pytz.timezone('Asia/Shanghai')
                    dt = beijing_tz.localize(dt)
                
                candle_data = {
                    'instrument': instrument,
                    'datetime': dt,
                    'interval': interval,
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume']),
                    'amount': float(row.get('amount', 0)),
                }
                
                # 检查是否已存在
                existing = CandleMinute.objects.filter(
                    instrument=instrument,
                    datetime=candle_data['datetime'],
                    interval=interval
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
                self.stdout.write(self.style.SUCCESS(f'创建 {len(candles_to_create)} 条新记录'))
            
            # 批量更新
            if candles_to_update:
                CandleMinute.objects.bulk_update(
                    candles_to_update,
                    ['open', 'high', 'low', 'close', 'volume', 'amount']
                )
                self.stdout.write(self.style.SUCCESS(f'更新 {len(candles_to_update)} 条记录'))
            
            self.stdout.write(self.style.SUCCESS('分钟数据同步完成！'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'错误: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())
            raise


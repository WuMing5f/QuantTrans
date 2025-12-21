"""
数据同步管理命令
使用方法：
    python manage.py sync_data --symbol AAPL --market US --start 2020-01-01 --end 2024-01-01
    python manage.py sync_data --symbol 510300 --market CN --start 2020-01-01 --end 2024-01-01
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from apps.data_master.models import Instrument, Candle
from apps.data_master.providers import get_provider
import pandas as pd


class Command(BaseCommand):
    help = '从数据源同步股票K线数据到数据库'
    
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
            '--start',
            type=str,
            required=True,
            help='开始日期 (格式: YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end',
            type=str,
            required=True,
            help='结束日期 (格式: YYYY-MM-DD)'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='标的名称（可选，如果不提供将尝试从数据源获取）'
        )
    
    def handle(self, *args, **options):
        symbol = options['symbol']
        market = options['market']
        start = options['start']
        end = options['end']
        name = options.get('name')
        
        self.stdout.write(f"开始同步 {market}:{symbol} 的数据...")
        
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
                # 更新市场（如果需要）
                if instrument.market != market:
                    instrument.market = market
                    instrument.save()
                self.stdout.write(f'使用现有标的: {instrument}')
            
            # 获取数据提供者
            provider = get_provider(market)
            
            # 获取历史数据
            self.stdout.write(f'正在从数据源获取数据 ({start} 到 {end})...')
            df = provider.fetch_history(symbol, start, end)
            
            self.stdout.write(f'获取到 {len(df)} 条记录')
            
            # 批量保存到数据库
            candles_to_create = []
            candles_to_update = []
            
            for _, row in df.iterrows():
                candle_data = {
                    'instrument': instrument,
                    'date': row['date'].date() if hasattr(row['date'], 'date') else row['date'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume']),
                    'amount': float(row.get('amount', 0)),
                    'turnover': float(row['turnover']) if pd.notna(row.get('turnover')) else None,
                }
                
                # 检查是否已存在
                existing = Candle.objects.filter(
                    instrument=instrument,
                    date=candle_data['date']
                ).first()
                
                if existing:
                    # 更新现有记录
                    for key, value in candle_data.items():
                        if key != 'instrument':
                            setattr(existing, key, value)
                    candles_to_update.append(existing)
                else:
                    candles_to_create.append(Candle(**candle_data))
            
            # 批量创建
            if candles_to_create:
                Candle.objects.bulk_create(candles_to_create, ignore_conflicts=True)
                self.stdout.write(self.style.SUCCESS(f'创建 {len(candles_to_create)} 条新记录'))
            
            # 批量更新
            if candles_to_update:
                Candle.objects.bulk_update(
                    candles_to_update,
                    ['open', 'high', 'low', 'close', 'volume', 'amount', 'turnover']
                )
                self.stdout.write(self.style.SUCCESS(f'更新 {len(candles_to_update)} 条记录'))
            
            self.stdout.write(self.style.SUCCESS('数据同步完成！'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'错误: {str(e)}'))
            raise


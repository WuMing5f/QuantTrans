"""
批量同步ETF分钟数据
使用方法：
    python manage.py batch_sync_minute --interval 1m --days 7
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from datetime import datetime, timedelta
import time


class Command(BaseCommand):
    help = '批量同步ETF分钟K线数据'
    
    # A股ETF列表
    CN_ETFS = [
        ('510300', '沪深300ETF', '宽基指数'),
        ('510500', '中证500ETF', '宽基指数'),
        ('159919', '沪深300ETF（深市）', '宽基指数'),
        ('159915', '创业板ETF', '宽基指数'),
        ('512100', '1000ETF', '宽基指数'),
        ('159901', '深证100ETF', '宽基指数'),
        ('510050', '50ETF', '宽基指数'),
        ('512000', '券商ETF', '金融'),
        ('515050', '5G ETF', '科技'),
    ]
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=str,
            required=True,
            choices=['1m', '5m', '15m', '30m', '60m'],
            help='时间间隔: 1m, 5m, 15m, 30m, 60m'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='同步最近多少天的数据（默认7天）'
        )
        parser.add_argument(
            '--start',
            type=str,
            help='开始日期 (格式: YYYY-MM-DD)，如果提供则同步从开始日期到现在的所有数据'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=2.0,
            help='每次请求之间的延迟时间（秒，默认2秒）'
        )
    
    def handle(self, *args, **options):
        interval = options['interval']
        days = options['days']
        start_date_str = options.get('start')
        delay = options['delay']
        
        self.stdout.write(f"开始批量同步ETF {interval}分钟数据...")
        self.stdout.write(f"请求延迟: {delay}秒")
        
        total = 0
        success = 0
        failed = []
        
        for symbol, name, category in self.CN_ETFS:
            total += 1
            self.stdout.write(f'\n[{total}/{len(self.CN_ETFS)}] 同步 {symbol} ({name}) 的{interval}分钟数据...')
            
            try:
                if start_date_str:
                    # 如果有开始日期，分批同步（每次7天，避免请求太大）
                    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                    end_dt = datetime.now()
                    current_dt = start_dt
                    
                    batch_count = 0
                    while current_dt < end_dt:
                        batch_start = current_dt.strftime('%Y-%m-%d')
                        batch_end_dt = min(current_dt + timedelta(days=7), end_dt)
                        batch_end = batch_end_dt.strftime('%Y-%m-%d')
                        
                        batch_count += 1
                        self.stdout.write(f'  批次 {batch_count}: {batch_start} 到 {batch_end}')
                        
                        call_command(
                            'sync_minute_data',
                            symbol=symbol,
                            market='CN',
                            interval=interval,
                            start=batch_start,
                            end=batch_end,
                            verbosity=0
                        )
                        
                        current_dt = batch_end_dt
                        time.sleep(delay)  # 批次间延迟
                else:
                    # 只同步最近N天的数据
                    call_command(
                        'sync_minute_data',
                        symbol=symbol,
                        market='CN',
                        interval=interval,
                        days=days,
                        verbosity=0
                    )
                
                success += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ {symbol} 同步成功'))
            except Exception as e:
                failed.append((symbol, str(e)))
                self.stdout.write(self.style.ERROR(f'  ✗ {symbol} 同步失败: {str(e)}'))
            
            # 延迟，避免请求过快
            if total < len(self.CN_ETFS):
                time.sleep(delay)
        
        # 总结
        self.stdout.write(self.style.SUCCESS(f'\n=== 同步完成 ==='))
        self.stdout.write(f'总计: {total} 个ETF')
        self.stdout.write(self.style.SUCCESS(f'成功: {success} 个'))
        if failed:
            self.stdout.write(self.style.ERROR(f'失败: {len(failed)} 个'))
            self.stdout.write('\n失败的ETF:')
            for symbol, error in failed:
                self.stdout.write(self.style.ERROR(f'  {symbol} - {error}'))
        else:
            self.stdout.write(self.style.SUCCESS('全部成功！'))


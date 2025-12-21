"""
批量数据同步管理命令
用于批量同步多个标的的数据
使用方法：
    python manage.py batch_sync --type etf --days 7
    python manage.py batch_sync --type us_stocks --days 7
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from datetime import datetime, timedelta
import time


class Command(BaseCommand):
    help = '批量同步股票K线数据到数据库'
    
    # A股ETF列表（常见的ETF）- (代码, 名称, 行业分类)
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
    
    # 美股龙头股票（各领域）
    US_STOCKS = [
        ('AAPL', 'Apple Inc.', '科技'),
        ('MSFT', 'Microsoft Corporation', '科技'),
        ('GOOGL', 'Alphabet Inc.', '科技'),
        ('AMZN', 'Amazon.com Inc.', '电商'),
        ('TSLA', 'Tesla Inc.', '新能源'),
        ('NVDA', 'NVIDIA Corporation', 'AI/芯片'),
        ('META', 'Meta Platforms Inc.', '科技'),
        ('JPM', 'JPMorgan Chase & Co.', '金融'),
        ('JNJ', 'Johnson & Johnson', '医疗'),
        ('V', 'Visa Inc.', '金融'),
        ('MA', 'Mastercard Incorporated', '金融'),
        ('DIS', 'The Walt Disney Company', '娱乐'),
        ('NFLX', 'Netflix Inc.', '娱乐'),
        ('BABA', 'Alibaba Group', '电商'),
    ]
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            required=True,
            choices=['etf', 'us_stocks', 'all'],
            help='同步类型: etf (A股ETF), us_stocks (美股龙头), all (全部)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='同步最近多少天的数据（默认7天）'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=2.0,
            help='每次请求之间的延迟时间（秒，默认2秒）'
        )
    
    def handle(self, *args, **options):
        sync_type = options['type']
        days = options['days']
        delay = options['delay']
        
        # 计算日期范围
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        self.stdout.write(f"开始批量同步数据（{start_str} 到 {end_str}）...")
        self.stdout.write(f"请求延迟: {delay}秒")
        
        total = 0
        success = 0
        failed = []
        
        if sync_type in ['etf', 'all']:
            self.stdout.write(self.style.SUCCESS('\n=== 同步A股ETF数据 ==='))
            for etf_info in self.CN_ETFS:
                if len(etf_info) == 3:
                    symbol, name, category = etf_info
                else:
                    symbol, name = etf_info
                    category = None
                
                total += 1
                self.stdout.write(f'\n[{total}] 同步 {symbol} ({name})...')
                try:
                    # 先同步数据
                    call_command(
                        'sync_data',
                        symbol=symbol,
                        market='CN',
                        start=start_str,
                        end=end_str,
                        name=name,
                        verbosity=0  # 减少输出
                    )
                    # 更新行业分类
                    if category:
                        from apps.data_master.models import Instrument
                        try:
                            instrument = Instrument.objects.get(symbol=symbol)
                            instrument.category = category
                            instrument.save()
                        except Instrument.DoesNotExist:
                            pass
                    
                    success += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {symbol} 同步成功'))
                except Exception as e:
                    failed.append((symbol, 'CN', str(e)))
                    self.stdout.write(self.style.ERROR(f'  ✗ {symbol} 同步失败: {str(e)}'))
                
                # 延迟，避免请求过快
                if total < len(self.CN_ETFS) + (len(self.US_STOCKS) if sync_type == 'all' else 0):
                    time.sleep(delay)
        
        if sync_type in ['us_stocks', 'all']:
            self.stdout.write(self.style.SUCCESS('\n=== 同步美股龙头股票数据 ==='))
            for symbol, name, category in self.US_STOCKS:
                total += 1
                self.stdout.write(f'\n[{total}] 同步 {symbol} ({name}) - {category}...')
                try:
                    call_command(
                        'sync_data',
                        symbol=symbol,
                        market='US',
                        start=start_str,
                        end=end_str,
                        name=name,
                        verbosity=0
                    )
                    success += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {symbol} 同步成功'))
                except Exception as e:
                    failed.append((symbol, 'US', str(e)))
                    self.stdout.write(self.style.ERROR(f'  ✗ {symbol} 同步失败: {str(e)}'))
                
                # 延迟，避免请求过快（美股需要更长的延迟）
                if total < len(self.CN_ETFS) + len(self.US_STOCKS) if sync_type == 'all' else len(self.US_STOCKS):
                    time.sleep(delay * 2)  # 美股延迟更长
        
        # 总结
        self.stdout.write(self.style.SUCCESS(f'\n=== 同步完成 ==='))
        self.stdout.write(f'总计: {total} 个标的')
        self.stdout.write(self.style.SUCCESS(f'成功: {success} 个'))
        if failed:
            self.stdout.write(self.style.ERROR(f'失败: {len(failed)} 个'))
            self.stdout.write('\n失败的标的:')
            for symbol, market, error in failed:
                self.stdout.write(self.style.ERROR(f'  {market}:{symbol} - {error}'))
        else:
            self.stdout.write(self.style.SUCCESS('全部成功！'))


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
        # 宽基指数
        ('510300', '沪深300ETF', '宽基指数'),
        ('510500', '中证500ETF', '宽基指数'),
        ('159919', '沪深300ETF（深市）', '宽基指数'),
        ('159915', '创业板ETF', '宽基指数'),
        ('512100', '1000ETF', '宽基指数'),
        ('159901', '深证100ETF', '宽基指数'),
        ('510050', '50ETF', '宽基指数'),
        # 行业ETF - 金融
        ('512000', '券商ETF', '金融'),
        ('512800', '银行ETF', '金融'),
        # 行业ETF - 科技
        ('515050', '5G ETF', '科技'),
        ('512760', '芯片ETF', '科技'),
        ('159997', '芯片ETF（广发）', '科技'),
        ('515880', '通信ETF', '科技'),
        ('515030', '新基建ETF', '科技'),
        ('159939', '信息技术ETF', '科技'),
        ('512480', '半导体ETF', '科技'),
        # 行业ETF - 消费
        ('159928', '消费ETF', '消费'),
        ('512600', '消费ETF（南方）', '消费'),
        ('159936', '可选消费ETF', '消费'),
        ('159996', '家电ETF', '消费'),
        ('512690', '酒ETF', '消费'),
        # 行业ETF - 新能源
        ('516160', '新能源ETF', '新能源'),
        ('159824', '新能源ETF（博时）', '新能源'),
        ('516850', '新能源车ETF', '新能源'),
        ('159806', '新能源80ETF', '新能源'),
        # 行业ETF - 医疗
        ('159929', '医药ETF', '医疗'),
        ('512170', '医疗ETF', '医疗'),
        ('159938', '医药卫生ETF', '医疗'),
        ('159992', '创新药ETF', '医疗'),
        ('512010', '医药ETF（易方达）', '医疗'),
        # 行业ETF - 金融（继续）
        ('159940', '金融ETF', '金融'),
        # 行业ETF - 军工
        ('512660', '军工ETF', '军工'),
        # 行业ETF - 其他
        ('512980', '传媒ETF', '传媒'),
        ('159805', '文化传媒ETF', '传媒'),
        ('159825', '农业ETF', '农业'),
        ('512200', '地产ETF', '地产'),
        ('512400', '有色ETF', '有色'),
        ('515220', '煤炭ETF', '煤炭'),
        ('159945', '能源ETF', '能源'),
        ('515210', '钢铁ETF', '钢铁'),
        ('512340', '原材料ETF', '原材料'),
        # 跨境ETF - T+0
        ('513310', '中韩半导体ETF', '半导体'),
        ('518880', '黄金ETF', '贵金属'),
        ('159502', '标普生物科技ETF', '生物科技'),
        ('513100', '纳指ETF', '海外指数'),
        ('513120', '恒生创新药ETF', '医疗'),
        ('513130', '恒生科技ETF', '科技'),
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
                    # 确定交易规则（T+0或T+1）
                    # 跨境ETF、黄金ETF通常是T+0，其他A股ETF通常是T+1
                    trading_rule = 'T+1'  # 默认T+1
                    if symbol in ['513310', '518880', '159502', '513100', '513120', '513130']:
                        trading_rule = 'T+0'  # 跨境ETF和黄金ETF通常是T+0
                    
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
                    # 更新行业分类和交易规则
                    from apps.data_master.models import Instrument
                    try:
                        instrument = Instrument.objects.get(symbol=symbol)
                        updated = False
                        if category and instrument.category != category:
                            instrument.category = category
                            updated = True
                        if instrument.trading_rule != trading_rule:
                            instrument.trading_rule = trading_rule
                            updated = True
                        if updated:
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


from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Index


class Instrument(models.Model):
    MARKET_CHOICES = [
        ('US', '美股'),
        ('CN', 'A股'),
        ('CRYPTO', '加密货币'),
    ]
    TRADING_RULE_CHOICES = [
        ('T+0', 'T+0'),
        ('T+1', 'T+1'),
    ]

    symbol = models.CharField(max_length=20, unique=True, verbose_name='代码')
    market = models.CharField(max_length=10, choices=MARKET_CHOICES, verbose_name='市场')
    exchange = models.CharField(max_length=20, default='', blank=True, verbose_name='交易所')  # 新增：支持多交易所
    name = models.CharField(max_length=100, verbose_name='名称')
    category = models.CharField(max_length=50, blank=True, null=True, verbose_name='行业分类')
    trading_rule = models.CharField(max_length=3, choices=TRADING_RULE_CHOICES, default='T+1', blank=True, null=True, verbose_name='交易规则')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'instruments'
        verbose_name = '标的'
        verbose_name_plural = '标的'
        ordering = ['symbol']

    def __str__(self):
        return f"{self.symbol} - {self.name} ({self.market})"


class Candle(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='candles', verbose_name='标的')
    date = models.DateField(verbose_name='日期')
    open = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(0)], verbose_name='开盘价')
    high = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(0)], verbose_name='最高价')
    low = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(0)], verbose_name='最低价')
    close = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(0)], verbose_name='收盘价')
    volume = models.BigIntegerField(validators=[MinValueValidator(0)], verbose_name='成交量')
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='成交额')
    turnover = models.DecimalField(max_digits=8, decimal_places=4, blank=True, null=True, verbose_name='换手率(%)')

    class Meta:
        db_table = 'candles'
        verbose_name = 'K线数据'
        verbose_name_plural = 'K线数据'
        ordering = ['instrument', 'date']
        unique_together = (('instrument', 'date'),)
        indexes = [
            Index(fields=['instrument', 'date']),
            Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.instrument.symbol} - {self.date}"


class CandleMinute(models.Model):
    INTERVAL_CHOICES = [
        ('1m', '1分钟'),
        ('5m', '5分钟'),
        ('15m', '15分钟'),
        ('30m', '30分钟'),
        ('60m', '60分钟'),
    ]
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='minute_candles', verbose_name='标的')
    datetime = models.DateTimeField(verbose_name='日期时间')
    interval = models.CharField(max_length=5, choices=INTERVAL_CHOICES, default='1m', verbose_name='时间间隔')
    open = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(0)], verbose_name='开盘价')
    high = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(0)], verbose_name='最高价')
    low = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(0)], verbose_name='最低价')
    close = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(0)], verbose_name='收盘价')
    volume = models.BigIntegerField(validators=[MinValueValidator(0)], verbose_name='成交量')
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='成交额')

    class Meta:
        db_table = 'candles_minute'
        verbose_name = '分钟K线数据'
        verbose_name_plural = '分钟K线数据'
        ordering = ['instrument', 'datetime']
        unique_together = (('instrument', 'datetime', 'interval'),)
        indexes = [
            Index(fields=['instrument', 'datetime', 'interval']),
            Index(fields=['datetime']),
        ]

    def __str__(self):
        return f"{self.instrument.symbol} - {self.datetime.strftime('%Y-%m-%d %H:%M')} ({self.get_interval_display()})"


class MarketData(models.Model):
    """
    统一行情表 - 兼容 Crypto (24h)、美股 (Tick)、A股 (Snapshot) 的统一结构
    设计思路：使用 symbol + exchange + datetime 作为联合主键
    """
    symbol = models.CharField(max_length=20, db_index=True, verbose_name='代码')
    exchange = models.CharField(max_length=20, db_index=True, verbose_name='交易所')  # "BINANCE", "USMART", "SH", "SZ"
    datetime = models.DateTimeField(db_index=True, verbose_name='时间戳')  # 统一存储为 UTC 时间
    
    # 基础 OHLCV
    open_price = models.DecimalField(max_digits=20, decimal_places=8, verbose_name='开盘价')
    high_price = models.DecimalField(max_digits=20, decimal_places=8, verbose_name='最高价')
    low_price = models.DecimalField(max_digits=20, decimal_places=8, verbose_name='最低价')
    close_price = models.DecimalField(max_digits=20, decimal_places=8, verbose_name='收盘价')
    volume = models.DecimalField(max_digits=30, decimal_places=8, verbose_name='总成交量')
    amount = models.DecimalField(max_digits=30, decimal_places=8, verbose_name='总成交额')
    
    # 核心增强字段 (用于策略方向判断)
    taker_buy_volume = models.DecimalField(
        max_digits=30, 
        decimal_places=8, 
        null=True, 
        blank=True,
        verbose_name='主动买入量'
    )
    volume_direction = models.IntegerField(
        default=0,
        verbose_name='成交量方向',
        help_text='1: 主动买入占优, -1: 主动卖出占优, 0: 中性'
    )
    
    # 时间间隔（用于区分日K、分钟K等）
    interval = models.CharField(
        max_length=10,
        default='1m',
        choices=[
            ('1m', '1分钟'),
            ('5m', '5分钟'),
            ('15m', '15分钟'),
            ('30m', '30分钟'),
            ('60m', '60分钟'),
            ('1d', '日线'),
        ],
        verbose_name='时间间隔'
    )
    
    # 元数据
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'market_data'
        verbose_name = '统一行情数据'
        verbose_name_plural = '统一行情数据'
        ordering = ['-datetime']
        unique_together = (('symbol', 'exchange', 'datetime', 'interval'),)
        indexes = [
            Index(fields=['symbol', 'datetime']),
            Index(fields=['exchange', 'datetime']),
            Index(fields=['symbol', 'exchange', 'datetime']),
            Index(fields=['datetime', 'interval']),
        ]
    
    def __str__(self):
        return f"{self.symbol}@{self.exchange} - {self.datetime.strftime('%Y-%m-%d %H:%M:%S')} ({self.interval})"


class TradeRecord(models.Model):
    """
    交易记录表 - 用于记录每一笔实盘或回测的成交
    """
    DIRECTION_CHOICES = [
        ('BUY', '买入'),
        ('SELL', '卖出'),
    ]
    
    ORDER_TYPE_CHOICES = [
        ('MARKET', '市价单'),
        ('LIMIT', '限价单'),
    ]
    
    strategy_name = models.CharField(max_length=50, db_index=True, verbose_name='策略名称')
    symbol = models.CharField(max_length=20, db_index=True, verbose_name='代码')
    exchange = models.CharField(max_length=20, default='', blank=True, verbose_name='交易所')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, verbose_name='方向')
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES, default='MARKET', verbose_name='订单类型')
    price = models.DecimalField(max_digits=20, decimal_places=8, verbose_name='成交价格')
    quantity = models.DecimalField(max_digits=20, decimal_places=8, verbose_name='成交数量')
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=0, verbose_name='手续费')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='成交时间')
    is_backtest = models.BooleanField(default=False, db_index=True, verbose_name='是否回测')
    
    # 关联信息
    backtest_id = models.CharField(max_length=50, blank=True, null=True, verbose_name='回测ID')
    order_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='订单ID')
    
    # 备注
    remark = models.TextField(blank=True, null=True, verbose_name='备注')
    
    class Meta:
        db_table = 'trade_records'
        verbose_name = '交易记录'
        verbose_name_plural = '交易记录'
        ordering = ['-timestamp']
        indexes = [
            Index(fields=['strategy_name', 'timestamp']),
            Index(fields=['symbol', 'timestamp']),
            Index(fields=['is_backtest', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.strategy_name} - {self.direction} {self.quantity}@{self.price} ({'回测' if self.is_backtest else '实盘'})"


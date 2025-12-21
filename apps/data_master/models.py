from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Index


class Instrument(models.Model):
    MARKET_CHOICES = [
        ('US', '美股'),
        ('CN', 'A股'),
    ]
    TRADING_RULE_CHOICES = [
        ('T+0', 'T+0'),
        ('T+1', 'T+1'),
    ]

    symbol = models.CharField(max_length=20, unique=True, verbose_name='代码')
    market = models.CharField(max_length=2, choices=MARKET_CHOICES, verbose_name='市场')
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


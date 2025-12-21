from django.db import models
from django.core.validators import MinValueValidator


class Instrument(models.Model):
    """标的模型：股票、ETF等"""
    MARKET_CHOICES = [
        ('US', '美股'),
        ('CN', 'A股'),
    ]
    
    symbol = models.CharField(max_length=20, unique=True, verbose_name='代码')
    market = models.CharField(max_length=2, choices=MARKET_CHOICES, verbose_name='市场')
    name = models.CharField(max_length=100, verbose_name='名称')
    category = models.CharField(max_length=50, blank=True, null=True, verbose_name='行业分类')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'instruments'
        verbose_name = '标的'
        verbose_name_plural = '标的'
        ordering = ['symbol']
    
    def __str__(self):
        return f"{self.symbol} ({self.name})"


class Candle(models.Model):
    """K线数据模型"""
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name='candles',
        verbose_name='标的'
    )
    date = models.DateField(verbose_name='日期')
    open = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        verbose_name='开盘价'
    )
    high = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        verbose_name='最高价'
    )
    low = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        verbose_name='最低价'
    )
    close = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        verbose_name='收盘价'
    )
    volume = models.BigIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='成交量'
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='成交额'
    )
    turnover = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='换手率(%)'
    )
    
    class Meta:
        db_table = 'candles'
        verbose_name = 'K线数据'
        verbose_name_plural = 'K线数据'
        unique_together = [['instrument', 'date']]
        indexes = [
            models.Index(fields=['instrument', 'date']),
            models.Index(fields=['date']),
        ]
        ordering = ['instrument', 'date']
    
    def __str__(self):
        return f"{self.instrument.symbol} - {self.date}"


class CandleMinute(models.Model):
    """分钟K线数据模型"""
    INTERVAL_CHOICES = [
        ('1m', '1分钟'),
        ('5m', '5分钟'),
        ('15m', '15分钟'),
        ('30m', '30分钟'),
        ('60m', '60分钟'),
    ]
    
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name='minute_candles',
        verbose_name='标的'
    )
    datetime = models.DateTimeField(verbose_name='日期时间')
    interval = models.CharField(max_length=5, choices=INTERVAL_CHOICES, default='1m', verbose_name='时间间隔')
    open = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        verbose_name='开盘价'
    )
    high = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        verbose_name='最高价'
    )
    low = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        verbose_name='最低价'
    )
    close = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        verbose_name='收盘价'
    )
    volume = models.BigIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='成交量'
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='成交额'
    )
    
    class Meta:
        db_table = 'candles_minute'
        verbose_name = '分钟K线数据'
        verbose_name_plural = '分钟K线数据'
        unique_together = [['instrument', 'datetime', 'interval']]
        indexes = [
            models.Index(fields=['instrument', 'datetime', 'interval']),
            models.Index(fields=['datetime']),
        ]
        ordering = ['instrument', 'datetime']
    
    def __str__(self):
        return f"{self.instrument.symbol} - {self.datetime} ({self.interval})"


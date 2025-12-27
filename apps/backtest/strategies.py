"""
交易策略库
包含多种常用的量化交易策略
"""
import backtrader as bt
import numpy as np
import pandas as pd


class MACrossStrategy(bt.Strategy):
    """
    双均线策略
    当短期均线上穿长期均线时买入，下穿时卖出
    
    参数:
        fast_period: 短期均线周期（默认5）
        slow_period: 长期均线周期（默认20）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('fast_period', 5),
        ('slow_period', 20),
        ('printlog', False),
    )
    
    def __init__(self):
        self.fast_ma = bt.indicators.SMA(
            self.data.close,
            period=self.params.fast_period
        )
        self.slow_ma = bt.indicators.SMA(
            self.data.close,
            period=self.params.slow_period
        )
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        
        self.order = None
        self.buyprice = None
        self.buycomm = None
        
        # 记录资产价值变化（用于绘制收益曲线）
        # 使用 object.__setattr__ 避免 Backtrader 将其当作 lines 属性
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])  # 记录交易时点
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')
        
        self.order = None
    
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'交易利润, 净利润: {trade.pnlcomm:.2f}')
    
    def next(self):
        # 记录每个时间点的资产价值
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        # 跳过前几个周期，等待指标稳定
        # CrossOver指标需要至少slow_period+1个数据点才能产生信号
        if len(self.data) < self.params.slow_period + 1:
            return
        
        if self.order:
            return
        
        # 检查CrossOver指标是否有有效值（不是NaN）
        try:
            crossover_value = self.crossover[0]
            if pd.isna(crossover_value):
                return
        except (IndexError, TypeError):
            return
        
        if not self.position:
            # 买入信号：快线上穿慢线（crossover > 0）
            if crossover_value > 0:
                self.log(f'买入信号: 快线={self.fast_ma[0]:.2f}, 慢线={self.slow_ma[0]:.2f}, crossover={crossover_value}')
                self.order = self.buy()
        else:
            # 卖出信号：快线下穿慢线（crossover < 0）
            if crossover_value < 0:
                self.log(f'卖出信号: 快线={self.fast_ma[0]:.2f}, 慢线={self.slow_ma[0]:.2f}, crossover={crossover_value}')
                self.order = self.sell()
    
    def stop(self):
        self.log(f'(快线={self.params.fast_period}, 慢线={self.params.slow_period}) 期末总价值: {self.broker.getvalue():.2f}')


class MACDStrategy(bt.Strategy):
    """
    MACD策略
    当MACD线上穿信号线时买入，下穿时卖出
    
    参数:
        fast_period: 快速EMA周期（默认12）
        slow_period: 慢速EMA周期（默认26）
        signal_period: 信号线周期（默认9）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
        ('printlog', False),
    )
    
    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast_period,
            period_me2=self.params.slow_period,
            period_signal=self.params.signal_period
        )
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
        
        self.order = None
        self.buyprice = None
        # 使用 object.__setattr__ 避免 Backtrader 将其当作 lines 属性
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])  # 记录交易时点
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}')
                self.buyprice = order.executed.price
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        
        self.order = None
    
    def next(self):
        # 记录每个时间点的资产价值
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        # 跳过前几个周期，等待MACD指标稳定
        # MACD需要至少 slow_period + signal_period 个数据点
        min_period = self.params.slow_period + self.params.signal_period
        if len(self.data) < min_period + 1:  # +1 因为CrossOver需要额外一个数据点
            return
        
        if self.order:
            return
        
        # 检查CrossOver指标是否有有效值（不是NaN）
        try:
            crossover_value = self.crossover[0]
            if pd.isna(crossover_value):
                return
        except (IndexError, TypeError):
            return
        
        if not self.position:
            # 买入信号：MACD线上穿信号线（crossover > 0）
            if crossover_value > 0:
                self.log(f'买入信号: MACD={self.macd.macd[0]:.2f}, Signal={self.macd.signal[0]:.2f}, crossover={crossover_value}')
                self.order = self.buy()
        else:
            # 卖出信号：MACD线下穿信号线（crossover < 0）
            if crossover_value < 0:
                self.log(f'卖出信号: MACD={self.macd.macd[0]:.2f}, Signal={self.macd.signal[0]:.2f}, crossover={crossover_value}')
                self.order = self.sell()
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


class RSIStrategy(bt.Strategy):
    """
    RSI策略
    RSI低于超卖线时买入，高于超买线时卖出
    
    参数:
        period: RSI周期（默认14）
        oversold: 超卖阈值（默认30）
        overbought: 超买阈值（默认70）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('period', 14),
        ('oversold', 30),
        ('overbought', 70),
        ('printlog', False),
    )
    
    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.period)
        self.order = None
        # 使用 object.__setattr__ 避免 Backtrader 将其当作 lines 属性
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])  # 记录交易时点
        object.__setattr__(self, 'trade_points', [])  # 记录交易时点
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}, RSI: {self.rsi[0]:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}, RSI: {self.rsi[0]:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        
        self.order = None
    
    def next(self):
        # 记录每个时间点的资产价值
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        # 跳过前几个周期，等待RSI指标稳定
        # RSI需要至少period个数据点
        if len(self.data) < self.params.period + 1:
            return
        
        if self.order:
            return
        
        # 检查RSI指标是否有有效值（不是NaN）
        try:
            rsi_value = self.rsi[0]
            if pd.isna(rsi_value):
                return
        except (IndexError, TypeError):
            return
        
        if not self.position:
            if rsi_value < self.params.oversold:
                self.log(f'买入信号: RSI={rsi_value:.2f} < {self.params.oversold}')
                self.order = self.buy()
        else:
            if rsi_value > self.params.overbought:
                self.log(f'卖出信号: RSI={rsi_value:.2f} > {self.params.overbought}')
                self.order = self.sell()
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


class BollingerBandsStrategy(bt.Strategy):
    """
    布林带策略
    价格触及下轨时买入，触及上轨时卖出
    
    参数:
        period: 布林带周期（默认20）
        devfactor: 标准差倍数（默认2.0）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('period', 20),
        ('devfactor', 2.0),
        ('printlog', False),
    )
    
    def __init__(self):
        self.bollinger = bt.indicators.BollingerBands(
            self.data.close,
            period=self.params.period,
            devfactor=self.params.devfactor
        )
        self.order = None
        # 使用 object.__setattr__ 避免 Backtrader 将其当作 lines 属性
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])  # 记录交易时点
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        
        self.order = None
    
    def next(self):
        # 记录每个时间点的资产价值
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        if self.order:
            return
        
        if not self.position:
            if self.data.close[0] < self.bollinger.lines.bot[0]:
                self.log(f'买入信号: 价格={self.data.close[0]:.2f} < 下轨={self.bollinger.lines.bot[0]:.2f}')
                self.order = self.buy()
        else:
            if self.data.close[0] > self.bollinger.lines.top[0]:
                self.log(f'卖出信号: 价格={self.data.close[0]:.2f} > 上轨={self.bollinger.lines.top[0]:.2f}')
                self.order = self.sell()
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


class TripleMAStrategy(bt.Strategy):
    """
    三均线策略
    短期均线 > 中期均线 > 长期均线时买入，反之卖出
    
    参数:
        fast_period: 短期均线周期（默认5）
        mid_period: 中期均线周期（默认10）
        slow_period: 长期均线周期（默认20）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('fast_period', 5),
        ('mid_period', 10),
        ('slow_period', 20),
        ('printlog', False),
    )
    
    def __init__(self):
        self.fast_ma = bt.indicators.SMA(self.data.close, period=self.params.fast_period)
        self.mid_ma = bt.indicators.SMA(self.data.close, period=self.params.mid_period)
        self.slow_ma = bt.indicators.SMA(self.data.close, period=self.params.slow_period)
        self.order = None
        # 使用 object.__setattr__ 避免 Backtrader 将其当作 lines 属性
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])  # 记录交易时点
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        
        self.order = None
    
    def next(self):
        # 记录每个时间点的资产价值
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        if self.order:
            return
        
        fast = self.fast_ma[0]
        mid = self.mid_ma[0]
        slow = self.slow_ma[0]
        
        if not self.position:
            # 买入条件：快线 > 中线 > 慢线
            if fast > mid > slow:
                self.log(f'买入信号: 快线={fast:.2f} > 中线={mid:.2f} > 慢线={slow:.2f}')
                self.order = self.buy()
        else:
            # 卖出条件：快线 < 中线 或 中线 < 慢线
            if fast < mid or mid < slow:
                self.log(f'卖出信号: 快线={fast:.2f}, 中线={mid:.2f}, 慢线={slow:.2f}')
                self.order = self.sell()
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


class MeanReversionStrategy(bt.Strategy):
    """
    均值回归策略
    当价格偏离均线一定比例时买入/卖出
    
    参数:
        period: 均线周期（默认20）
        threshold: 偏离阈值（默认0.02，即2%）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('period', 20),
        ('threshold', 0.02),
        ('printlog', False),
    )
    
    def __init__(self):
        self.ma = bt.indicators.SMA(self.data.close, period=self.params.period)
        self.order = None
        # 使用 object.__setattr__ 避免 Backtrader 将其当作 lines 属性
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])  # 记录交易时点
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        
        self.order = None
    
    def next(self):
        # 记录每个时间点的资产价值
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        if self.order:
            return
        
        price = self.data.close[0]
        ma_value = self.ma[0]
        deviation = (price - ma_value) / ma_value if ma_value > 0 else 0
        
        if not self.position:
            # 价格低于均线一定比例时买入
            if deviation < -self.params.threshold:
                self.log(f'买入信号: 价格={price:.2f}, 均线={ma_value:.2f}, 偏离={deviation*100:.2f}%')
                self.order = self.buy()
        else:
            # 价格回归到均线以上一定比例时卖出
            if deviation > self.params.threshold:
                self.log(f'卖出信号: 价格={price:.2f}, 均线={ma_value:.2f}, 偏离={deviation*100:.2f}%')
                self.order = self.sell()
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


class VCPStrategy(bt.Strategy):
    """
    VCP波动收缩模式策略（Mark Minervini方法）
    识别价格波动逐渐收缩、成交量减少的形态，在突破时买入
    右侧交易策略，等待趋势确认后入场
    
    参数:
        lookback: 回看周期用于计算波动率（默认20）
        contraction_ratio: 波动收缩比例阈值（默认0.7，表示当前波动小于历史波动的70%）
        volume_ratio: 成交量收缩比例（默认0.8，表示当前成交量小于历史均量的80%）
        breakout_threshold: 突破阈值（默认1.02，表示价格突破前高的2%）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('lookback', 20),
        ('contraction_ratio', 0.7),
        ('volume_ratio', 0.8),
        ('breakout_threshold', 1.02),
        ('printlog', False),
    )
    
    def __init__(self):
        # 计算ATR（平均真实波幅）来衡量波动率
        self.atr = bt.indicators.ATR(self.data, period=self.params.lookback)
        # 计算ATR的移动平均，用于比较当前波动率与历史平均波动率
        self.atr_sma = bt.indicators.SMA(self.atr, period=self.params.lookback)
        self.sma_volume = bt.indicators.SMA(self.data.volume, period=self.params.lookback)
        
        # 记录最高价用于判断突破
        self.highest = bt.indicators.Highest(self.data.high, period=self.params.lookback)
        
        self.order = None
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        
        self.order = None
    
    def next(self):
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        if self.order:
            return
        
        # 需要足够的历史数据
        # ATR 需要至少 lookback 个数据点才能计算
        # 我们需要 lookback * 2 个数据点来比较当前和历史 ATR
        if len(self.data) < self.params.lookback * 2:
            return
        
        # 检查指标是否有有效值（避免访问未计算的指标值）
        try:
            # 获取指标值并转换为 Python 数值类型，避免 LineOwnOperation 对象
            current_price = float(self.data.close[0])
            current_atr = float(self.atr[0])
            current_volume = float(self.data.volume[0])
            avg_volume = float(self.sma_volume[0])
            recent_high = float(self.highest[0])
            avg_atr = float(self.atr_sma[0])  # ATR的移动平均，代表历史平均波动率
            
            # 检查是否有 NaN 或无效值
            if (pd.isna(current_atr) or pd.isna(avg_volume) or pd.isna(avg_atr) or
                current_atr <= 0 or avg_volume <= 0 or avg_atr <= 0):
                return
        except (IndexError, TypeError, AttributeError, ValueError):
            return
        
        # 计算波动率收缩：当前ATR小于历史平均ATR的收缩比例
        # 使用 ATR 的移动平均作为历史基准，这样更安全且符合回测逻辑
        try:
            # 当前波动率小于历史平均波动率的收缩比例
            volatility_contracted = current_atr < (avg_atr * self.params.contraction_ratio)
        except (IndexError, TypeError, AttributeError):
            volatility_contracted = False
        
        # 成交量收缩：当前成交量小于平均成交量的比例
        volume_contracted = current_volume < (avg_volume * self.params.volume_ratio) if avg_volume > 0 else False
        
        # 突破判断：价格突破近期高点
        price_breakout = current_price > (recent_high * self.params.breakout_threshold)
        
        if not self.position:
            # VCP买入条件：波动收缩 + 成交量收缩 + 价格突破
            if volatility_contracted and volume_contracted and price_breakout:
                self.log(f'VCP买入信号: 价格={current_price:.2f}, 突破高点={recent_high:.2f}, ATR={current_atr:.2f}')
                self.order = self.buy()
        else:
            # 卖出条件：价格跌破买入价的8%或跌破近期低点
            try:
                if len(self.data) >= self.params.lookback:
                    recent_low = bt.indicators.Lowest(self.data.low, period=self.params.lookback)[0]
                    # 不要直接使用 if recent_low，而是检查数值是否有效
                    # 在 Backtrader 中，直接对指标值进行布尔判断会触发 __bool__ 错误
                    if not pd.isna(recent_low) and recent_low > 0:
                        stop_loss = current_price < (self.position.price * 0.92)  # 8%止损
                        break_down = current_price < (recent_low * 0.98)
                        
                        if stop_loss or break_down:
                            self.log(f'VCP卖出信号: 价格={current_price:.2f}, 买入价={self.position.price:.2f}')
                            self.order = self.sell()
                    else:
                        # 如果 recent_low 无效，只使用止损
                        if current_price < (self.position.price * 0.92):
                            self.log(f'VCP止损卖出: 价格={current_price:.2f}, 买入价={self.position.price:.2f}')
                            self.order = self.sell()
            except (IndexError, TypeError, AttributeError):
                # 如果计算失败，只使用止损
                if current_price < (self.position.price * 0.92):
                    self.log(f'VCP止损卖出: 价格={current_price:.2f}, 买入价={self.position.price:.2f}')
                    self.order = self.sell()
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


class CandlestickStrategy(bt.Strategy):
    """
    蜡烛图形态交易策略
    识别常见的蜡烛图形态（锤子线、吞没形态、十字星等）进行交易
    
    参数:
        pattern_type: 形态类型 ('hammer', 'engulfing', 'doji', 'all')
        confirmation_period: 确认周期（默认2，形态出现后确认的天数）
        min_body_ratio: 最小实体比例（默认0.3）
        min_shadow_ratio: 最小影线比例（默认2.0）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('pattern_type', 'all'),  # 'hammer', 'engulfing', 'doji', 'all'
        ('confirmation_period', 2),
        ('min_body_ratio', 0.3),
        ('min_shadow_ratio', 2.0),
        ('printlog', False),
    )
    
    def __init__(self):
        self.order = None
        self.pattern_detected = 0  # 记录检测到的形态日期
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])
    
    def detect_pattern(self):
        """检测蜡烛图形态"""
        # 需要至少2个数据点才能检测形态
        if len(self.data) < 2:
            return None
        
        try:
            # 获取当前和前一日的OHLC
            # 在Backtrader中，[0]是当前数据点，[-1]或(ago=1)是前一个数据点
            open0 = self.data.open[0]
            close0 = self.data.close[0]
            high0 = self.data.high[0]
            low0 = self.data.low[0]
            
            # 安全访问前一日数据 - 使用负索引或 ago 参数
            try:
                # 优先使用 ago 参数（更安全）
                open1 = self.data.open(-1)
                close1 = self.data.close(-1)
                high1 = self.data.high(-1)
                low1 = self.data.low(-1)
            except (IndexError, TypeError):
                # 如果 ago 失败，尝试使用负索引
                try:
                    if len(self.data) >= 2:
                        open1 = self.data.open[-1]
                        close1 = self.data.close[-1]
                        high1 = self.data.high[-1]
                        low1 = self.data.low[-1]
                    else:
                        return None
                except (IndexError, TypeError):
                    # 如果都无法访问，返回None
                    return None
        except (IndexError, TypeError, AttributeError):
            return None
        
        body0 = abs(close0 - open0)
        body1 = abs(close1 - open1)
        range0 = high0 - low0
        range1 = high1 - low1
        
        patterns = []
        
        # 1. 锤子线（Hammer）或上吊线
        if range0 > 0:
            upper_shadow = high0 - max(open0, close0)
            lower_shadow = min(open0, close0) - low0
            body_ratio = body0 / range0 if range0 > 0 else 0
            
            # 锤子线：下影线是实体的2倍以上，上影线很小，出现在下跌趋势中
            if (lower_shadow >= body0 * self.params.min_shadow_ratio and 
                upper_shadow <= body0 * 0.5 and 
                body_ratio < self.params.min_body_ratio):
                if close1 > open1:  # 前一日是阳线，可能是反转信号
                    patterns.append('bullish_hammer')
                else:
                    patterns.append('bearish_hammer')
        
        # 2. 吞没形态（Engulfing）
        if len(self.data) >= 2:
            # 看涨吞没：前一日阴线，当前阳线完全包裹前一日
            if (close1 < open1 and close0 > open0 and 
                open0 < close1 and close0 > open1):
                patterns.append('bullish_engulfing')
            
            # 看跌吞没：前一日阳线，当前阴线完全包裹前一日
            if (close1 > open1 and close0 < open0 and 
                open0 > close1 and close0 < open1):
                patterns.append('bearish_engulfing')
        
        # 3. 十字星（Doji）
        if range0 > 0:
            body_ratio = body0 / range0
            if body_ratio < 0.1:  # 实体很小，类似十字星
                patterns.append('doji')
        
        return patterns[0] if patterns else None
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        
        self.order = None
    
    def next(self):
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        if self.order:
            return
        
        # 检测蜡烛图形态
        pattern = self.detect_pattern()
        
        if not self.position:
            # 买入信号：看涨形态
            if pattern and pattern in ['bullish_hammer', 'bullish_engulfing', 'doji']:
                if self.params.pattern_type == 'all' or pattern.startswith(self.params.pattern_type):
                    # 等待确认：需要足够的数据点
                    try:
                        # 确保有足够的历史数据
                        if len(self.data) > self.params.confirmation_period:
                            # 在 Backtrader 中，使用 ago 参数访问历史数据
                            # ago=1 表示前一个数据点，ago=2 表示前两个数据点
                            try:
                                # 使用 ago 参数访问 confirmation_period 个周期前的数据
                                prev_close = self.data.close(-self.params.confirmation_period)
                            except (IndexError, TypeError):
                                # 如果 ago 参数失败，尝试使用负索引
                                # 但需要确保数据足够
                                if len(self.data) > self.params.confirmation_period:
                                    try:
                                        prev_close = self.data.close[-self.params.confirmation_period]
                                    except (IndexError, TypeError):
                                        return  # 数据不足，跳过
                                else:
                                    return  # 数据不足，跳过
                            
                            # 比较当前价格和历史价格
                            if self.data.close[0] > prev_close:
                                self.log(f'蜡烛图买入信号: {pattern}, 价格={self.data.close[0]:.2f}')
                                self.order = self.buy()
                    except (IndexError, TypeError, AttributeError):
                        # 如果访问历史数据失败，跳过本次交易
                        pass
        else:
            # 卖出信号：看跌形态或止损
            if pattern and pattern in ['bearish_hammer', 'bearish_engulfing']:
                self.log(f'蜡烛图卖出信号: {pattern}, 价格={self.data.close[0]:.2f}')
                self.order = self.sell()
            elif self.position:
                # 止损：亏损超过5%
                if self.data.close[0] < (self.position.price * 0.95):
                    self.log(f'止损卖出: 价格={self.data.close[0]:.2f}, 买入价={self.position.price:.2f}')
                    self.order = self.sell()
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


class SwingTradingStrategy(bt.Strategy):
    """
    波段交易策略
    在上升趋势中，等待价格回调至支撑位买入，在阻力位卖出
    适合中短期交易
    
    参数:
        trend_period: 趋势判断周期（默认20）
        swing_period: 波段周期（默认10）
        pullback_ratio: 回调比例（默认0.05，表示回调5%时买入）
        profit_target: 盈利目标（默认0.10，表示盈利10%时卖出）
        stop_loss: 止损比例（默认0.05，表示亏损5%时止损）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('trend_period', 20),
        ('swing_period', 10),
        ('pullback_ratio', 0.05),
        ('profit_target', 0.10),
        ('stop_loss', 0.05),
        ('printlog', False),
    )
    
    def __init__(self):
        # 趋势指标
        self.sma_fast = bt.indicators.SMA(self.data.close, period=10)
        self.sma_slow = bt.indicators.SMA(self.data.close, period=self.params.trend_period)
        
        # 波段高点和低点
        self.swing_high = bt.indicators.Highest(self.data.high, period=self.params.swing_period)
        self.swing_low = bt.indicators.Lowest(self.data.low, period=self.params.swing_period)
        
        self.order = None
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        
        self.order = None
    
    def next(self):
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        if self.order:
            return
        
        if len(self.data) < self.params.trend_period:
            return
        
        current_price = self.data.close[0]
        
        # 判断趋势：快线上穿慢线为上升趋势
        uptrend = self.sma_fast[0] > self.sma_slow[0]
        
        if not self.position:
            # 买入条件：上升趋势 + 价格回调至支撑位
            if uptrend:
                swing_low_price = self.swing_low[0]
                # 价格从波段高点回调一定比例
                try:
                    if len(self.data) >= self.params.swing_period + 1:
                        # 使用正索引访问历史数据，确保索引有效
                        max_idx = min(self.params.swing_period + 1, len(self.data))
                        recent_high = max([self.data.high[i] for i in range(1, max_idx) if i < len(self.data)])
                        pullback = (recent_high - current_price) / recent_high if recent_high > 0 else 0
                    else:
                        pullback = 0
                except (IndexError, TypeError, ValueError):
                    pullback = 0
                    
                    # 价格接近波段低点或回调达到阈值
                    if (current_price <= swing_low_price * 1.02 or 
                        pullback >= self.params.pullback_ratio):
                        self.log(f'波段买入信号: 价格={current_price:.2f}, 波段低点={swing_low_price:.2f}, 回调={pullback*100:.2f}%')
                        self.order = self.buy()
        else:
            # 卖出条件：达到盈利目标、止损或趋势反转
            buy_price = self.position.price
            profit_pct = (current_price - buy_price) / buy_price if buy_price > 0 else 0
            
            # 盈利目标
            if profit_pct >= self.params.profit_target:
                self.log(f'波段盈利卖出: 价格={current_price:.2f}, 盈利={profit_pct*100:.2f}%')
                self.order = self.sell()
            # 止损
            elif profit_pct <= -self.params.stop_loss:
                self.log(f'波段止损卖出: 价格={current_price:.2f}, 亏损={profit_pct*100:.2f}%')
                self.order = self.sell()
            # 趋势反转
            elif not uptrend:
                self.log(f'波段趋势反转卖出: 价格={current_price:.2f}')
                self.order = self.sell()
            # 达到波段高点
            elif current_price >= self.swing_high[0] * 0.98:
                self.log(f'波段高点卖出: 价格={current_price:.2f}, 波段高点={self.swing_high[0]:.2f}')
                self.order = self.sell()
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


class TrendFollowingStrategy(bt.Strategy):
    """
    趋势跟踪策略（右侧交易）
    等待趋势确认后入场，跟随趋势进行交易，避免左侧交易的逆势风险
    
    参数:
        fast_period: 快线周期（默认10）
        slow_period: 慢线周期（默认30）
        adx_period: ADX周期（默认14，用于确认趋势强度）
        adx_threshold: ADX阈值（默认25，ADX高于此值认为趋势强劲）
        trailing_stop: 追踪止损比例（默认0.03，表示3%）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
        ('adx_period', 14),
        ('adx_threshold', 25),
        ('trailing_stop', 0.03),
        ('printlog', False),
    )
    
    def __init__(self):
        # 趋势指标
        self.sma_fast = bt.indicators.SMA(self.data.close, period=self.params.fast_period)
        self.sma_slow = bt.indicators.SMA(self.data.close, period=self.params.slow_period)
        
        # ADX指标确认趋势强度
        self.adx = bt.indicators.ADX(self.data, period=self.params.adx_period)
        
        # 追踪止损
        self.highest_price = None
        
        self.order = None
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}')
                self.highest_price = order.executed.price
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}')
                self.highest_price = None
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
        
        self.order = None
    
    def next(self):
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        if self.order:
            return
        
        if len(self.data) < self.params.slow_period:
            return
        
        current_price = self.data.close[0]
        
        # 趋势确认：快线上穿慢线 + ADX确认趋势强度
        trend_up = self.sma_fast[0] > self.sma_slow[0]
        trend_strong = self.adx.lines.adx[0] > self.params.adx_threshold
        
        if not self.position:
            # 右侧买入：等待趋势确认后入场
            if trend_up and trend_strong:
                # 确认突破：价格站上快线
                if current_price > self.sma_fast[0]:
                    self.log(f'趋势跟踪买入: 价格={current_price:.2f}, ADX={self.adx.lines.adx[0]:.2f}')
                    self.order = self.buy()
        else:
            # 更新最高价（用于追踪止损）
            if self.highest_price is None:
                self.highest_price = current_price
            else:
                self.highest_price = max(self.highest_price, current_price)
            
            # 卖出条件：趋势反转或追踪止损
            # 1. 趋势反转：快线下穿慢线
            if not trend_up:
                self.log(f'趋势反转卖出: 价格={current_price:.2f}')
                self.order = self.sell()
            # 2. 追踪止损：从最高点回撤超过阈值
            elif self.highest_price and current_price < (self.highest_price * (1 - self.params.trailing_stop)):
                self.log(f'追踪止损卖出: 价格={current_price:.2f}, 最高价={self.highest_price:.2f}')
                self.order = self.sell()
            # 3. 趋势减弱：ADX下降
            elif self.adx.lines.adx[0] < (self.params.adx_threshold * 0.8):
                self.log(f'趋势减弱卖出: 价格={current_price:.2f}, ADX={self.adx.lines.adx[0]:.2f}')
                self.order = self.sell()
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


class PyramidAddStrategy(bt.Strategy):
    """
    金字塔加仓策略（让利润奔跑，截断止损）
    
    核心逻辑：
    1. 开仓条件：大盘情绪不错（价格在均线之上）+ ETF高开（开盘价 > 前一天收盘价 * (1 + high_open_threshold)）
    2. 初始仓位：5%
    3. 止损：-2%（相对于开仓价格），浮亏绝不加仓
    4. 加仓：价格较上一开仓点位上涨+2%就加仓（盈利后才加仓）
    5. 让利润奔跑，及时止损
    
    参数:
        initial_position_size: 初始仓位比例（默认0.05，即5%）
        stop_loss_pct: 止损百分比（默认0.02，即2%）
        add_position_threshold: 加仓阈值（默认0.02，即2%）
        ma_period: 均线周期，用于判断大盘情绪（默认20）
        high_open_threshold: 高开阈值（默认0.01，即1%）
        printlog: 是否打印日志（默认False）
    """
    params = (
        ('initial_position_size', 0.05),  # 5%初始仓位
        ('stop_loss_pct', 0.02),  # 2%止损
        ('add_position_threshold', 0.02),  # 2%加仓阈值
        ('ma_period', 20),  # 均线周期
        ('high_open_threshold', 0.01),  # 1%高开阈值
        ('printlog', False),
    )
    
    def __init__(self):
        # 均线指标，用于判断大盘情绪
        self.ma = bt.indicators.SMA(
            self.data.close,
            period=self.params.ma_period
        )
        
        self.order = None
        self.buyprice = None
        self.buycomm = None
        
        # 记录所有开仓点位（用于加仓判断）
        self.entry_prices = []  # 所有开仓价格
        self.entry_sizes = []  # 所有开仓仓位（占总资金的比例）
        
        # 追踪止损：记录持仓期间的最高价格
        self.highest_price = None  # 持仓期间的最高价格
        
        # 记录资产价值变化（用于绘制收益曲线）
        object.__setattr__(self, 'equity_curve', [])
        object.__setattr__(self, 'trade_points', [])
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
            date_str = current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date)
            trade_points = object.__getattribute__(self, 'trade_points')
            
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}, 数量: {order.executed.size}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
                
                # 记录开仓点位
                self.entry_prices.append(float(order.executed.price))
                position_value = float(order.executed.price * order.executed.size)
                total_value = float(self.broker.getvalue())
                position_size = position_value / total_value if total_value > 0 else 0
                self.entry_sizes.append(position_size)
                
                trade_points.append({
                    'date': date_str,
                    'type': 'buy',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}, 数量: {order.executed.size}')
                trade_points.append({
                    'date': date_str,
                    'type': 'sell',
                    'price': float(order.executed.price),
                    'value': float(self.broker.getvalue())
                })
                
                # 清仓时重置开仓点位和最高价
                if not self.position:
                    self.entry_prices = []
                    self.entry_sizes = []
                    self.highest_price = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')
        
        self.order = None
    
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'交易利润, 净利润: {trade.pnlcomm:.2f}')
    
    def next(self):
        # 记录每个时间点的资产价值
        current_value = self.broker.getvalue()
        current_date = self.datas[0].datetime.date(0) if hasattr(self.datas[0].datetime, 'date') else self.datas[0].datetime.datetime(0)
        equity_curve = object.__getattribute__(self, 'equity_curve')
        equity_curve.append({
            'date': current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
            'value': current_value,
            'return_pct': ((current_value - self.broker.startingcash) / self.broker.startingcash) * 100
        })
        
        # 需要足够的数据才能计算均线
        if len(self.data) < self.params.ma_period + 1:
            return
        
        if self.order:
            return
        
        current_price = self.data.close[0]
        current_open = self.data.open[0]
        prev_close = self.data.close[-1] if len(self.data) > 1 else current_price
        
        # 判断大盘情绪：价格在均线之上
        market_sentiment_good = current_price > self.ma[0]
        
        # 判断是否高开：开盘价 > 前一天收盘价 * (1 + high_open_threshold)
        high_open = current_open > prev_close * (1 + self.params.high_open_threshold)
        
        if not self.position:
            # 没有持仓时，检查开仓条件
            if market_sentiment_good and high_open:
                # 计算初始仓位（5%）
                total_value = self.broker.getvalue()
                position_value = total_value * self.params.initial_position_size
                size = int(position_value / current_price)
                
                if size > 0:
                    self.log(f'开仓: 价格={current_price:.2f}, 仓位={self.params.initial_position_size*100:.1f}%, 数量={size}')
                    self.order = self.buy(size=size)
        else:
            # 有持仓时，检查止损和加仓
            if self.entry_prices:
                # 获取初始开仓价格（用于保底止损判断）
                initial_entry_price = self.entry_prices[0]
                # 获取最新的开仓价格（用于加仓判断）
                latest_entry_price = self.entry_prices[-1]
                
                # 更新持仓期间的最高价格（用于追踪止损）
                if self.highest_price is None:
                    self.highest_price = current_price
                else:
                    self.highest_price = max(self.highest_price, current_price)
                
                # 获取当前持仓数量
                position_size = self.position.size
                if position_size <= 0:
                    return
                
                # 1. 优先检查追踪止损：如果价格从最高点回撤超过2%，止损卖出
                # 这是让利润奔跑的关键：基于最高点的回撤止损
                if self.highest_price and current_price < self.highest_price * (1 - self.params.stop_loss_pct):
                    drawdown_pct = (1 - current_price / self.highest_price) * 100
                    self.log(f'追踪止损卖出: 当前价格={current_price:.2f}, 最高价格={self.highest_price:.2f}, 回撤={drawdown_pct:.2f}%, 持仓数量={position_size}, 全部清仓')
                    self.order = self.sell(size=position_size)
                    return
                
                # 2. 保底止损：如果当前价格 < 初始开仓价格 * (1 - stop_loss_pct)，止损卖出
                # 这是防止开仓后立即下跌的保护机制
                if current_price < initial_entry_price * (1 - self.params.stop_loss_pct):
                    loss_pct = (current_price / initial_entry_price - 1) * 100
                    self.log(f'保底止损卖出: 当前价格={current_price:.2f}, 初始开仓价格={initial_entry_price:.2f}, 亏损={loss_pct:.2f}%, 持仓数量={position_size}, 全部清仓')
                    self.order = self.sell(size=position_size)
                    return
                
                # 3. 检查加仓条件：价格较第一次买入价格涨了2%就加仓（盈利后才加仓）
                # 关键：加仓条件是基于第一次买入价格，而不是最新开仓价格
                # 浮亏绝不加仓，所以只检查盈利情况（当前价格 > 第一次买入价格 * (1 + add_position_threshold)）
                if current_price > initial_entry_price * (1 + self.params.add_position_threshold):
                    # 检查是否已经加过仓（避免重复加仓）
                    # 如果当前价格已经比最新开仓价格高2%以上，说明已经加过仓了，需要检查是否还能继续加仓
                    # 但根据用户理解，应该是：如果价格比第一次买入价涨了2%，就加仓5%
                    # 为了避免重复加仓，需要检查：当前价格是否比最新开仓价格高2%以上
                    # 如果已经加过仓，且价格继续上涨，需要等待价格比最新开仓价格再涨2%才能继续加仓
                    
                    # 如果还没有加过仓（只有一次买入），直接加仓
                    if len(self.entry_prices) == 1:
                        # 计算加仓数量（也是5%仓位）
                        total_value = self.broker.getvalue()
                        position_value = total_value * self.params.initial_position_size
                        size = int(position_value / current_price)
                        
                        if size > 0:
                            self.log(f'加仓: 价格={current_price:.2f}, 第一次买入价格={initial_entry_price:.2f}, 涨幅={(current_price/initial_entry_price - 1)*100:.2f}%, 数量={size}')
                            self.order = self.buy(size=size)
                    else:
                        # 如果已经加过仓，需要检查：当前价格是否比最新开仓价格高2%以上
                        # 这样才能继续加仓（每次加仓都是基于上一次加仓价格再涨2%）
                        if current_price > latest_entry_price * (1 + self.params.add_position_threshold):
                            # 计算加仓数量（也是5%仓位）
                            total_value = self.broker.getvalue()
                            position_value = total_value * self.params.initial_position_size
                            size = int(position_value / current_price)
                            
                            if size > 0:
                                self.log(f'继续加仓: 价格={current_price:.2f}, 上一次加仓价格={latest_entry_price:.2f}, 涨幅={(current_price/latest_entry_price - 1)*100:.2f}%, 数量={size}')
                                self.order = self.buy(size=size)
    
    def stop(self):
        self.log(f'期末总价值: {self.broker.getvalue():.2f}')


# 策略注册字典，方便动态调用
STRATEGY_REGISTRY = {
    'macross': MACrossStrategy,
    'macd': MACDStrategy,
    'rsi': RSIStrategy,
    'bollinger': BollingerBandsStrategy,
    'triple_ma': TripleMAStrategy,
    'mean_reversion': MeanReversionStrategy,
    'vcp': VCPStrategy,
    'candlestick': CandlestickStrategy,
    'swing': SwingTradingStrategy,
    'trend_following': TrendFollowingStrategy,
    'pyramid_add': PyramidAddStrategy,
}

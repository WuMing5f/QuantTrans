"""
交易策略定义
"""
import backtrader as bt


class MACrossStrategy(bt.Strategy):
    """
    双均线策略
    当短期均线上穿长期均线时买入，下穿时卖出
    """
    params = (
        ('fast_period', 5),   # 短期均线周期
        ('slow_period', 20),  # 长期均线周期
        ('printlog', False),
    )
    
    def __init__(self):
        # 计算移动平均线
        self.fast_ma = bt.indicators.SMA(
            self.data.close,
            period=self.params.fast_period
        )
        self.slow_ma = bt.indicators.SMA(
            self.data.close,
            period=self.params.slow_period
        )
        
        # 交叉信号
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        
        # 跟踪订单
        self.order = None
        self.buyprice = None
        self.buycomm = None
        
    def log(self, txt, dt=None):
        """日志输出"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
    
    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'买入执行, 价格: {order.executed.price:.2f}, '
                    f'成本: {order.executed.value:.2f}, '
                    f'手续费: {order.executed.comm:.2f}'
                )
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                self.log(
                    f'卖出执行, 价格: {order.executed.price:.2f}, '
                    f'成本: {order.executed.value:.2f}, '
                    f'手续费: {order.executed.comm:.2f}'
                )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')
        
        self.order = None
    
    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return
        self.log(f'交易利润, 毛利润: {trade.pnl:.2f}, 净利润: {trade.pnlcomm:.2f}')
    
    def next(self):
        """策略逻辑"""
        # 如果有未完成的订单，不执行新逻辑
        if self.order:
            return
        
        # 如果没有持仓
        if not self.position:
            # 如果短期均线上穿长期均线，买入
            if self.crossover > 0:
                self.log(f'买入信号: 快线={self.fast_ma[0]:.2f}, 慢线={self.slow_ma[0]:.2f}')
                self.order = self.buy()
        else:
            # 如果持有仓位，且短期均线下穿长期均线，卖出
            if self.crossover < 0:
                self.log(f'卖出信号: 快线={self.fast_ma[0]:.2f}, 慢线={self.slow_ma[0]:.2f}')
                self.order = self.sell()
    
    def stop(self):
        """回测结束"""
        self.log(
            f'快线周期={self.params.fast_period}, 慢线周期={self.params.slow_period}, '
            f'期末资产: {self.broker.getvalue():.2f}',
            dt=self.datas[0].datetime.date(0)
        )


class MACDStrategy(bt.Strategy):
    """
    MACD策略
    当MACD线上穿信号线时买入，下穿时卖出
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
    
    def next(self):
        if self.order:
            return
        
        if not self.position:
            if self.crossover > 0:
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.order = self.sell()


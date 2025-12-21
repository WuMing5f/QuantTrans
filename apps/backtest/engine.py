"""
回测引擎
"""
import backtrader as bt
from datetime import datetime, date
from typing import Dict, Any, Union
import pandas as pd
from apps.data_master.models import Instrument, Candle
from apps.backtest.feeds import DjangoPandasData
from apps.backtest.strategies import MACrossStrategy, MACDStrategy


def run_backtest(
    symbol: str,
    strategy_name: str,
    start_date: Union[str, date],
    end_date: Union[str, date],
    initial_cash: float = 100000.0,
    commission: float = 0.001,  # 0.1% 手续费
    **strategy_params
) -> Dict[str, Any]:
    """
    运行回测
    
    Args:
        symbol: 股票代码
        strategy_name: 策略名称 ('macross' 或 'macd')
        start_date: 开始日期
        end_date: 结束日期
        initial_cash: 初始资金
        commission: 手续费率
        **strategy_params: 策略参数
        
    Returns:
        包含回测结果的字典
    """
    # 转换日期格式
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # 获取标的
    try:
        instrument = Instrument.objects.get(symbol=symbol)
    except Instrument.DoesNotExist:
        raise ValueError(f"Instrument {symbol} not found. Please sync data first.")
    
    # 从数据库查询K线数据
    candles = Candle.objects.filter(
        instrument=instrument,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    if not candles.exists():
        raise ValueError(f"No candle data found for {symbol} in range {start_date} to {end_date}")
    
    # 转换为DataFrame
    data_list = []
    for candle in candles:
        data_list.append({
            'date': candle.date,
            'open': float(candle.open),
            'high': float(candle.high),
            'low': float(candle.low),
            'close': float(candle.close),
            'volume': int(candle.volume),
            'amount': float(candle.amount),
        })
    
    df = pd.DataFrame(data_list)
    df['date'] = pd.to_datetime(df['date'])
    
    # 初始化Cerebro回测引擎
    cerebro = bt.Cerebro()
    
    # 设置初始资金
    cerebro.broker.setcash(initial_cash)
    
    # 设置手续费
    cerebro.broker.setcommission(commission=commission)
    
    # 添加数据源
    data_feed = DjangoPandasData(df)
    cerebro.adddata(data_feed)
    
    # 选择策略
    strategies = {
        'macross': MACrossStrategy,
        'macd': MACDStrategy,
    }
    
    strategy_class = strategies.get(strategy_name.lower())
    if not strategy_class:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(strategies.keys())}")
    
    # 添加策略
    cerebro.addstrategy(strategy_class, **strategy_params)
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    
    # 运行回测
    print(f'开始回测: {symbol}, 策略: {strategy_name}, 初始资金: {initial_cash}')
    results = cerebro.run()
    
    # 获取结果
    strat = results[0]
    final_value = cerebro.broker.getvalue()
    
    # 获取分析结果
    sharpe = strat.analyzers.sharpe.get_analysis()
    returns = strat.analyzers.returns.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    
    # 计算收益率
    total_return = (final_value - initial_cash) / initial_cash * 100
    
    result = {
        'symbol': symbol,
        'strategy': strategy_name,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'initial_cash': initial_cash,
        'final_value': final_value,
        'total_return': total_return,
        'sharpe_ratio': sharpe.get('sharperatio', None),
        'total_return_pct': returns.get('rtot', 0) * 100 if returns.get('rtot') else 0,
        'annual_return_pct': returns.get('rnorm', 0) * 100 if returns.get('rnorm') else 0,
        'max_drawdown': drawdown.get('max', {}).get('drawdown', 0) if drawdown.get('max') else 0,
        'max_drawdown_period': drawdown.get('max', {}).get('len', 0) if drawdown.get('max') else 0,
    }
    
    return result


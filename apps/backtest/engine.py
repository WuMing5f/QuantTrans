"""
回测引擎
"""
import backtrader as bt
from datetime import datetime, date
from typing import Dict, Any, Union
import pandas as pd
from apps.data_master.models import Instrument, Candle
from apps.backtest.feeds import DjangoPandasData
from apps.backtest.strategies import STRATEGY_REGISTRY


def run_backtest(
    symbol: str,
    strategy_name: str,
    start_date: Union[str, date],
    end_date: Union[str, date],
    data_type: str = 'daily',  # 'daily' 或 'minute'
    interval: str = '1m',  # 分钟数据的间隔: '1m', '5m', '15m', '30m', '60m'
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
    # 保存原始日期字符串用于结果返回
    original_start_date = start_date
    original_end_date = end_date
    
    # 转换日期格式（仅对日K数据需要date类型）
    if data_type == 'daily':
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
    if data_type == 'daily':
        # 日K数据
        from apps.data_master.models import Candle
        # 自动过滤未来日期，只使用历史数据
        from datetime import date as date_type
        today = date_type.today()
        
        # 如果结束日期是未来日期，自动调整为今天
        if isinstance(end_date, date_type):
            effective_end_date = min(end_date, today)
            if end_date > today:
                print(f'⚠️ 警告: 结束日期 {end_date} 是未来日期，已自动调整为今天 {today}')
        else:
            # end_date应该已经是date类型（在前面已经转换）
            effective_end_date = end_date if end_date <= today else today
            if end_date > today:
                print(f'⚠️ 警告: 结束日期 {end_date} 是未来日期，已自动调整为今天 {today}')
        
        # 确保effective_end_date是date类型
        if not isinstance(effective_end_date, date_type):
            effective_end_date = today
        
        candles = Candle.objects.filter(
            instrument=instrument,
            date__gte=start_date,
            date__lte=effective_end_date
        ).order_by('date')
        
        # 调试信息：打印实际使用的日期范围
        if candles.exists():
            actual_start = candles.first().date
            actual_end = candles.last().date
            print(f'实际使用的数据范围: {actual_start} 到 {actual_end} (共 {candles.count()} 条)')
        else:
            # 获取标的的数据范围，提供更详细的错误信息
            all_candles = Candle.objects.filter(instrument=instrument).order_by('date')
            if all_candles.exists():
                earliest = all_candles.first().date
                latest = all_candles.last().date
                raise ValueError(
                    f"No daily candle data found for {symbol} in range {start_date} to {end_date}. "
                    f"Available data range: {earliest} to {latest}. "
                    f"Please adjust your date range."
                )
            else:
                raise ValueError(f"No daily candle data found for {symbol}. Please sync data first.")
        
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
    else:
        # 分钟K数据
        from apps.data_master.models import CandleMinute
        from datetime import datetime as dt
        import pytz
        
        # 转换日期为datetime
        if isinstance(start_date, date):
            start_datetime = dt.combine(start_date, dt.min.time())
        else:
            start_datetime = dt.strptime(start_date, '%Y-%m-%d') if isinstance(start_date, str) else start_date
        
        if isinstance(end_date, date):
            end_datetime = dt.combine(end_date, dt.max.time())
        else:
            end_datetime = dt.strptime(end_date, '%Y-%m-%d') if isinstance(end_date, str) else end_date
        
        # 转换为UTC时间（Django存储的是UTC）
        beijing_tz = pytz.timezone('Asia/Shanghai')
        if start_datetime.tzinfo is None:
            start_datetime = beijing_tz.localize(start_datetime).astimezone(pytz.utc)
        if end_datetime.tzinfo is None:
            end_datetime = beijing_tz.localize(end_datetime).astimezone(pytz.utc)
        
        minute_candles = CandleMinute.objects.filter(
            instrument=instrument,
            interval=interval,
            datetime__gte=start_datetime,
            datetime__lte=end_datetime
        ).order_by('datetime')
        
        if not minute_candles.exists():
            raise ValueError(f"No {interval} minute candle data found for {symbol} in range {original_start_date} to {original_end_date}")
        
        # 转换为DataFrame
        data_list = []
        for candle in minute_candles:
            # 转换为本地时间用于显示
            dt_local = candle.datetime.astimezone(beijing_tz) if candle.datetime.tzinfo else candle.datetime
            data_list.append({
                'date': dt_local,
                'open': float(candle.open),
                'high': float(candle.high),
                'low': float(candle.low),
                'close': float(candle.close),
                'volume': int(candle.volume),
                'amount': float(candle.amount),
            })
    
    df = pd.DataFrame(data_list)
    
    # 准备DataFrame：确保索引是DatetimeIndex
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
    elif not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have 'date' column or DatetimeIndex")
    
    # 确保索引是DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # 排序
    df = df.sort_index()
    
    # 初始化Cerebro回测引擎
    cerebro = bt.Cerebro()
    
    # 设置初始资金
    cerebro.broker.setcash(initial_cash)
    
    # 设置手续费
    cerebro.broker.setcommission(commission=commission)
    
    # 设置每次交易的仓位大小（使用百分比sizer，确保按比例买入）
    # 这样可以确保不同初始资金时，交易规模成比例
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)  # 每次使用95%的资金
    
    # 添加数据源 - 直接传递DataFrame给PandasData
    data_feed = DjangoPandasData(dataname=df)
    cerebro.adddata(data_feed)
    
    # 选择策略
    strategy_class = STRATEGY_REGISTRY.get(strategy_name.lower())
    if not strategy_class:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(STRATEGY_REGISTRY.keys())}")
    
    # 添加策略
    cerebro.addstrategy(strategy_class, **strategy_params)
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')  # 交易统计
    
    # 运行回测
    print(f'开始回测: {symbol}, 策略: {strategy_name}, 初始资金: {initial_cash}')
    print(f'数据条数: {len(df)}, 日期范围: {df.index[0]} 到 {df.index[-1]}')
    results = cerebro.run()
    
    # 获取结果
    strat = results[0]
    final_value = cerebro.broker.getvalue()
    
    # 获取分析结果
    sharpe = strat.analyzers.sharpe.get_analysis()
    returns = strat.analyzers.returns.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trades_analysis = strat.analyzers.trades.get_analysis()
    
    # 统计交易信息（正确的方式）
    total_trades = trades_analysis.get('total', {}).get('total', 0) if trades_analysis else 0
    won_trades = trades_analysis.get('won', {}).get('total', 0) if trades_analysis else 0
    lost_trades = trades_analysis.get('lost', {}).get('total', 0) if trades_analysis else 0
    print(f'最终资产: {final_value:.2f}, 交易次数: {total_trades}')
    print(f'交易统计: 总交易={total_trades}, 盈利={won_trades}, 亏损={lost_trades}')
    
    # 如果没有任何交易，打印调试信息
    if total_trades == 0:
        print(f'\n⚠️ 警告: 策略 {strategy_name} 没有产生任何交易！')
        print(f'  - 初始资金: {initial_cash}')
        print(f'  - 最终资金: {final_value}')
        print(f'  - 数据点数: {len(df)}')
        if len(df) > 0:
            print(f'  - 第一个收盘价: {df.iloc[0]["close"]:.2f}')
            print(f'  - 最后一个收盘价: {df.iloc[-1]["close"]:.2f}')
            # 计算最小购买金额
            min_price = df['close'].min()
            max_price = df['close'].max()
            print(f'  - 价格范围: {min_price:.2f} ~ {max_price:.2f}')
            print(f'  - 可购买股数（最低价）: {int(initial_cash * 0.95 / min_price)}')
            
            # 检查日期范围是否合理（不应该选择未来日期）
            today = datetime.now().date()
            first_date = df.index[0].date() if hasattr(df.index[0], 'date') else df.index[0]
            last_date = df.index[-1].date() if hasattr(df.index[-1], 'date') else df.index[-1]
            if last_date > today:
                print(f'  ⚠️ 警告: 数据包含未来日期！最后日期: {last_date}, 今天: {today}')
                print(f'  ⚠️ 建议: 请使用历史日期范围进行回测，例如: 2022-01-01 到 2024-12-20')
            
            # 检查策略参数，判断数据是否足够
            strategy_params_str = ', '.join([f'{k}={v}' for k, v in strategy_params.items()])
            print(f'  - 策略参数: {strategy_params_str}')
            
            # 对于双均线策略，检查数据是否足够
            if strategy_name == 'macross':
                fast_period = strategy_params.get('fast_period', 5)
                slow_period = strategy_params.get('slow_period', 20)
                min_required = slow_period
                print(f'  - 双均线策略需要至少 {min_required} 条数据（slow_period={slow_period}）')
                if len(df) < min_required:
                    print(f'  ❌ 数据不足！只有 {len(df)} 条，需要至少 {min_required} 条')
                else:
                    print(f'  ✅ 数据充足（{len(df)} >= {min_required}）')
                    print(f'  💡 可能原因: 快线（{fast_period}）和慢线（{slow_period}）在数据范围内没有发生交叉')
                    print(f'  💡 建议: 尝试更长的日期范围，或者调整参数范围')
            
            # 对于MACD策略
            elif strategy_name == 'macd':
                slow_period = strategy_params.get('slow_period', 26)
                signal_period = strategy_params.get('signal_period', 9)
                min_required = slow_period + signal_period
                print(f'  - MACD策略需要至少 {min_required} 条数据（slow_period={slow_period} + signal_period={signal_period}）')
                if len(df) < min_required:
                    print(f'  ❌ 数据不足！只有 {len(df)} 条，需要至少 {min_required} 条')
                else:
                    print(f'  ✅ 数据充足（{len(df)} >= {min_required}）')
                    print(f'  💡 可能原因: MACD线和信号线在数据范围内没有发生交叉')
            
            print(f'  💡 通用建议:')
            print(f'     1. 确保日期范围有足够的历史数据（建议至少1年）')
            print(f'     2. 检查策略参数是否合理')
            print(f'     3. 某些策略在某些市场条件下可能不会产生交易信号（这是正常的）')
    
    # 计算收益率
    total_return = (final_value - initial_cash) / initial_cash * 100
    
    # 准备K线数据（用于图表展示）
    price_data = []
    for idx, row in df.iterrows():
        date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        price_data.append({
            'date': date_str,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume']) if 'volume' in row else 0,
        })
    
    # 获取收益曲线数据和交易时点
    equity_curve = []
    trade_points = []
    try:
        # 使用 object.__getattribute__ 来获取 equity_curve 属性，避免 Backtrader 的 __getattr__ 拦截
        equity_curve = object.__getattribute__(strat, 'equity_curve')
        if equity_curve:
            print(f"Found equity curve with {len(equity_curve)} data points")
        
        try:
            trade_points = object.__getattribute__(strat, 'trade_points')
            if trade_points:
                print(f"Found {len(trade_points)} trade points")
        except AttributeError:
            print("No trade_points found in strategy")
            trade_points = []
        
        if not equity_curve:
            # 如果没有记录，从数据重建（使用最终价值作为估算）
            print("Warning: equity_curve is empty, creating simplified version")
            # 简化版本：使用线性插值估算（df的索引已经是date）
            total_days = len(df)
            for i, (idx, row) in enumerate(df.iterrows()):
                # 计算进度百分比
                progress = (i + 1) / total_days if total_days > 0 else 0
                # 线性插值从初始资金到最终价值
                estimated_value = initial_cash + (final_value - initial_cash) * progress
                date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
                equity_curve.append({
                    'date': date_str,
                    'value': estimated_value,
                    'return_pct': ((estimated_value - initial_cash) / initial_cash) * 100 if initial_cash > 0 else 0
                })
            print(f"Created simplified equity curve with {len(equity_curve)} data points")
    except AttributeError:
        # 如果没有记录，从数据重建（使用最终价值作为估算）
        print("Warning: No equity_curve found in strategy, creating simplified version")
        # 简化版本：使用线性插值估算（df的索引已经是date）
        total_days = len(df)
        for i, (idx, row) in enumerate(df.iterrows()):
            # 计算进度百分比
            progress = (i + 1) / total_days if total_days > 0 else 0
            # 线性插值从初始资金到最终价值
            estimated_value = initial_cash + (final_value - initial_cash) * progress
            date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
            equity_curve.append({
                'date': date_str,
                'value': estimated_value,
                'return_pct': ((estimated_value - initial_cash) / initial_cash) * 100 if initial_cash > 0 else 0
            })
        print(f"Created simplified equity curve with {len(equity_curve)} data points")
    
    # 格式化日期用于显示（使用原始输入）
    start_date_str = str(original_start_date)
    end_date_str = str(original_end_date)
    
    result = {
        'symbol': symbol,
        'strategy': strategy_name,
        'data_type': data_type,
        'interval': interval if data_type == 'minute' else None,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'initial_cash': initial_cash,
        'final_value': final_value,
        'total_return': total_return,
        'sharpe_ratio': sharpe.get('sharperatio', None),
        'total_return_pct': returns.get('rtot', 0) * 100 if returns.get('rtot') else 0,
        'annual_return_pct': returns.get('rnorm', 0) * 100 if returns.get('rnorm') else 0,
        'max_drawdown': drawdown.get('max', {}).get('drawdown', 0) if drawdown.get('max') else 0,
        'max_drawdown_period': drawdown.get('max', {}).get('len', 0) if drawdown.get('max') else 0,
        'data_points': len(df),
        'equity_curve': equity_curve,  # 收益曲线数据
        'trade_points': trade_points,  # 交易时点数据（买入/卖出标记）
        'price_data': price_data,  # K线数据（用于展示基金净值变化）
        'total_trades': total_trades,  # 总交易次数
        'won_trades': won_trades,  # 盈利交易次数
        'lost_trades': lost_trades,  # 亏损交易次数
    }
    
    return result


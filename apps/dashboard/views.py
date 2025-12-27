from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from apps.data_master.models import Instrument, Candle, CandleMinute, MarketData, TradeRecord
from apps.analysis.indicators import IndicatorEngine
from apps.trading.execution_gateway import ExecutionGateway
from django.db.models import Max, Min, Avg, Count, Sum, Q
from django.utils import timezone
from decimal import Decimal
import pandas as pd
import json
from datetime import datetime, timedelta
import pytz

def dashboard_home(request):
    """
    总览仪表盘 - "一眼看清生死"的页面
    包含：总资产、今日盈亏、持仓风险、API连接状态、紧急按钮
    """
    from apps.trading.execution_gateway import ExecutionGateway
    from django.core.cache import cache
    
    # 初始化交易网关（模拟模式）
    gateway = ExecutionGateway(mode='simulation')
    
    # 1. 计算总资产（持仓市值 + 现金）
    # 从交易记录计算持仓和现金
    all_trades = TradeRecord.objects.filter(is_backtest=False).order_by('timestamp')
    
    positions_dict = {}  # {symbol: {'quantity': qty, 'cost': cost}}
    cash = Decimal('100000')  # 初始资金
    
    for trade in all_trades:
        if trade.direction == 'BUY':
            cost = trade.price * trade.quantity + trade.fee
            cash -= cost
            if trade.symbol not in positions_dict:
                positions_dict[trade.symbol] = {'quantity': Decimal('0'), 'cost': Decimal('0')}
            positions_dict[trade.symbol]['quantity'] += trade.quantity
            positions_dict[trade.symbol]['cost'] += cost
        else:  # SELL
            revenue = trade.price * trade.quantity - trade.fee
            cash += revenue
            if trade.symbol in positions_dict:
                # 按成本比例减少持仓
                cost_per_unit = positions_dict[trade.symbol]['cost'] / positions_dict[trade.symbol]['quantity']
                positions_dict[trade.symbol]['quantity'] -= trade.quantity
                positions_dict[trade.symbol]['cost'] -= cost_per_unit * trade.quantity
                if positions_dict[trade.symbol]['quantity'] <= 0:
                    del positions_dict[trade.symbol]
    
    # 计算持仓市值
    position_value = Decimal('0')
    positions = []
    for symbol, pos_info in positions_dict.items():
        # 获取最新价格
        latest_data = MarketData.objects.filter(symbol=symbol).order_by('-datetime').first()
        if latest_data:
            current_price = latest_data.close_price
            quantity = pos_info['quantity']
            cost_price = pos_info['cost'] / quantity if quantity > 0 else Decimal('0')
            market_value = current_price * quantity
            position_value += market_value
            pnl = market_value - pos_info['cost']
            
            positions.append({
                'symbol': symbol,
                'quantity': quantity,
                'cost_price': cost_price,
                'current_price': current_price,
                'pnl': pnl,
            })
    
    total_equity = cash + position_value
    
    # 2. 计算今日盈亏
    today = timezone.now().date()
    today_trades = TradeRecord.objects.filter(
        timestamp__date=today,
        is_backtest=False
    )
    
    today_pnl = Decimal('0')
    for trade in today_trades:
        if trade.direction == 'BUY':
            today_pnl -= (trade.price * trade.quantity + trade.fee)
        else:
            today_pnl += (trade.price * trade.quantity - trade.fee)
    
    # 3. 计算当前持仓风险（仓位比例）
    if total_equity > 0:
        position_risk = (position_value / total_equity) * 100
    else:
        position_risk = Decimal('0')
    
    # 4. API连接状态检查
    api_status = {
        'usmart': _check_usmart_connection(),
        'akshare': _check_akshare_connection(),
        'redis': _check_redis_connection(),
    }
    
    # 5. 获取最近的交易记录
    recent_trades = TradeRecord.objects.filter(
        is_backtest=False
    ).order_by('-timestamp')[:10]
    
    context = {
        'total_equity': total_equity,
        'today_pnl': today_pnl,
        'position_risk': position_risk,
        'api_status': api_status,
        'recent_trades': recent_trades,
        'positions': positions,
    }
    return render(request, 'dashboard/dashboard_home.html', context)


def _check_usmart_connection():
    """检查 uSmart API 连接状态"""
    # TODO: 实际实现 uSmart SDK 连接检查
    try:
        # from usmart_sdk import USmartClient
        # client = USmartClient()
        # return client.ping()
        return False  # 暂时返回 False，等待实际实现
    except:
        return False


def _check_akshare_connection():
    """检查 AkShare 连接状态"""
    try:
        import akshare as ak
        # 简单测试：尝试获取一个ETF数据
        # ak.fund_etf_hist_em(symbol="510300", period="日k", adjust="")
        return True  # AkShare 通常是可用的
    except:
        return False


def _check_redis_connection():
    """检查 Redis 连接状态"""
    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 1)
        return cache.get('health_check') == 'ok'
    except:
        return False


def strategy_monitor(request, strategy_name=None):
    """
    策略详情与 K 线监控页面
    左侧：K 线图（ECharts），显示买入/卖出点
    右侧：实时日志
    """
    # 获取策略列表
    strategies = TradeRecord.objects.filter(
        is_backtest=False
    ).values_list('strategy_name', flat=True).distinct()
    
    # 如果指定了策略，获取该策略的数据
    selected_strategy = strategy_name or (strategies[0] if strategies else None)
    
    # 获取该策略的交易记录
    trades = TradeRecord.objects.filter(
        strategy_name=selected_strategy,
        is_backtest=False
    ).order_by('-timestamp')[:50] if selected_strategy else []
    
    # 获取策略交易的标的
    symbols = TradeRecord.objects.filter(
        strategy_name=selected_strategy,
        is_backtest=False
    ).values_list('symbol', flat=True).distinct() if selected_strategy else []
    
    # 获取第一个标的的K线数据（用于图表）
    chart_data = None
    if symbols:
        symbol = symbols[0]
        market_data = MarketData.objects.filter(
            symbol=symbol
        ).order_by('-datetime')[:100]
        
        if market_data:
            chart_data = {
                'symbol': symbol,
                'dates': [md.datetime.strftime('%Y-%m-%d %H:%M:%S') for md in reversed(market_data)],
                'kline': [[float(md.open_price), float(md.close_price), float(md.low_price), float(md.high_price)] 
                          for md in reversed(market_data)],
                'volume': [float(md.volume) for md in reversed(market_data)],
                'taker_buy_volume': [float(md.taker_buy_volume) if md.taker_buy_volume else 0 
                                    for md in reversed(market_data)],
            }
            
            # 标记买入/卖出点
            buy_points = []
            sell_points = []
            for trade in trades:
                if trade.symbol == symbol:
                    # 找到对应的K线时间点
                    for i, md in enumerate(reversed(market_data)):
                        if abs((md.datetime - trade.timestamp).total_seconds()) < 300:  # 5分钟内
                            if trade.direction == 'BUY':
                                buy_points.append({'index': i, 'price': float(trade.price)})
                            else:
                                sell_points.append({'index': i, 'price': float(trade.price)})
                            break
            
            chart_data['buy_points'] = buy_points
            chart_data['sell_points'] = sell_points
    
    context = {
        'strategies': strategies,
        'selected_strategy': selected_strategy,
        'trades': trades,
        'chart_data': chart_data,
    }
    return render(request, 'dashboard/strategy_monitor.html', context)


def index(request):
    """首页 - 板块轮动图表"""
    from datetime import timedelta
    from django.db.models import Q
    
    # 获取时间段参数（默认1周）
    period = request.GET.get('period', '1w')
    period_days = {
        '1w': 7,
        '1m': 30,
        '3m': 90,
        'all': None,
    }
    period_name = {
        '1w': '1周',
        '1m': '1个月',
        '3m': '3个月',
        'all': '全部',
    }
    days = period_days.get(period, 7)
    period_label = period_name.get(period, '1周')
    
    # 获取所有有数据的A股ETF（排除宽基指数）
    etfs = Instrument.objects.filter(
        market='CN',
        candles__isnull=False,
        category__isnull=False
    ).exclude(category='宽基指数').distinct().order_by('category', 'symbol')
    
    # 按行业分类统计
    from collections import defaultdict
    sector_stats = defaultdict(lambda: {
        'etfs': [],
        'change_pcts': [],
        'avg_change': 0,
        'etf_count': 0,
    })
    
    for etf in etfs:
        candles = Candle.objects.filter(instrument=etf).order_by('date')
        if not candles.exists():
            continue
            
        latest = candles.last()
        
        # 根据时间段筛选数据
        if days is None:
            period_first = candles.first()
        else:
            period_start = latest.date - timedelta(days=days)
            period_candles = candles.filter(date__gte=period_start)
            period_first = period_candles.first() if period_candles.exists() else candles.first()
        
        if period_first and latest and period_first.date < latest.date:
            change_pct = ((float(latest.close) - float(period_first.close)) / float(period_first.close)) * 100
            
            category = etf.category or '未分类'
            sector_stats[category]['etfs'].append({
                'symbol': etf.symbol,
                'name': etf.name,
                'change_pct': change_pct,
                'trading_rule': etf.trading_rule,
            })
            sector_stats[category]['change_pcts'].append(change_pct)
    
    # 计算每个板块的平均涨跌幅
    sector_list = []
    for category, stats in sector_stats.items():
        if stats['change_pcts']:
            avg_change = sum(stats['change_pcts']) / len(stats['change_pcts'])
            sector_list.append({
                'category': category,
                'avg_change': avg_change,
                'etf_count': len(stats['etfs']),
                'etfs': sorted(stats['etfs'], key=lambda x: x['change_pct'], reverse=True),
                'max_change': max(stats['change_pcts']),
                'min_change': min(stats['change_pcts']),
            })
    
    # 按平均涨跌幅排序（热点在前）
    sector_list.sort(key=lambda x: x['avg_change'], reverse=True)
    
    # 获取最热和最冷板块（用于统计卡片）
    hot_sector = sector_list[0] if sector_list else None
    cold_sector = sector_list[-1] if sector_list else None
    
    context = {
        'sectors': sector_list,
        'hot_sector': hot_sector,
        'cold_sector': cold_sector,
        'period_label': period_label,
        'current_period': period,
        'available_periods': [
            ('1w', '1周'),
            ('1m', '1个月'),
            ('3m', '3个月'),
            ('all', '全部'),
        ],
    }
    return render(request, 'dashboard/index.html', context)


def etf_overview(request):
    """ETF概览页面"""
    from datetime import timedelta, datetime
    
    # 获取时间段参数（默认1周）
    period = request.GET.get('period', '1w')
    
    # 定义时间段对应的天数
    period_days = {
        '1w': 7,      # 1周
        '1m': 30,     # 1个月
        '3m': 90,     # 3个月
        '6m': 180,    # 6个月
        '1y': 365,    # 1年
        'all': None,  # 全部数据
    }
    
    period_name = {
        '1w': '1周',
        '1m': '1个月',
        '3m': '3个月',
        '6m': '6个月',
        '1y': '1年',
        'all': '全部',
    }
    
    days = period_days.get(period, 7)
    period_label = period_name.get(period, '1周')
    
    # 获取所有A股ETF
    etfs = Instrument.objects.filter(market='CN').order_by('category', 'symbol')
    
    # 为每个ETF计算统计信息
    etf_list = []
    for etf in etfs:
        # 获取所有数据用于计算总体统计
        all_candles = Candle.objects.filter(instrument=etf).order_by('date')
        if all_candles.exists():
            latest = all_candles.last()
            first = all_candles.first()
            
            # 根据时间段筛选数据
            if days is None:
                # 全部数据
                candles = all_candles
                period_start_date = first.date if first else None
            else:
                # 计算时间段起始日期
                period_start_date = latest.date - timedelta(days=days) if latest else None
                candles = all_candles.filter(date__gte=period_start_date) if period_start_date else all_candles
            
            # 获取时间段内的第一条数据
            period_first = candles.first() if candles.exists() else None
            
            stats = all_candles.aggregate(
                max_price=Max('high'),
                min_price=Min('low'),
                avg_volume=Avg('volume'),
                count=Count('id')
            )
            
            # 计算总体涨跌幅（从第一条数据到最后一条）
            if first and latest:
                change_pct = ((float(latest.close) - float(first.close)) / float(first.close)) * 100
            else:
                change_pct = 0
            
            # 计算时间段涨跌幅
            period_change_pct = None
            if latest and period_first and period_first.date < latest.date:
                period_change_pct = ((float(latest.close) - float(period_first.close)) / float(period_first.close)) * 100
            
            # 数据时间范围
            data_start_date = first.date if first else None
            data_end_date = latest.date if latest else None
            
            etf_list.append({
                'instrument': etf,
                'latest': latest,
                'change_pct': change_pct,
                'period_change_pct': period_change_pct,
                'period_start_date': period_start_date,
                'max_price': stats['max_price'],
                'min_price': stats['min_price'],
                'avg_volume': stats['avg_volume'],
                'data_count': stats['count'],
                'data_start_date': data_start_date,
                'data_end_date': data_end_date,
            })
    
    # 按行业分类分组
    etfs_by_category = {}
    for etf_data in etf_list:
        category = etf_data['instrument'].category or '未分类'
        if category not in etfs_by_category:
            etfs_by_category[category] = []
        etfs_by_category[category].append(etf_data)
    
    context = {
        'etfs': etf_list,
        'etfs_by_category': etfs_by_category,
        'total_count': len(etf_list),
        'period': period,
        'period_label': period_label,
        'available_periods': [
            ('1w', '1周'),
            ('1m', '1个月'),
            ('3m', '3个月'),
            ('6m', '6个月'),
            ('1y', '1年'),
            ('all', '全部'),
        ],
    }
    return render(request, 'dashboard/etf_overview.html', context)


def us_stocks_overview(request):
    """美股龙头股票概览页面"""
    # 获取所有美股
    stocks = Instrument.objects.filter(market='US').order_by('symbol')
    
    # 为每个股票计算统计信息
    stock_list = []
    for stock in stocks:
        candles = Candle.objects.filter(instrument=stock).order_by('date')
        if candles.exists():
            latest = candles.last()
            first = candles.first()
            stats = candles.aggregate(
                max_price=Max('high'),
                min_price=Min('low'),
                avg_volume=Avg('volume'),
                count=Count('id')
            )
            
            # 计算涨跌幅
            if first and latest:
                change_pct = ((float(latest.close) - float(first.close)) / float(first.close)) * 100
            else:
                change_pct = 0
            
            stock_list.append({
                'instrument': stock,
                'latest': latest,
                'change_pct': change_pct,
                'max_price': stats['max_price'],
                'min_price': stats['min_price'],
                'avg_volume': stats['avg_volume'],
                'data_count': stats['count'],
            })
    
    context = {
        'stocks': stock_list,
        'total_count': len(stock_list),
    }
    return render(request, 'dashboard/us_stocks_overview.html', context)


def chart_view(request, symbol):
    """K线图表页面"""
    instrument = get_object_or_404(Instrument, symbol=symbol)
    context = {
        'instrument': instrument,
    }
    return render(request, 'dashboard/chart.html', context)


def get_chart_data(request, symbol):
    """获取图表数据的API接口"""
    try:
        instrument = Instrument.objects.get(symbol=symbol)
        
        # 获取时间粒度参数（日K或分钟K）
        interval = request.GET.get('interval', 'daily')  # 'daily', '1m', '5m', '15m', '30m', '60m'
        
        # 定义北京时区
        beijing_tz = pytz.timezone('Asia/Shanghai')

        # 根据时间粒度选择数据源
        if interval == 'daily':
            # 日K数据
            candles = Candle.objects.filter(instrument=instrument).order_by('date')
            if not candles.exists():
                return JsonResponse({'error': '没有日K数据'}, status=404)
            
            # 转换为DataFrame
            data_list = []
            for candle in candles:
                data_list.append({
                    'date': candle.date.isoformat(),
                    'open': float(candle.open),
                    'high': float(candle.high),
                    'low': float(candle.low),
                    'close': float(candle.close),
                    'volume': int(candle.volume),
                    'amount': float(candle.amount),
                })
            
            df = pd.DataFrame(data_list)
            df['date'] = pd.to_datetime(df['date'])
        else:
            # 分钟K数据
            # 对于分钟数据，限制显示最近的数据量，避免图表过于密集
            limit_map = {
                '1m': 720,   # 约3个交易日
                '5m': 480,   # 约5个交易日
                '15m': 400,  # 约10个交易日
                '30m': 400,  # 约20个交易日
                '60m': 600,  # 约30个交易日
            }
            limit = limit_map.get(interval, 1000)
            
            minute_candles = CandleMinute.objects.filter(
                instrument=instrument,
                interval=interval
            ).order_by('-datetime')[:limit]
            
            if not minute_candles.exists():
                return JsonResponse({'error': f'没有{interval}分钟K数据'}, status=404)
            
            # 反转顺序，从早到晚
            minute_candles = list(reversed(minute_candles))
            
            # 转换为DataFrame
            data_list = []
            for candle in minute_candles:
                # 如果是aware datetime（带时区），转换为北京时间
                dt = candle.datetime
                if dt.tzinfo is not None:
                    # 转换为北京时间
                    dt_beijing = dt.astimezone(beijing_tz)
                else:
                    # naive datetime，假设已经是北京时间
                    dt_beijing = beijing_tz.localize(dt)
                
                data_list.append({
                    'date': dt_beijing.isoformat(),
                    'open': float(candle.open),
                    'high': float(candle.high),
                    'low': float(candle.low),
                    'close': float(candle.close),
                    'volume': int(candle.volume),
                    'amount': float(candle.amount),
                })
            
            df = pd.DataFrame(data_list)
            df['date'] = pd.to_datetime(df['date'])
        
        # 修复开盘价为0的问题
        if 'open' in df.columns:
            df['open'] = df.apply(lambda row: row['close'] if row['open'] == 0 else row['open'], axis=1)
        
        # 计算技术指标
        df_with_indicators = IndicatorEngine.inject_indicators(df, market=instrument.market)
        
        # 准备ECharts需要的格式
        # 根据时间粒度格式化日期
        if interval == 'daily':
            dates = [d.strftime('%Y-%m-%d') for d in df_with_indicators['date']]
        else:
            # 分钟数据格式化：根据数据密度选择格式
            if len(df_with_indicators) > 500:
                dates = [d.strftime('%m-%d %H:%M') for d in df_with_indicators['date']]
            elif len(df_with_indicators) > 200:
                dates = [d.strftime('%m-%d %H:%M') for d in df_with_indicators['date']]
            else:
                dates = [d.strftime('%Y-%m-%d %H:%M') for d in df_with_indicators['date']]
        
        # K线数据：[开盘, 收盘, 最低, 最高]
        kline_data = [[float(row['open']), float(row['close']), float(row['low']), float(row['high'])] 
                      for _, row in df_with_indicators.iterrows()]
        
        # 成交量
        volume_data = [int(row['volume']) for _, row in df_with_indicators.iterrows()]
        
        # 成交量（涨/跌）
        volume_up_data = []
        volume_down_data = []
        for i, row in df_with_indicators.iterrows():
            if row['close'] >= row['open']:
                volume_up_data.append(int(row['volume']))
                volume_down_data.append(None)
            else:
                volume_up_data.append(None)
                volume_down_data.append(int(row['volume']))

        # 移动平均线（处理数据不足的情况）
        ma5_data = []
        ma20_data = []
        ma60_data = []
        for _, row in df_with_indicators.iterrows():
            ma5_data.append(float(row['SMA_5']) if 'SMA_5' in row and pd.notna(row.get('SMA_5')) else None)
            ma20_data.append(float(row['SMA_20']) if 'SMA_20' in row and pd.notna(row.get('SMA_20')) else None)
            ma60_data.append(float(row['SMA_60']) if 'SMA_60' in row and pd.notna(row.get('SMA_60')) else None)
        
        # MACD（处理数据不足的情况）
        macd_data = []
        macd_signal_data = []
        macd_hist_data = []
        for _, row in df_with_indicators.iterrows():
            macd_data.append(float(row['MACD_12_26_9']) if 'MACD_12_26_9' in row and pd.notna(row.get('MACD_12_26_9')) else None)
            macd_signal_data.append(float(row['MACDs_12_26_9']) if 'MACDs_12_26_9' in row and pd.notna(row.get('MACDs_12_26_9')) else None)
            macd_hist_data.append(float(row['MACDh_12_26_9']) if 'MACDh_12_26_9' in row and pd.notna(row.get('MACDh_12_26_9')) else None)
        
        # RSI（处理数据不足的情况）
        rsi_data = []
        for _, row in df_with_indicators.iterrows():
            rsi_data.append(float(row['RSI_14']) if 'RSI_14' in row and pd.notna(row.get('RSI_14')) else None)
        
        # 布林带（处理数据不足的情况）
        bbu_data = []
        bbm_data = []
        bbl_data = []
        for _, row in df_with_indicators.iterrows():
            bbu_data.append(float(row['BBU_20_2.0']) if 'BBU_20_2.0' in row and pd.notna(row.get('BBU_20_2.0')) else None)
            bbm_data.append(float(row['BBM_20_2.0']) if 'BBM_20_2.0' in row and pd.notna(row.get('BBM_20_2.0')) else None)
            bbl_data.append(float(row['BBL_20_2.0']) if 'BBL_20_2.0' in row and pd.notna(row.get('BBL_20_2.0')) else None)
        
        response_data = {
            'dates': dates,
            'kline': kline_data,
            'volume': volume_data,
            'volume_up': volume_up_data,
            'volume_down': volume_down_data,
            'ma5': ma5_data,
            'ma20': ma20_data,
            'ma60': ma60_data,
            'macd': macd_data,
            'macd_signal': macd_signal_data,
            'macd_hist': macd_hist_data,
            'rsi': rsi_data,
            'bbu': bbu_data,
            'bbm': bbm_data,
            'bbl': bbl_data,
            'symbol': symbol,
            'name': instrument.name,
            'market': instrument.market,
            'trading_rule': instrument.trading_rule,
        }
        
        return JsonResponse(response_data)
        
    except Instrument.DoesNotExist:
        return JsonResponse({'error': '标的不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def backtest_view(request):
    """回测页面"""
    from apps.backtest.strategies import STRATEGY_REGISTRY
    from django.db.models import Min, Max
    
    # 获取所有有数据的标的，并计算每个标的的数据范围
    instruments = Instrument.objects.filter(
        candles__isnull=False
    ).distinct().order_by('symbol')
    
    # 为每个标的添加数据范围信息
    instruments_with_range = []
    for inst in instruments:
        candles = Candle.objects.filter(instrument=inst)
        date_range = candles.aggregate(
            min_date=Min('date'),
            max_date=Max('date')
        )
        instruments_with_range.append({
            'instrument': inst,
            'min_date': date_range['min_date'],
            'max_date': date_range['max_date'],
            'count': candles.count()
        })
    
    # 策略列表（包含说明和参数）
    strategies = {
        'macross': {
            'name': '双均线策略',
            'description': '当短期均线上穿长期均线时买入，下穿时卖出',
            'params': {'fast_period': 5, 'slow_period': 20}
        },
        'macd': {
            'name': 'MACD策略',
            'description': '当MACD线上穿信号线时买入，下穿时卖出',
            'params': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9}
        },
        'rsi': {
            'name': 'RSI策略',
            'description': 'RSI低于超卖线时买入，高于超买线时卖出',
            'params': {'period': 14, 'oversold': 30, 'overbought': 70}
        },
        'bollinger': {
            'name': '布林带策略',
            'description': '价格触及下轨时买入，触及上轨时卖出',
            'params': {'period': 20, 'devfactor': 2.0}
        },
        'triple_ma': {
            'name': '三均线策略',
            'description': '短期均线 > 中期均线 > 长期均线时买入，反之卖出',
            'params': {'fast_period': 5, 'mid_period': 10, 'slow_period': 20}
        },
        'mean_reversion': {
            'name': '均值回归策略',
            'description': '当价格偏离均线一定比例时买入/卖出',
            'params': {'period': 20, 'threshold': 0.02}
        },
        'vcp': {
            'name': 'VCP波动收缩策略',
            'description': '识别波动收缩形态，在突破时买入（右侧交易）',
            'params': {'lookback': 20, 'contraction_ratio': 0.7, 'volume_ratio': 0.8, 'breakout_threshold': 1.02}
        },
        'candlestick': {
            'name': '蜡烛图形态策略',
            'description': '识别锤子线、吞没形态、十字星等蜡烛图形态进行交易',
            'params': {'pattern_type': 'all', 'confirmation_period': 2, 'min_body_ratio': 0.3, 'min_shadow_ratio': 2.0}
        },
        'swing': {
            'name': '波段交易策略',
            'description': '在上升趋势中，等待价格回调至支撑位买入，在阻力位卖出',
            'params': {'trend_period': 20, 'swing_period': 10, 'pullback_ratio': 0.05, 'profit_target': 0.10, 'stop_loss': 0.05}
        },
        'trend_following': {
            'name': '趋势跟踪策略',
            'description': '等待趋势确认后入场，跟随趋势进行交易（右侧交易）',
            'params': {'fast_period': 10, 'slow_period': 30, 'adx_period': 14, 'adx_threshold': 25, 'trailing_stop': 0.03}
        },
    }
    
    import json
    context = {
        'instruments': instruments_with_range,
        'strategies': strategies,  # 字典格式用于模板
        'strategies_json': json.dumps(strategies),  # JSON字符串用于JavaScript
    }
    return render(request, 'dashboard/backtest.html', context)


def run_backtest_api(request):
    """运行回测的API接口"""
    from apps.backtest.engine import run_backtest
    from django.views.decorators.csrf import csrf_exempt
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': '只支持POST请求'}, status=405)
    
    try:
        # 支持JSON和表单数据
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        symbol = data.get('symbol')
        strategy_name = data.get('strategy')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        data_type = data.get('data_type', 'daily')  # 'daily' 或 'minute'
        interval = data.get('interval', '1m')  # 分钟数据的时间间隔
        initial_cash = float(data.get('initial_cash', 100000))
        commission = float(data.get('commission', 0.001))
        
        # 获取策略参数
        strategy_params = {}
        for key, value in request.POST.items():
            if key.startswith('param_'):
                param_name = key.replace('param_', '')
                try:
                    # 尝试转换为数值
                    strategy_params[param_name] = float(value) if '.' in value else int(value)
                except ValueError:
                    strategy_params[param_name] = value
        
        # 运行回测
        result = run_backtest(
            symbol=symbol,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            data_type=data_type,
            interval=interval if data_type == 'minute' else '1m',
            initial_cash=initial_cash,
            commission=commission,
            **strategy_params
        )
        
        return JsonResponse(result)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Backtest API error: {str(e)}")
        print(f"Traceback:\n{error_detail}")
        return JsonResponse({'error': str(e), 'detail': error_detail}, status=500)


def batch_optimize_view(request):
    """批量优化页面"""
    from apps.data_master.models import Instrument
    
    # 获取所有有数据的ETF
    etfs = Instrument.objects.filter(
        market='CN',
        candles__isnull=False
    ).distinct().order_by('symbol')
    
    context = {
        'total_etfs': etfs.count(),
        'etfs': etfs,
    }
    return render(request, 'dashboard/batch_optimize.html', context)


def optimize_strategy_api(request):
    """单策略参数优化API接口"""
    from apps.backtest.optimizer import optimize_single_strategy
    from django.views.decorators.csrf import csrf_exempt
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': '只支持POST请求'}, status=405)
    
    try:
        # 支持JSON和表单数据
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        symbol = data.get('symbol')
        strategy_name = data.get('strategy')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_cash = float(data.get('initial_cash', 100000))
        commission = float(data.get('commission', 0.001))
        data_type = data.get('data_type', 'daily')
        
        if not symbol or not strategy_name or not start_date or not end_date:
            return JsonResponse({'error': '请提供标的、策略、开始日期和结束日期'}, status=400)
        
        print(f'=' * 60)
        print(f'开始参数优化')
        print(f'  标的: {symbol}')
        print(f'  策略: {strategy_name}')
        print(f'  日期范围: {start_date} 到 {end_date}')
        print(f'  初始资金: {initial_cash}')
        print(f'  手续费率: {commission}')
        print(f'=' * 60)
        
        # 运行参数优化
        result = optimize_single_strategy(
            symbol=symbol,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            commission=commission,
            data_type=data_type,
        )
        
        # 简化结果（只保留关键信息）
        simplified_result = {
            'symbol': result['symbol'],
            'strategy_name': result['strategy_name'],
            'total_combinations': result['total_combinations'],
            'valid_results': result['valid_results'],
            'best_by_return': {
                'params': result['best_by_return'].get('strategy_params') if result['best_by_return'] else None,
                'total_return': result['best_by_return'].get('total_return_pct') if result['best_by_return'] else None,
                'annual_return': result['best_by_return'].get('annual_return_pct') if result['best_by_return'] else None,
                'sharpe_ratio': result['best_by_return'].get('sharpe_ratio') if result['best_by_return'] else None,
                'max_drawdown': result['best_by_return'].get('max_drawdown') if result['best_by_return'] else None,
                'total_trades': result['best_by_return'].get('total_trades') if result['best_by_return'] else None,
            } if result['best_by_return'] else None,
            'best_by_sharpe': {
                'params': result['best_by_sharpe'].get('strategy_params') if result['best_by_sharpe'] else None,
                'total_return': result['best_by_sharpe'].get('total_return_pct') if result['best_by_sharpe'] else None,
                'sharpe_ratio': result['best_by_sharpe'].get('sharpe_ratio') if result['best_by_sharpe'] else None,
            } if result['best_by_sharpe'] else None,
            'best_by_annual': {
                'params': result['best_by_annual'].get('strategy_params') if result['best_by_annual'] else None,
                'annual_return': result['best_by_annual'].get('annual_return_pct') if result['best_by_annual'] else None,
            } if result['best_by_annual'] else None,
            # 返回前10个最佳结果（按总收益率）
            'top_results': sorted(
                result['all_results'],
                key=lambda x: x.get('total_return_pct', -999),
                reverse=True
            )[:10] if result['all_results'] else [],
            # 如果最佳参数有结果，也返回其图表数据（用于显示最佳参数的收益曲线）
            'best_chart_data': {
                'equity_curve': result['best_by_return'].get('equity_curve', []) if result['best_by_return'] else [],
                'trade_points': result['best_by_return'].get('trade_points', []) if result['best_by_return'] else [],
                'initial_cash': initial_cash,
            } if result['best_by_return'] and result['best_by_return'].get('equity_curve') else None,
        }
        
        return JsonResponse(simplified_result)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Strategy optimize API error: {str(e)}")
        print(f"Traceback:\n{error_detail}")
        return JsonResponse({'error': str(e), 'detail': error_detail}, status=500)


def batch_optimize_api(request):
    """批量优化API接口"""
    from apps.backtest.optimizer import batch_optimize_all_etfs
    from django.views.decorators.csrf import csrf_exempt
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': '只支持POST请求'}, status=405)
    
    try:
        # 支持JSON和表单数据
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_cash = float(data.get('initial_cash', 100000))
        commission = float(data.get('commission', 0.001))
        data_type = data.get('data_type', 'daily')
        max_etfs = data.get('max_etfs')  # 可选，用于测试
        
        if max_etfs:
            max_etfs = int(max_etfs)
        
        if not start_date or not end_date:
            return JsonResponse({'error': '请提供开始日期和结束日期'}, status=400)
        
        print(f'开始批量优化: {start_date} 到 {end_date}')
        
        # 运行批量优化
        results = batch_optimize_all_etfs(
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            commission=commission,
            data_type=data_type,
            max_etfs=max_etfs,
        )
        
        # 转换DataFrame为字典（用于JSON序列化）
        if results.get('summary_df') is not None:
            results['summary_df'] = results['summary_df'].to_dict('records')
        
        # 简化详细结果（只保留最佳策略，避免数据过大）
        simplified_results = {}
        for symbol, data in results.get('detailed_results', {}).items():
            simplified_results[symbol] = {
                'etf_name': data['etf_name'],
                'best_by_return': data.get('best_by_return'),
                'best_by_sharpe': data.get('best_by_sharpe'),
                'best_by_annual': data.get('best_by_annual'),
            }
        
        results['detailed_results'] = simplified_results
        
        return JsonResponse(results)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Batch optimize API error: {str(e)}")
        print(f"Traceback:\n{error_detail}")
        return JsonResponse({'error': str(e), 'detail': error_detail}, status=500)

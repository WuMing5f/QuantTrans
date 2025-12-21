from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from apps.data_master.models import Instrument, Candle, CandleMinute
from apps.analysis.indicators import IndicatorEngine
from django.db.models import Max, Min, Avg, Count
import pandas as pd
import json
from datetime import datetime, timedelta
import pytz

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
    
    # 获取所有有数据的标的
    instruments = Instrument.objects.filter(
        candles__isnull=False
    ).distinct().order_by('symbol')
    
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
        'instruments': instruments,
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

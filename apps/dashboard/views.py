from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from apps.data_master.models import Instrument, Candle, CandleMinute
from apps.analysis.indicators import IndicatorEngine
from django.db.models import Max, Min, Avg, Count
import pandas as pd
import json


def index(request):
    """首页"""
    instruments = Instrument.objects.all()[:10]
    context = {
        'instruments': instruments,
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
            # 1分钟数据：最近3天（约720条）
            # 5分钟数据：最近5天（约480条）
            # 15分钟数据：最近10天（约400条）
            # 30分钟数据：最近20天（约400条）
            # 60分钟数据：最近30天（约600条）
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
            # 注意：Django存储的datetime是UTC时间，需要转换为北京时间（UTC+8）
            import pytz
            beijing_tz = pytz.timezone('Asia/Shanghai')
            
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
        
        # 计算技术指标
        df_with_indicators = IndicatorEngine.inject_indicators(df, market=instrument.market)
        
        # 准备ECharts需要的格式
        # 根据时间粒度格式化日期
        if interval == 'daily':
            dates = [d.strftime('%Y-%m-%d') for d in df_with_indicators['date']]
        else:
            # 分钟数据格式化：根据数据密度选择格式
            # 如果数据量很大（>500），使用更简洁的格式
            if len(df_with_indicators) > 500:
                # 对于密集数据，使用简洁格式：月-日 时:分
                dates = [d.strftime('%m-%d %H:%M') for d in df_with_indicators['date']]
            elif len(df_with_indicators) > 200:
                # 中等数据量，显示完整日期但简化格式
                dates = [d.strftime('%m-%d %H:%M') for d in df_with_indicators['date']]
            else:
                # 少量数据，显示完整日期时间
                dates = [d.strftime('%Y-%m-%d %H:%M') for d in df_with_indicators['date']]
        
        # K线数据：[开盘, 收盘, 最低, 最高]
        kline_data = [[float(row['open']), float(row['close']), float(row['low']), float(row['high'])] 
                      for _, row in df_with_indicators.iterrows()]
        
        # 成交量
        volume_data = [int(row['volume']) for _, row in df_with_indicators.iterrows()]
        
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
        }
        
        return JsonResponse(response_data)
        
    except Instrument.DoesNotExist:
        return JsonResponse({'error': '标的不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

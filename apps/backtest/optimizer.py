"""
策略参数优化器
用于批量回测和参数优化
"""
import backtrader as bt
from typing import Dict, List, Tuple, Any
from itertools import product
from apps.backtest.engine import run_backtest
from apps.backtest.strategies import STRATEGY_REGISTRY
import pandas as pd


# 定义每个策略的参数网格（限制参数范围，避免组合爆炸）
# 注意：参数组合数量 = 各参数值数量的乘积，建议控制在100以内
STRATEGY_PARAM_GRIDS = {
    'macross': {
        'fast_period': [5, 10, 15, 20],
        'slow_period': [20, 30, 40, 60],
    },
    'macd': {
        'fast_period': [10, 12, 15],
        'slow_period': [20, 26, 30],
        'signal_period': [7, 9, 12],
    },
    'rsi': {
        'period': [10, 14, 20],
        'oversold': [25, 30, 35],
        'overbought': [65, 70, 75],
    },
    'bollinger': {
        'period': [15, 20, 25],
        'devfactor': [1.5, 2.0, 2.5],
    },
    'triple_ma': {
        'fast_period': [3, 5, 8],
        'mid_period': [8, 10, 15],
        'slow_period': [15, 20, 30],
    },
    'mean_reversion': {
        'period': [15, 20, 25],
        'threshold': [0.015, 0.02, 0.025, 0.03],
    },
    'vcp': {
        'lookback': [15, 20, 25],
        'contraction_ratio': [0.6, 0.7, 0.8],
        'volume_ratio': [0.7, 0.8, 0.9],
        'breakout_threshold': [1.01, 1.02, 1.03],
    },
    'candlestick': {
        'pattern_type': ['all', 'hammer', 'engulfing'],
        'confirmation_period': [1, 2, 3],
        'min_body_ratio': [0.2, 0.3, 0.4],
        'min_shadow_ratio': [1.5, 2.0, 2.5],
    },
    'swing': {
        'trend_period': [15, 20, 25],
        'swing_period': [8, 10, 12],
        'pullback_ratio': [0.03, 0.05, 0.07],
        'profit_target': [0.08, 0.10, 0.12],
        'stop_loss': [0.03, 0.05, 0.07],
    },
    'trend_following': {
        'fast_period': [8, 10, 12],
        'slow_period': [25, 30, 35],
        'adx_period': [12, 14, 16],
        'adx_threshold': [20, 25, 30],
        'trailing_stop': [0.02, 0.03, 0.04],
    },
    'pyramid_add': {
        'initial_position_size': [0.03, 0.05, 0.07],  # 3%, 5%, 7%初始仓位
        'stop_loss_pct': [0.015, 0.02, 0.025],  # 1.5%, 2%, 2.5%止损
        'add_position_threshold': [0.015, 0.02, 0.025],  # 1.5%, 2%, 2.5%加仓阈值
        'ma_period': [15, 20, 25],  # 均线周期
        'high_open_threshold': [0.005, 0.01, 0.015],  # 0.5%, 1%, 1.5%高开阈值
    },
}


def optimize_single_strategy(
    symbol: str,
    strategy_name: str,
    start_date: str,
    end_date: str,
    initial_cash: float = 100000.0,
    commission: float = 0.001,
    data_type: str = 'daily',
) -> Dict[str, Any]:
    """
    对单个标的的单个策略进行参数优化
    
    Args:
        symbol: 股票代码
        strategy_name: 策略名称
        start_date: 开始日期
        end_date: 结束日期
        initial_cash: 初始资金
        commission: 手续费率
        data_type: 数据类型
        
    Returns:
        包含所有参数组合的回测结果和最佳参数
    """
    # 生成所有参数组合
    param_combinations = generate_param_combinations(strategy_name)
    
    print(f'\n标的 {symbol}, 策略 {strategy_name}')
    print(f'日期范围: {start_date} 到 {end_date}')
    print(f'共 {len(param_combinations)} 个参数组合需要测试')
    
    results = []
    for i, params in enumerate(param_combinations, 1):
        try:
            print(f'[{i}/{len(param_combinations)}] 测试参数: {params}')
            
            result = run_backtest(
                symbol=symbol,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                data_type=data_type,
                initial_cash=initial_cash,
                commission=commission,
                **params
            )
            
            # 添加参数信息
            result['strategy_params'] = params
            results.append(result)
            
        except Exception as e:
            print(f'参数 {params} 回测失败: {str(e)}')
            continue
    
    # 找出最佳参数（按总收益率）
    best_by_return = find_best_strategy(results, 'total_return_pct')
    
    # 找出最佳参数（按夏普比率）
    best_by_sharpe = find_best_strategy(results, 'sharpe_ratio')
    
    # 找出最佳参数（按年化收益率）
    best_by_annual = find_best_strategy(results, 'annual_return_pct')
    
    return {
        'symbol': symbol,
        'strategy_name': strategy_name,
        'all_results': results,
        'total_combinations': len(param_combinations),
        'valid_results': len(results),
        'best_by_return': best_by_return,
        'best_by_sharpe': best_by_sharpe,
        'best_by_annual': best_by_annual,
    }


def generate_param_combinations(strategy_name: str) -> List[Dict[str, Any]]:
    """
    生成策略的所有参数组合
    
    Args:
        strategy_name: 策略名称
        
    Returns:
        参数组合列表
    """
    if strategy_name not in STRATEGY_PARAM_GRIDS:
        return [{}]
    
    param_grid = STRATEGY_PARAM_GRIDS[strategy_name]
    
    # 生成所有参数组合
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    
    combinations = []
    for combo in product(*values):
        combinations.append(dict(zip(keys, combo)))
    
    return combinations


def batch_backtest_all_strategies(
    symbol: str,
    start_date: str,
    end_date: str,
    initial_cash: float = 100000.0,
    commission: float = 0.001,
    data_type: str = 'daily',
    max_strategies: int = None,  # 限制测试的策略数量（None表示全部）
) -> List[Dict[str, Any]]:
    """
    对单个标的运行所有策略的所有参数组合
    
    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        initial_cash: 初始资金
        commission: 手续费率
        data_type: 数据类型（'daily' 或 'minute'）
        max_strategies: 最大测试策略数（用于测试）
        
    Returns:
        所有策略和参数组合的回测结果列表
    """
    results = []
    
    # 获取所有策略
    strategies_to_test = list(STRATEGY_REGISTRY.keys())
    if max_strategies:
        strategies_to_test = strategies_to_test[:max_strategies]
    
    total_combinations = 0
    for strategy_name in strategies_to_test:
        param_combinations = generate_param_combinations(strategy_name)
        total_combinations += len(param_combinations)
    
    print(f'标的 {symbol}: 共 {len(strategies_to_test)} 个策略, {total_combinations} 个参数组合')
    
    combination_count = 0
    for strategy_name in strategies_to_test:
        param_combinations = generate_param_combinations(strategy_name)
        
        for params in param_combinations:
            combination_count += 1
            try:
                print(f'[{combination_count}/{total_combinations}] 测试 {strategy_name} 参数: {params}')
                
                result = run_backtest(
                    symbol=symbol,
                    strategy_name=strategy_name,
                    start_date=start_date,
                    end_date=end_date,
                    data_type=data_type,
                    initial_cash=initial_cash,
                    commission=commission,
                    printlog=False,  # 批量测试时不打印日志
                    **params
                )
                
                # 添加策略和参数信息
                result['strategy_name'] = strategy_name
                result['strategy_params'] = params
                result['symbol'] = symbol
                
                # 如果没有任何交易，添加警告信息
                if result.get('total_trades', 0) == 0:
                    print(f'  ⚠️ 警告: 此参数组合没有产生任何交易')
                    print(f'     数据点数: {result.get("data_points", 0)}')
                    # 检查是否是数据不足的问题
                    if result.get('data_points', 0) < 50:
                        print(f'     💡 数据可能不足，建议使用更长的日期范围')
                
                results.append(result)
                
            except Exception as e:
                error_msg = str(e)
                print(f'策略 {strategy_name} 参数 {params} 回测失败: {error_msg}')
                # 如果是数据不足的错误，提供更详细的提示
                if 'No daily candle data' in error_msg or 'No data found' in error_msg:
                    print(f'  💡 提示: 请检查日期范围，确保有足够的历史数据')
                continue
    
    return results


def find_best_strategy(results: List[Dict[str, Any]], metric: str = 'total_return_pct') -> Dict[str, Any]:
    """
    从回测结果中找到最佳策略
    
    Args:
        results: 回测结果列表
        metric: 用于排序的指标（'total_return_pct', 'sharpe_ratio', 'annual_return_pct'）
        
    Returns:
        最佳策略的结果字典
    """
    if not results:
        return None
    
    # 过滤掉无效结果
    valid_results = [r for r in results if r.get(metric) is not None]
    
    if not valid_results:
        print(f'Warning: No valid results with {metric}')
        return None
    
    # 检查是否有任何交易发生
    has_trades = any(r.get('total_trades', 0) > 0 for r in valid_results)
    if not has_trades:
        print(f'Warning: No trades occurred in any strategy for {metric}')
        # 即使没有交易，也返回第一个结果，但打印警告
    
    # 如果所有结果的metric值都相同（比如都是0），按total_trades排序
    metric_values = [r.get(metric, 0) for r in valid_results]
    all_same = len(set(metric_values)) == 1
    if all_same and metric == 'total_return_pct':
        # 如果收益率都相同，优先选择有交易的
        print(f'All strategies have same {metric} ({metric_values[0]}), sorting by trades')
        valid_results.sort(key=lambda x: (x.get('total_trades', 0), x.get('sharpe_ratio', -999)), reverse=True)
    
    # 按指标排序
    if metric == 'sharpe_ratio':
        # 夏普比率可能为负，优先选择正值，然后按大小排序
        valid_results.sort(
            key=lambda x: (
                0 if x.get(metric, 0) > 0 else 1,  # 正数优先
                -x.get(metric, -999)  # 降序
            )
        )
    else:
        # 其他指标按降序排序
        valid_results.sort(key=lambda x: x.get(metric, -999), reverse=True)
    
    best = valid_results[0]
    print(f'Best strategy by {metric}: {best.get("strategy_name")}, value: {best.get(metric)}')
    return best


def batch_optimize_all_etfs(
    start_date: str,
    end_date: str,
    initial_cash: float = 100000.0,
    commission: float = 0.001,
    data_type: str = 'daily',
    max_etfs: int = None,  # 限制测试的ETF数量（用于测试）
) -> Dict[str, Any]:
    """
    对所有ETF运行所有策略，找出每个ETF的最佳策略
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        initial_cash: 初始资金
        commission: 手续费率
        data_type: 数据类型
        max_etfs: 最大测试ETF数（None表示全部）
        
    Returns:
        包含所有ETF最佳策略的字典
    """
    from apps.data_master.models import Instrument, Candle
    
    # 获取所有有数据的ETF
    etfs = Instrument.objects.filter(
        market='CN',
        candles__isnull=False
    ).distinct().order_by('symbol')
    
    if max_etfs:
        etfs = etfs[:max_etfs]
    
    print(f'开始批量优化，共 {etfs.count()} 个ETF')
    
    all_results = {}
    summary = []
    
    for etf in etfs:
        symbol = etf.symbol
        print(f'\n{"="*60}')
        print(f'处理 ETF: {symbol} - {etf.name}')
        print(f'{"="*60}')
        
        try:
            # 运行所有策略
            results = batch_backtest_all_strategies(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                commission=commission,
                data_type=data_type,
            )
            
            if not results:
                print(f'ETF {symbol} 没有有效的回测结果')
                continue
            
            # 打印调试信息
            print(f'ETF {symbol} 共有 {len(results)} 个回测结果')
            if results:
                sample = results[0]
                print(f'样本结果字段: {list(sample.keys())}')
                print(f'样本 total_return_pct: {sample.get("total_return_pct")}')
                print(f'样本 total_trades: {sample.get("total_trades")}')
            
            # 找出最佳策略（按总收益率）
            best_by_return = find_best_strategy(results, 'total_return_pct')
            
            # 找出最佳策略（按夏普比率）
            best_by_sharpe = find_best_strategy(results, 'sharpe_ratio')
            
            # 找出最佳策略（按年化收益率）
            best_by_annual = find_best_strategy(results, 'annual_return_pct')
            
            all_results[symbol] = {
                'etf_name': etf.name,
                'all_results': results,
                'best_by_return': best_by_return,
                'best_by_sharpe': best_by_sharpe,
                'best_by_annual': best_by_annual,
            }
            
            # 添加到摘要
            if best_by_return:
                summary.append({
                    'symbol': symbol,
                    'name': etf.name,
                    'best_strategy': best_by_return.get('strategy_name'),
                    'best_params': best_by_return.get('strategy_params'),
                    'total_return': best_by_return.get('total_return_pct', 0),
                    'annual_return': best_by_return.get('annual_return_pct', 0),
                    'sharpe_ratio': best_by_return.get('sharpe_ratio') if best_by_return.get('sharpe_ratio') is not None else 0,
                    'max_drawdown': best_by_return.get('max_drawdown', 0),
                    'total_trades': best_by_return.get('total_trades', 0),
                    'data_points': best_by_return.get('data_points', 0),  # 添加数据点数量用于调试
                })
                # 打印详细信息
                print(f'  - 最佳策略: {best_by_return.get("strategy_name")}')
                print(f'  - 总收益率: {best_by_return.get("total_return_pct", 0):.2f}%')
                print(f'  - 交易次数: {best_by_return.get("total_trades", 0)}')
                print(f'  - 数据点数: {best_by_return.get("data_points", 0)}')
            
            print(f'ETF {symbol} 完成，最佳策略: {best_by_return.get("strategy_name") if best_by_return else "无"}')
            
        except Exception as e:
            print(f'ETF {symbol} 处理失败: {str(e)}')
            import traceback
            traceback.print_exc()
            continue
    
    # 生成汇总报告
    summary_df = pd.DataFrame(summary)
    
    return {
        'summary': summary,
        'summary_df': summary_df,
        'detailed_results': all_results,
        'total_etfs': len(all_results),
        'total_strategies_tested': len(STRATEGY_REGISTRY),
    }


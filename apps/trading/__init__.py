"""
交易模块
包含策略基类、交易网关等
"""
# 延迟导入，避免循环导入问题
__all__ = ['StrategyBase', 'ExecutionGateway']

def __getattr__(name):
    """延迟导入模块"""
    if name == 'StrategyBase':
        from apps.trading.strategy_base import StrategyBase
        return StrategyBase
    elif name == 'ExecutionGateway':
        from apps.trading.execution_gateway import ExecutionGateway
        return ExecutionGateway
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


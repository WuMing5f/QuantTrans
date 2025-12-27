"""
策略基类 (StrategyBase)
所有具体策略必须继承此类，确保回测与实盘代码一致
"""
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
from decimal import Decimal

if TYPE_CHECKING:
    from apps.data_master.models import MarketData


class StrategyBase(ABC):
    """
    策略基类
    
    所有策略必须实现 on_bar 方法，在每分钟K线生成时触发
    """
    
    def __init__(self, name: str, **params):
        """
        初始化策略
        
        Args:
            name: 策略名称
            **params: 策略参数
        """
        self.name = name
        self.params = params
        self.positions = {}  # 持仓信息 {symbol: quantity}
        self.cash = Decimal('0')  # 现金
        self.execution_gateway = None  # 交易网关，由外部注入
    
    def set_execution_gateway(self, gateway):
        """设置交易网关"""
        self.execution_gateway = gateway
    
    @abstractmethod
    def on_bar(self, bar: 'MarketData'):
        """
        每分钟K线生成时触发
        
        Args:
            bar: MarketData对象，包含当前K线的所有信息
        """
        raise NotImplementedError("子类必须实现 on_bar 方法")
    
    def buy(
        self,
        symbol: str,
        price: Optional[Decimal] = None,
        quantity: Optional[Decimal] = None,
        order_type: str = 'MARKET'
    ) -> bool:
        """
        发送买单信号
        
        Args:
            symbol: 代码
            price: 价格（限价单需要，市价单可为None）
            quantity: 数量（如果为None，则使用默认仓位）
            order_type: 订单类型，'MARKET' 或 'LIMIT'
            
        Returns:
            bool: 是否成功下单
        """
        if self.execution_gateway is None:
            raise ValueError("交易网关未设置，请先调用 set_execution_gateway()")
        
        return self.execution_gateway.execute_order(
            strategy_name=self.name,
            symbol=symbol,
            direction='BUY',
            price=price,
            quantity=quantity,
            order_type=order_type
        )
    
    def sell(
        self,
        symbol: str,
        price: Optional[Decimal] = None,
        quantity: Optional[Decimal] = None,
        order_type: str = 'MARKET'
    ) -> bool:
        """
        发送卖单信号
        
        Args:
            symbol: 代码
            price: 价格（限价单需要，市价单可为None）
            quantity: 数量（如果为None，则卖出全部持仓）
            order_type: 订单类型，'MARKET' 或 'LIMIT'
            
        Returns:
            bool: 是否成功下单
        """
        if self.execution_gateway is None:
            raise ValueError("交易网关未设置，请先调用 set_execution_gateway()")
        
        # 如果未指定数量，卖出全部持仓
        if quantity is None:
            quantity = self.positions.get(symbol, Decimal('0'))
        
        if quantity <= 0:
            return False
        
        return self.execution_gateway.execute_order(
            strategy_name=self.name,
            symbol=symbol,
            direction='SELL',
            price=price,
            quantity=quantity,
            order_type=order_type
        )
    
    def get_position(self, symbol: str) -> Decimal:
        """获取持仓数量"""
        return self.positions.get(symbol, Decimal('0'))
    
    def update_position(self, symbol: str, quantity: Decimal):
        """更新持仓"""
        if quantity <= 0:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = quantity
    
    def get_total_equity(self) -> Decimal:
        """计算总资产（持仓市值 + 现金）"""
        # 这里需要根据当前价格计算持仓市值
        # 简化版本，只返回现金
        return self.cash


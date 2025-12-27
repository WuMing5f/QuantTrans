"""
交易网关 (ExecutionGateway)
支持"实盘模式"和"模拟模式"切换
"""
from typing import Optional
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

from apps.data_master.models import TradeRecord, MarketData


class ExecutionGateway:
    """
    交易网关
    
    功能：
    1. 实盘模式：对接 uSmart 交易接口
    2. 模拟模式：仅在数据库写入 TradeRecord，模拟扣费和滑点
    """
    
    def __init__(self, mode: str = 'simulation', **kwargs):
        """
        初始化交易网关
        
        Args:
            mode: 模式，'simulation' (模拟) 或 'live' (实盘)
            **kwargs: 其他参数
                - commission_rate: 手续费率，默认0.001 (0.1%)
                - slippage: 滑点比例，默认0.0005 (0.05%)
        """
        self.mode = mode
        self.commission_rate = kwargs.get('commission_rate', Decimal('0.001'))
        self.slippage = kwargs.get('slippage', Decimal('0.0005'))
        
        # 实盘模式需要配置API密钥等
        if mode == 'live':
            self.api_key = kwargs.get('api_key')
            self.api_secret = kwargs.get('api_secret')
            # TODO: 初始化 uSmart SDK
    
    def execute_order(
        self,
        strategy_name: str,
        symbol: str,
        direction: str,
        price: Optional[Decimal] = None,
        quantity: Optional[Decimal] = None,
        order_type: str = 'MARKET',
        exchange: str = ''
    ) -> bool:
        """
        执行订单
        
        Args:
            strategy_name: 策略名称
            symbol: 代码
            direction: 方向，'BUY' 或 'SELL'
            price: 价格（限价单需要）
            quantity: 数量
            order_type: 订单类型，'MARKET' 或 'LIMIT'
            exchange: 交易所
            
        Returns:
            bool: 是否成功
        """
        if self.mode == 'simulation':
            return self._execute_simulation_order(
                strategy_name=strategy_name,
                symbol=symbol,
                direction=direction,
                price=price,
                quantity=quantity,
                order_type=order_type,
                exchange=exchange
            )
        else:
            return self._execute_live_order(
                strategy_name=strategy_name,
                symbol=symbol,
                direction=direction,
                price=price,
                quantity=quantity,
                order_type=order_type,
                exchange=exchange
            )
    
    def _execute_simulation_order(
        self,
        strategy_name: str,
        symbol: str,
        direction: str,
        price: Optional[Decimal],
        quantity: Optional[Decimal],
        order_type: str,
        exchange: str
    ) -> bool:
        """
        模拟模式：执行订单（只写入数据库，不实际下单）
        """
        # 获取最新价格（用于市价单）
        if price is None:
            try:
                latest_bar = MarketData.objects.filter(
                    symbol=symbol,
                    exchange=exchange
                ).order_by('-datetime').first()
                
                if latest_bar is None:
                    return False
                
                price = latest_bar.close_price
            except Exception:
                return False
        
        # 应用滑点
        if direction == 'BUY':
            # 买入时，价格向上滑点
            execution_price = price * (Decimal('1') + self.slippage)
        else:
            # 卖出时，价格向下滑点
            execution_price = price * (Decimal('1') - self.slippage)
        
        # 计算手续费
        total_amount = execution_price * quantity
        fee = total_amount * self.commission_rate
        
        # 创建交易记录
        trade_record = TradeRecord.objects.create(
            strategy_name=strategy_name,
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            order_type=order_type,
            price=execution_price,
            quantity=quantity,
            fee=fee,
            is_backtest=False,  # 模拟模式不算回测
            remark=f'模拟交易 - {order_type}'
        )
        
        return True
    
    def _execute_live_order(
        self,
        strategy_name: str,
        symbol: str,
        direction: str,
        price: Optional[Decimal],
        quantity: Optional[Decimal],
        order_type: str,
        exchange: str
    ) -> bool:
        """
        实盘模式：执行订单（对接 uSmart SDK）
        """
        # TODO: 实现 uSmart SDK 对接
        # 1. 构建订单请求
        # 2. 调用 uSmart API
        # 3. 获取订单ID
        # 4. 创建 TradeRecord 记录
        
        try:
            # 示例代码（需要根据实际 uSmart SDK 调整）
            # from usmart_sdk import USmartClient
            # client = USmartClient(api_key=self.api_key, api_secret=self.api_secret)
            # order_result = client.place_order(
            #     symbol=symbol,
            #     side=direction,
            #     order_type=order_type,
            #     quantity=quantity,
            #     price=price
            # )
            # 
            # TradeRecord.objects.create(
            #     strategy_name=strategy_name,
            #     symbol=symbol,
            #     exchange=exchange,
            #     direction=direction,
            #     order_type=order_type,
            #     price=Decimal(str(order_result['price'])),
            #     quantity=Decimal(str(order_result['quantity'])),
            #     fee=Decimal(str(order_result['fee'])),
            #     is_backtest=False,
            #     order_id=order_result['order_id']
            # )
            
            # 临时返回 False，等待实际实现
            return False
        except Exception as e:
            print(f"实盘下单失败: {e}")
            return False
    
    def get_balance(self) -> Decimal:
        """获取账户余额"""
        if self.mode == 'simulation':
            # 模拟模式：从数据库计算
            # TODO: 实现余额计算逻辑
            return Decimal('100000')  # 默认10万
        else:
            # 实盘模式：从 uSmart API 获取
            # TODO: 实现 API 调用
            return Decimal('0')


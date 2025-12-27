"""
成交量方向估算器 (VolumeEstimator)
使用 Tick Rule 算法估算主动买入量和成交量方向
"""
from typing import Tuple, Optional
import numpy as np


class VolumeEstimator:
    """
    成交量方向估算器
    
    算法：Tick Rule（价格变化规则）
    - 如果当前价格 > 前一个价格，认为是主动买入
    - 如果当前价格 < 前一个价格，认为是主动卖出
    - 如果价格相等，使用前一个方向或中性
    """
    
    def __init__(self, buy_ratio: float = 0.6):
        """
        初始化估算器
        
        Args:
            buy_ratio: 当价格上升时，估算的主动买入比例（默认0.6，即60%）
        """
        self.buy_ratio = buy_ratio
        self.last_direction = 0  # 记录上一个方向，用于价格不变时
    
    def estimate(
        self,
        current_price: float,
        prev_price: float,
        volume: float
    ) -> Tuple[int, Optional[float]]:
        """
        估算成交量方向
        
        Args:
            current_price: 当前价格
            prev_price: 前一个价格
            volume: 当前成交量
            
        Returns:
            Tuple[int, Optional[float]]: (方向, 主动买入量)
            - 方向: 1 (买入占优), -1 (卖出占优), 0 (中性)
            - 主动买入量: 估算的主动买入量，如果无法估算则为None
        """
        if prev_price == 0:
            return (0, None)
        
        price_change = current_price - prev_price
        
        if price_change > 0:
            # 价格上涨，认为是主动买入占优
            direction = 1
            taker_buy_volume = volume * self.buy_ratio
            self.last_direction = 1
        elif price_change < 0:
            # 价格下跌，认为是主动卖出占优
            direction = -1
            taker_buy_volume = volume * (1 - self.buy_ratio)
            self.last_direction = -1
        else:
            # 价格不变，使用上一个方向或中性
            direction = self.last_direction
            if direction == 1:
                taker_buy_volume = volume * self.buy_ratio
            elif direction == -1:
                taker_buy_volume = volume * (1 - self.buy_ratio)
            else:
                taker_buy_volume = volume * 0.5  # 中性，各占50%
        
        return (direction, taker_buy_volume)
    
    def estimate_batch(
        self,
        prices: list,
        volumes: list
    ) -> Tuple[list, list]:
        """
        批量估算成交量方向
        
        Args:
            prices: 价格列表
            volumes: 成交量列表
            
        Returns:
            Tuple[list, list]: (方向列表, 主动买入量列表)
        """
        directions = []
        taker_buy_volumes = []
        
        for i in range(len(prices)):
            if i == 0:
                directions.append(0)
                taker_buy_volumes.append(None)
            else:
                direction, taker_buy_vol = self.estimate(
                    current_price=prices[i],
                    prev_price=prices[i - 1],
                    volume=volumes[i]
                )
                directions.append(direction)
                taker_buy_volumes.append(taker_buy_vol)
        
        return (directions, taker_buy_volumes)


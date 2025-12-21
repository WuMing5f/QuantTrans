from .base import DataProvider
from .us_yahoo import YahooUSProvider
from .cn_akshare import AkShareCNProvider


def get_provider(market: str) -> DataProvider:
    """工厂函数：根据市场类型返回对应的数据提供者"""
    providers = {
        'US': YahooUSProvider,
        'CN': AkShareCNProvider,
    }
    provider_class = providers.get(market.upper())
    if not provider_class:
        raise ValueError(f"Unsupported market: {market}")
    return provider_class()


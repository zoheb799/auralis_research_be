import httpx

from app.core.config import Settings
from app.integrations.market_data.errors import ProviderConfigurationError
from app.integrations.market_data.base import (
    IPODataProvider,
    MutualFundDataProvider,
    StockDataProvider,
)
from app.integrations.market_data.providers.mfapi import MFAPIProvider
from app.integrations.market_data.providers.alpha_vantage import (
    AlphaVantageFundamentalsProvider,
)
from app.integrations.market_data.providers.bharatstock import (
    BharatStockFundamentalsProvider,
)
from app.integrations.market_data.providers.nse import (
    NSEEquityCatalogProvider,
)
from app.integrations.market_data.providers.tejhq import TejHQProvider
from app.integrations.market_data.providers.xflot import XflotProvider


StockFundamentalsProvider = (
    AlphaVantageFundamentalsProvider | BharatStockFundamentalsProvider
)


class MarketDataProviderRegistry:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    def stocks(self) -> StockDataProvider:
        if self.settings.market_data_stock_provider.lower() != "tejhq":
            raise ProviderConfigurationError(
                "Unsupported stock provider; configured provider must implement stocks"
            )
        return TejHQProvider(self.settings, self.http_client)

    def stock_catalog(self) -> NSEEquityCatalogProvider:
        return NSEEquityCatalogProvider(self.http_client)

    def stock_fundamentals(self) -> StockFundamentalsProvider:
        provider = self.settings.market_data_fundamentals_provider.lower()
        if provider == "bharatstock":
            return BharatStockFundamentalsProvider(
                self.settings,
                self.http_client,
            )
        if provider == "alphavantage":
            return AlphaVantageFundamentalsProvider(
                self.settings,
                self.http_client,
            )
        raise ProviderConfigurationError(
            "Unsupported stock fundamentals provider"
        )

    def ipos(self) -> IPODataProvider:
        if self.settings.market_data_ipo_provider.lower() != "xflot":
            raise ProviderConfigurationError(
                "Unsupported IPO provider; configured provider must implement IPOs"
            )
        return XflotProvider(self.settings, self.http_client)

    def mutual_funds(self) -> MutualFundDataProvider:
        if self.settings.market_data_mutual_fund_provider.lower() != "mfapi":
            raise ProviderConfigurationError(
                "Unsupported mutual-fund provider; configured provider must implement NAV"
            )
        return MFAPIProvider(self.settings, self.http_client)
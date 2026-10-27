from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Auralis Backend"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str
    jwt_secret_key: str
    x_api_key: str | None = None
    ai_provider: str = "gemini"
    llm_api_key: str | None = None
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    llm_model: str = "gemini-3.5-flash-lite"
    llm_timeout: float = 60.0
    market_data_sync_enabled: bool = False
    market_data_stock_provider: str = "tejhq"
    market_data_ipo_provider: str = "xflot"
    market_data_mutual_fund_provider: str = "mfapi"
    market_data_cron_secret: str | None = None
    market_data_request_timeout: float = 15.0
    market_data_max_retries: int = 3
    market_data_max_concurrency: int = 5
    market_data_quote_batch_size: int = 500
    market_data_stock_sync_limit: int = 500
    market_data_mf_discovery_limit: int = 100
    market_data_ipo_max_records: int = 100
    market_data_stock_symbols: str = ""
    market_data_eod_lookback_days: int = 7
    tejhq_api_base_url: str = "https://api.tejhq.dev"
    xflot_api_base_url: str = "https://www.xflot.com"
    mfapi_base_url: str = "https://api.mfapi.in"
    alpha_vantage_api_key: str | None = None
    alpha_vantage_base_url: str = "https://www.alphavantage.co/query"
    alpha_vantage_exchange_suffix: str = ".BSE"
    alpha_vantage_daily_request_limit: int = 25
    market_data_fundamentals_provider: str = "bharatstock"
    bharatstock_api_key: str | None = None
    bharatstock_base_url: str = "https://bharatstockapi.com"
    bharatstock_daily_request_limit: int = 60
    upstox_access_token: str | None = None
    market_data_stock_instrument_keys: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
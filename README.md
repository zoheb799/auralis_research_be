# Auralis Market Data Sync

Market-data writes are isolated from the existing database read and AI services. Provider adapters normalize responses; `MarketDataSyncService` resolves provider identifiers and writes to the existing asset and price models. Internal stock responses include additive `price_data_type` and `price_interval` fields so EOD observations are not represented as live quotes.

## Deploying to Render

The root `render.yaml` configures a free Python web service. On each service start, Render runs `alembic upgrade head` first; Uvicorn only starts if the migrations succeed. Do not use `--reload` in production; it is intended for local development.

Create the service from the repository using Render's Blueprint flow, then set `DATABASE_URL` to the hosted PostgreSQL connection string in the Render dashboard. This project uses `asyncpg` for the API and converts the URL to `psycopg2` for Alembic, so use the normal PostgreSQL URL form, for example `postgresql+asyncpg://...`. Keep database credentials and other secrets in Render's environment settings, not in the repository or `.env`.

The Blueprint generates `JWT_SECRET_KEY` and `X_API_KEY`. Clients must send the configured `X-API-Key` header for protected API routes. If the AI endpoints are needed, also set `LLM_API_KEY` in Render to the key for the configured AI provider.

Local development remains separate: start the API with `uvicorn app.main:app --reload` and apply migrations with `alembic upgrade head` after setting local environment variables and starting PostgreSQL.

## Combined market-data sync

Call `POST /api/v1/internal/market-data/sync/all?discover=true&discovery_offset=0` with the `X-Cron-Secret` header. The endpoint returns `202 Accepted` with a `job_id` instead of waiting for all providers to finish. Poll `GET /api/v1/internal/market-data/sync/status` with the same header to follow the combined and individual job statuses; the combined job becomes `success` or `failed` when its child syncs finish. Apply migrations before deploying this behavior.

The sync runs as an in-process FastAPI background task, not a durable queue. If the Render instance restarts while the work is running, the task may be interrupted; call the endpoint again after restart. Use a persistent worker/queue if syncs must survive service restarts.

## Providers

- **Stocks: TejHQ.** Uses the keyless `GET /v1/ohlcv/{exchange}/{symbol}` endpoint at `https://api.tejhq.dev`, with documented `from` and `to` date parameters. Response rows contain trading date and OHLCV values. The close is stored as `observation_type=eod`, `interval=1d`; the provider returns a date, so `price_timestamp` is that trading date at midnight IST as the daily identity key. This is end-of-day data, not intraday or live data. TejHQ says its feed refreshes around 18:30 IST on trading days, with a retry around 21:30 IST.
- **IPOs: Xflot.** Uses `GET /api/public/market/ipos` at `https://www.xflot.com` with `limit` up to 200. Records are keyed by `slug`; mapped fields are name, status, price band, lot size, issue size in crore, and open/close dates. Its response disclaimer and Xflot attribution are stored and exposed in IPO list/detail responses. GMP and subscription data are deliberately ignored; GMP is unofficial and is not stored as verified market data.
- **Mutual funds: MFAPI.** Uses paginated `GET /mf?limit=...&offset=...` and `GET /mf/{scheme_code}/latest`. Scheme code is the primary identifier; supplied ISINs are aliases. NAV is a daily publication, not an intraday quote.
- **Stock fundamentals: BharatStock API by default.** Uses the stock detail endpoint for market cap (derived from price and shares outstanding), P/E, EPS, dividend yield, book value, debt/equity, and ROE, plus the annual financial-statement endpoint for available periods. Source dates, provider, and missing fields are recorded; a null provider value does not erase an existing value. The free plan documents 60 requests per UTC day and two annual periods, so a full backfill takes multiple days and later syncs resume from saved per-stock state. Alpha Vantage remains available as an explicitly selected alternative, but Indian-symbol coverage and exchange suffixes must be verified for that account.

Provider modules are in `app/integrations/market_data/providers`. Capability-specific interfaces are in `base.py`; register another adapter in `MarketDataProviderRegistry` without changing the sync or AI read services.

## Provider Terms

TejHQ documents the OHLCV endpoint as keyless. Its pricing page distinguishes the free/open tier from Pro, which is explicitly described for commercial use. Confirm the appropriate commercial API terms for an Auralis SaaS before customer-facing distribution; the open-source pipeline license alone does not grant API usage rights.

Xflot documents its public API as free and unauthenticated, requires attribution with a link, requires carrying the API disclaimer, and says to poll no more than once per minute. The integration enforces the one-minute minimum and returns `429` with `Retry-After`. Its terms warn that data can be delayed, incomplete, or wrong and prohibit bulk republication of paid data. Confirm rights for your intended product use.

MFAPI documents no authentication and rate limiting, and asks clients to cache appropriately. Its documentation does not establish a commercial redistribution license or SLA; confirm before exposing data to customers. Provider terms can change, so recheck them before deployment.

BharatStock's documented free plan is limited to 60 requests per UTC day and allows display inside your application to your own end-users. It prohibits reselling or bulk-redistributing its raw data; exchange-sourced data may require a separate exchange redistribution license. Review its current [API reference](https://bharatstockapi.com/reference) and [terms](https://bharatstockapi.com/terms) before deployment.

## Configuration

Copy the market-data settings from `.env.example` into the project-root `.env`. Existing `DATABASE_URL`, `JWT_SECRET_KEY`, and normal application `X_API_KEY` settings remain application requirements. **No Upstox account, brokerage login, token, or API key is used.** TejHQ's selected endpoint, Xflot's public IPO list, and MFAPI do not require provider credentials. Cron authentication uses your own `MARKET_DATA_CRON_SECRET`. Set `MARKET_DATA_FUNDAMENTALS_PROVIDER=bharatstock` and add a BharatStock API key to `BHARATSTOCK_API_KEY` in local configuration and Render secrets before enabling fundamentals sync.

BharatStock Free allows 60 requests per UTC day. This sync reserves two requests per stock (detail and annual statements), so it processes at most 30 stocks per UTC day and resumes on later runs. Successful records become eligible for a daily refresh; with the current 2,364-stock local catalog, one full pass takes about 79 days if no other calls share that API key's quota. The free plan returns two years of annual history. A lower or higher quota can be configured with `BHARATSTOCK_DAILY_REQUEST_LIMIT`, but never set it above the provider account entitlement. Alpha Vantage is available by setting `MARKET_DATA_FUNDAMENTALS_PROVIDER=alphavantage`; its free limit is 25 requests per day, with three reserved per stock. Unsupported symbols are skipped and retried after 90 days; provider/network errors remain eligible for a later retry.

The stock catalog is imported from the NSE equity master CSV during `POST /api/v1/internal/market-data/sync/stocks?discover=true` or `POST /api/v1/internal/market-data/sync/all`. Import adds or refreshes all current NSE `EQ`-series assets and ensures each has a `stocks` row, then links TejHQ identifiers in bounded batches. `MARKET_DATA_STOCK_SYNC_LIMIT` bounds each discovery batch and the number of stocks whose prices are fetched per run. The same request then syncs prices for up to that many linked stocks. The import is additive and does not delete assets that are no longer in the NSE master. The NSE master does not provide sector data, so existing sectors are left unchanged and new assets' sectors are empty. This covers NSE `EQ`-series listings, not BSE or other NSE series; TejHQ may not return observations for every symbol. Provider identity is stored as provider + exchange scope + symbol, without replacing the internal UUID. The old `MARKET_DATA_STOCK_SYMBOLS` setting is ignored and may be removed from local `.env` files when convenient.

## Migration

Apply all unapplied market-data migrations, including IPO provenance and fundamentals quota/progress tracking:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

The market-data migrations are additive; fundamentals migrations add per-asset progress, daily API-usage tracking, source provenance, and annual-period idempotency while preserving legacy rows. Do not run a downgrade in production without a backup and an explicit data-retention review.

## Discovery And Sync

1. For a one-call bootstrap/refresh of all catalogs and their available data, run `POST /api/v1/internal/market-data/sync/all`. Discovery is enabled by default on this combined endpoint: it imports the NSE stock catalog, discovers a bounded page of MFAPI schemes, refreshes the Xflot IPO catalog, and syncs available stock prices, MF NAVs, and eligible stock fundamentals. The stock job response reports `catalog_assets_inserted`, `catalog_assets_updated`, and `catalog_stock_records_inserted`. `MARKET_DATA_MF_DISCOVERY_LIMIT` bounds fund discovery and `discovery_offset` can be used on `/sync/all` to discover later pages. Routine EOD updates can use `POST /api/v1/internal/market-data/sync/all?discover=false`.
2. Run `POST /api/v1/internal/market-data/sync/mutual-funds?discover=true&discovery_offset=0` to import up to `MARKET_DATA_MF_DISCOVERY_LIMIT` schemes. Continue with the next offset for later pages.
3. Run `POST /api/v1/internal/market-data/sync/ipos` to refresh the bounded Xflot IPO catalog.
4. `POST /api/v1/internal/market-data/sync/all` runs the stock, IPO, mutual-fund, and fundamentals jobs sequentially and discovers catalogs by default. Use `?discover=false` to sync only previously discovered stocks and funds.

Run `POST /api/v1/internal/market-data/sync/fundamentals` to update linked stock fundamentals independently. It uses the same resumable daily request budget as `/sync/all`; responses include `requests_used` and `request_budget_remaining`. Add `?symbol=RELIANCE&exchange=NSE&limit=1` to target a stock, or use `?force_refresh=true` to refresh eligible rows regardless of their last attempt. A missing provider key is reported as an error rather than a successful empty result.

For safe, filtered backfills use the CLI from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\sync_stock_fundamentals.py --dry-run
.\.venv\Scripts\python.exe scripts\sync_stock_fundamentals.py --limit 10
.\.venv\Scripts\python.exe scripts\sync_stock_fundamentals.py --symbol RELIANCE --exchange NSE
.\.venv\Scripts\python.exe scripts\sync_stock_fundamentals.py --retry-failed
.\.venv\Scripts\python.exe scripts\sync_stock_fundamentals.py --force-refresh --limit 5
```

The CLI supports `--provider bharatstock|alphavantage`, `--symbol`, `--exchange NSE|BSE`, `--limit`, `--retry-failed`, and `--force-refresh`. It never deletes records. The old `scripts/seed_stocks.py` and `scripts/seed_market_data.py` demo seeders are disabled because they deleted market data and generated synthetic values.

Price history upserts on asset, provider, observation type, interval, and provider trading timestamp; repeated EOD data updates the same daily observation rather than creating duplicates. MFAPI NAV history uses the same observation table with `observation_type=nav`, `interval=daily`. Network calls are bounded and occur before database writes. PostgreSQL advisory locks prevent overlapping jobs across workers; sync summaries and last success are retained in `market_data_sync_state`.

## Cron And Freshness

Each internal route requires `X-Cron-Secret`, separate from user JWTs and the app's `X-API-Key`:

```sh
curl -X POST "$AURALIS_URL/api/v1/internal/market-data/sync/stocks" \
  -H "X-Cron-Secret: $MARKET_DATA_CRON_SECRET"
```

Recommended starting schedules:

- TejHQ stock EOD: once daily after its documented 18:30 IST publication; a later retry can fill delayed publication. Polling every 5 minutes does not create intraday data.
- MFAPI NAV: once daily after NAV publication.
- Xflot IPO list: every 30–60 minutes; never more frequently than once per minute.
- Discovery: manual, bounded, and separate from routine sync.

The protected `GET /api/v1/internal/market-data/sync/status` reports the latest job state. A successful HTTP response does not make the underlying provider data real-time; inspect `price_data_type` (`eod`) and the observation timestamp. No live quote provider is configured in this initial integration.

## Tests

Tests use mocked HTTP responses and do not require provider credentials or external calls:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_market_data_sync.py -q
```

Historical TejHQ backfills, intraday quotes, MFAPI historical NAV backfills, and Xflot subscription/GMP fields are not implemented. Xflot GMP is intentionally excluded. Alpha Vantage may not cover every NSE/BSE symbol, and fields remain null when the provider does not supply them. One-year return still requires at least 365 days of stored price history; the current TejHQ sync only requests a short recent window, so fundamentals sync alone does not populate that analysis field. Confirm Alpha Vantage terms and Indian exchange coverage before customer-facing use.
#   a u r a l i s _ r e s e a r c h _ b e  
 
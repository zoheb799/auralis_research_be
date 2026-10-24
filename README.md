# Auralis Market Data Sync

Market-data writes are isolated from the existing database read and AI services. Provider adapters normalize responses; `MarketDataSyncService` resolves provider identifiers and writes to the existing asset and price models. Internal stock responses include additive `price_data_type` and `price_interval` fields so EOD observations are not represented as live quotes.

## Deploying to Render

The root `render.yaml` configures a free Python web service. On each service start, Render runs `alembic upgrade head` first; Uvicorn only starts if the migrations succeed. Do not use `--reload` in production; it is intended for local development.

Create the service from the repository using Render's Blueprint flow, then set `DATABASE_URL` to the hosted PostgreSQL connection string in the Render dashboard. This project uses `asyncpg` for the API and converts the URL to `psycopg2` for Alembic, so use the normal PostgreSQL URL form, for example `postgresql+asyncpg://...`. Keep database credentials and other secrets in Render's environment settings, not in the repository or `.env`.

The Blueprint generates `JWT_SECRET_KEY` and `X_API_KEY`. Clients must send the configured `X-API-Key` header for protected API routes. If the AI endpoints are needed, also set `LLM_API_KEY` in Render to the key for the configured AI provider.

Local development remains separate: start the API with `uvicorn app.main:app --reload` and apply migrations with `alembic upgrade head` after setting local environment variables and starting PostgreSQL.

## Providers

- **Stocks: TejHQ.** Uses the keyless `GET /v1/ohlcv/{exchange}/{symbol}` endpoint at `https://api.tejhq.dev`, with documented `from` and `to` date parameters. Response rows contain trading date and OHLCV values. The close is stored as `observation_type=eod`, `interval=1d`; the provider returns a date, so `price_timestamp` is that trading date at midnight IST as the daily identity key. This is end-of-day data, not intraday or live data. TejHQ says its feed refreshes around 18:30 IST on trading days, with a retry around 21:30 IST.
- **IPOs: Xflot.** Uses `GET /api/public/market/ipos` at `https://www.xflot.com` with `limit` up to 200. Records are keyed by `slug`; mapped fields are name, status, price band, lot size, issue size in crore, and open/close dates. Its response disclaimer and Xflot attribution are stored and exposed in IPO list/detail responses. GMP and subscription data are deliberately ignored; GMP is unofficial and is not stored as verified market data.
- **Mutual funds: MFAPI.** Uses paginated `GET /mf?limit=...&offset=...` and `GET /mf/{scheme_code}/latest`. Scheme code is the primary identifier; supplied ISINs are aliases. NAV is a daily publication, not an intraday quote.

Provider modules are in `app/integrations/market_data/providers`. Capability-specific interfaces are in `base.py`; register another adapter in `MarketDataProviderRegistry` without changing the sync or AI read services.

## Provider Terms

TejHQ documents the OHLCV endpoint as keyless. Its pricing page distinguishes the free/open tier from Pro, which is explicitly described for commercial use. Confirm the appropriate commercial API terms for an Auralis SaaS before customer-facing distribution; the open-source pipeline license alone does not grant API usage rights.

Xflot documents its public API as free and unauthenticated, requires attribution with a link, requires carrying the API disclaimer, and says to poll no more than once per minute. The integration enforces the one-minute minimum and returns `429` with `Retry-After`. Its terms warn that data can be delayed, incomplete, or wrong and prohibit bulk republication of paid data. Confirm rights for your intended product use.

MFAPI documents no authentication and rate limiting, and asks clients to cache appropriately. Its documentation does not establish a commercial redistribution license or SLA; confirm before exposing data to customers. Provider terms can change, so recheck them before deployment.

## Configuration

Copy the market-data settings from `.env.example` into the project-root `.env`. Existing `DATABASE_URL`, `JWT_SECRET_KEY`, and normal application `X_API_KEY` settings remain application requirements. **No Upstox account, brokerage login, token, or API key is used.** TejHQ's selected endpoint, Xflot's public IPO list, and MFAPI do not require provider credentials. Cron authentication uses your own `MARKET_DATA_CRON_SECRET`.

Set `MARKET_DATA_SYNC_ENABLED=true` only after confirming provider terms and applying the migration. Keep real secrets out of source control.

The active stock catalog is the TejHQ allowlist. Discovery selects active `Asset` rows with a matching `Stock` record, a symbol, and an NSE/BSE exchange, bounded by `MARKET_DATA_STOCK_SYNC_LIMIT`. Add or deactivate catalog records to control which stocks are synced; the service does not import the whole exchange. TejHQ's per-symbol OHLCV response does not provide enough company metadata to create an unknown asset safely. Provider identity is stored as provider + exchange scope + symbol, without replacing the internal UUID. The old `MARKET_DATA_STOCK_SYMBOLS` setting is ignored and may be removed from local `.env` files when convenient.

## Migration

Apply the additive IPO provenance migration (along with any unapplied market-data migrations):

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

The newest migration only adds nullable `source_attribution` and `source_disclaimer` columns to `ipos`; it does not delete or rewrite existing data. Existing identifier and price-observation migrations add stable provider IDs and an idempotency key while preserving legacy price rows. Do not run a downgrade in production without a backup and an explicit data-retention review.

## Discovery And Sync

1. Ensure the curated stock assets exist and are active in `assets` with corresponding rows in `stocks`. Run `POST /api/v1/internal/market-data/sync/stocks?discover=true` to attach TejHQ identifiers, then run the same endpoint without `discover=true` for EOD updates.
2. Run `POST /api/v1/internal/market-data/sync/mutual-funds?discover=true&discovery_offset=0` to import up to `MARKET_DATA_MF_DISCOVERY_LIMIT` schemes. Continue with the next offset for later pages.
3. Run `POST /api/v1/internal/market-data/sync/ipos` to refresh the bounded Xflot IPO catalog.
4. `POST /api/v1/internal/market-data/sync/all` runs all three sequentially. Discovery remains opt-in.

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

Historical TejHQ backfills, intraday quotes, MFAPI historical NAV backfills, and Xflot subscription/GMP fields are not implemented. Xflot GMP is intentionally excluded, and the existing stock fundamentals remain unchanged because these EOD/IPO/NAV endpoints do not provide those values.
#   a u r a l i s _ r e s e a r c h _ b e  
 
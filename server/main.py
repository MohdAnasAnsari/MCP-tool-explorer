from fastmcp import FastMCP
from tools import (
    _fetch_weather, _fetch_country, _fetch_crypto, _fetch_crypto_history,
    _fetch_ip, _fetch_news, _fetch_github, _fetch_exchange_rates, _fetch_stock,
)
from db_tool import (
    _fetch_db_status, _fetch_db_tables,
    _fetch_table_schema, _run_dialer_query,
)

mcp = FastMCP(
    name="Free API Tools Server",
    instructions=(
        "10 tools: Weather, Country+WorldBank, Crypto spot+history, "
        "IP geo, Hacker News, GitHub, Exchange rates, Stocks (Yahoo Finance), "
        "and Dialer DB (read-only PostgreSQL)."
    ),
)

# ── Public API tools ──────────────────────────────────────────────────────────

@mcp.tool()
async def get_weather(city: str, country: str, date: str) -> dict:
    """Get weather for a city on a date (historical 1940+ or forecast 16 days)."""
    return await _fetch_weather(city, country, date)


@mcp.tool()
async def get_country_info(name: str) -> dict:
    """Get country details, World Bank indicators, and major defense/tech companies."""
    return await _fetch_country(name)


@mcp.tool()
async def get_crypto_price(coin_id: str, vs_currency: str = "usd") -> dict:
    """Get current spot price, market cap, 24h volume and change via CoinGecko."""
    return await _fetch_crypto(coin_id, vs_currency)


@mcp.tool()
async def get_crypto_history(coin_id: str, vs_currency: str = "usd", days: int = 30) -> dict:
    """Get historical price series and period stats for a crypto (1–365 days)."""
    return await _fetch_crypto_history(coin_id, vs_currency, days)


@mcp.tool()
async def get_ip_info(ip: str) -> dict:
    """Get geolocation and ISP info for an IP address. Use 'self' for the server's IP."""
    return await _fetch_ip(ip)


@mcp.tool()
async def get_top_news(count: int = 10) -> list:
    """Fetch top stories from Hacker News (1–30 stories)."""
    return await _fetch_news(count)


@mcp.tool()
async def get_github_repo(owner: str, repo: str) -> dict:
    """Get public GitHub repo info including a README snippet."""
    return await _fetch_github(owner, repo)


@mcp.tool()
async def get_exchange_rates(base_currency: str = "USD") -> dict:
    """Get live exchange rates for a base currency (open.er-api.com, free)."""
    return await _fetch_exchange_rates(base_currency)


@mcp.tool()
async def get_stock_data(symbol: str, period: str = "1mo") -> dict:
    """Get stock price history from Yahoo Finance. Period: 1d 5d 1mo 3mo 6mo 1y 2y 5y ytd max."""
    return await _fetch_stock(symbol, period)


# ── Dialer DB tools (read-only PostgreSQL) ────────────────────────────────────

@mcp.tool()
async def get_db_status() -> dict:
    """Test the remote dialer database connection and return server info."""
    return await _fetch_db_status()


@mcp.tool()
async def list_db_tables() -> list:
    """List all tables in the dialer database with their sizes and approximate row counts."""
    return await _fetch_db_tables()


@mcp.tool()
async def get_table_schema(table_name: str) -> list:
    """Return the column definitions for a given table in the dialer database."""
    return await _fetch_table_schema(table_name)


@mcp.tool()
async def query_dialer(sql: str, limit: int = 200) -> dict:
    """Run a read-only SELECT query against the dialer database. Max 200 rows."""
    return await _run_dialer_query(sql, limit)


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8000)

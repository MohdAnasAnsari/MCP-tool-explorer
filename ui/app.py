import nest_asyncio
nest_asyncio.apply()

import asyncio
import json
import os
from datetime import datetime, timedelta, date as date_type

from openai import OpenAI
import httpx
import pandas as pd
import plotly.express as px
import requests as _requests
import streamlit as st
from mcp.client.sse import sse_client
from mcp import ClientSession

MCP_SERVER_URL   = os.environ.get("MCP_SERVER_URL",   "http://localhost:8000/sse")
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8001")
OPENAI_API_KEY   = os.environ.get("OPENAI_API_KEY", "")
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY",   "")
_AI_KEY   = GROQ_API_KEY or OPENAI_API_KEY
_AI_BASE  = "https://api.groq.com/openai/v1" if GROQ_API_KEY else None
_AI_MODEL = "llama-3.3-70b-versatile" if GROQ_API_KEY else "gpt-4o-mini"

# ── Static hint data ──────────────────────────────────────────────────────────

POPULAR_COINS = [
    ("bitcoin",     "Bitcoin",       "BTC",  "🟡"),
    ("ethereum",    "Ethereum",      "ETH",  "🔷"),
    ("binancecoin", "BNB",           "BNB",  "🟡"),
    ("solana",      "Solana",        "SOL",  "🟣"),
    ("ripple",      "XRP",           "XRP",  "🔵"),
    ("cardano",     "Cardano",       "ADA",  "🔵"),
    ("dogecoin",    "Dogecoin",      "DOGE", "🐶"),
    ("polkadot",    "Polkadot",      "DOT",  "🟣"),
    ("chainlink",   "Chainlink",     "LINK", "🔵"),
    ("litecoin",    "Litecoin",      "LTC",  "⚪"),
    ("avalanche-2", "Avalanche",     "AVAX", "🔴"),
    ("polygon",     "Polygon",       "MATIC","🟣"),
    ("stellar",     "Stellar",       "XLM",  "⚫"),
    ("uniswap",     "Uniswap",       "UNI",  "🩷"),
    ("cosmos",      "Cosmos",        "ATOM", "🔵"),
    ("monero",      "Monero",        "XMR",  "🟠"),
    ("bitcoin-cash","Bitcoin Cash",  "BCH",  "🟢"),
    ("near",        "NEAR Protocol", "NEAR", "⚫"),
    ("filecoin",    "Filecoin",      "FIL",  "🔵"),
    ("tron",        "TRON",          "TRX",  "🔴"),
    ("__custom__",  "Other (enter manually)", "", "✏️"),
]

POPULAR_STOCKS = [
    ("AAPL",     "Apple Inc.",                "Technology"),
    ("MSFT",     "Microsoft",                 "Technology"),
    ("GOOGL",    "Alphabet (Google)",         "Technology"),
    ("AMZN",     "Amazon",                    "E-commerce"),
    ("NVDA",     "NVIDIA",                    "Semiconductors"),
    ("META",     "Meta Platforms",            "Social Media"),
    ("TSLA",     "Tesla",                     "EV / Energy"),
    ("JPM",      "JPMorgan Chase",            "Finance"),
    ("NFLX",     "Netflix",                   "Streaming"),
    ("SHOP",     "Shopify",                   "E-commerce"),
    ("COIN",     "Coinbase",                  "Crypto"),
    ("LMT",      "Lockheed Martin",           "Defense"),
    ("RTX",      "Raytheon Technologies",     "Defense"),
    ("BA",       "Boeing",                    "Aerospace"),
    ("TSM",      "TSMC",                      "Semiconductors"),
    ("BABA",     "Alibaba",                   "E-commerce CN"),
    ("TCS.NS",   "Tata Consultancy (India)",  "IT Services"),
    ("INFY",     "Infosys (India)",           "IT Services"),
    ("__custom__","Other (enter manually)",   ""),
]

POPULAR_REPOS = [
    ("microsoft",    "vscode",            "Visual Studio Code editor"),
    ("torvalds",     "linux",             "Linux kernel"),
    ("tensorflow",   "tensorflow",        "TensorFlow ML framework"),
    ("facebook",     "react",             "React UI library"),
    ("langchain-ai", "langchain",         "LangChain LLM framework"),
    ("openai",       "openai-python",     "OpenAI Python SDK"),
    ("huggingface",  "transformers",      "HuggingFace Transformers"),
    ("kubernetes",   "kubernetes",        "Kubernetes orchestration"),
    ("django",       "django",            "Django web framework"),
    ("fastapi",      "fastapi",           "FastAPI web framework"),
]

IP_EXAMPLES = [
    ("8.8.8.8",        "Google Public DNS"),
    ("1.1.1.1",        "Cloudflare DNS"),
    ("208.67.222.222", "OpenDNS"),
    ("9.9.9.9",        "Quad9 DNS"),
    ("151.101.1.1",    "Fastly CDN"),
    ("self",           "This server's own IP"),
]

CURRENCIES = [
    "USD","EUR","GBP","JPY","CHF","CAD","AUD","CNY","INR","BRL",
    "MXN","KRW","SGD","HKD","NOK","SEK","DKK","NZD","ZAR","TRY",
    "AED","SAR","THB","IDR","MYR","PHP","PKR","RUB","EGP","NGN",
]

TOOL_META = {
    "get_weather":        {"emoji": "🌤️", "label": "Weather",        "api": "Open-Meteo"},
    "get_country_info":   {"emoji": "🌍", "label": "Country Info",    "api": "REST Countries + World Bank"},
    "get_crypto_price":   {"emoji": "₿",  "label": "Crypto",          "api": "CoinGecko"},
    "get_ip_info":        {"emoji": "📡", "label": "IP Geolocation",  "api": "IP-API"},
    "get_top_news":       {"emoji": "📰", "label": "Top News",        "api": "Hacker News"},
    "get_github_repo":    {"emoji": "🐙", "label": "GitHub Repo",     "api": "GitHub"},
    "get_exchange_rates": {"emoji": "💱", "label": "Exchange Rates",  "api": "Open ER-API"},
    "get_stock_data":     {"emoji": "📈", "label": "Stocks",          "api": "Yahoo Finance"},
    "dialer_db":          {"emoji": "🗄️", "label": "Dialer DB",       "api": "PostgreSQL (private)"},
}

# ── Agent tool schemas (OpenAI function-calling format) ───────────────────────
AGENT_TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "Get weather forecast or historical weather for any city on a specific date.",
        "parameters": {"type": "object", "required": ["city", "country", "date"],
            "properties": {
                "city":    {"type": "string"},
                "country": {"type": "string"},
                "date":    {"type": "string", "description": "YYYY-MM-DD"},
            }},
    }},
    {"type": "function", "function": {
        "name": "get_country_info",
        "description": "Get country details: population, capital, GDP per capita, military spending, defense and tech companies.",
        "parameters": {"type": "object", "required": ["name"],
            "properties": {"name": {"type": "string"}}},
    }},
    {"type": "function", "function": {
        "name": "get_crypto_price",
        "description": "Get current cryptocurrency price, market cap, 24h volume and change.",
        "parameters": {"type": "object", "required": ["coin_id"],
            "properties": {
                "coin_id":     {"type": "string", "description": "CoinGecko ID e.g. bitcoin, ethereum, solana"},
                "vs_currency": {"type": "string", "default": "usd"},
            }},
    }},
    {"type": "function", "function": {
        "name": "get_crypto_history",
        "description": "Get historical price chart for a cryptocurrency over N days.",
        "parameters": {"type": "object", "required": ["coin_id"],
            "properties": {
                "coin_id":     {"type": "string"},
                "vs_currency": {"type": "string", "default": "usd"},
                "days":        {"type": "integer", "default": 30},
            }},
    }},
    {"type": "function", "function": {
        "name": "get_ip_info",
        "description": "Get geolocation, ISP and timezone info for an IP address.",
        "parameters": {"type": "object", "required": ["ip"],
            "properties": {"ip": {"type": "string"}}},
    }},
    {"type": "function", "function": {
        "name": "get_top_news",
        "description": "Get top stories from Hacker News (tech news).",
        "parameters": {"type": "object",
            "properties": {"count": {"type": "integer", "default": 5}}},
    }},
    {"type": "function", "function": {
        "name": "get_github_repo",
        "description": "Get GitHub repository info: stars, forks, language, license, README.",
        "parameters": {"type": "object", "required": ["owner", "repo"],
            "properties": {
                "owner": {"type": "string"},
                "repo":  {"type": "string"},
            }},
    }},
    {"type": "function", "function": {
        "name": "get_exchange_rates",
        "description": "Get live currency exchange rates for a base currency.",
        "parameters": {"type": "object",
            "properties": {"base_currency": {"type": "string", "default": "USD"}}},
    }},
    {"type": "function", "function": {
        "name": "get_stock_data",
        "description": "Get stock price history and current data from Yahoo Finance.",
        "parameters": {"type": "object", "required": ["symbol"],
            "properties": {
                "symbol": {"type": "string", "description": "Ticker e.g. AAPL, MSFT, TSLA, NVDA"},
                "period": {"type": "string", "default": "1mo",
                           "description": "1d 5d 1mo 3mo 6mo 1y 2y 5y ytd max"},
            }},
    }},
    {"type": "function", "function": {
        "name": "query_app_db",
        "description": (
            "Query the connected PostgreSQL database. Use for ANY question about data "
            "stored in the database — records, aggregations, trends, filtering, joining tables. "
            "The schema is fetched automatically from the connected database."
        ),
        "parameters": {"type": "object", "required": ["question"],
            "properties": {
                "question": {"type": "string",
                             "description": "Plain English description of what data to fetch"},
            }},
    }},
]


# ── CSS ───────────────────────────────────────────────────────────────────────

def inject_css():
    st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    div[data-testid="metric-container"] {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.09);
        border-radius: 12px;
        padding: 14px 18px;
    }
    div[data-testid="metric-container"] label { font-size: 0.78em !important; }
    .tag {
        display: inline-block; background: rgba(88,166,255,0.15);
        color: #58a6ff; border: 1px solid rgba(88,166,255,0.25);
        border-radius: 20px; padding: 2px 11px; margin: 2px; font-size: 0.78em;
    }
    .pill {
        display: inline-block; background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.13); border-radius: 24px;
        padding: 7px 20px; font-size: 1.05em; font-weight: 600;
    }
    .sub-label {
        font-size: 0.75em; text-transform: uppercase;
        letter-spacing: 0.07em; color: #777; margin-bottom: 3px;
    }
    .hint-row {
        font-size: 0.82em; padding: 3px 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        display: flex; gap: 10px;
    }
    .company-chip {
        display: inline-block; background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.1); border-radius: 8px;
        padding: 3px 10px; margin: 2px; font-size: 0.8em;
    }
    .placeholder {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; height: 220px; color: #555;
        font-size: 1.05em; text-align: center;
    }
    .rate-card {
        background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07);
        border-radius: 8px; padding: 8px 12px; text-align: center; font-size: 0.88em;
    }
    .login-box {
        background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px; padding: 32px;
    }
    .claude-box {
        background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.25);
        border-radius: 12px; padding: 16px; margin-top: 12px;
    }
    </style>
    """, unsafe_allow_html=True)


# ── Core helpers ──────────────────────────────────────────────────────────────

def check_server_health() -> bool:
    try:
        with httpx.stream("GET", MCP_SERVER_URL, timeout=2.0) as r:
            return r.status_code == 200
    except Exception:
        return False


async def _call(tool_name: str, arguments: dict):
    async with sse_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


async def _call_many(*calls):
    return await asyncio.gather(*[_call(t, a) for t, a in calls])


def run_tool(tool_name: str, arguments: dict):
    return asyncio.run(_call(tool_name, arguments))


def run_tools(*calls):
    return asyncio.run(_call_many(*calls))


def parse(raw) -> dict | list:
    if hasattr(raw, "content") and raw.content and hasattr(raw.content[0], "text"):
        try:
            return json.loads(raw.content[0].text)
        except json.JSONDecodeError:
            return {"raw": raw.content[0].text}
    return {"raw": str(raw)}


def error_of(result) -> str | None:
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    if isinstance(result, list) and result and isinstance(result[0], dict) and "error" in result[0]:
        return result[0]["error"]
    return None


def wmo_emoji(code: int) -> str:
    if code == 0:            return "☀️"
    if code in (1, 2):       return "🌤️"
    if code == 3:            return "☁️"
    if code in (45, 48):     return "🌫️"
    if 51 <= code <= 67:     return "🌧️"
    if 71 <= code <= 77:     return "❄️"
    if code in (80, 81, 82): return "🌦️"
    if code in (85, 86):     return "🌨️"
    if code in (95, 96, 99): return "⛈️"
    return "🌡️"


# ── Auth service client ───────────────────────────────────────────────────────

def _auth_post(endpoint: str, data: dict, token: str = None) -> dict:
    headers = {"x-auth-token": token} if token else {}
    try:
        r = _requests.post(f"{AUTH_SERVICE_URL}{endpoint}", json=data,
                           headers=headers, timeout=5)
        return {"ok": r.status_code < 300,
                "data": r.json() if r.status_code < 300 else None,
                "error": r.json().get("detail", r.text) if r.status_code >= 300 else ""}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _auth_get(endpoint: str, token: str, params: dict = None) -> dict:
    try:
        r = _requests.get(f"{AUTH_SERVICE_URL}{endpoint}",
                          headers={"x-auth-token": token},
                          params=params, timeout=5)
        return {"ok": r.status_code < 300,
                "data": r.json() if r.status_code < 300 else None,
                "error": r.json().get("detail", r.text) if r.status_code >= 300 else ""}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def verify_session() -> bool:
    token = st.session_state.get("auth_token", "")
    if not token:
        return False
    r = _auth_post("/auth/verify", {"token": token})
    if r["ok"]:
        st.session_state["current_user"] = r["data"]["user"]
        return True
    return False


def do_logout():
    token = st.session_state.get("auth_token", "")
    if token:
        _auth_post("/auth/logout", {"token": token})
    for k in ("auth_token", "current_user", "db_tables_cache", "db_schema_ctx",
              "chat_history", "nl_history", "nl_last_sql", "nl_last_rows"):
        st.session_state.pop(k, None)
    st.rerun()


def audit_log(action: str, resource: str = "", details: dict = None):
    token = st.session_state.get("auth_token", "")
    if not token:
        return
    try:
        _requests.post(f"{AUTH_SERVICE_URL}/audit/log", json={
            "token": token, "action": action,
            "resource": resource, "details": details or {},
        }, timeout=2)
    except Exception:
        pass


def fmt_num(n, dec=2) -> str:
    if n is None: return "N/A"
    if abs(n) >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if abs(n) >= 1_000_000:     return f"{n/1_000_000:.2f}M"
    if abs(n) >= 1_000:         return f"{n:,.{dec}f}"
    return f"{n:.{dec}f}"


# ── Claude AI ─────────────────────────────────────────────────────────────────

def _ai_client():
    if not _AI_KEY:
        return None
    return OpenAI(api_key=_AI_KEY, base_url=_AI_BASE) if _AI_BASE else OpenAI(api_key=_AI_KEY)


def ask_claude(data, question: str) -> str:
    if not _AI_KEY:
        return "⚠️ Add GROQ_API_KEY (free) or OPENAI_API_KEY to your .env file."
    try:
        client = _ai_client()
        data_str = json.dumps(data, indent=2, default=str)[:5000]
        msg = client.chat.completions.create(
            model=_AI_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a sharp data analyst. Analyze the data below and answer the question.\n\n"
                    f"DATA:\n{data_str}\n\n"
                    f"QUESTION: {question}\n\n"
                    "Answer in clear, concise bullet points. Highlight key insights and any red flags."
                ),
            }],
        )
        return msg.choices[0].message.content
    except Exception as e:
        return f"OpenAI error: {e}"


def claude_sql(tables_info: str, question: str) -> str:
    if not _AI_KEY:
        return "-- Add GROQ_API_KEY to .env to use NL→SQL"
    try:
        client = _ai_client()
        msg = client.chat.completions.create(
            model=_AI_MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a PostgreSQL expert. Generate a read-only SELECT query.\n\n"
                    f"Available tables and columns:\n{tables_info}\n\n"
                    f"Request: {question}\n\n"
                    "Return ONLY the SQL query, no explanation, no markdown fences."
                ),
            }],
        )
        return msg.choices[0].message.content.strip()
    except Exception as e:
        return f"-- OpenAI error: {e}"


def render_ask_claude(result, tool_key: str):
    """Universal 'Ask Claude' expander shown below every tool result."""
    if not _AI_KEY:
        return
    with st.expander("🤖 Ask Claude about this data", expanded=False):
        st.caption("Claude reads the result above and answers your question.")
        q_key = f"cq_{tool_key}"
        a_key = f"ca_{tool_key}"
        question = st.text_input(
            "Your question",
            placeholder="What are the key insights? Any risks or opportunities?",
            key=q_key,
        )
        if st.button("Ask Claude ✨", key=f"cb_{tool_key}"):
            with st.spinner("Claude is analyzing…"):
                answer = ask_claude(result, question)
            st.session_state[a_key] = answer
        if st.session_state.get(a_key):
            st.markdown(
                f"<div class='claude-box'>{st.session_state[a_key]}</div>",
                unsafe_allow_html=True,
            )


# ── Graph selector (for DB + any tabular data) ────────────────────────────────

def render_chart(df: pd.DataFrame, key_prefix: str = "chart"):
    if df.empty:
        st.info("No data to chart.")
        return

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    other_cols   = df.select_dtypes(exclude="number").columns.tolist()

    chart_type = st.radio(
        "📊 Display as",
        ["Table", "Bar", "Line", "Area", "Pie", "Scatter"],
        horizontal=True,
        key=f"{key_prefix}_type",
    )

    if chart_type == "Table":
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    if not numeric_cols:
        st.warning("No numeric columns found — showing table instead.")
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    cc1, cc2, cc3 = st.columns(3)
    x_col = cc1.selectbox("X axis", options=df.columns.tolist(),
                           index=0, key=f"{key_prefix}_x")
    y_col = cc2.selectbox("Y axis", options=numeric_cols,
                           index=0, key=f"{key_prefix}_y")
    color_col = cc3.selectbox("Color (optional)",
                               options=["None"] + other_cols,
                               index=0, key=f"{key_prefix}_c")
    color = None if color_col == "None" else color_col

    try:
        if chart_type == "Bar":
            fig = px.bar(df,   x=x_col, y=y_col, color=color, template="plotly_dark")
        elif chart_type == "Line":
            fig = px.line(df,  x=x_col, y=y_col, color=color, template="plotly_dark")
        elif chart_type == "Area":
            fig = px.area(df,  x=x_col, y=y_col, color=color, template="plotly_dark")
        elif chart_type == "Pie":
            fig = px.pie(df,   names=x_col, values=y_col,     template="plotly_dark")
        elif chart_type == "Scatter":
            fig = px.scatter(df, x=x_col, y=y_col, color=color, template="plotly_dark")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            return
        fig.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=380)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render chart: {e}")
        st.dataframe(df, use_container_width=True, hide_index=True)


# ── Form renderers ────────────────────────────────────────────────────────────

def form_weather() -> dict | None:
    with st.form("form_weather"):
        c1, c2 = st.columns(2)
        city    = c1.text_input("City",    value="New Delhi")
        country = c2.text_input("Country", value="India")
        today = datetime.today().date()
        sel_date = st.date_input("📅 Date", value=today,
                                  min_value=date_type(1940, 1, 1),
                                  max_value=today + timedelta(days=16))
        submitted = st.form_submit_button("Get Weather", use_container_width=True, type="primary")
    if submitted:
        if not city.strip() or not country.strip():
            st.warning("Enter both city and country.")
            return None
        return {"city": city.strip(), "country": country.strip(), "date": sel_date.strftime("%Y-%m-%d")}
    return None


def form_country() -> dict | None:
    with st.form("form_country"):
        name = st.text_input("Country Name", value="India")
        st.caption("Fetches World Bank indicators + defense/tech company lists.")
        submitted = st.form_submit_button("Get Country Info", use_container_width=True, type="primary")
    if submitted and name.strip():
        return {"name": name.strip()}
    return None


def form_crypto() -> tuple | None:
    coin_ids   = [c[0] for c in POPULAR_COINS]
    coin_label = {c[0]: f"{c[3]} {c[1]}  ({c[2]})" for c in POPULAR_COINS}
    with st.form("form_crypto"):
        selected = st.selectbox("Select Coin", options=coin_ids,
                                 format_func=lambda x: coin_label.get(x, x))
        custom_id = ""
        if selected == "__custom__":
            custom_id = st.text_input("CoinGecko Coin ID", placeholder="e.g. polkadot, near")
        c1, c2 = st.columns(2)
        currency  = c1.selectbox("Currency", CURRENCIES)
        range_key = c2.radio("Range", ["7D","1M","3M","6M","1Y","Custom"], index=1, horizontal=True)
        days = 30
        if range_key == "Custom":
            dc1, dc2 = st.columns(2)
            sd = dc1.date_input("From", value=datetime.today().date() - timedelta(days=30))
            ed = dc2.date_input("To",   value=datetime.today().date())
            days = max(1, (ed - sd).days)
        else:
            days = {"7D":7,"1M":30,"3M":90,"6M":180,"1Y":365}[range_key]
        submitted = st.form_submit_button("Fetch Crypto Data", use_container_width=True, type="primary")
    if submitted:
        coin_id = (custom_id.strip().lower() if selected == "__custom__" else selected)
        if not coin_id:
            st.warning("Enter a coin ID.")
            return None
        cur = currency.lower()
        return ({"coin_id": coin_id, "vs_currency": cur},
                {"coin_id": coin_id, "vs_currency": cur, "days": days})
    return None


def form_ip() -> dict | None:
    with st.form("form_ip"):
        ip = st.text_input("IP Address", value="8.8.8.8")
        submitted = st.form_submit_button("Look Up IP", use_container_width=True, type="primary")
    with st.expander("📋 Well-known IPs"):
        for addr, label in IP_EXAMPLES:
            st.markdown(f"<div class='hint-row'><code>{addr}</code>"
                        f"<span style='color:#888'>{label}</span></div>", unsafe_allow_html=True)
    if submitted and ip.strip():
        return {"ip": ip.strip()}
    return None


def form_news() -> dict | None:
    with st.form("form_news"):
        count = st.slider("Stories", 1, 30, 10)
        submitted = st.form_submit_button("Fetch Stories", use_container_width=True, type="primary")
    if submitted:
        return {"count": count}
    return None


def form_github() -> dict | None:
    with st.form("form_github"):
        c1, c2 = st.columns(2)
        owner = c1.text_input("Owner", value="microsoft")
        repo  = c2.text_input("Repo",  value="vscode")
        submitted = st.form_submit_button("Get Repo", use_container_width=True, type="primary")
    with st.expander("🔍 Popular repos"):
        for o, r, desc in POPULAR_REPOS:
            st.markdown(f"<div class='hint-row'><code>{o}/{r}</code>"
                        f"<span style='color:#888;font-size:.82em'>{desc}</span></div>",
                        unsafe_allow_html=True)
    if submitted and owner.strip() and repo.strip():
        return {"owner": owner.strip(), "repo": repo.strip()}
    return None


def form_exchange() -> dict | None:
    with st.form("form_exchange"):
        base = st.selectbox("Base Currency", CURRENCIES)
        submitted = st.form_submit_button("Get Rates", use_container_width=True, type="primary")
    if submitted:
        return {"base_currency": base}
    return None


def form_stock() -> dict | None:
    ids    = [s[0] for s in POPULAR_STOCKS]
    labels = {s[0]: f"{s[0]}  —  {s[1]}  ({s[2]})" for s in POPULAR_STOCKS}
    with st.form("form_stock"):
        selected = st.selectbox("Stock", ids, format_func=lambda x: labels.get(x, x))
        custom_sym = ""
        if selected == "__custom__":
            custom_sym = st.text_input("Ticker", placeholder="e.g. AAPL, TSLA")
        period = st.radio("Period", ["5d","1mo","3mo","6mo","1y","2y","5y","ytd"],
                          index=1, horizontal=True)
        submitted = st.form_submit_button("Fetch Stock Data", use_container_width=True, type="primary")
    if submitted:
        sym = (custom_sym.strip().upper() if selected == "__custom__" else selected)
        if not sym:
            st.warning("Enter a symbol.")
            return None
        return {"symbol": sym, "period": period}
    return None


# ── Result renderers ──────────────────────────────────────────────────────────

def render_weather(r: dict):
    code = r.get("weather_code", 0)
    emoji = wmo_emoji(code)
    st.markdown(f"## {emoji} {r.get('city','')}, {r.get('country','')}")
    tag = "📅 Forecast" if r.get("is_forecast") else "🗂️ Historical"
    st.caption(f"{tag}  ·  **{r.get('date','')}**")
    st.divider()
    tmax, tmin = r.get("temp_max_celsius"), r.get("temp_min_celsius")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Max Temp",      f"{tmax}°C" if tmax is not None else "—")
    c2.metric("Min Temp",      f"{tmin}°C" if tmin is not None else "—",
              delta=f"{tmax-tmin:.1f}° range" if tmax and tmin else None)
    c3.metric("Max Wind",      f"{r.get('wind_speed_max_kmh','—')} km/h")
    c4.metric("Precipitation", f"{r.get('precipitation_mm') or 0} mm")
    st.divider()
    ca, cb = st.columns(2)
    with ca:
        st.markdown(f"<div class='pill'>{emoji}&nbsp;{r.get('description','')}</div>",
                    unsafe_allow_html=True)
    with cb:
        sr, ss = r.get("sunrise"), r.get("sunset")
        if sr:
            st.markdown(f"🌅 **Sunrise** `{sr}`  \n🌇 **Sunset** `{ss or '—'}`")


def render_country(r: dict):
    flag = r.get("flag_emoji", "🌍")
    st.markdown(f"## {flag} {r.get('common_name','')}")
    st.caption(r.get("official_name",""))
    st.divider()
    pop, area = r.get("population"), r.get("area_km2")
    c1, c2, c3 = st.columns(3)
    c1.metric("👥 Population", f"{pop:,}"        if pop  else "N/A")
    c2.metric("📍 Capital",    r.get("capital","N/A"))
    c3.metric("📐 Area",       f"{area:,.0f} km²" if area else "N/A")
    gdppc = r.get("gdp_per_capita_usd")
    mil   = r.get("military_spend_pct_gdp")
    ht    = r.get("hitech_exports_pct")
    if any(v is not None for v in [gdppc, mil, ht]):
        st.divider()
        st.markdown("#### 📊 World Bank Indicators")
        e1, e2, e3 = st.columns(3)
        e1.metric("💵 GDP per Capita",       f"${gdppc:,.0f}" if gdppc else "N/A")
        e2.metric("⚔️ Military Spend % GDP", f"{mil:.2f}%"    if mil   else "N/A")
        e3.metric("🔬 Hi-Tech Exports %",    f"{ht:.1f}%"     if ht    else "N/A")
    defense = r.get("defense_companies", [])
    tech    = r.get("tech_companies",    [])
    if defense or tech:
        st.divider()
        col_d, col_t = st.columns(2)
        with col_d:
            st.markdown("#### ⚔️ Defense & Aerospace")
            chips = "".join(f"<span class='company-chip'>🏭 {c}</span>" for c in defense) or "—"
            st.markdown(chips, unsafe_allow_html=True)
        with col_t:
            st.markdown("#### 💻 Technology")
            chips = "".join(f"<span class='company-chip'>🖥️ {c}</span>" for c in tech) or "—"
            st.markdown(chips, unsafe_allow_html=True)


def render_crypto(spot: dict, history: dict):
    coin, currency = spot.get("coin","").capitalize(), spot.get("currency","usd").upper()
    price, change  = spot.get("price"), spot.get("24h_change_percent")
    mcap, vol24    = spot.get("market_cap"), spot.get("24h_volume")
    direction = "📈" if (change or 0) >= 0 else "📉"
    st.markdown(f"## {direction} {coin}")
    st.caption(f"Quoted in **{currency}**  ·  CoinGecko")
    st.divider()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric(f"💰 Price", f"{currency} {price:,.4f}" if price else "N/A",
              delta=f"{change:+.2f}%" if change is not None else None)
    c2.metric("📊 24h Change", f"{change:+.2f}%" if change is not None else "N/A")
    c3.metric("🏦 Market Cap",  fmt_num(mcap) + f" {currency}" if mcap else "N/A")
    c4.metric("📦 24h Volume",  fmt_num(vol24) + f" {currency}" if vol24 else "N/A")
    err_h = error_of(history)
    if err_h:
        st.warning(f"History: {err_h}")
        return
    days = history.get("days", 30)
    chg  = history.get("change_percent", 0)
    hi, lo = history.get("period_high"), history.get("period_low")
    st.divider()
    st.markdown(f"#### 📈 Last **{days} days**")
    h1,h2,h3,h4 = st.columns(4)
    h1.metric("Period High",   f"{hi:,.4f}"   if hi else "N/A")
    h2.metric("Period Low",    f"{lo:,.4f}"   if lo else "N/A")
    h3.metric("Start Price",   f"{history.get('start_price',0):,.4f}")
    h4.metric("Period Change", f"{chg:+.2f}%", delta=f"{chg:+.2f}%")
    series = history.get("series", [])
    if series:
        df = pd.DataFrame(series)[["date","price"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        fig = px.area(df, y="price", template="plotly_dark",
                      labels={"price": f"Price ({currency})", "date": ""})
        fig.update_layout(margin=dict(t=20,b=10,l=10,r=10), height=260)
        st.plotly_chart(fig, use_container_width=True)


def render_ip(r: dict):
    st.markdown(f"## 📡 {r.get('ip','')}")
    st.caption(f"{r.get('city','')} · {r.get('region','')} · {r.get('country','')}")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<p class='sub-label'>Location</p>", unsafe_allow_html=True)
        st.markdown(f"**City** &emsp;&emsp;&emsp; {r.get('city','—')}  \n"
                    f"**Region** &emsp;&emsp; {r.get('region','—')}  \n"
                    f"**Country** &emsp;&nbsp; {r.get('country','—')} `{r.get('country_code','')}`  \n"
                    f"**Coords** &emsp;&emsp;&ensp; {r.get('latitude','')}°, {r.get('longitude','')}°")
    with c2:
        st.markdown("<p class='sub-label'>Network</p>", unsafe_allow_html=True)
        st.markdown(f"**ISP** &emsp;&emsp; {r.get('isp','—')}  \n"
                    f"**Org** &emsp;&emsp; {r.get('org','—')}  \n"
                    f"**Timezone** {r.get('timezone','—')}")


def render_news(stories: list):
    st.markdown(f"## 📰 Top {len(stories)} Hacker News Stories")
    st.divider()
    for i, s in enumerate(stories, 1):
        with st.expander(f"**#{i}** &nbsp; {s.get('title','Untitled')}", expanded=(i == 1)):
            ca, cb, cc = st.columns(3)
            ca.metric("⬆️ Score",    s.get("score", 0))
            cb.metric("💬 Comments", s.get("comments", 0))
            cc.markdown(f"<p class='sub-label'>Author</p>{s.get('by','?')}",
                        unsafe_allow_html=True)
            url = s.get("url") or f"https://news.ycombinator.com/item?id={s.get('id')}"
            st.markdown(f"[🔗 Read story →]({url})")


def render_github(r: dict):
    st.markdown(f"## 🐙 {r.get('full_name','')}")
    if r.get("description"):
        st.info(r["description"])
    st.divider()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("⭐ Stars",       f"{r.get('stars',0):,}")
    c2.metric("🍴 Forks",       f"{r.get('forks',0):,}")
    c3.metric("👁️ Watchers",   f"{r.get('watchers',0):,}")
    c4.metric("🐛 Open Issues", f"{r.get('open_issues',0):,}")
    st.divider()
    ca, cb = st.columns(2)
    with ca:
        st.markdown(f"**💻 Language** &ensp; `{r.get('language') or 'N/A'}`  \n"
                    f"**📄 License** &emsp;&ensp; {r.get('license') or 'N/A'}  \n"
                    f"**🌿 Branch** &emsp;&ensp;&ensp; `{r.get('default_branch','main')}`")
    with cb:
        st.markdown(f"**📅 Created** &emsp; {r.get('created_at','')[:10]}  \n"
                    f"**🔄 Updated** &emsp; {r.get('updated_at','')[:10]}")
        if r.get("homepage"):
            st.markdown(f"**🌐** [{r['homepage']}]({r['homepage']})")
    readme = r.get("readme_snippet")
    if readme:
        st.divider()
        st.markdown("**📄 README Preview**")
        st.markdown(f"<div style='background:rgba(255,255,255,0.04);border-left:3px solid #444;"
                    f"border-radius:4px;padding:10px 14px;font-size:.88em;color:#ccc'>{readme}</div>",
                    unsafe_allow_html=True)
    topics = r.get("topics", [])
    if topics:
        tags = " ".join(f'<span class="tag">{t}</span>' for t in topics)
        st.markdown(f"<p class='sub-label' style='margin-top:12px'>Topics</p>{tags}",
                    unsafe_allow_html=True)
    st.markdown(f"\n[🔗 Open on GitHub →]({r.get('html_url','')})")


def render_exchange(r: dict):
    base, rates = r.get("base","USD"), r.get("major_rates",{})
    st.markdown(f"## 💱 Exchange Rates — **{base}**")
    st.caption(f"Updated: {r.get('updated','')}  ·  {r.get('total_currencies',0)} currencies")
    st.divider()
    items = list(rates.items())
    n = 5
    for row in [items[i:i+n] for i in range(0, len(items), n)]:
        cols = st.columns(n)
        for col, (cur, rate) in zip(cols, row):
            with col:
                fmt = f"{rate:,.4f}" if rate < 1000 else f"{rate:,.2f}"
                st.markdown(f"<div class='rate-card'>"
                            f"<div style='font-weight:700'>{cur}</div>"
                            f"<div style='color:#aaa;font-size:.9em'>{fmt}</div>"
                            f"</div>", unsafe_allow_html=True)
        st.markdown("")


def render_stock(r: dict):
    sym, name     = r.get("symbol",""), r.get("name",r.get("symbol",""))
    cur, price    = r.get("currency","USD"), r.get("current_price")
    change, w52h  = r.get("change_percent"), r.get("week52_high")
    w52l, state   = r.get("week52_low"), r.get("market_state","")
    direction     = "📈" if (change or 0) >= 0 else "📉"
    state_badge   = {"REGULAR":"🟢 Open","CLOSED":"🔴 Closed",
                     "PRE":"🟡 Pre-Market","POST":"🟠 After-Hours"}.get(state.upper(), state)
    st.markdown(f"## {direction} {sym}")
    st.caption(f"{name}  ·  {r.get('exchange','')}  ·  {state_badge}")
    st.divider()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric(f"💰 Price ({cur})", f"{price:,.2f}" if price else "N/A",
              delta=f"{change:+.2f}%" if change is not None else None)
    c2.metric("📊 Day Change",    f"{change:+.2f}%" if change is not None else "N/A")
    c3.metric("⬆️ 52W High",      f"{w52h:,.2f}" if w52h else "N/A")
    c4.metric("⬇️ 52W Low",       f"{w52l:,.2f}" if w52l else "N/A")
    series = r.get("series",[])
    if series:
        st.divider()
        st.markdown(f"#### 📊 Closing Price — **{r.get('period','')}**  ({r.get('data_points',0)} days)")
        df = pd.DataFrame(series)[["date","close"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        fig = px.area(df, x="date", y="close", template="plotly_dark",
                      labels={"close": f"Close ({cur})", "date": ""})
        fig.update_layout(margin=dict(t=20,b=10,l=10,r=10), height=260)
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("📋 OHLCV Table"):
            disp = pd.DataFrame(series)[["date","close","high","low","volume"]]
            disp.columns = ["Date","Close","High","Low","Volume"]
            st.dataframe(disp, use_container_width=True, hide_index=True)


# ── Natural Language Query helpers ───────────────────────────────────────────

def build_schema_context(tables: list) -> str:
    """Fetch all table schemas and return a single string for the LLM prompt. Cached."""
    if st.session_state.get("db_schema_ctx"):
        return st.session_state["db_schema_ctx"]
    calls = [("get_table_schema", {"table_name": t["table"]}) for t in tables]
    results = run_tools(*calls)
    lines = ["-- Connected PostgreSQL database\n"]
    for t, raw in zip(tables, results):
        schema = parse(raw)
        if isinstance(schema, list) and schema and "column_name" in schema[0]:
            cols = ", ".join(f"{c['column_name']} {c['data_type']}" for c in schema)
            lines.append(f"TABLE {t['table']} ({cols});")
    ctx = "\n".join(lines)
    st.session_state["db_schema_ctx"] = ctx
    return ctx


def nl_to_sql_query(schema_ctx: str, question: str, prev_error: str = None) -> str:
    """Convert a plain-English question to a PostgreSQL SELECT via LLM."""
    if not _AI_KEY:
        return ""
    error_hint = (
        f"\n\nThe previous SQL failed with error: {prev_error}\nFix it."
        if prev_error else ""
    )
    try:
        client = _ai_client()
        resp = client.chat.completions.create(
            model=_AI_MODEL,
            max_tokens=600,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a PostgreSQL expert. "
                        "Write clean read-only SELECT queries only. "
                        "Always qualify column names with table aliases to avoid ambiguity. "
                        "Prefer LEFT JOIN. Default LIMIT 200 unless user specifies. "
                        "Return ONLY the raw SQL — no markdown, no explanation, no backticks."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{schema_ctx}\n\nUser request: {question}{error_hint}",
                },
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"-- OpenAI error: {e}"


def smart_render_result(df: pd.DataFrame, key_prefix: str):
    """Auto-detect best display: metrics for single-row aggregates, chart+table otherwise."""
    if df.empty:
        st.info("No records match your query.")
        return

    rows, cols_n = len(df), len(df.columns)

    if rows == 1 and cols_n <= 6:
        st.markdown("#### Summary")
        mcols = st.columns(min(cols_n, 4))
        for i, (cname, val) in enumerate(df.iloc[0].items()):
            mcols[i % 4].metric(cname.replace("_", " ").title(), str(val))
    else:
        render_chart(df, key_prefix=key_prefix)

    csv_bytes = df.to_csv(index=False).encode()
    st.download_button("📥 Download CSV", csv_bytes,
                       file_name="query_result.csv", mime="text/csv",
                       key=f"{key_prefix}_dl")


def _render_nl_tab(tables: list):
    """The full 'Ask in Plain English' tab content."""
    st.markdown("#### 🤖 Ask Your Database in Plain English")
    st.caption(
        "Type what you want in everyday language — "
        "GPT-4o-mini writes the SQL, runs it, and shows your data."
    )

    if not _AI_KEY:
        st.warning("Add `GROQ_API_KEY` (free) or `OPENAI_API_KEY` to your `.env` and run `docker compose restart ui`.")
        return

    for key, default in [
        ("nl_history",   []),
        ("nl_last_sql",  ""),
        ("nl_last_rows", None),
        ("nl_last_q",    ""),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Query history chips ────────────────────────────────────────────────
    history = st.session_state["nl_history"]
    if history:
        st.markdown("<p class='sub-label'>Recent searches — click to re-run</p>",
                    unsafe_allow_html=True)
        chip_cols = st.columns(min(len(history), 5))
        for i, hq in enumerate(list(reversed(history[-5:]))):
            label = (hq[:28] + "…") if len(hq) > 28 else hq
            if chip_cols[i].button(label, key=f"nlh_{i}", use_container_width=True):
                st.session_state["nl_prefill"] = hq
                st.rerun()
        st.divider()

    # ── Input ──────────────────────────────────────────────────────────────
    prefill      = st.session_state.pop("nl_prefill", "")
    nl_question  = st.text_area(
        "What do you want to find?",
        value=prefill,
        placeholder=(
            "• Show me the top 10 records ordered by date\n"
            "• How many rows were created this month?\n"
            "• Which users are most active based on the data?\n"
            "• Give me a summary grouped by status"
        ),
        height=105,
    )

    ca, cb, cc = st.columns([1.2, 1, 2.5])
    auto_run   = ca.toggle("Auto-run SQL", value=True, key="nl_autorun",
                            help="Run the generated SQL immediately")
    clear_btn  = cb.button("🗑️ Clear", key="nl_clear", use_container_width=True)
    search_btn = cc.button("🔍 Search", type="primary", use_container_width=True, key="nl_search")

    if clear_btn:
        st.session_state["nl_last_sql"]  = ""
        st.session_state["nl_last_rows"] = None
        st.session_state["nl_last_q"]    = ""
        st.rerun()

    # ── Execute flow ───────────────────────────────────────────────────────
    if search_btn and nl_question.strip():
        hist = st.session_state["nl_history"]
        if nl_question not in hist:
            hist.append(nl_question)
        st.session_state["nl_history"] = hist[-5:]
        st.session_state["nl_last_q"]  = nl_question

        # Schema context (fetched once, cached)
        with st.spinner("Building schema context…"):
            schema_ctx = build_schema_context(tables)

        # Generate SQL
        with st.spinner("GPT-4o-mini is writing SQL…"):
            sql = nl_to_sql_query(schema_ctx, nl_question)
        st.session_state["nl_last_sql"] = sql

        if auto_run and sql and not sql.startswith("--"):
            with st.spinner("Running query…"):
                qr = parse(run_tool("query_dialer", {"sql": sql, "limit": 200}))
            if "error" in qr:
                with st.spinner("SQL had an error — asking GPT to fix it…"):
                    sql2 = nl_to_sql_query(schema_ctx, nl_question, prev_error=qr["error"])
                    st.session_state["nl_last_sql"] = sql2
                    qr = parse(run_tool("query_dialer", {"sql": sql2, "limit": 200}))
            st.session_state["nl_last_rows"] = qr

    # ── SQL preview (collapsible) ──────────────────────────────────────────
    if st.session_state["nl_last_sql"]:
        st.divider()
        expanded = not st.session_state.get("nl_autorun", True)
        with st.expander("🔎 Generated SQL — click to view or edit", expanded=expanded):
            edited_sql = st.text_area(
                "SQL (editable):",
                value=st.session_state["nl_last_sql"],
                height=130,
                key="nl_sql_edit_box",
            )
            if st.button("▶️ Run edited SQL", key="nl_run_edit"):
                with st.spinner("Running…"):
                    qr = parse(run_tool("query_dialer", {"sql": edited_sql, "limit": 200}))
                st.session_state["nl_last_rows"] = qr
                st.session_state["nl_last_sql"]  = edited_sql

    # ── Results ────────────────────────────────────────────────────────────
    qr = st.session_state.get("nl_last_rows")
    if qr is not None:
        st.divider()
        if "error" in qr:
            st.error(f"**Query error:** {qr['error']}")
            st.caption("Try rephrasing or check the SQL above.")
        else:
            rc = qr.get("row_count", 0)
            st.success(f"✅ **{rc} record{'s' if rc != 1 else ''}** found")
            df_nl = pd.DataFrame(qr.get("rows", []))
            smart_render_result(df_nl, key_prefix="nl_result")
            render_ask_claude(qr, "nl_query")


# ── Global AI Agent ───────────────────────────────────────────────────────────

_AGENT_SYSTEM = """You are a smart AI assistant with access to live data tools and a connected database.

Available capabilities:
- Weather data for any city and date
- Country information (population, GDP, military, companies)
- Cryptocurrency prices and history
- IP address geolocation
- Tech news from Hacker News
- GitHub repository information
- Live currency exchange rates
- Stock market data
- Your connected PostgreSQL database (any tables)

Rules:
- Use tools whenever the user asks for live data or database records.
- For questions about data in the database → always use query_app_db.
- For general knowledge questions → answer directly without calling any tool.
- Be concise and friendly. Format numbers cleanly. Use bullet points for lists.
- After getting database results, summarize the key insight in one sentence, then show details.
- Today's date: {today}."""


def _execute_agent_tool(tool_name: str, args: dict) -> dict:
    """Dispatcher: runs the right MCP tool or NL→SQL pipeline."""
    if tool_name == "query_app_db":
        question = args.get("question", "")
        if not st.session_state.get("db_schema_ctx"):
            try:
                _t = parse(run_tool("list_db_tables", {}))
                if isinstance(_t, list) and _t and "error" not in _t[0]:
                    st.session_state["db_tables_cache"] = _t
                    build_schema_context(_t)
            except Exception:
                pass
        schema_ctx = st.session_state.get("db_schema_ctx", "")
        sql = nl_to_sql_query(schema_ctx, question)
        qr  = parse(run_tool("query_dialer", {"sql": sql, "limit": 100}))
        return {"sql": sql, "db_result": qr}
    try:
        return parse(run_tool(tool_name, args))
    except Exception as e:
        return {"error": str(e)}


def run_agent_turn(history: list, user_msg: str) -> dict:
    """One full agent turn: decide → call tool(s) → format response."""
    if not _AI_KEY:
        return {"content": "⚠️ No AI key configured. Add GROQ_API_KEY to .env.", "tools_used": []}

    client = _ai_client()
    today  = datetime.today().strftime("%Y-%m-%d")
    system = _AGENT_SYSTEM.format(today=today)

    messages = [{"role": "system", "content": system}]
    for m in history[-12:]:                    # keep last 12 turns for context
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_msg})

    try:
        # First call — let LLM decide whether to use a tool
        resp = client.chat.completions.create(
            model=_AI_MODEL, messages=messages,
            tools=AGENT_TOOLS, tool_choice="auto",
            max_tokens=1024, temperature=0.3,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return {"content": msg.content or "…", "tools_used": []}

        # Execute every tool the LLM requested
        tools_used = []
        messages.append(msg)                   # assistant turn with tool_calls

        for tc in msg.tool_calls:
            name  = tc.function.name
            try:
                a = json.loads(tc.function.arguments)
            except Exception:
                a = {}

            with st.spinner(f"🔧 Using **{name}**…"):
                result = _execute_agent_tool(name, a)

            tools_used.append({"name": name, "args": a, "result": result})
            result_str = json.dumps(result, default=str)[:4000]
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

        # Second call — let LLM format a natural language response
        final = client.chat.completions.create(
            model=_AI_MODEL, messages=messages,
            max_tokens=1024, temperature=0.3,
        )
        return {
            "content":    final.choices[0].message.content or "Done.",
            "tools_used": tools_used,
        }

    except Exception as e:
        return {"content": f"Agent error: {e}", "tools_used": []}


def render_assistant_tab():
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Header row
    h1, h2 = st.columns([5, 1])
    h1.markdown("## 🤖 AI Assistant")
    h1.caption(
        "Ask anything in plain English — I'll call the right tool, query the database, "
        "or answer from my own knowledge."
    )
    if h2.button("🗑️ Clear", key="chat_clear", use_container_width=True):
        st.session_state["chat_history"] = []
        st.rerun()

    if not _AI_KEY:
        st.warning("Add `GROQ_API_KEY` (free) or `OPENAI_API_KEY` to your `.env` and restart.")
        return

    # ── Suggested prompts (shown only when chat is empty) ──────────────────
    if not st.session_state["chat_history"]:
        st.markdown("<p class='sub-label'>Try asking…</p>", unsafe_allow_html=True)
        suggestions = [
            "Show me records from the database",
            "What's the Bitcoin price?",
            "Top 5 Hacker News stories",
            "Show NVDA stock last 3 months",
            "What's the weather in London today?",
            "Convert 1000 USD to EUR",
            "Tell me about Germany",
            "Look up IP 8.8.8.8",
        ]
        cols = st.columns(4)
        for i, s in enumerate(suggestions):
            if cols[i % 4].button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state["chat_prefill"] = s
                st.rerun()
        st.divider()

    # ── Chat history ───────────────────────────────────────────────────────
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for t in msg.get("tools_used", []):
                with st.expander(f"🔧 `{t['name']}` — click to inspect", expanded=False):
                    st.json(t["args"])
                    if t["name"] == "query_app_db":
                        sql = t["result"].get("sql", "")
                        if sql:
                            st.code(sql, language="sql")
                        db_r = t["result"].get("db_result", {})
                        rows = db_r.get("rows", [])
                        if rows:
                            df = pd.DataFrame(rows)
                            st.dataframe(df, use_container_width=True, hide_index=True)
                            csv = df.to_csv(index=False).encode()
                            st.download_button("📥 CSV", csv, "result.csv",
                                               key=f"dl_{t['name']}_{id(t)}")

    # ── Input ──────────────────────────────────────────────────────────────
    prefill    = st.session_state.pop("chat_prefill", "")
    user_input = st.chat_input(prefill or "Ask me anything…")

    if user_input:
        history = st.session_state["chat_history"]
        history.append({"role": "user", "content": user_input, "tools_used": []})

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            response = run_agent_turn(
                [m for m in history[:-1]],   # history without the current user msg
                user_input,
            )
            st.markdown(response["content"])

            for t in response.get("tools_used", []):
                with st.expander(f"🔧 `{t['name']}` — click to inspect", expanded=False):
                    st.json(t["args"])
                    if t["name"] == "query_app_db":
                        sql = t["result"].get("sql", "")
                        if sql:
                            st.code(sql, language="sql")
                        db_r = t["result"].get("db_result", {})
                        rows = db_r.get("rows", [])
                        if rows:
                            df = pd.DataFrame(rows)
                            st.dataframe(df, use_container_width=True, hide_index=True)
                            csv = df.to_csv(index=False).encode()
                            st.download_button("📥 CSV", csv, "result.csv",
                                               key=f"dl2_{t['name']}_{len(history)}")

        history.append({
            "role":       "assistant",
            "content":    response["content"],
            "tools_used": response.get("tools_used", []),
        })
        st.session_state["chat_history"] = history


# ── Dialer DB tab ─────────────────────────────────────────────────────────────

def render_login_page():
    """Full-page login/register shown when user is not authenticated."""
    st.markdown("""
    <div style='text-align:center;padding:2rem 0 1rem'>
        <span style='font-size:2.8em'>🛠️</span>
        <h1 style='margin:0'>MCP Tool Explorer</h1>
        <p style='color:#888;margin-top:.3rem'>AI-powered tools · Live data · Dialer intelligence</p>
    </div>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        mode = st.radio("", ["🔐 Sign In", "👤 Create Account"],
                        horizontal=True, label_visibility="collapsed")
        st.markdown("<div class='login-box'>", unsafe_allow_html=True)

        if mode == "🔐 Sign In":
            st.markdown("### Sign In")
            with st.form("login_form"):
                email    = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                ok = st.form_submit_button("Sign In →", type="primary",
                                           use_container_width=True)
            if ok:
                if not email or not password:
                    st.error("Enter email and password.")
                else:
                    r = _auth_post("/auth/login", {"email": email, "password": password})
                    if r["ok"]:
                        st.session_state["auth_token"]   = r["data"]["token"]
                        st.session_state["current_user"] = r["data"]["user"]
                        audit_log("login")
                        st.rerun()
                    else:
                        st.error(f"❌ {r['error']}")

        else:
            st.markdown("### Create Account")
            with st.form("reg_form"):
                c1, c2 = st.columns(2)
                name   = c1.text_input("Full Name *")
                email  = c2.text_input("Email *")
                c3, c4 = st.columns(2)
                mobile = c3.text_input("Mobile")
                state  = c4.text_input("State / Region")
                c5, c6 = st.columns(2)
                pw1 = c5.text_input("Password *",         type="password")
                pw2 = c6.text_input("Confirm Password *", type="password")
                ok = st.form_submit_button("Create Account", type="primary",
                                           use_container_width=True)
            if ok:
                if not all([name, email, pw1]):
                    st.error("Name, email and password are required.")
                elif pw1 != pw2:
                    st.error("Passwords do not match.")
                else:
                    r = _auth_post("/auth/register", {
                        "name": name, "email": email, "password": pw1,
                        "mobile": mobile, "state": state,
                    })
                    if r["ok"]:
                        st.success("✅ Account created! Please sign in.")
                    else:
                        st.error(f"❌ {r['error']}")

        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("Admin credentials are set via `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`")


def render_user_management():
    """Admin-only user management and audit log page."""
    token = st.session_state.get("auth_token", "")
    me    = st.session_state.get("current_user", {})
    if me.get("role") != "admin":
        st.error("🔒 Admin access required.")
        return

    st.markdown("## 👥 User Management")

    # ── Stats ──────────────────────────────────────────────────────────────
    sr = _auth_get("/audit/stats", token)
    if sr["ok"]:
        s = sr["data"]
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("👥 Total Users",    s.get("total_users",   0))
        c2.metric("✅ Active",         s.get("active_users",  0))
        c3.metric("🔑 Admins",         s.get("admin_count",   0))
        c4.metric("🔐 Logins Today",   s.get("logins_today",  0))
        c5.metric("❌ Failed (24h)",   s.get("failed_logins", 0))
        c6.metric("📋 Total Actions",  s.get("total_actions", 0))
    st.divider()

    tab_u, tab_new, tab_audit = st.tabs(["👤 Users", "➕ Create User", "📋 Audit Logs"])

    # ── Tab: Users ─────────────────────────────────────────────────────────
    with tab_u:
        ur = _auth_get("/auth/users", token)
        if not ur["ok"]:
            st.error(ur["error"]); return
        users_list = ur["data"] or []
        if not users_list:
            st.info("No users found."); return

        df_u = pd.DataFrame(users_list)
        for col in ("created_at", "last_login", "updated_at"):
            if col in df_u.columns:
                df_u[col] = pd.to_datetime(df_u[col], utc=True, errors="coerce") \
                              .dt.strftime("%Y-%m-%d %H:%M").fillna("—")
        show_cols = [c for c in ["name","email","mobile","state","role","is_active",
                                  "login_count","last_login","last_login_ip","created_at"]
                     if c in df_u.columns]
        st.dataframe(df_u[show_cols], use_container_width=True, hide_index=True)
        st.divider()

        st.markdown("#### ⚙️ Manage a User")
        emails     = [u["email"] for u in users_list]
        sel_email  = st.selectbox("Select user", emails, key="mgmt_sel")
        sel_u      = next(u for u in users_list if u["email"] == sel_email)
        uid        = str(sel_u["id"])

        with st.expander("✏️ Edit details"):
            with st.form("edit_user_form"):
                ec1, ec2 = st.columns(2)
                new_name   = ec1.text_input("Name",   value=sel_u.get("name",""))
                new_mobile = ec2.text_input("Mobile", value=sel_u.get("mobile",""))
                ec3, ec4 = st.columns(2)
                new_state  = ec3.text_input("State",  value=sel_u.get("state",""))
                new_role   = ec4.selectbox("Role", ["user","admin"],
                                           index=0 if sel_u.get("role") == "user" else 1)
                save = st.form_submit_button("Save Changes", type="primary",
                                             use_container_width=True)
            if save:
                r2 = _requests.patch(
                    f"{AUTH_SERVICE_URL}/auth/users/{uid}",
                    json={"name": new_name, "mobile": new_mobile,
                          "state": new_state, "role": new_role},
                    headers={"x-auth-token": token}, timeout=5,
                )
                if r2.status_code < 300:
                    st.success("Updated."); audit_log("update_user", resource=sel_email)
                else:
                    st.error(r2.json().get("detail", r2.text))

        ba, bb = st.columns(2)
        if ba.button("🔄 Toggle Active / Inactive", key="tog", use_container_width=True):
            r3 = _auth_post(f"/auth/users/{uid}/toggle", {}, token=token)
            if r3["ok"]:
                new_s = r3["data"]["is_active"]
                st.success(f"User {'activated ✅' if new_s else 'deactivated 🚫'}.")
                audit_log("toggle_user", resource=sel_email)
                st.rerun()
            else:
                st.error(r3["error"])
        if bb.button("🔑 Reset Password → Welcome@123", key="rpw", use_container_width=True):
            r4 = _auth_post(f"/auth/users/{uid}/reset-password", {}, token=token)
            if r4["ok"]:
                st.success(f"Password reset to `{r4['data']['new_password']}`")
                audit_log("reset_password", resource=sel_email)
            else:
                st.error(r4["error"])

    # ── Tab: Create user ───────────────────────────────────────────────────
    with tab_new:
        st.markdown("#### ➕ Create New User")
        with st.form("create_user"):
            n1, n2 = st.columns(2)
            nu_name  = n1.text_input("Full Name *")
            nu_email = n2.text_input("Email *")
            n3, n4 = st.columns(2)
            nu_mob   = n3.text_input("Mobile")
            nu_state = n4.text_input("State / Region")
            n5, n6 = st.columns(2)
            nu_role  = n5.selectbox("Role", ["user", "admin"])
            nu_pw    = n6.text_input("Temporary Password *", type="password")
            nu_ok = st.form_submit_button("Create User", type="primary",
                                          use_container_width=True)
        if nu_ok:
            if not all([nu_name, nu_email, nu_pw]):
                st.error("Name, email and password are required.")
            else:
                r5 = _auth_post("/auth/register",
                                {"name": nu_name, "email": nu_email, "password": nu_pw,
                                 "mobile": nu_mob, "state": nu_state, "role": nu_role},
                                token=token)
                if r5["ok"]:
                    st.success(f"✅ User **{nu_name}** created as **{nu_role}**.")
                    audit_log("create_user", resource=nu_email,
                              details={"name": nu_name, "role": nu_role})
                else:
                    st.error(r5["error"])

    # ── Tab: Audit logs ────────────────────────────────────────────────────
    with tab_audit:
        st.markdown("#### 📋 Audit Log")
        f1, f2 = st.columns([2, 1])
        action_f = f1.selectbox("Filter by action", [
            "all", "login", "logout", "register", "tool_call", "db_query",
            "toggle_user", "reset_password", "create_user", "update_user",
        ])
        al_limit = f2.number_input("Limit", 10, 1000, 100, key="al_limit")

        params = {"limit": int(al_limit)}
        if action_f != "all":
            params["action"] = action_f
        ar = _auth_get("/audit/logs", token, params=params)
        if ar["ok"]:
            logs = ar["data"] or []
            if logs:
                df_al = pd.DataFrame(logs)
                if "created_at" in df_al.columns:
                    df_al["created_at"] = pd.to_datetime(
                        df_al["created_at"], utc=True, errors="coerce"
                    ).dt.strftime("%Y-%m-%d %H:%M:%S").fillna("—")
                show = [c for c in ["created_at","user_name","user_email","action",
                                    "resource","status","ip_address","details"]
                        if c in df_al.columns]
                st.dataframe(df_al[show], use_container_width=True, hide_index=True)
                st.download_button("📥 Export CSV",
                                   df_al.to_csv(index=False).encode(),
                                   "audit_log.csv", mime="text/csv")
            else:
                st.info("No logs found for this filter.")
        else:
            st.error(ar.get("error", "Failed to load logs."))


def render_db_page(is_online: bool):
    st.markdown("## 🗄️ Dialer Database")

    st.caption(f"Connected as: **{st.session_state.get('current_user',{}).get('email','—')}**")

    if not is_online:
        st.error("MCP Server is offline — cannot reach the DB tool.")
        return

    # ── Connection status ──────────────────────────────────────────────────
    with st.spinner("Checking connection…"):
        status = parse(run_tool("get_db_status", {}))

    if status.get("status") == "error":
        st.error(f"**DB Connection Failed:** {status.get('error')}")
        st.caption("Check your DB_HOST, DB_PORT, DB_USER, DB_PASSWORD in .env")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Status",   "Connected")
    c2.metric("🗃️ Database", status.get("database", "—"))
    c3.metric("💾 DB Size",  status.get("db_size", "—"))
    c4.metric("🖥️ Host",     f"{status.get('host','—')}:{status.get('port','—')}")
    st.caption(status.get("pg_version", ""))
    st.divider()

    # ── Fetch + cache table list (shared across all tabs) ──────────────────
    if "db_tables_cache" not in st.session_state:
        with st.spinner("Loading tables…"):
            _t = parse(run_tool("list_db_tables", {}))
        st.session_state["db_tables_cache"] = (
            _t if isinstance(_t, list) and _t and "error" not in _t[0] else []
        )
    tables = st.session_state.get("db_tables_cache", [])

    if st.button("🔄 Refresh", key="db_refresh", help="Reload table list and schema"):
        for k in ("db_tables_cache", "db_schema_ctx"):
            st.session_state.pop(k, None)
        st.rerun()

    # ── Three tabs ─────────────────────────────────────────────────────────
    tab_browse, tab_query, tab_nl = st.tabs([
        "📋 Browse Tables",
        "🔍 Run Query",
        "🤖 Ask in Plain English",
    ])

    # ── Tab 1: Browse Tables ───────────────────────────────────────────────
    with tab_browse:
        if tables:
            st.dataframe(pd.DataFrame(tables), use_container_width=True, hide_index=True)
            st.divider()
            selected_table = st.selectbox(
                "Inspect a table schema",
                options=[t["table"] for t in tables],
            )
            if st.button("Show Schema", key="show_schema"):
                with st.spinner(f"Loading schema for {selected_table}…"):
                    schema = parse(run_tool("get_table_schema", {"table_name": selected_table}))
                if isinstance(schema, list) and schema:
                    st.dataframe(pd.DataFrame(schema), use_container_width=True, hide_index=True)
            if st.button(f"Preview first 20 rows of `{selected_table}`", key="preview"):
                result = parse(run_tool("query_dialer",
                               {"sql": f'SELECT * FROM "{selected_table}" LIMIT 20'}))
                if "error" not in result:
                    render_chart(pd.DataFrame(result.get("rows", [])), key_prefix="preview")
                    render_ask_claude(result, "db_preview")
                else:
                    st.error(result["error"])
        else:
            st.warning("Could not load table list. Check DB connection.")

    # ── Tab 2: Run Query (SQL editor for technical users) ──────────────────
    with tab_query:
        st.markdown("#### ✍️ Write a Query")
        if _AI_KEY:
            with st.expander("🤖 Generate SQL with AI (Natural Language → SQL)"):
                nl_q = st.text_input(
                    "Describe what you want",
                    placeholder="e.g. Show me all calls longer than 5 minutes from last week",
                )
                if st.button("Generate SQL ✨", key="gen_sql"):
                    tables_ctx = "\n".join(t.get("table", "") for t in tables if "table" in t)
                    with st.spinner("AI is writing SQL…"):
                        generated = claude_sql(tables_ctx, nl_q)
                    st.session_state["db_generated_sql"] = generated
                if st.session_state.get("db_generated_sql"):
                    st.code(st.session_state["db_generated_sql"], language="sql")
                    if st.button("▶️ Run this SQL", key="run_gen_sql"):
                        st.session_state["db_run_sql"] = st.session_state["db_generated_sql"]
        st.divider()
        default_sql  = st.session_state.get("db_run_sql", "SELECT * FROM calls LIMIT 50")
        sql_input    = st.text_area("SQL Query (SELECT only)", value=default_sql, height=120)
        c_lim, c_btn = st.columns([1, 2])
        row_limit    = c_lim.number_input("Row limit", min_value=1, max_value=1000, value=200)
        run_clicked  = c_btn.button("▶️ Run Query", type="primary",
                                     use_container_width=True, key="run_custom_sql")
        if run_clicked:
            with st.spinner("Running query…"):
                qresult = parse(run_tool("query_dialer",
                                {"sql": sql_input, "limit": int(row_limit)}))
            if "error" in qresult:
                st.error(f"Query error: {qresult['error']}")
            else:
                st.success(f"✅ {qresult.get('row_count', 0)} rows returned")
                render_chart(pd.DataFrame(qresult.get("rows", [])), key_prefix="query_result")
                st.caption(f"SQL ran: `{qresult.get('sql_ran', '')}`")
                render_ask_claude(qresult, "db_query")

    # ── Tab 3: Natural Language Query ──────────────────────────────────────
    with tab_nl:
        _render_nl_tab(tables)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="MCP Tool Explorer", page_icon="🛠️",
                       layout="wide", initial_sidebar_state="expanded")
    inject_css()

    if "result"      not in st.session_state: st.session_state.result      = None
    if "result_tool" not in st.session_state: st.session_state.result_tool = None

    # ── Global authentication gate ─────────────────────────────────────────────
    if not st.session_state.get("auth_token"):
        render_login_page()
        st.stop()

    if not verify_session():
        st.warning("Session expired — please sign in again.")
        do_logout()

    me = st.session_state.get("current_user", {})

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 🛠️ MCP Tools")
        st.divider()

        # Logged-in user info
        role_badge = "🔑 Admin" if me.get("role") == "admin" else "👤 User"
        st.markdown(f"**{me.get('name','—')}** &nbsp; `{role_badge}`")
        st.caption(me.get("email", ""))
        if st.button("🚪 Sign Out", key="global_logout", use_container_width=True):
            do_logout()
        st.divider()

        is_online = check_server_health()
        if is_online:
            st.success("MCP Server Online", icon="✅")
        else:
            st.error("MCP Server Offline", icon="🔴")
        st.caption(f"`{MCP_SERVER_URL}`")
        st.divider()

        for name, meta in TOOL_META.items():
            st.markdown(f"{meta['emoji']} **{meta['label']}** "
                        f"<span style='font-size:.72em;color:#666;float:right'>{meta['api']}</span>",
                        unsafe_allow_html=True)
        st.divider()
        ai_label  = "Groq (free)" if GROQ_API_KEY else ("OpenAI" if OPENAI_API_KEY else "")
        ai_status = f"✅ {ai_label}" if _AI_KEY else "⚠️ No API key"
        st.caption(f"🤖 AI: {ai_status}")
        st.caption("All other APIs: **free, no keys**")

    st.markdown("# 🛠️ MCP Tool Explorer")
    st.caption("AI agent · 10 tools · free APIs · Dialer DB · User Management")

    # Build tab list — add User Management for admins
    tab_keys   = ["assistant"] + list(TOOL_META.keys())
    tab_labels = ["🤖 Assistant"] + [
        f"{TOOL_META[k]['emoji']} {TOOL_META[k]['label']}" for k in TOOL_META
    ]
    if me.get("role") == "admin":
        tab_keys.append("user_mgmt")
        tab_labels.append("👥 User Management")

    tabs = st.tabs(tab_labels)

    for tab, tool_key in zip(tabs, tab_keys):
        with tab:

            # ── Global AI Assistant ─────────────────────────────────────────
            if tool_key == "assistant":
                render_assistant_tab()
                continue

            # ── User Management (admin only) ────────────────────────────────
            if tool_key == "user_mgmt":
                render_user_management()
                continue

            # ── Dialer DB (all authenticated users) ─────────────────────────
            if tool_key == "dialer_db":
                render_db_page(is_online)
                continue

            # ── All other tools (left form | right result) ─────────────────
            left, right = st.columns([1, 1.5], gap="large")

            with left:
                st.markdown("#### Parameters")

                if tool_key == "get_crypto_price":
                    result_pair = form_crypto()
                    if result_pair is not None:
                        if not is_online:
                            st.error("Server offline.")
                        else:
                            price_args, history_args = result_pair
                            with st.spinner("Fetching price + history…"):
                                try:
                                    rp, rh = run_tools(
                                        ("get_crypto_price",   price_args),
                                        ("get_crypto_history", history_args),
                                    )
                                    result = {"spot": parse(rp), "history": parse(rh)}
                                except Exception as e:
                                    result = {"error": str(e)}
                            st.session_state.result      = result
                            st.session_state.result_tool = tool_key
                else:
                    form_fn = {
                        "get_weather":        form_weather,
                        "get_country_info":   form_country,
                        "get_ip_info":        form_ip,
                        "get_top_news":       form_news,
                        "get_github_repo":    form_github,
                        "get_exchange_rates": form_exchange,
                        "get_stock_data":     form_stock,
                    }
                    args = form_fn[tool_key]()
                    if args is not None:
                        if not is_online:
                            st.error("Server offline.")
                        else:
                            with st.spinner("Calling tool…"):
                                try:
                                    result = parse(run_tool(tool_key, args))
                                    audit_log("tool_call", resource=tool_key,
                                              details={"args": args})
                                except Exception as e:
                                    result = {"error": str(e)}
                            st.session_state.result      = result
                            st.session_state.result_tool = tool_key

            with right:
                st.markdown("#### Result")
                result      = st.session_state.result
                result_tool = st.session_state.result_tool

                if result is None or result_tool != tool_key:
                    st.markdown("<div class='placeholder'>⬅️ Fill in the parameters<br>"
                                "and click the button</div>", unsafe_allow_html=True)
                    continue

                # Crypto combined result
                if tool_key == "get_crypto_price":
                    err = (error_of(result.get("spot",{})) or
                           error_of(result.get("history",{})) or
                           result.get("error"))
                    if err:
                        st.error(f"**Error:** {err}")
                    else:
                        render_crypto(result["spot"], result["history"])
                        render_ask_claude(result, tool_key)
                        with st.expander("Raw JSON"):
                            st.json(result)
                    continue

                err = error_of(result)
                if err:
                    st.error(f"**Tool error:** {err}")
                else:
                    render_fns = {
                        "get_weather":        render_weather,
                        "get_country_info":   render_country,
                        "get_ip_info":        render_ip,
                        "get_top_news":       render_news,
                        "get_github_repo":    render_github,
                        "get_exchange_rates": render_exchange,
                        "get_stock_data":     render_stock,
                    }
                    render_fns[result_tool](result)
                    render_ask_claude(result, tool_key)
                    with st.expander("Raw JSON"):
                        st.json(result)


if __name__ == "__main__":
    main()

# MCP Tool Explorer

A full-stack, Dockerized AI assistant platform built on the **Model Context Protocol (MCP)**. It connects a Streamlit UI to a FastMCP server that exposes 10 live data tools, an optional PostgreSQL database, and a complete user authentication system with audit logging.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Docker Network                          │
│                                                              │
│  ┌────────────────┐   ┌────────────────┐   ┌─────────────┐ │
│  │  Streamlit UI  │──▶│  MCP Server    │   │ Auth Service│ │
│  │  (port 8501)   │   │  (port 8000)   │   │ (port 8001) │ │
│  │                │   │  FastMCP/SSE   │   │  FastAPI    │ │
│  └───────┬────────┘   └───────┬────────┘   └──────┬──────┘ │
│          │                    │                    │        │
│          │         ┌──────────┘                    │        │
│          │         │  10 Free API Tools             │        │
│          │         │  + DB Query Tool               │        │
│          │         └───────────────────────────────┘        │
│          │                                                   │
│          └──────────────────┐                               │
│                     ┌───────▼──────┐  ┌────────────────┐   │
│                     │  Your Postgres│  │   App DB       │   │
│                     │  (external)   │  │ Users+Audit    │   │
│                     └──────────────┘  └────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

| Service | Port | Description |
|---|---|---|
| `ui` | 8501 | Streamlit frontend — all user interaction |
| `server` | 8000 | FastMCP server — 10 tools over SSE transport |
| `auth` | 8001 | FastAPI auth service — JWT login, user CRUD, audit logs |
| `app-db` | internal | PostgreSQL — stores users and audit logs |

---

## Features

### 10 Live Data Tools (all free, no API keys required)
| Tool | Data Source | What it does |
|---|---|---|
| Weather | Open-Meteo | Forecast + historical weather by city/country/date |
| Country Info | REST Countries + World Bank | Population, GDP, military spend, tech/defense companies |
| Crypto Price | CoinGecko | Spot price, market cap, 24h change |
| Crypto History | CoinGecko | Price chart over 7d / 1m / 3m / 1y / custom range |
| IP Geolocation | IP-API | City, region, ISP, timezone for any IP |
| Top News | Hacker News | Top stories with score and comment count |
| GitHub Repo | GitHub Public API | Stars, forks, language, README snippet |
| Exchange Rates | Open ER-API | Live rates for any base currency |
| Stock Data | Yahoo Finance | OHLCV history for any ticker |
| DB Query | Your PostgreSQL | Read-only SELECT against your connected database |

### AI Assistant
- Global chat interface powered by **Groq (free)** or OpenAI
- Automatically decides which tool to call based on your question
- Converts natural language to SQL for database queries
- Full conversation memory (12-turn context window)
- Tool inspector — see exactly what SQL was generated and what args were passed

### Plain English Database Queries
Dedicated tab inside the DB section:
- Type a question → LLM writes SQL → executes → shows results
- Auto-retry on SQL errors (LLM self-corrects)
- View/edit generated SQL before running
- Graph type selector: Table / Bar / Line / Area / Pie / Scatter
- CSV export for every result
- Ask AI to explain the results

### Authentication & User Management
- JWT-based login with configurable expiry
- Role-based access: `admin` and `user`
- Admin panel: create users, toggle active/inactive, reset passwords
- Full **audit log**: every login, tool call, DB query, and admin action is recorded
- Login activity: last login time, IP address, login count per user

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- A Groq API key (free) **or** an OpenAI API key

### 1. Clone the repository
```bash
git clone https://github.com/your-username/mcp-tool-explorer.git
cd mcp-tool-explorer
```

### 2. Configure environment
```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Your PostgreSQL database (optional)
DB_HOST=your_postgres_host
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_db_username
DB_PASSWORD=your_db_password

# AI — Groq is free: https://console.groq.com → API Keys → Create
GROQ_API_KEY=your_groq_key_here

# Internal app DB password (choose anything)
APP_DB_PASSWORD=choose_a_strong_password

# JWT signing secret (use a long random string)
JWT_SECRET=replace_with_a_long_random_string

# First admin account
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=YourSecurePassword@123
ADMIN_NAME=System Admin
```

### 3. Start all services
```bash
docker compose up --build
```

### 4. Open the app
Visit **http://localhost:8501** and sign in with your admin credentials.

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `DB_HOST` | No | Hostname/IP of your PostgreSQL server |
| `DB_PORT` | No | PostgreSQL port (default `5432`) |
| `DB_NAME` | No | Database name |
| `DB_USER` | No | Database username |
| `DB_PASSWORD` | No | Database password |
| `GROQ_API_KEY` | One of | Free LLM API key from console.groq.com |
| `OPENAI_API_KEY` | One of | OpenAI API key (fallback if no Groq key) |
| `APP_DB_PASSWORD` | Yes | Password for the internal users/audit PostgreSQL |
| `JWT_SECRET` | Yes | Secret string for signing JWT tokens |
| `JWT_EXPIRE_HOURS` | No | Token lifetime in hours (default `24`) |
| `ADMIN_EMAIL` | Yes | Email for the first admin account |
| `ADMIN_PASSWORD` | Yes | Password for the first admin account |
| `ADMIN_NAME` | No | Display name for the first admin |

> **Note:** `MCP_SERVER_URL` and `AUTH_SERVICE_URL` are set automatically by docker-compose and should not be changed.

---

## Connecting Your Own Database

The DB tools work with **any PostgreSQL database**. The server enforces read-only access — only `SELECT` and `WITH` queries are permitted. `INSERT`, `UPDATE`, `DELETE`, `DROP`, and similar statements are blocked.

Set the four `DB_*` variables in `.env`, then restart:
```bash
docker compose restart server
```

If your database requires SSL, edit `server/db_tool.py` and change `"sslmode": "disable"` to `"sslmode": "require"`.

---

## Auth Service API

The auth service runs on port 8001 and exposes these endpoints:

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Service health check |
| `POST` | `/auth/login` | None | Login, returns JWT token |
| `POST` | `/auth/logout` | Token | Invalidate session |
| `POST` | `/auth/verify` | None | Validate a JWT token |
| `POST` | `/auth/register` | Admin | Create a new user |
| `GET` | `/auth/users` | Admin | List all users |
| `PATCH` | `/auth/users/{id}` | Admin | Update user details |
| `POST` | `/auth/users/{id}/toggle` | Admin | Activate / deactivate user |
| `POST` | `/auth/users/{id}/reset-password` | Admin | Reset to `Welcome@123` |
| `POST` | `/auth/change-password` | Token | Change own password |
| `POST` | `/audit/log` | Token | Write an audit entry |
| `GET` | `/audit/logs` | Admin | Read audit log |
| `GET` | `/audit/stats` | Admin | Summary statistics |

Interactive API docs: **http://localhost:8001/docs**

---

## Project Structure

```
mcp-tool-explorer/
├── .env.example          ← copy to .env and fill in your values
├── .gitignore
├── docker-compose.yml
│
├── auth/                 ← FastAPI authentication service
│   ├── Dockerfile
│   ├── main.py           ← login, JWT, user CRUD, audit log endpoints
│   ├── init.sql          ← users + audit_logs schema
│   └── requirements.txt
│
├── server/               ← FastMCP tool server
│   ├── Dockerfile
│   ├── main.py           ← tool registration
│   ├── tools.py          ← 9 public API tool implementations
│   ├── db_tool.py        ← PostgreSQL read-only query tool
│   └── requirements.txt
│
└── ui/                   ← Streamlit frontend
    ├── Dockerfile
    ├── app.py            ← full UI + AI agent + auth client
    └── requirements.txt
```

---

## Adding a New Tool

**1. Add the implementation in `server/tools.py`:**
```python
async def _fetch_my_tool(param: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.example.com/{param}")
        return r.json()
```

**2. Register it in `server/main.py`:**
```python
@mcp.tool()
async def my_tool(param: str) -> dict:
    """Description shown to AI agents."""
    return await _fetch_my_tool(param)
```

**3. Add a form and renderer in `ui/app.py`** (follow the pattern of existing tools).

**4. Rebuild:**
```bash
docker compose up --build server ui
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| MCP Server | [FastMCP](https://github.com/jlowin/fastmcp) 3.2.x over SSE |
| Frontend | [Streamlit](https://streamlit.io) |
| Auth Service | [FastAPI](https://fastapi.tiangolo.com) + [PyJWT](https://pyjwt.readthedocs.io) + bcrypt |
| AI / LLM | [Groq](https://console.groq.com) (Llama 3.3 70B) or OpenAI (GPT-4o-mini) |
| Charts | [Plotly](https://plotly.com/python/) |
| Database client | [psycopg2](https://www.psycopg.org/) |
| Containerization | Docker Compose |

---

## Security Notes

- `.env` is listed in `.gitignore` — never committed
- DB access is read-only enforced at the application layer
- JWT tokens are signed with `JWT_SECRET` — use a strong random value in production
- Passwords are hashed with bcrypt (cost factor 10)
- All user actions are recorded in the audit log
- Change default admin credentials immediately after first login

---

## License

MIT License — free to use, modify and distribute.

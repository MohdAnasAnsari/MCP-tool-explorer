"""
Dialer DB Tool — connects to a remote PostgreSQL database (read-only).
All credentials come from environment variables defined in .env / docker-compose.
"""
import asyncio
import os

_CFG = {
    "host":            os.environ.get("DB_HOST",     "localhost"),
    "port":            int(os.environ.get("DB_PORT", "5432")),
    "dbname":          os.environ.get("DB_NAME",     "postgres"),
    "user":            os.environ.get("DB_USER",     "postgres"),
    "password":        os.environ.get("DB_PASSWORD", ""),
    "sslmode":         "disable",
    "connect_timeout": 8,
    "options":         "-c statement_timeout=30000",  # 30 s query cap
}

_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE",
    "ALTER", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
)


def _sync_query(sql: str, params=None) -> list[dict]:
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(**_CFG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


async def _q(sql: str, params=None) -> list[dict]:
    return await asyncio.to_thread(_sync_query, sql, params)


# ── Public helpers ────────────────────────────────────────────────────────────

async def _fetch_db_status() -> dict:
    try:
        rows = await _q(
            "SELECT version() AS v, current_database() AS db, current_user AS u, "
            "pg_size_pretty(pg_database_size(current_database())) AS size"
        )
        r = rows[0]
        return {
            "status":   "connected",
            "host":     _CFG["host"],
            "port":     _CFG["port"],
            "database": r["db"],
            "user":     r["u"],
            "db_size":  r["size"],
            "pg_version": r["v"][:80],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _fetch_db_tables() -> list:
    try:
        rows = await _q("""
            SELECT  t.table_name,
                    pg_size_pretty(pg_total_relation_size(quote_ident(t.table_name))) AS size,
                    COALESCE(c.reltuples::bigint, 0) AS approx_rows
            FROM    information_schema.tables   t
            LEFT JOIN pg_class                  c ON c.relname = t.table_name
            WHERE   t.table_schema = 'public'
              AND   t.table_type   = 'BASE TABLE'
            ORDER BY t.table_name
        """)
        return [
            {
                "table":       r["table_name"],
                "size":        r["size"],
                "approx_rows": max(int(r["approx_rows"]), 0),
            }
            for r in rows
        ]
    except Exception as e:
        return [{"error": str(e)}]


async def _fetch_table_schema(table_name: str) -> list:
    try:
        return await _q("""
            SELECT  column_name,
                    data_type,
                    is_nullable,
                    column_default
            FROM    information_schema.columns
            WHERE   table_schema = 'public'
              AND   table_name   = %s
            ORDER BY ordinal_position
        """, (table_name,))
    except Exception as e:
        return [{"error": str(e)}]


async def _run_dialer_query(sql: str, limit: int = 200) -> dict:
    cleaned = sql.strip().upper()
    if not (cleaned.startswith("SELECT") or cleaned.startswith("WITH")):
        return {"error": "Only SELECT / WITH queries are allowed (read-only access)"}
    for kw in _FORBIDDEN_KEYWORDS:
        if kw in cleaned:
            return {"error": f"Keyword '{kw}' is not permitted — read-only access only"}

    # Inject LIMIT only if the outermost query has none
    if "LIMIT" not in cleaned:
        sql = f"{sql.rstrip(';')} LIMIT {limit}"

    try:
        rows = await _q(sql)
        return {
            "row_count": len(rows),
            "columns":   list(rows[0].keys()) if rows else [],
            "rows":      rows,
            "sql_ran":   sql,
        }
    except Exception as e:
        return {"error": str(e)}

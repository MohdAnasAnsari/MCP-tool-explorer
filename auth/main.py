import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="MCP Auth Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

JWT_SECRET        = os.environ.get("JWT_SECRET",        "mcp-super-secret-change-in-prod")
JWT_EXPIRE_HOURS  = int(os.environ.get("JWT_EXPIRE_HOURS", "24"))
ADMIN_EMAIL       = os.environ.get("ADMIN_EMAIL",       "admin@mcp.local")
ADMIN_PASSWORD    = os.environ.get("ADMIN_PASSWORD",    "Admin@123")
ADMIN_NAME        = os.environ.get("ADMIN_NAME",        "System Admin")

_DB = {
    "host":            os.environ.get("APP_DB_HOST",     "app-db"),
    "port":            int(os.environ.get("APP_DB_PORT", "5432")),
    "dbname":          os.environ.get("APP_DB_NAME",     "app_db"),
    "user":            os.environ.get("APP_DB_USER",     "app_user"),
    "password":        os.environ.get("APP_DB_PASSWORD", ""),
    "connect_timeout": 8,
}


# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn():
    return psycopg2.connect(**_DB, cursor_factory=psycopg2.extras.RealDictCursor)


def q(sql: str, params=None) -> list:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            try:
                return [dict(r) for r in cur.fetchall()]
            except Exception:
                return []
    finally:
        conn.close()


def q1(sql: str, params=None) -> Optional[dict]:
    rows = q(sql, params)
    return rows[0] if rows else None


# ── Startup: seed admin ───────────────────────────────────────────────────────

@app.on_event("startup")
def seed_admin():
    for _ in range(15):
        try:
            existing = q1("SELECT id FROM users WHERE email = %s", (ADMIN_EMAIL,))
            if not existing:
                pw = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt(rounds=10)).decode()
                q("""INSERT INTO users (name, email, role, password_hash)
                     VALUES (%s, %s, 'admin', %s)
                     ON CONFLICT (email) DO NOTHING""",
                  (ADMIN_NAME, ADMIN_EMAIL, pw))
            return
        except Exception:
            time.sleep(2)


# ── JWT ───────────────────────────────────────────────────────────────────────

def _make_token(user_id: str, email: str, role: str) -> str:
    return jwt.encode(
        {
            "sub":   user_id,
            "email": email,
            "role":  role,
            "exp":   datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
            "iat":   datetime.now(timezone.utc),
        },
        JWT_SECRET, algorithm="HS256",
    )


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired — please log in again.")
    except Exception:
        raise HTTPException(401, "Invalid token.")


def _require_admin(token: str) -> dict:
    p = _decode(token)
    if p.get("role") != "admin":
        raise HTTPException(403, "Admin access required.")
    return p


# ── Audit helper ──────────────────────────────────────────────────────────────

def _audit(user_id, email, action, resource="", details=None, ip="", status="success"):
    try:
        q("""INSERT INTO audit_logs
               (user_id, user_email, action, resource, details, ip_address, status)
             VALUES (%s, %s, %s, %s, %s, %s, %s)""",
          (user_id, email, action, resource,
           json.dumps(details or {}), ip, status))
    except Exception:
        pass


# ── Models ────────────────────────────────────────────────────────────────────

class LoginReq(BaseModel):
    email: str
    password: str

class RegisterReq(BaseModel):
    name: str
    email: str
    password: str
    mobile: Optional[str] = ""
    state:  Optional[str] = ""
    role:   Optional[str] = "user"

class VerifyReq(BaseModel):
    token: str

class AuditReq(BaseModel):
    token:      str
    action:     str
    resource:   Optional[str]  = ""
    details:    Optional[dict] = {}
    ip_address: Optional[str]  = ""

class UpdateUserReq(BaseModel):
    name:   Optional[str] = None
    mobile: Optional[str] = None
    state:  Optional[str] = None
    role:   Optional[str] = None

class ChangePasswordReq(BaseModel):
    token:        str
    old_password: str
    new_password: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}


@app.post("/auth/login")
def login(req: LoginReq, request: Request):
    ip   = request.client.host if request.client else ""
    user = q1("SELECT * FROM users WHERE email = %s AND is_active = true", (req.email,))

    if not user or not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
        _audit(None, req.email, "login", status="failed",
               details={"reason": "invalid credentials"}, ip=ip)
        raise HTTPException(401, "Invalid email or password.")

    uid = str(user["id"])
    q("""UPDATE users
         SET last_login = NOW(), last_login_ip = %s, login_count = login_count + 1,
             updated_at = NOW()
         WHERE id = %s""", (ip, uid))
    _audit(uid, user["email"], "login", ip=ip)

    return {
        "token": _make_token(uid, user["email"], user["role"]),
        "user": {
            "id":     uid,
            "name":   user["name"],
            "email":  user["email"],
            "role":   user["role"],
            "mobile": user["mobile"] or "",
            "state":  user["state"]  or "",
        },
    }


@app.post("/auth/verify")
def verify(req: VerifyReq):
    p    = _decode(req.token)
    user = q1("SELECT id, name, email, role, mobile, state FROM users WHERE id = %s AND is_active = true",
              (p["sub"],))
    if not user:
        raise HTTPException(401, "User not found or deactivated.")
    return {"valid": True, "user": {**user, "id": str(user["id"])}}


@app.post("/auth/logout")
def logout(req: VerifyReq, request: Request):
    ip = request.client.host if request.client else ""
    try:
        p = _decode(req.token)
        _audit(p["sub"], p["email"], "logout", ip=ip)
    except Exception:
        pass
    return {"status": "logged_out"}


@app.post("/auth/register")
def register(req: RegisterReq, x_auth_token: Optional[str] = Header(None)):
    # Only admins can create users, or allow open registration via env flag
    if x_auth_token:
        _require_admin(x_auth_token)

    if q1("SELECT id FROM users WHERE email = %s", (req.email,)):
        raise HTTPException(409, "Email already registered.")

    uid = str(uuid.uuid4())
    pw  = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt(rounds=10)).decode()
    q("""INSERT INTO users (id, name, email, mobile, state, role, password_hash)
         VALUES (%s, %s, %s, %s, %s, %s, %s)""",
      (uid, req.name, req.email, req.mobile, req.state, req.role, pw))

    by = _decode(x_auth_token)["email"] if x_auth_token else "self-register"
    _audit(uid, req.email, "register",
           details={"name": req.name, "role": req.role, "created_by": by})
    return {"status": "created", "user_id": uid}


@app.get("/auth/users")
def list_users(x_auth_token: str = Header()):
    _require_admin(x_auth_token)
    return q("""SELECT id, name, email, mobile, state, role, is_active,
                       created_at, updated_at, last_login, last_login_ip, login_count
                FROM users ORDER BY created_at DESC""")


@app.patch("/auth/users/{user_id}")
def update_user(user_id: str, req: UpdateUserReq,
                x_auth_token: str = Header()):
    p = _require_admin(x_auth_token)
    fields, vals = [], []
    for col, val in [("name", req.name), ("mobile", req.mobile),
                     ("state", req.state), ("role", req.role)]:
        if val is not None:
            fields.append(f"{col} = %s")
            vals.append(val)
    if not fields:
        raise HTTPException(400, "No fields to update.")
    vals += [user_id]
    q(f"UPDATE users SET {', '.join(fields)}, updated_at = NOW() WHERE id = %s", vals)
    _audit(p["sub"], p["email"], "update_user",
           details={"target": user_id, "changes": req.model_dump(exclude_none=True)})
    return {"status": "updated"}


@app.post("/auth/users/{user_id}/toggle")
def toggle_user(user_id: str, x_auth_token: str = Header()):
    p    = _require_admin(x_auth_token)
    user = q1("SELECT is_active, email FROM users WHERE id = %s", (user_id,))
    if not user:
        raise HTTPException(404, "User not found.")
    new_status = not user["is_active"]
    q("UPDATE users SET is_active = %s, updated_at = NOW() WHERE id = %s",
      (new_status, user_id))
    _audit(p["sub"], p["email"], "toggle_user",
           details={"target_email": user["email"], "is_active": new_status})
    return {"status": "ok", "is_active": new_status}


@app.post("/auth/users/{user_id}/reset-password")
def reset_password(user_id: str, x_auth_token: str = Header()):
    p    = _require_admin(x_auth_token)
    user = q1("SELECT email FROM users WHERE id = %s", (user_id,))
    if not user:
        raise HTTPException(404, "User not found.")
    default_pw = "Welcome@123"
    pw = bcrypt.hashpw(default_pw.encode(), bcrypt.gensalt(rounds=10)).decode()
    q("UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s", (pw, user_id))
    _audit(p["sub"], p["email"], "reset_password",
           details={"target_email": user["email"]})
    return {"status": "ok", "new_password": default_pw}


@app.post("/auth/change-password")
def change_password(req: ChangePasswordReq):
    p    = _decode(req.token)
    user = q1("SELECT * FROM users WHERE id = %s", (p["sub"],))
    if not user or not bcrypt.checkpw(req.old_password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Current password is incorrect.")
    pw = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt(rounds=10)).decode()
    q("UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
      (pw, str(user["id"])))
    _audit(str(user["id"]), user["email"], "change_password")
    return {"status": "ok"}


@app.post("/audit/log")
def log_audit(req: AuditReq):
    try:
        p = _decode(req.token)
        _audit(p["sub"], p["email"], req.action, req.resource,
               req.details, req.ip_address)
    except Exception:
        pass
    return {"status": "logged"}


@app.get("/audit/logs")
def get_audit_logs(limit: int = 200, action: str = None,
                   x_auth_token: str = Header()):
    _require_admin(x_auth_token)
    if action:
        return q("""SELECT al.*, u.name as user_name
                    FROM audit_logs al LEFT JOIN users u ON u.id = al.user_id
                    WHERE al.action = %s ORDER BY al.created_at DESC LIMIT %s""",
                 (action, limit))
    return q("""SELECT al.*, u.name as user_name
                FROM audit_logs al LEFT JOIN users u ON u.id = al.user_id
                ORDER BY al.created_at DESC LIMIT %s""", (limit,))


@app.get("/audit/stats")
def audit_stats(x_auth_token: str = Header()):
    _require_admin(x_auth_token)
    return {
        "total_users":    (q1("SELECT COUNT(*) AS n FROM users") or {}).get("n", 0),
        "active_users":   (q1("SELECT COUNT(*) AS n FROM users WHERE is_active = true") or {}).get("n", 0),
        "admin_count":    (q1("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'") or {}).get("n", 0),
        "logins_today":   (q1("""SELECT COUNT(*) AS n FROM audit_logs
                                 WHERE action = 'login' AND status = 'success'
                                   AND created_at >= NOW() - INTERVAL '24 hours'""") or {}).get("n", 0),
        "failed_logins":  (q1("""SELECT COUNT(*) AS n FROM audit_logs
                                 WHERE action = 'login' AND status = 'failed'
                                   AND created_at >= NOW() - INTERVAL '24 hours'""") or {}).get("n", 0),
        "total_actions":  (q1("SELECT COUNT(*) AS n FROM audit_logs") or {}).get("n", 0),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

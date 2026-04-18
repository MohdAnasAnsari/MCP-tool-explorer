-- ── App database schema ──────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    mobile        VARCHAR(20)  DEFAULT '',
    state         VARCHAR(100) DEFAULT '',
    role          VARCHAR(50)  DEFAULT 'user',   -- 'admin' | 'user'
    password_hash TEXT         NOT NULL,
    is_active     BOOLEAN      DEFAULT true,
    created_at    TIMESTAMPTZ  DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  DEFAULT NOW(),
    last_login    TIMESTAMPTZ,
    last_login_ip VARCHAR(45)  DEFAULT '',
    login_count   INTEGER      DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     UUID         REFERENCES users(id) ON DELETE SET NULL,
    user_email  VARCHAR(255) DEFAULT '',
    action      VARCHAR(100) NOT NULL,
    resource    VARCHAR(255) DEFAULT '',
    details     JSONB        DEFAULT '{}',
    ip_address  VARCHAR(45)  DEFAULT '',
    user_agent  TEXT         DEFAULT '',
    status      VARCHAR(20)  DEFAULT 'success',
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user_id   ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created   ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action    ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_users_email     ON users(email);

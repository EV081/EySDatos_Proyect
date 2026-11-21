-- Segundo factor independiente del perfil de Discord. No guardar el secreto TOTP en claro.
CREATE TABLE IF NOT EXISTS mfa_accounts (
    discord_id text PRIMARY KEY CHECK (discord_id ~ '^[0-9]{17,20}$'),
    encrypted_secret text NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    last_step bigint NOT NULL DEFAULT -1,
    recovery_hashes bytea[] NOT NULL DEFAULT '{}',
    failed_attempts integer NOT NULL DEFAULT 0,
    locked_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mfa_sessions (
    session_hash bytea PRIMARY KEY,
    csrf_hash bytea NOT NULL,
    discord_id text NOT NULL REFERENCES mfa_accounts(discord_id) ON DELETE CASCADE,
    enrolling boolean NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS mfa_sessions_by_id ON mfa_sessions(discord_id);
REVOKE ALL ON mfa_accounts, mfa_sessions FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON mfa_accounts, mfa_sessions TO directory_app;
GRANT SELECT ON mfa_accounts, mfa_sessions TO directory_backup;

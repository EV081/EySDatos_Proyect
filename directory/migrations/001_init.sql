-- Esquema mínimo del directorio (C-05): ID de Discord, llave pública, fechas y versión del aviso aceptado.
-- No hay nombre de usuario, correo, avatar ni direcciones IP. Se ejecuta como directory_owner.

CREATE TABLE IF NOT EXISTS keys (
    discord_id      text        PRIMARY KEY CHECK (discord_id ~ '^[0-9]{17,20}$'),
    public_key      bytea       NOT NULL CHECK (octet_length(public_key) = 32),
    registered_at   timestamptz NOT NULL DEFAULT now(),
    key_changed_at  timestamptz,
    consent_version text        NOT NULL CHECK (length(consent_version) BETWEEN 1 AND 32),
    consent_at      timestamptz NOT NULL DEFAULT now()
);

-- Llaves reemplazadas: sirven para revisar un cambio sospechoso y se borran a los 90 días (C-10).
CREATE TABLE IF NOT EXISTS replaced_keys (
    discord_id  text        NOT NULL REFERENCES keys (discord_id) ON DELETE CASCADE,
    public_key  bytea       NOT NULL CHECK (octet_length(public_key) = 32),
    replaced_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS replaced_keys_by_id ON replaced_keys (discord_id);

-- Estado efímero de OAuth2 y de la prueba de posesión. Solo se guardan hashes de los secretos.
CREATE TABLE IF NOT EXISTS oauth_states (
    state_hash    bytea       PRIMARY KEY,
    code_verifier text        NOT NULL,
    expires_at    timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash bytea       PRIMARY KEY,
    discord_id text        NOT NULL,
    expires_at timestamptz NOT NULL,
    used       boolean     NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS challenges (
    nonce_hash bytea       PRIMARY KEY,
    discord_id text        NOT NULL,
    purpose    text        NOT NULL CHECK (purpose IN ('register', 'cancel')),
    expires_at timestamptz NOT NULL,
    used       boolean     NOT NULL DEFAULT false
);

-- Mínimos permisos (C-08): la aplicación solo lee y escribe filas, no crea ni altera nada.
REVOKE ALL ON ALL TABLES IN SCHEMA directory FROM PUBLIC;
GRANT USAGE ON SCHEMA directory TO directory_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON keys, replaced_keys, oauth_states, auth_tokens, challenges
    TO directory_app;

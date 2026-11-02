"""Único módulo que habla con Postgres. Todas las consultas usan parámetros (`%s`): nunca se arma SQL con
texto del usuario (C-08). Los secretos efímeros (state, token, nonce) se guardan solo como SHA-256."""
import hashlib

from psycopg_pool import ConnectionPool

REPLACED_KEY_RETENTION_DAYS = 90


def digest(secret: bytes) -> bytes:
    return hashlib.sha256(secret).digest()


class Repo:
    def __init__(self, database_url: str, min_size: int = 1, max_size: int = 5):
        self._pool = ConnectionPool(database_url, min_size=min_size, max_size=max_size, open=True,
                                    kwargs={"options": "-c search_path=directory"})

    def close(self) -> None:
        self._pool.close()

    # --- OAuth2 ---------------------------------------------------------------------

    def save_oauth_state(self, state: bytes, code_verifier: str, ttl: int) -> None:
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO oauth_states (state_hash, code_verifier, expires_at) "
                         "VALUES (%s, %s, now() + make_interval(secs => %s))", (digest(state), code_verifier, ttl))

    def pop_oauth_state(self, state: bytes) -> str | None:
        """Un state sirve una sola vez: se borra al leerlo."""
        with self._pool.connection() as conn:
            row = conn.execute("DELETE FROM oauth_states WHERE state_hash = %s RETURNING code_verifier, "
                               "expires_at > now()", (digest(state),)).fetchone()
        return row[0] if row and row[1] else None

    def create_token(self, token: bytes, discord_id: str, ttl: int) -> None:
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO auth_tokens (token_hash, discord_id, expires_at) "
                         "VALUES (%s, %s, now() + make_interval(secs => %s))", (digest(token), discord_id, ttl))

    def token_owner(self, token: bytes) -> str | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT discord_id FROM auth_tokens WHERE token_hash = %s AND NOT used "
                               "AND expires_at > now()", (digest(token),)).fetchone()
        return row[0] if row else None

    # --- prueba de posesión ---------------------------------------------------------

    def create_challenge(self, nonce: bytes, discord_id: str, purpose: str, ttl: int) -> None:
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO challenges (nonce_hash, discord_id, purpose, expires_at) "
                         "VALUES (%s, %s, %s, now() + make_interval(secs => %s))",
                         (digest(nonce), discord_id, purpose, ttl))

    def consume_challenge(self, nonce: bytes, discord_id: str, purpose: str) -> bool:
        """Marca el nonce como usado aunque la firma luego falle: no se puede reintentar con el mismo."""
        with self._pool.connection() as conn:
            row = conn.execute("UPDATE challenges SET used = true WHERE nonce_hash = %s AND discord_id = %s "
                               "AND purpose = %s AND NOT used AND expires_at > now() RETURNING 1",
                               (digest(nonce), discord_id, purpose)).fetchone()
        return row is not None

    # --- llaves ---------------------------------------------------------------------

    def get_key(self, discord_id: str) -> bytes | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT public_key FROM keys WHERE discord_id = %s", (discord_id,)).fetchone()
        return bytes(row[0]) if row else None

    def get_record(self, discord_id: str) -> dict | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT public_key, registered_at, key_changed_at, consent_version, consent_at "
                               "FROM keys WHERE discord_id = %s", (discord_id,)).fetchone()
        if row is None:
            return None
        return {"public_key": bytes(row[0]), "registered_at": row[1], "key_changed_at": row[2],
                "consent_version": row[3], "consent_at": row[4]}

    def publish_key(self, token: bytes, discord_id: str, public_key: bytes, consent_version: str) -> str | None:
        """Consume el token y publica la llave en una sola transacción.

        Devuelve "created", "changed" o "same"; None si el token ya no es válido para ese ID."""
        with self._pool.connection() as conn, conn.transaction():
            if conn.execute("UPDATE auth_tokens SET used = true WHERE token_hash = %s AND discord_id = %s "
                            "AND NOT used AND expires_at > now() RETURNING 1",
                            (digest(token), discord_id)).fetchone() is None:
                return None
            row = conn.execute("SELECT public_key FROM keys WHERE discord_id = %s FOR UPDATE",
                               (discord_id,)).fetchone()
            if row is None:
                conn.execute("INSERT INTO keys (discord_id, public_key, consent_version) VALUES (%s, %s, %s)",
                             (discord_id, public_key, consent_version))
                return "created"
            if bytes(row[0]) == public_key:
                conn.execute("UPDATE keys SET consent_version = %s, consent_at = now() WHERE discord_id = %s",
                             (consent_version, discord_id))
                return "same"
            conn.execute("INSERT INTO replaced_keys (discord_id, public_key) VALUES (%s, %s)",
                         (discord_id, bytes(row[0])))
            conn.execute("UPDATE keys SET public_key = %s, key_changed_at = now(), consent_version = %s, "
                         "consent_at = now() WHERE discord_id = %s", (public_key, consent_version, discord_id))
            return "changed"

    def cancel(self, token: bytes, discord_id: str) -> bool:
        """Borra el registro y sus llaves reemplazadas en el acto (C-11). Consume el token."""
        with self._pool.connection() as conn, conn.transaction():
            if conn.execute("UPDATE auth_tokens SET used = true WHERE token_hash = %s AND discord_id = %s "
                            "AND NOT used AND expires_at > now() RETURNING 1",
                            (digest(token), discord_id)).fetchone() is None:
                return False
            conn.execute("DELETE FROM replaced_keys WHERE discord_id = %s", (discord_id,))
            return conn.execute("DELETE FROM keys WHERE discord_id = %s RETURNING 1",
                                (discord_id,)).fetchone() is not None

    # --- retención (C-10) -----------------------------------------------------------

    def purge(self) -> dict[str, int]:
        """Borra llaves reemplazadas de más de 90 días y todo el estado efímero vencido o usado."""
        with self._pool.connection() as conn, conn.transaction():
            counts = {
                "replaced_keys": conn.execute(
                    "DELETE FROM replaced_keys WHERE replaced_at < now() - make_interval(days => %s)",
                    (REPLACED_KEY_RETENTION_DAYS,)).rowcount,
                "oauth_states": conn.execute("DELETE FROM oauth_states WHERE expires_at < now()").rowcount,
                "auth_tokens": conn.execute("DELETE FROM auth_tokens WHERE used OR expires_at < now()").rowcount,
                "challenges": conn.execute("DELETE FROM challenges WHERE used OR expires_at < now()").rowcount,
            }
        return counts

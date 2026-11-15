"""Único módulo que habla con Postgres. Todas las consultas usan parámetros (`%s`): nunca se arma SQL con
texto del usuario (C-08). Los secretos efímeros (state, token, nonce) se guardan solo como SHA-256."""
import hashlib
import hmac
import re

from psycopg_pool import ConnectionPool

from .mfa import Authenticator, new_recovery_codes, recovery_digest

REPLACED_KEY_RETENTION_DAYS = 90


def digest(secret: bytes) -> bytes:
    return hashlib.sha256(secret).digest()


class Repo:
    def __init__(self, database_url: str, min_size: int = 1, max_size: int = 5):
        self._pool = ConnectionPool(database_url, min_size=min_size, max_size=max_size, open=True)  # search_path: fijado en el rol (migrations/apply.py)

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

    # --- segundo factor ------------------------------------------------------------

    def start_mfa(self, discord_id: str, session: bytes, csrf: bytes, ciphertext: str,
                  ttl: int = 300) -> tuple[str, bool]:
        with self._pool.connection() as conn, conn.transaction():
            conn.execute("INSERT INTO mfa_accounts (discord_id, encrypted_secret) VALUES (%s, %s) "
                         "ON CONFLICT (discord_id) DO NOTHING", (discord_id, ciphertext))
            row = conn.execute("SELECT encrypted_secret, enabled FROM mfa_accounts "
                               "WHERE discord_id = %s FOR UPDATE", (discord_id,)).fetchone()
            # Un único intento de OAuth pendiente por cuenta. Un nuevo OAuth no quita el bloqueo.
            conn.execute("DELETE FROM mfa_sessions WHERE discord_id = %s", (discord_id,))
            conn.execute("INSERT INTO mfa_sessions (session_hash, csrf_hash, discord_id, enrolling, expires_at) "
                         "VALUES (%s, %s, %s, %s, now() + make_interval(secs => %s))",
                         (digest(session), digest(csrf), discord_id, not row[1], ttl))
        return row[0], not row[1]

    def verify_mfa(self, session: bytes, csrf: bytes, code: str, authenticator: Authenticator,
                   token: bytes, token_ttl: int) -> tuple[str, list[str], str | None] | None:
        """Verifica, consume el factor y emite el token en la misma transacción.

        Recuperación: reemplaza el factor perdido y exige confirmar el nuevo QR antes de emitir token.
        El bloqueo por cuenta persiste entre sesiones, reinicios y procesos del servidor.
        """
        with self._pool.connection() as conn, conn.transaction():
            owner = conn.execute("SELECT discord_id FROM mfa_sessions WHERE session_hash = %s",
                                 (digest(session),)).fetchone()
            if owner is None:
                return None
            discord_id = owner[0]
            # Mismo orden de bloqueo que start_mfa para serializar sesiones de la misma cuenta.
            account = conn.execute("SELECT encrypted_secret, enabled, last_step, recovery_hashes, "
                                   "failed_attempts, locked_until > now() FROM mfa_accounts "
                                   "WHERE discord_id = %s FOR UPDATE", (discord_id,)).fetchone()
            pending = conn.execute("SELECT csrf_hash, enrolling, attempts, expires_at > now() "
                                   "FROM mfa_sessions WHERE session_hash = %s FOR UPDATE",
                                   (digest(session),)).fetchone()
            if (account is None or pending is None or not pending[3] or pending[2] >= 5
                    or account[5] or not hmac.compare_digest(bytes(pending[0]), digest(csrf))
                    or pending[1] == account[1]):
                return None
            step = authenticator.matching_step(account[0], code, account[2])
            recovery = (account[1] and re.fullmatch(r"[0-9A-Fa-f-]{32,35}", code)
                        and any(hmac.compare_digest(recovery_digest(code), bytes(h)) for h in account[3]))
            if step is None and not recovery:
                # Un bloqueo vencido inicia un nuevo presupuesto; OAuth no lo restablece.
                failures = account[4] + 1 if account[5] is None else 1
                conn.execute("UPDATE mfa_accounts SET failed_attempts = %s, locked_until = "
                             "CASE WHEN %s >= 5 THEN now() + interval '5 minutes' ELSE NULL END "
                             "WHERE discord_id = %s", (failures, failures, discord_id))
                conn.execute("UPDATE mfa_sessions SET attempts = attempts + 1 WHERE session_hash = %s",
                             (digest(session),))
                return None
            if recovery:
                ciphertext = authenticator.new_secret()
                conn.execute("UPDATE mfa_accounts SET encrypted_secret = %s, enabled = false, last_step = -1, "
                             "recovery_hashes = '{}', failed_attempts = 0, locked_until = NULL, created_at = now() "
                             "WHERE discord_id = %s", (ciphertext, discord_id))
                conn.execute("DELETE FROM auth_tokens WHERE discord_id = %s", (discord_id,))
                conn.execute("UPDATE mfa_sessions SET enrolling = true, attempts = 0, "
                             "expires_at = now() + interval '5 minutes' WHERE session_hash = %s", (digest(session),))
                return discord_id, [], ciphertext
            codes = new_recovery_codes() if pending[1] else []
            if codes:
                conn.execute("UPDATE mfa_accounts SET recovery_hashes = %s WHERE discord_id = %s",
                             ([recovery_digest(c) for c in codes], discord_id))
            conn.execute("UPDATE mfa_accounts SET enabled = true, last_step = %s, failed_attempts = 0, "
                         "locked_until = NULL WHERE discord_id = %s", (step, discord_id))
            conn.execute("DELETE FROM mfa_sessions WHERE discord_id = %s", (discord_id,))
            conn.execute("INSERT INTO auth_tokens (token_hash, discord_id, expires_at) "
                         "VALUES (%s, %s, now() + make_interval(secs => %s))", (digest(token), discord_id, token_ttl))
            return discord_id, codes, None

    def mfa_status(self, discord_id: str) -> dict | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT enabled, cardinality(recovery_hashes), created_at FROM mfa_accounts "
                               "WHERE discord_id = %s", (discord_id,)).fetchone()
        return {"enabled": row[0], "recovery_codes_remaining": row[1],
                "created_at": row[2].isoformat()} if row else None

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

    def replaced_keys(self, discord_id: str) -> list[dict]:
        """Llaves anteriores que aún se conservan (máximo 90 días), de la más reciente a la más antigua."""
        with self._pool.connection() as conn:
            rows = conn.execute("SELECT public_key, replaced_at FROM replaced_keys WHERE discord_id = %s "
                                "ORDER BY replaced_at DESC", (discord_id,)).fetchall()
        return [{"public_key": bytes(r[0]), "replaced_at": r[1]} for r in rows]

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
            conn.execute("DELETE FROM mfa_accounts WHERE discord_id = %s", (discord_id,))
            conn.execute("DELETE FROM auth_tokens WHERE discord_id = %s", (discord_id,))
            conn.execute("DELETE FROM challenges WHERE discord_id = %s", (discord_id,))
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
                "mfa_sessions": conn.execute("DELETE FROM mfa_sessions WHERE expires_at < now()").rowcount,
                "mfa_pending": conn.execute("DELETE FROM mfa_accounts WHERE NOT enabled "
                                            "AND created_at < now() - interval '1 day' "
                                            "AND NOT EXISTS (SELECT 1 FROM mfa_sessions s "
                                            "WHERE s.discord_id = mfa_accounts.discord_id)").rowcount,
            }
        return counts

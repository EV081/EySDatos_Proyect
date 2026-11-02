"""Configuración del directorio. Todo sale del entorno (RS10); nada sensible tiene valor por defecto."""
import os
from dataclasses import dataclass

from crypto import Pseudonymizer


@dataclass(frozen=True)
class Settings:
    database_url: str
    discord_client_id: str
    discord_client_secret: str
    discord_redirect_uri: str
    pseudonymizer: Pseudonymizer
    token_ttl: int = 600       # token de registro emitido tras OAuth2: 10 min, un solo uso
    challenge_ttl: int = 120   # nonce de la prueba de posesión
    oauth_state_ttl: int = 600
    lookup_limit: int = 30     # consultas por minuto y por IP (anti-enumeración)
    write_limit: int = 10      # publicaciones, nonces y logins por minuto y por IP
    audit_log_dir: str | None = None       # registros de auditoría (90 días); sin él, solo consola
    alert_webhook_url: str | None = None   # opcional: canal privado de operadores

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ["DATABASE_URL"],
            discord_client_id=os.environ["DISCORD_CLIENT_ID"],
            discord_client_secret=os.environ["DISCORD_CLIENT_SECRET"],
            discord_redirect_uri=os.environ["DISCORD_REDIRECT_URI"],
            pseudonymizer=Pseudonymizer.from_env("PSEUDONYM_KEY"),
            audit_log_dir=os.environ.get("AUDIT_LOG_DIR", "logs"),
            alert_webhook_url=os.environ.get("ALERT_WEBHOOK_URL") or None,
        )

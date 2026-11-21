"""Interfaces con los servicios que implementa Farid. El cliente no importa sus módulos."""
from typing import Callable, Protocol


class DirectoryError(Exception):
    """El directorio no respondió o devolvió un error. `status`: código HTTP si respondió (401, 404...)."""

    def __init__(self, message: str = "", status: int | None = None):
        super().__init__(message)
        self.status = status


class DirectoryPort(Protocol):
    requires_mfa: bool

    def authenticate_session(self, discord_id: str, code: str, sign: Callable[[bytes], bytes]) -> None:
        """Exige un código nuevo del autenticador y la firma de la llave registrada para cada desbloqueo."""

    def register(self, discord_id: str, public_key: bytes, sign: Callable[[bytes], bytes],
                 consent_version: str, sign_old: Callable[[bytes], bytes] | None = None) -> None:
        """Publica la llave. El directorio entrega un nonce; `sign(nonce)` devuelve la prueba de posesión.

        `consent_version` es la versión del aviso de privacidad que la persona aceptó: el directorio debe
        guardarla junto con la fecha para poder demostrar el consentimiento. Con `sign_old(nonce)` la llave
        vigente autoriza el cambio a la nueva (rectificación)."""

    def record(self, discord_id: str) -> dict:
        """Derecho de acceso: todo lo que el directorio guarda de esta persona."""

    def cancel(self, discord_id: str, sign_key_change: Callable[[bytes, bytes], bytes]) -> None:
        """Cancelación: borra el registro. `sign_key_change(llave_nula, nonce)` firma con la llave vigente."""

    def get_key(self, discord_id: str) -> bytes | None:
        """Llave de firma publicada de ese usuario, o None si no está registrado (TLS 1.3, RS6)."""


class DiscordPort(Protocol):
    def send(self, text: str) -> None:
        """Publica un texto en el canal del proyecto. Puede lanzar si Discord no responde."""

    def set_receiver(self, callback: Callable[[str], None]) -> None:
        """Registra a quién se le entrega cada texto nuevo del canal. Se ignora el autor: siempre es un bot."""

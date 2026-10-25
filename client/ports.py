"""Interfaces con los servicios que implementa Farid. El cliente no importa sus módulos."""
from typing import Callable, Protocol


class DirectoryError(Exception):
    """El directorio no respondió o devolvió un error."""


class DirectoryPort(Protocol):
    def register(self, discord_id: str, public_key: bytes, sign: Callable[[bytes], bytes]) -> None:
        """Publica la llave. El directorio entrega un nonce; `sign(nonce)` devuelve la prueba de posesión."""

    def get_key(self, discord_id: str) -> bytes | None:
        """Llave de firma publicada de ese usuario, o None si no está registrado (TLS 1.3, RS6)."""


class DiscordPort(Protocol):
    def send(self, text: str) -> None:
        """Publica un texto en el canal del proyecto. Puede lanzar si Discord no responde."""

    def set_receiver(self, callback: Callable[[str], None]) -> None:
        """Registra a quién se le entrega cada texto nuevo del canal. Se ignora el autor: siempre es un bot."""

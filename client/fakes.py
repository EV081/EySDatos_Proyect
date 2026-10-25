"""Implementaciones en memoria de los puertos, para pruebas y para desarrollar sin Discord."""
from typing import Callable

from crypto import SignatureError, verify_registration

from .ports import DirectoryError


class FakeDirectory:
    """Directorio en memoria; valida la prueba de posesión igual que el real."""

    def __init__(self):
        self.keys: dict[str, bytes] = {}
        self.down = False
        self._nonce = 0

    def register(self, discord_id: str, public_key: bytes, sign: Callable[[bytes], bytes]) -> None:
        if self.down:
            raise DirectoryError("directorio caído")
        self._nonce += 1
        nonce = self._nonce.to_bytes(32, "big")
        try:
            verify_registration(public_key, discord_id, nonce, sign(nonce))
        except SignatureError:
            raise DirectoryError("prueba de posesión inválida") from None
        self.keys[discord_id] = public_key

    def get_key(self, discord_id: str) -> bytes | None:
        if self.down:
            raise DirectoryError("directorio caído")
        return self.keys.get(discord_id)


class FakeChannel:
    """Canal compartido: guarda todo lo publicado y lo entrega con `flush()` (sin reentrada)."""

    def __init__(self):
        self.log: list[str] = []
        self._ports: list["FakeDiscord"] = []
        self._pending: list[tuple[str, "FakeDiscord | None"]] = []

    def attach(self, port: "FakeDiscord") -> None:
        self._ports.append(port)

    def flush(self) -> int:
        delivered = 0
        while self._pending:
            text, only = self._pending.pop(0)
            for port in ([only] if only else list(self._ports)):
                if port.online and port.receiver:
                    port.receiver(text)
                    delivered += 1
        return delivered


class FakeDiscord:
    def __init__(self, channel: FakeChannel):
        self.channel, self.online, self.receiver = channel, True, None
        self.fail_sends = False
        channel.attach(self)

    def send(self, text: str) -> None:
        if self.fail_sends:
            raise ConnectionError("Discord no responde")
        self.channel.log.append(text)
        self.channel._pending.append((text, None))

    def set_receiver(self, callback) -> None:
        self.receiver = callback

    def reconnect_with_backlog(self) -> None:
        """Como al reabrir la app: el canal reentrega lo publicado mientras no estaba."""
        self.online = True
        for text in self.channel.log:
            self.channel._pending.append((text, self))

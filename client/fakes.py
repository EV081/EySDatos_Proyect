"""Implementaciones en memoria de los puertos, para pruebas y para desarrollar sin Discord."""
import time
from typing import Callable

from crypto import SignatureError, verify_key_change, verify_registration
from crypto.encoding import b64e

from .ports import DirectoryError


class FakeDirectory:
    """Directorio en memoria; valida la prueba de posesión igual que el real."""

    CANCEL_MARKER = bytes(32)

    def __init__(self):
        self.keys: dict[str, bytes] = {}
        self.consents: dict[str, str] = {}
        self.records: dict[str, dict] = {}
        self.down = False
        self._nonce = 0

    def _next_nonce(self) -> bytes:
        if self.down:
            raise DirectoryError("directorio caído")
        self._nonce += 1
        return self._nonce.to_bytes(32, "big")

    def register(self, discord_id: str, public_key: bytes, sign: Callable[[bytes], bytes],
                 consent_version: str, sign_old: Callable[[bytes], bytes] | None = None) -> None:
        nonce = self._next_nonce()
        current = self.keys.get(discord_id)
        try:
            verify_registration(public_key, discord_id, nonce, sign(nonce))
            if sign_old is not None:
                if current is None or current == public_key:
                    raise DirectoryError("cambio de llave inválido")
                verify_key_change(current, discord_id, public_key, nonce, sign_old(nonce))
        except SignatureError:
            raise DirectoryError("prueba de posesión inválida") from None
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rec = self.records.setdefault(discord_id, {"registered_at": now, "key_changed_at": None,
                                                   "replaced_keys": []})
        if current is not None and current != public_key:
            rec["key_changed_at"] = now
            rec["replaced_keys"].insert(0, {"public_key": b64e(current), "replaced_at": now, "delete_after": None})
        rec.update(consent_version=consent_version, consent_at=now)
        self.keys[discord_id] = public_key
        self.consents[discord_id] = consent_version

    def record(self, discord_id: str) -> dict:
        if self.down:
            raise DirectoryError("directorio caído")
        if discord_id not in self.keys:
            raise DirectoryError("no registrado", 404)
        return {"discord_id": discord_id, "public_key": b64e(self.keys[discord_id]), **self.records[discord_id]}

    def cancel(self, discord_id: str, sign_key_change: Callable[[bytes, bytes], bytes]) -> None:
        nonce = self._next_nonce()
        current = self.keys.get(discord_id)
        if current is None:
            raise DirectoryError("no registrado", 401)
        try:
            verify_key_change(current, discord_id, self.CANCEL_MARKER, nonce, sign_key_change(self.CANCEL_MARKER, nonce))
        except SignatureError:
            raise DirectoryError("firma inválida", 401) from None
        del self.keys[discord_id], self.consents[discord_id], self.records[discord_id]

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

    def replay_backlog(self) -> None:
        """Como `DiscordAdapter.replay_backlog()`: el canal vuelve a entregar lo publicado (se entrega con `flush()`)."""
        self.reconnect_with_backlog()

    def reconnect_with_backlog(self) -> None:
        """Como al reabrir la app: el canal reentrega lo publicado mientras no estaba."""
        self.online = True
        for text in self.channel.log:
            self.channel._pending.append((text, self))

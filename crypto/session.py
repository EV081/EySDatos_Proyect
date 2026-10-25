import time

from . import aead
from .constants import (
    AAD_MSG, HARD_LIMIT_FACTOR, MAX_PLAINTEXT, REPLAY_WINDOW, ROTATE_AFTER_MESSAGES,
    ROTATE_AFTER_SECONDS,
)
from .errors import DecryptError, ReplayError, SessionExpired, WireError
from .wire import Msg


def _lp(text: str) -> bytes:
    data = text.encode("utf-8")
    return len(data).to_bytes(2, "big") + data


def _aad(sid: bytes, sender: str, receiver: str, ctr: int) -> bytes:
    return AAD_MSG + sid + _lp(sender) + _lp(receiver) + ctr.to_bytes(8, "big")


class _ReplayWindow:
    """Ventana deslizante de contadores ya vistos (RS14)."""

    def __init__(self):
        self._highest = 0
        self._bitmap = 0

    def accepts(self, ctr: int) -> bool:
        if ctr <= 0:
            return False
        if ctr > self._highest:
            return True
        diff = self._highest - ctr
        return diff < REPLAY_WINDOW and not (self._bitmap >> diff) & 1

    def commit(self, ctr: int) -> None:
        if ctr > self._highest:
            self._bitmap = ((self._bitmap << (ctr - self._highest)) | 1) & ((1 << REPLAY_WINDOW) - 1)
            self._highest = ctr
        else:
            self._bitmap |= 1 << (self._highest - ctr)


class Session:
    """Sesión activa entre dos usuarios: una llave AES-256-GCM por dirección."""

    def __init__(self, sid: bytes, my_id: str, peer_id: str, send_key: bytes, recv_key: bytes,
                 clock=time.time):
        self._sid = sid
        self._my_id, self._peer_id = my_id, peer_id
        self._send_key, self._recv_key = bytearray(send_key), bytearray(recv_key)
        self._clock = clock
        self._created = clock()
        self._sent = 0
        self._received = 0
        self._window = _ReplayWindow()
        self._used_nonces: set[bytes] = set()

    @property
    def sid(self) -> bytes:
        return self._sid

    @property
    def peer_id(self) -> str:
        return self._peer_id

    @property
    def destroyed(self) -> bool:
        return self._send_key is None

    def _messages(self) -> int:
        return self._sent + self._received

    def needs_rotation(self) -> bool:
        """Umbral blando (RS9): el cliente debe iniciar un nuevo handshake."""
        return (self._messages() >= ROTATE_AFTER_MESSAGES
                or self._clock() - self._created >= ROTATE_AFTER_SECONDS)

    def expired(self) -> bool:
        """Umbral duro: la sesión deja de cifrar y descifrar."""
        return (self._messages() >= ROTATE_AFTER_MESSAGES * HARD_LIMIT_FACTOR
                or self._clock() - self._created >= ROTATE_AFTER_SECONDS * HARD_LIMIT_FACTOR)

    def _ensure_usable(self) -> None:
        if self.destroyed:
            raise SessionExpired("la sesión fue destruida")
        if self.expired():
            self.destroy()
            raise SessionExpired("la sesión superó su límite; se requiere un nuevo handshake")

    def encrypt(self, plaintext: bytes) -> Msg:
        self._ensure_usable()
        if len(plaintext) > MAX_PLAINTEXT:
            raise WireError("el mensaje excede el tamaño máximo; debe partirse")
        ctr = self._sent + 1
        aad = _aad(self._sid, self._my_id, self._peer_id, ctr)
        nonce, ct = aead.seal(bytes(self._send_key), plaintext, aad, self._fresh_nonce())
        self._sent = ctr
        return Msg(self._my_id, self._peer_id, self._sid, ctr, nonce, ct)

    def _fresh_nonce(self) -> bytes:
        """Nunca repite un nonce bajo la misma llave (RS4)."""
        while True:
            nonce = aead.new_nonce()
            if nonce not in self._used_nonces:
                self._used_nonces.add(nonce)
                return nonce

    def decrypt(self, msg: Msg) -> bytes:
        self._ensure_usable()
        if msg.sid != self._sid or msg.sender != self._peer_id or msg.receiver != self._my_id:
            raise DecryptError("el mensaje no corresponde a esta sesión")
        if not self._window.accepts(msg.ctr):
            raise ReplayError("contador repetido o fuera de ventana")
        aad = _aad(self._sid, msg.sender, msg.receiver, msg.ctr)
        plaintext = aead.open_(bytes(self._recv_key), msg.nonce, msg.ct, aad)
        self._window.commit(msg.ctr)  # solo tras autenticar: un atacante no puede adelantarla
        self._received += 1
        return plaintext

    def destroy(self) -> None:
        """Borra las llaves de sesión de la memoria (mejor esfuerzo en Python)."""
        for key in (self._send_key, self._recv_key):
            if key is not None:
                key[:] = bytes(len(key))
        self._send_key = self._recv_key = None

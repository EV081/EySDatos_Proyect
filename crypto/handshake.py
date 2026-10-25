"""Handshake autenticado de tres mensajes con Diffie-Hellman efímero en ambos extremos.

    A -> B   hs1: ids, sid, R_A, epk_A, ts
    B -> A   hs2: R_B, epk_B, σ_B, tag_B
    A -> B   hs3: σ_A, tag_A

T = versión ‖ ids ‖ sid ‖ ts ‖ R_A ‖ R_B ‖ epk_A ‖ epk_B. Las firmas y las confirmaciones
de clave cubren T completa. Las llaves efímeras se destruyen al terminar (PFS, RS12).
La llave pública del otro extremo la entrega el cliente tras consultar el directorio y
comparar con su pin; esta librería no hace red.
"""
import hashlib
import hmac
import os
import time

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .constants import (
    CLOCK_SKEW, CTX_INITIATOR, CTX_RESPONDER, HANDSHAKE_TTL, INFO_KEY_AB, INFO_KEY_BA,
    INFO_KEY_CONF, LABEL_TAG_INITIATOR, LABEL_TAG_RESPONDER, VERSION,
)
from .errors import HandshakeError, ReplayError, SignatureError
from .identity import Identity, verify
from .session import Session
from .wire import Hs1, Hs2, Hs3

_MAX_SEEN = 4096


def _lp(text: str) -> bytes:
    data = text.encode("utf-8")
    return len(data).to_bytes(2, "big") + data


def _transcript(id_a: str, id_b: str, sid: bytes, ts: int, ra: bytes, rb: bytes,
                epk_a: bytes, epk_b: bytes) -> bytes:
    return b"".join([bytes([VERSION]), _lp(id_a), _lp(id_b), sid, ts.to_bytes(8, "big"),
                     ra, rb, epk_a, epk_b])


def _exchange(private: X25519PrivateKey, peer_public: bytes) -> bytes:
    try:
        shared = private.exchange(X25519PublicKey.from_public_bytes(peer_public))
    except (ValueError, InvalidKey):
        raise HandshakeError("llave efímera inválida") from None
    if not any(shared):  # punto de orden bajo: secreto compartido nulo
        raise HandshakeError("llave efímera inválida")
    return shared


def _derive(shared: bytes, transcript: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    digest = hashlib.sha256(transcript).digest()

    def expand(info: bytes) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=digest, info=info).derive(shared)

    return expand(INFO_KEY_AB), expand(INFO_KEY_BA), expand(INFO_KEY_CONF), digest


def _tag(k_conf: bytes, label: bytes, digest: bytes) -> bytes:
    return hmac.new(k_conf, label + digest, hashlib.sha256).digest()


def _verify_peer(peer_public: bytes, context: bytes, transcript: bytes, sig: bytes) -> None:
    try:
        verify(peer_public, context, transcript, sig)
    except SignatureError:
        raise HandshakeError("firma del handshake inválida") from None


def _verify_tag(expected: bytes, received: bytes) -> None:
    if not hmac.compare_digest(expected, received):
        raise HandshakeError("confirmación de clave inválida")


class SidCache:
    """Recuerda los `sid` de hs1 ya aceptados para rechazar un handshake repetido."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self._seen: dict[bytes, float] = {}

    def check_and_add(self, sid: bytes) -> None:
        now = self._clock()
        self._seen = {s: t for s, t in self._seen.items() if now - t <= HANDSHAKE_TTL + CLOCK_SKEW}
        if sid in self._seen:
            raise ReplayError("handshake repetido")
        if len(self._seen) >= _MAX_SEEN:
            self._seen.pop(next(iter(self._seen)))
        self._seen[sid] = now


class Initiator:
    """Lado que abre la sesión (Alice)."""

    def __init__(self, identity: Identity, my_id: str, peer_id: str, peer_public_key: bytes,
                 clock=time.time):
        self._identity, self._my_id, self._peer_id = identity, my_id, peer_id
        self._peer_pk, self._clock = peer_public_key, clock
        self._a: X25519PrivateKey | None = None
        self._hs1: Hs1 | None = None
        self._done = False

    def start(self) -> Hs1:
        if self._hs1 is not None:
            raise HandshakeError("el handshake ya fue iniciado")
        self._a = X25519PrivateKey.generate()
        self._hs1 = Hs1(self._my_id, self._peer_id, os.urandom(16), os.urandom(32),
                        self._a.public_key().public_bytes_raw(), int(self._clock()))
        return self._hs1

    def finish(self, hs2: Hs2) -> tuple[Hs3, Session]:
        """Un hs2 inválido se rechaza sin matar el intento; solo caducar o triunfar lo cierra."""
        if self._hs1 is None or self._done:
            raise HandshakeError("no hay un handshake pendiente")
        hs1 = self._hs1
        if self._clock() - hs1.ts > HANDSHAKE_TTL:
            self._close()
            raise HandshakeError("el intento de handshake caducó")
        if (hs2.sender, hs2.receiver, hs2.sid) != (self._peer_id, self._my_id, hs1.sid):
            raise HandshakeError("la respuesta no corresponde a este handshake")
        transcript = _transcript(self._my_id, self._peer_id, hs1.sid, hs1.ts, hs1.ra, hs2.rb,
                                 hs1.epk, hs2.epk)
        _verify_peer(self._peer_pk, CTX_RESPONDER, transcript, hs2.sig)
        k_ab, k_ba, k_conf, digest = _derive(_exchange(self._a, hs2.epk), transcript)
        _verify_tag(_tag(k_conf, LABEL_TAG_RESPONDER, digest), hs2.tag)
        hs3 = Hs3(self._my_id, self._peer_id, hs1.sid,
                  self._identity.sign(CTX_INITIATOR, transcript),
                  _tag(k_conf, LABEL_TAG_INITIATOR, digest))
        self._close()  # la llave efímera no sobrevive al handshake (RS12)
        return hs3, Session(hs1.sid, self._my_id, self._peer_id, k_ab, k_ba, self._clock)

    def _close(self) -> None:
        self._a = None
        self._done = True


class Responder:
    """Lado que acepta la sesión (Bob). Una instancia por cada hs1 recibido."""

    def __init__(self, identity: Identity, my_id: str, peer_id: str, peer_public_key: bytes,
                 seen: SidCache | None = None, clock=time.time):
        self._identity, self._my_id, self._peer_id = identity, my_id, peer_id
        self._peer_pk, self._seen, self._clock = peer_public_key, seen, clock
        self._state: tuple | None = None  # (transcript, digest, k_ab, k_ba, k_conf, sid, started)
        self._done = False

    def respond(self, hs1: Hs1) -> Hs2:
        if self._state is not None or self._done:
            raise HandshakeError("este respondedor ya procesó un hs1")
        if (hs1.sender, hs1.receiver) != (self._peer_id, self._my_id):
            raise HandshakeError("el hs1 no está dirigido a este usuario")
        age = self._clock() - hs1.ts
        if age > HANDSHAKE_TTL or age < -CLOCK_SKEW:
            raise HandshakeError("hs1 caducado o con fecha inválida")
        if self._seen is not None:
            self._seen.check_and_add(hs1.sid)
        b = X25519PrivateKey.generate()  # vive solo dentro de este método: ya no hace falta tras el ECDH
        epk_b, rb = b.public_key().public_bytes_raw(), os.urandom(32)
        transcript = _transcript(self._peer_id, self._my_id, hs1.sid, hs1.ts, hs1.ra, rb, hs1.epk, epk_b)
        k_ab, k_ba, k_conf, digest = _derive(_exchange(b, hs1.epk), transcript)
        self._state = (transcript, digest, k_ab, k_ba, k_conf, hs1.sid, self._clock())
        return Hs2(self._my_id, self._peer_id, hs1.sid, rb, epk_b,
                   self._identity.sign(CTX_RESPONDER, transcript),
                   _tag(k_conf, LABEL_TAG_RESPONDER, digest))

    def finish(self, hs3: Hs3) -> Session:
        """Un hs3 inválido se rechaza sin matar el intento; solo caducar o triunfar lo cierra."""
        if self._state is None or self._done:
            raise HandshakeError("no hay un handshake pendiente")
        transcript, digest, k_ab, k_ba, k_conf, sid, started = self._state
        if self._clock() - started > HANDSHAKE_TTL:
            self._close()
            raise HandshakeError("el intento de handshake caducó")
        if (hs3.sender, hs3.receiver, hs3.sid) != (self._peer_id, self._my_id, sid):
            raise HandshakeError("la confirmación no corresponde a este handshake")
        _verify_peer(self._peer_pk, CTX_INITIATOR, transcript, hs3.sig)
        _verify_tag(_tag(k_conf, LABEL_TAG_INITIATOR, digest), hs3.tag)
        self._close()  # la llave efímera se destruye al terminar (RS12)
        return Session(sid, self._my_id, self._peer_id, k_ba, k_ab, self._clock)

    def _close(self) -> None:
        self._state = None
        self._done = True

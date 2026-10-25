"""Núcleo criptográfico del proyecto: identidad, handshake autenticado, sesión y huella.

No hace red ni habla con Discord: solo recibe y produce estructuras de `wire`.
"""
from .errors import (
    CryptoError, DecryptError, HandshakeError, ReplayError, SessionExpired,
    SignatureError, VaultError, WireError,
)
from .fingerprint import fingerprint
from .handshake import Initiator, Responder, SidCache
from .pseudonym import Pseudonymizer, mask_id
from .identity import (
    Identity, KdfParams, sign_key_change, sign_registration, verify, verify_key_change,
    verify_registration,
)
from .session import Session
from .wire import Hs1, Hs2, Hs3, Msg, decode, encode

__all__ = [
    "CryptoError", "DecryptError", "HandshakeError", "ReplayError", "SessionExpired",
    "SignatureError", "VaultError", "WireError", "fingerprint", "Initiator", "Responder",
    "SidCache", "Identity", "KdfParams", "verify", "Session", "Hs1", "Hs2", "Hs3", "Msg",
    "decode", "encode", "Pseudonymizer", "mask_id", "sign_registration", "verify_registration", "sign_key_change",
    "verify_key_change",
]

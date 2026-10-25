import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .errors import DecryptError

NONCE_LEN = 12
KEY_LEN = 32


def new_nonce() -> bytes:
    return os.urandom(NONCE_LEN)  # CSPRNG del sistema operativo (RS4, RS11)


def seal(key: bytes, plaintext: bytes, aad: bytes, nonce: bytes | None = None) -> tuple[bytes, bytes]:
    """AES-256-GCM. Devuelve (nonce, ciphertext+tag)."""
    if len(key) != KEY_LEN:
        raise ValueError("la llave AES debe ser de 256 bits")
    nonce = nonce or new_nonce()
    return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)


def open_(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    """Descifra verificando la etiqueta GCM; cualquier fallo es DecryptError (RS5)."""
    if len(key) != KEY_LEN or len(nonce) != NONCE_LEN:
        raise DecryptError("llave o nonce con longitud inválida")
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag:
        raise DecryptError("etiqueta de autenticación inválida") from None

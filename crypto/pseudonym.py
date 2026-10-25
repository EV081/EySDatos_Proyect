"""Seudonimización y enmascarado de identificadores para registros y mensajes de diagnóstico.

Un hash sin clave de un ID de Discord no sirve: los IDs tienen una estructura conocida (llevan la fecha de
creación) y se pueden enumerar, así que bastaría probar candidatos para invertirlo. Por eso se usa HMAC-SHA256
con una clave secreta que vive en una variable de entorno (RS10), y el resultado se trata como dato personal
seudonimizado, no como anónimo.
"""
import base64
import binascii
import hashlib
import hmac
import os

MIN_KEY_LEN = 32
PSEUDONYM_LEN = 16  # caracteres hexadecimales = 64 bits
_DOMAIN = b"e2ee-discord/v1 pseudonym\x00"


def generate_key() -> bytes:
    return os.urandom(MIN_KEY_LEN)


class Pseudonymizer:
    """Produce un seudónimo estable por identificador mientras la clave no cambie.

    Rotar la clave cada 90 días (el plazo de retención de los registros) impide vincular a una persona entre
    periodos distintos. Para buscar a alguien en los registros se calcula su seudónimo con la clave; no hay
    forma de recorrer el camino inverso.
    """

    def __init__(self, key: bytes):
        if len(key) < MIN_KEY_LEN:
            raise ValueError(f"la clave de seudonimización debe tener al menos {MIN_KEY_LEN} bytes")
        self._key = bytes(key)

    @classmethod
    def from_env(cls, name: str = "PSEUDONYM_KEY") -> "Pseudonymizer":
        """Lee la clave (base64url) de una variable de entorno; falla si falta o es débil."""
        raw = os.environ.get(name)
        if not raw:
            raise ValueError(f"falta la variable de entorno {name}")
        try:
            key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        except (binascii.Error, ValueError):
            raise ValueError(f"{name} no es base64 válido") from None
        return cls(key)

    def pseudonym(self, identifier: str) -> str:
        if not isinstance(identifier, str):
            raise TypeError("el identificador debe ser texto")
        digest = hmac.new(self._key, _DOMAIN + identifier.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest[:PSEUDONYM_LEN]


def mask_id(identifier: str, visible: int = 4) -> str:
    """Enmascara un identificador dejando solo el inicio y el final: `123456789012345678` -> `1234…5678`.

    Es para pantallas y mensajes de diagnóstico donde alguien debe reconocer el ID sin verlo completo; no es
    una protección para almacenar datos.
    """
    if not isinstance(identifier, str):
        raise TypeError("el identificador debe ser texto")
    if len(identifier) <= visible * 2:
        return "*" * len(identifier)
    return f"{identifier[:visible]}…{identifier[-visible:]}"

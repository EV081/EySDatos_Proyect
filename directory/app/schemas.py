"""Formato de las solicitudes. Binarios en base64url sin relleno, decodificado de forma estricta."""
import base64
import binascii
from typing import Literal

from pydantic import BaseModel, Field

DISCORD_ID = r"^[0-9]{17,20}$"
B64URL = r"^[A-Za-z0-9_-]+$"


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64d(text: str, length: int) -> bytes:
    """Solo la forma canónica y con la longitud exacta; si no, ValueError."""
    try:
        data = base64.b64decode(text + "=" * (-len(text) % 4), altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("base64 inválido") from None
    if b64e(data) != text or len(data) != length:
        raise ValueError("base64 inválido")
    return data


class ChallengeRequest(BaseModel):
    discord_id: str = Field(pattern=DISCORD_ID)
    purpose: Literal["register", "cancel"]


class PublishKey(BaseModel):
    public_key: str = Field(pattern=B64URL, max_length=64)
    nonce: str = Field(pattern=B64URL, max_length=64)
    signature: str = Field(pattern=B64URL, max_length=128)
    consent_version: str = Field(pattern=r"^[0-9A-Za-z.\-]{1,32}$")
    old_signature: str | None = Field(default=None, pattern=B64URL, max_length=128)


class CancelKey(BaseModel):
    nonce: str = Field(pattern=B64URL, max_length=64)
    signature: str = Field(pattern=B64URL, max_length=128)

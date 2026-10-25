import base64
import binascii


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64d(text: str, length: int | None = None) -> bytes:
    """Decodifica base64url sin relleno de forma estricta (solo la forma canónica)."""
    if not isinstance(text, str) or not text.isascii():
        raise ValueError("base64 inválido")
    try:
        data = base64.b64decode(text + "=" * (-len(text) % 4), altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("base64 inválido") from None
    if b64e(data) != text:
        raise ValueError("base64 no canónico")
    if length is not None and len(data) != length:
        raise ValueError("longitud inválida")
    return data

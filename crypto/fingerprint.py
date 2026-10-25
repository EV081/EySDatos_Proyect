import hashlib

DIGITS = 60
GROUP = 5


def _digest(pk_a: bytes, pk_b: bytes) -> bytes:
    if pk_a == pk_b:
        raise ValueError("las llaves de ambos extremos no pueden ser iguales")
    first, second = sorted((pk_a, pk_b))  # mismo orden en ambos extremos (RS8)
    return hashlib.sha256(first + second).digest()


def fingerprint(pk_a: bytes, pk_b: bytes) -> str:
    """Huella de verificación: 60 dígitos decimales en 12 grupos de 5 (RF6, RS8)."""
    number = int.from_bytes(_digest(pk_a, pk_b), "big") % 10**DIGITS
    digits = str(number).zfill(DIGITS)
    return " ".join(digits[i:i + GROUP] for i in range(0, DIGITS, GROUP))


def qr_payload(pk_a: bytes, pk_b: bytes) -> bytes:
    """Contenido del QR: el digest completo, para comparar sin truncar."""
    return _digest(pk_a, pk_b)

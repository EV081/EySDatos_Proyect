"""TOTP estándar para Microsoft Authenticator. Los secretos se cifran fuera de Postgres."""
import hashlib
import hmac
import re
import secrets
from time import time

import pyotp
import qrcode
from cryptography.fernet import Fernet
from qrcode.image.svg import SvgPathFillImage


class Authenticator:
    def __init__(self, encryption_key: bytes):
        self.cipher = Fernet(encryption_key)

    def new_secret(self) -> str:
        return self.cipher.encrypt(pyotp.random_base32().encode("ascii")).decode("ascii")

    def secret(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode("ascii")).decode("ascii")

    def provisioning(self, ciphertext: str, discord_id: str) -> tuple[str, str]:
        secret = self.secret(ciphertext)
        uri = pyotp.TOTP(secret).provisioning_uri(name=discord_id, issuer_name="EySDatos")
        qr = qrcode.make(uri, image_factory=SvgPathFillImage, box_size=5)
        return secret, qr.to_string(encoding="unicode")

    def matching_step(self, ciphertext: str, code: str, last_step: int) -> int | None:
        if not re.fullmatch(r"[0-9]{6}", code):
            return None
        totp = pyotp.TOTP(self.secret(ciphertext))
        current = int(time()) // 30
        # Un paso de tolerancia por desfase de reloj; nunca aceptar de nuevo un paso usado.
        for step in (current, current - 1, current + 1):
            if step > last_step and hmac.compare_digest(totp.at(step * 30), code):
                return step
        return None


def recovery_digest(code: str) -> bytes:
    return hashlib.sha256(code.replace("-", "").upper().encode("ascii")).digest()


def new_recovery_codes() -> list[str]:
    codes = [secrets.token_hex(16).upper() for _ in range(10)]
    return ["-".join(code[i:i + 8] for i in range(0, 32, 8)) for code in codes]

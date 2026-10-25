import json
import os
import unicodedata
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import aead
from .constants import AAD_VAULT, CTX_KEY_CHANGE, CTX_PREFIX, CTX_REGISTER
from .encoding import b64d, b64e
from .errors import DecryptError, SignatureError, VaultError

SALT_LEN = 16
_RAW = serialization.Encoding.Raw
_RAW_PRIV = serialization.PrivateFormat.Raw
_NO_ENC = serialization.NoEncryption()


@dataclass(frozen=True)
class KdfParams:
    """Parámetros de Argon2id. Los valores por defecto superan la guía de OWASP."""

    time_cost: int = 3
    memory_kib: int = 64 * 1024
    parallelism: int = 4

    def validate(self) -> None:
        # Una bóveda importada no debe poder agotar la memoria del dispositivo.
        if not (1 <= self.time_cost <= 10 and 8 <= self.memory_kib <= 1024 * 1024 and 1 <= self.parallelism <= 16):
            raise VaultError("parámetros de Argon2id fuera de rango")


def _signed_payload(context: bytes, message: bytes) -> bytes:
    return CTX_PREFIX + context + b"\x00" + message


def _lp(text: str) -> bytes:
    data = text.encode("utf-8")
    return len(data).to_bytes(2, "big") + data


def verify(public_key: bytes, context: bytes, message: bytes, signature: bytes) -> None:
    """Verifica una firma con separación de dominio; lanza SignatureError si no vale."""
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, _signed_payload(context, message))
    except (InvalidSignature, ValueError):
        raise SignatureError("firma inválida") from None


def _derive(password: str, salt: bytes, kdf: KdfParams) -> bytes:
    secret = unicodedata.normalize("NFKC", password).encode("utf-8")
    return hash_secret_raw(
        secret, salt, kdf.time_cost, kdf.memory_kib, kdf.parallelism, aead.KEY_LEN, Type.ID
    )


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("ascii")


class Identity:
    """Identidad de firma Ed25519 de un usuario, más la llave del almacén local.

    La llave privada solo sale de esta clase dentro de una bóveda cifrada (RS1, RS2).
    """

    def __init__(self, signing_key: Ed25519PrivateKey, store_key: bytes):
        self._sk = signing_key
        self._store_key = store_key

    @classmethod
    def create(cls) -> "Identity":
        return cls(Ed25519PrivateKey.generate(), os.urandom(aead.KEY_LEN))

    @property
    def public_key(self) -> bytes:
        return self._sk.public_key().public_bytes_raw()

    @property
    def store_key(self) -> bytes:
        """Llave AES-256 para cifrar en reposo el historial y la cola local."""
        return self._store_key

    def sign(self, context: bytes, message: bytes) -> bytes:
        return self._sk.sign(_signed_payload(context, message))

    # --- bóveda: custodia en disco y exportación/importación (RF12) ---------------

    def to_vault(self, password: str, kdf: KdfParams = KdfParams()) -> bytes:
        kdf.validate()
        salt = os.urandom(SALT_LEN)
        header = {"v": 1, "kdf": {"alg": "argon2id", "t": kdf.time_cost, "m": kdf.memory_kib,
                                  "p": kdf.parallelism, "salt": b64e(salt)}}
        secret = _canonical({"sk": b64e(self._sk.private_bytes(_RAW, _RAW_PRIV, _NO_ENC)),
                             "store": b64e(self._store_key)})
        nonce, ct = aead.seal(_derive(password, salt, kdf), secret, AAD_VAULT + _canonical(header))
        return _canonical({**header, "nonce": b64e(nonce), "ct": b64e(ct)})

    @classmethod
    def from_vault(cls, blob: bytes, password: str) -> "Identity":
        try:
            doc = json.loads(blob)
            header = {"v": doc["v"], "kdf": doc["kdf"]}
            kdf_doc = doc["kdf"]
            if doc["v"] != 1 or kdf_doc["alg"] != "argon2id":
                raise VaultError("versión o algoritmo de bóveda no soportado")
            kdf = KdfParams(int(kdf_doc["t"]), int(kdf_doc["m"]), int(kdf_doc["p"]))
            salt = b64d(kdf_doc["salt"], SALT_LEN)
            nonce, ct = b64d(doc["nonce"], aead.NONCE_LEN), b64d(doc["ct"])
        except VaultError:
            raise
        except (ValueError, KeyError, TypeError):
            raise VaultError("bóveda mal formada") from None
        kdf.validate()
        try:
            plain = aead.open_(_derive(password, salt, kdf), nonce, ct, AAD_VAULT + _canonical(header))
            secret = json.loads(plain)
            return cls(Ed25519PrivateKey.from_private_bytes(b64d(secret["sk"], 32)), b64d(secret["store"], 32))
        except (ValueError, KeyError, TypeError, DecryptError):
            raise VaultError("contraseña incorrecta o bóveda corrupta") from None


# --- firmas del directorio: prueba de posesión y cambio de llave --------------------

def _registration_message(discord_id: str, public_key: bytes, nonce: bytes) -> bytes:
    return _lp(discord_id) + public_key + nonce


def sign_registration(identity: Identity, discord_id: str, nonce: bytes) -> bytes:
    """Prueba de posesión que pide el directorio al publicar una llave."""
    return identity.sign(CTX_REGISTER, _registration_message(discord_id, identity.public_key, nonce))


def verify_registration(public_key: bytes, discord_id: str, nonce: bytes, signature: bytes) -> None:
    verify(public_key, CTX_REGISTER, _registration_message(discord_id, public_key, nonce), signature)


def sign_key_change(old: Identity, discord_id: str, new_public_key: bytes, nonce: bytes) -> bytes:
    """La llave anterior autoriza la nueva (rotación de identidad)."""
    return old.sign(CTX_KEY_CHANGE, _registration_message(discord_id, new_public_key, nonce))


def verify_key_change(old_public_key: bytes, discord_id: str, new_public_key: bytes,
                      nonce: bytes, signature: bytes) -> None:
    verify(old_public_key, CTX_KEY_CHANGE, _registration_message(discord_id, new_public_key, nonce), signature)

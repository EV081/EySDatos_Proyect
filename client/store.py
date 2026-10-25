"""Almacenamiento local en reposo: la bóveda de identidad y un documento cifrado con la `store_key`."""
import json
import os
import tempfile
from pathlib import Path

from crypto import aead

AAD_STORE = b"e2ee-discord/v1 client store"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class VaultFile:
    """`vault.json`: el id de Discord (no secreto) y la bóveda cifrada por contraseña maestra."""

    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "vault.json"

    def exists(self) -> bool:
        return self.path.exists()

    def save(self, discord_id: str, vault: bytes) -> None:
        _atomic_write(self.path, json.dumps({"discord_id": discord_id, "vault": json.loads(vault)}).encode())

    def load(self) -> tuple[str, bytes]:
        doc = json.loads(self.path.read_text())
        return doc["discord_id"], json.dumps(doc["vault"]).encode()


class EncryptedStore:
    """Un único documento JSON cifrado con AES-256-GCM: contactos, historial, cola y contadores."""

    def __init__(self, data_dir: Path, key: bytes):
        self.path = Path(data_dir) / "store.enc"
        self._key = key

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        raw = self.path.read_bytes()
        nonce, ct = raw[:aead.NONCE_LEN], raw[aead.NONCE_LEN:]
        return json.loads(aead.open_(self._key, nonce, ct, AAD_STORE))

    def save(self, doc: dict) -> None:
        nonce, ct = aead.seal(self._key, json.dumps(doc, separators=(",", ":")).encode(), AAD_STORE)
        _atomic_write(self.path, nonce + ct)

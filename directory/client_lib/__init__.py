"""Cliente HTTP del directorio; implementa `client.ports.DirectoryPort` sin importar `client/` (sin ciclos).

El token de registro (obtenido con `python -m directory.client_lib.login`) se busca en este orden: el
parámetro `auth_token`, la variable `DIRECTORY_AUTH_TOKEN` o el archivo `DIRECTORY_AUTH_TOKEN_FILE`. Se lee al
publicar, no al arrancar, para poder iniciar sesión con el cliente ya abierto.
"""
import base64
import binascii
import os
import ssl
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlsplit

import httpx

# Llave nula: la cancelación se firma como un cambio de llave hacia ella (ver directory/app/main.py).
CANCEL_MARKER = bytes(32)
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class DirectoryError(Exception):
    """El directorio no respondió, rechazó la solicitud o devolvió algo inesperado."""


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str, length: int) -> bytes:
    try:
        data = base64.b64decode(text + "=" * (-len(text) % 4), altchars=b"-_", validate=True)
    except (binascii.Error, ValueError, TypeError):
        raise DirectoryError("respuesta inválida del directorio") from None
    if len(data) != length:
        raise DirectoryError("respuesta inválida del directorio")
    return data


def tls_context(ca_file: str, crl_file: str | None = None) -> ssl.SSLContext:
    """Solo confía en la CA propia del proyecto (no en las del sistema) y exige TLS 1.3 (RS6).

    Con `crl_file`, además rechaza un certificado revocado; si la CRL falta o venció, la conexión falla
    (falla cerrada). No hay ninguna opción para "continuar de todos modos"."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # verifica certificado y nombre del host
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(cafile=ca_file)
    if crl_file:
        ctx.load_verify_locations(cafile=crl_file)
        ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
    return ctx


class DirectoryClient:
    def __init__(self, base_url: str, ca_file: str | None = None, auth_token: str | None = None,
                 timeout: float = 10.0, transport: httpx.BaseTransport | None = None, crl_file: str | None = None):
        parts = urlsplit(base_url)
        if transport is not None:
            verify = True
        elif parts.scheme == "https":
            if not ca_file:
                raise ValueError("falta ca_file: el directorio solo se valida contra la CA del proyecto")
            verify = tls_context(ca_file, crl_file or os.environ.get("DIRECTORY_CRL_FILE") or None)
        elif parts.scheme == "http" and parts.hostname in _LOOPBACK:
            verify = True  # solo para desarrollo local, mientras F2 no esté listo
        else:
            raise ValueError("el directorio debe usar https (solo se admite http en 127.0.0.1)")
        self._auth_token = auth_token
        self._http = httpx.Client(base_url=base_url.rstrip("/"), verify=verify, timeout=timeout,
                                  transport=transport, follow_redirects=False)

    def close(self) -> None:
        self._http.close()

    # --- DirectoryPort ----------------------------------------------------------------

    def register(self, discord_id: str, public_key: bytes, sign: Callable[[bytes], bytes],
                 consent_version: str) -> None:
        token = self._token()
        nonce = self._challenge(discord_id, "register", token)
        self._call("PUT", f"/v1/keys/{quote(discord_id, safe='')}", token, {
            "public_key": _b64e(public_key), "nonce": _b64e(nonce), "signature": _b64e(sign(nonce)),
            "consent_version": consent_version,
        }, expect=204)

    def get_key(self, discord_id: str) -> bytes | None:
        try:
            resp = self._http.get(f"/v1/keys/{quote(discord_id, safe='')}")
        except httpx.HTTPError:
            raise DirectoryError("el directorio no respondió") from None
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise DirectoryError(f"el directorio respondió {resp.status_code}")
        try:
            body = resp.json()
            if body["discord_id"] != discord_id:
                raise DirectoryError("respuesta inválida del directorio")
            return _b64d(body["public_key"], 32)
        except (ValueError, KeyError, TypeError):
            raise DirectoryError("respuesta inválida del directorio") from None

    # --- extras (aún no están en el puerto) -------------------------------------------

    def cancel(self, discord_id: str, sign_key_change: Callable[[bytes, bytes], bytes]) -> None:
        """Borra el registro. `sign_key_change(new_public_key, nonce)` firma con la llave vigente; p. ej.
        `lambda pk, n: crypto.sign_key_change(identity, discord_id, pk, n)`."""
        token = self._token()
        nonce = self._challenge(discord_id, "cancel", token)
        self._call("DELETE", f"/v1/keys/{quote(discord_id, safe='')}", token, {
            "nonce": _b64e(nonce), "signature": _b64e(sign_key_change(CANCEL_MARKER, nonce)),
        }, expect=204)

    # --- internos ---------------------------------------------------------------------

    def _challenge(self, discord_id: str, purpose: str, token: str) -> bytes:
        resp = self._call("POST", "/v1/challenge", token, {"discord_id": discord_id, "purpose": purpose},
                          expect=200)
        try:
            return _b64d(resp.json()["nonce"], 32)
        except (ValueError, KeyError, TypeError):
            raise DirectoryError("respuesta inválida del directorio") from None

    def _call(self, method: str, path: str, token: str, body: dict, expect: int) -> httpx.Response:
        try:
            resp = self._http.request(method, path, json=body, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            raise DirectoryError("el directorio no respondió") from None
        if resp.status_code != expect:
            raise DirectoryError(f"el directorio respondió {resp.status_code}")
        return resp

    def _token(self) -> str:
        token = self._auth_token or os.environ.get("DIRECTORY_AUTH_TOKEN")
        path = os.environ.get("DIRECTORY_AUTH_TOKEN_FILE")
        if not token and path:
            try:
                token = Path(path).read_text(encoding="ascii").strip()
            except OSError:
                token = None
        if not token:
            raise DirectoryError("falta el token de registro: ejecuta python -m directory.client_lib.login")
        return token

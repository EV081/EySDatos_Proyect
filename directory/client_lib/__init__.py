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
    """El directorio no respondió, rechazó la solicitud o devolvió algo inesperado.

    `status` es el código HTTP cuando el directorio sí respondió (401: falta iniciar sesión con Discord o el
    token venció; 404: no hay registro); None si no respondió."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


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


def public_ca_context() -> ssl.SSLContext:
    """Para un directorio detrás de una plataforma (Render): confía en las CA del sistema, TLS 1.3 y nombre verificado.
    Solo se usa si se pide a propósito (`public_ca=True` / `DIRECTORY_PUBLIC_CA=1`)."""
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    return ctx


class DirectoryClient:
    # El cliente real siempre exige MFA para desbloquear; solo el entorno FakeDirectory es offline.
    requires_mfa = True

    def __init__(self, base_url: str, ca_file: str | None = None, auth_token: str | None = None,
                 timeout: float = 10.0, transport: httpx.BaseTransport | None = None, crl_file: str | None = None,
                 public_ca: bool = False):
        parts = urlsplit(base_url)
        if transport is not None:
            verify = True
        elif parts.scheme == "https" and public_ca and not ca_file:
            verify = public_ca_context()
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
                 consent_version: str, sign_old: Callable[[bytes], bytes] | None = None) -> None:
        """Publica la llave. Con `sign_old(nonce)` (firma `sign_key_change` de la llave vigente) es un cambio
        de llave autorizado también por la anterior: así se ejerce la rectificación."""
        token = self._token()
        nonce = self._challenge(discord_id, "register", token)
        body = {"public_key": _b64e(public_key), "nonce": _b64e(nonce), "signature": _b64e(sign(nonce)),
                "consent_version": consent_version}
        if sign_old is not None:
            body["old_signature"] = _b64e(sign_old(nonce))
        self._call("PUT", f"/v1/keys/{quote(discord_id, safe='')}", token, body, expect=204)

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

    def authenticate_session(self, discord_id: str, code: str, sign: Callable[[bytes], bytes]) -> None:
        """Valida el desbloqueo habitual con posesión de la llave y TOTP, sin token de registro.

        Ni la contraseña ni la llave privada salen del cliente. No conservar autorizaciones entre desbloqueos.
        """
        try:
            response = self._http.post("/v1/sessions/challenge", json={"discord_id": discord_id})
            if response.status_code != 200:
                raise DirectoryError("no se pudo iniciar la verificación de sesión", response.status_code)
            try:
                nonce = _b64d(response.json()["nonce"], 32)
            except (ValueError, KeyError, TypeError):
                raise DirectoryError("respuesta inválida del directorio") from None
            response = self._http.post("/v1/sessions/verify", json={
                "discord_id": discord_id, "nonce": _b64e(nonce), "signature": _b64e(sign(nonce)), "code": code,
            })
        except httpx.HTTPError:
            raise DirectoryError("el directorio no respondió") from None
        if response.status_code != 204:
            raise DirectoryError("no se pudo verificar la sesión", response.status_code)

    # --- derechos ARCO ----------------------------------------------------------------

    def record(self, discord_id: str) -> dict:
        """Acceso: todo lo que el directorio guarda de esta persona (exige el token de OAuth2, no lo consume)."""
        resp = self._call("GET", "/v1/me", self._token(), None, expect=200)
        try:
            body = resp.json()
            if body["discord_id"] != discord_id:
                raise DirectoryError("respuesta inválida del directorio")
            return body
        except (ValueError, KeyError, TypeError):
            raise DirectoryError("respuesta inválida del directorio") from None

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

    def _call(self, method: str, path: str, token: str, body: dict | None, expect: int) -> httpx.Response:
        try:
            resp = self._http.request(method, path, json=body, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            raise DirectoryError("el directorio no respondió") from None
        if resp.status_code != expect:
            raise DirectoryError(f"el directorio respondió {resp.status_code}", resp.status_code)
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
            raise DirectoryError("falta el token de registro: ejecuta python -m directory.client_lib.login", 401)
        return token

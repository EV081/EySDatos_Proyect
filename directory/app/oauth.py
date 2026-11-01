"""OAuth2 con Discord (alcance `identify`): solo sirve para saber qué ID de Discord tiene quien publica.

El access token de Discord no sale de esta función: se usa una vez para leer `/users/@me` y se revoca."""
import base64
import hashlib
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"  # nosec B105
REVOKE_URL = "https://discord.com/api/oauth2/token/revoke"
ME_URL = "https://discord.com/api/users/@me"


class OAuthError(Exception):
    pass


def code_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


class DiscordOAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, http: httpx.Client):
        self._id, self._secret, self._redirect, self._http = client_id, client_secret, redirect_uri, http

    def authorize_url(self, state: str, verifier: str) -> str:
        return AUTHORIZE_URL + "?" + urlencode({
            "response_type": "code", "client_id": self._id, "scope": "identify", "redirect_uri": self._redirect,
            "state": state, "code_challenge": code_challenge(verifier), "code_challenge_method": "S256",
        })

    def discord_id(self, code: str, verifier: str) -> str:
        """Canjea el código y devuelve el ID de la cuenta. Cualquier fallo lanza OAuthError."""
        auth = (self._id, self._secret)
        try:
            token = self._http.post(TOKEN_URL, auth=auth, data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": self._redirect,
                "code_verifier": verifier,
            })
            token.raise_for_status()
            access = token.json()["access_token"]
            try:
                me = self._http.get(ME_URL, headers={"Authorization": f"Bearer {access}"})
                me.raise_for_status()
                discord_id = str(me.json()["id"])
            finally:
                try:  # no lo necesitamos más: mejor que no quede vigente
                    self._http.post(REVOKE_URL, auth=auth,
                                    data={"token": access, "token_type_hint": "access_token"})  # nosec B105
                except httpx.HTTPError:
                    pass
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            raise OAuthError("no se pudo completar OAuth2") from None
        return discord_id

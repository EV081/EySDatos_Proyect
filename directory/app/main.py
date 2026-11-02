"""Directorio de llaves (F1): asocia IDs de Discord a llaves públicas de firma Ed25519.

Arranque: `uvicorn --factory directory.app.main:create_app_from_env --host 127.0.0.1 --port 8000`.

Publicar, cambiar o cancelar una llave exige dos cosas a la vez:
* **OAuth2 con Discord** (`/auth/login`): demuestra que quien publica controla ese ID. El directorio emite un
  token de registro de 10 minutos, de un solo uso y ligado a ese ID; solo el dueño modifica su registro.
* **Prueba de posesión**: firma `verify_registration` sobre un nonce de un solo uso entregado por `/v1/challenge`.
"""
import contextlib
import html
import logging
import secrets

import httpx
from fastapi import Depends, FastAPI, Header, Path, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from crypto import SignatureError, verify_key_change, verify_registration

from . import errors
from .audit import AlertMonitor, Audit, setup_logging
from .config import Settings
from .errors import ApiError
from .oauth import DiscordOAuth, OAuthError
from .ratelimit import RateLimiter
from .repo import Repo
from .schemas import DISCORD_ID, CancelKey, ChallengeRequest, PublishKey, b64d, b64e

KEY_LEN, SIG_LEN, NONCE_LEN, TOKEN_LEN = 32, 64, 32, 32
# La cancelación se firma como un "cambio de llave" hacia una llave nula, que nadie puede registrar.
# Pendiente: reemplazarlo por sign_cancellation/verify_cancellation con contexto propio en crypto/ (Elmer).
CANCEL_MARKER = bytes(KEY_LEN)
NO_STORE = {"Cache-Control": "no-store"}
HTML_HEADERS = {**NO_STORE, "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
                "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}

DiscordIdPath = Path(pattern=DISCORD_ID)


def create_app(settings: Settings, repo: Repo | None = None, http: httpx.Client | None = None,
               limiter: RateLimiter | None = None, monitor: AlertMonitor | None = None) -> FastAPI:
    repo = repo or Repo(settings.database_url)
    http = http or httpx.Client(timeout=10)
    limiter = limiter or RateLimiter()
    oauth = DiscordOAuth(settings.discord_client_id, settings.discord_client_secret,
                         settings.discord_redirect_uri, http)
    audit = Audit(settings.pseudonymizer.pseudonym, monitor or AlertMonitor(webhook_url=settings.alert_webhook_url))

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        repo.close()
        http.close()

    app = FastAPI(title="Directorio de llaves", lifespan=lifespan, docs_url=None, redoc_url=None,
                  openapi_url=None)
    errors.install(app)
    app.state.audit = audit

    def limit(bucket: str, max_hits: int):
        def check(request: Request) -> None:
            client = request.client.host if request.client else "?"
            if not limiter.allow(bucket, client, max_hits):
                audit.event("limite", logging.WARNING, grupo=bucket)  # sin la IP
                raise ApiError(429)
        return Depends(check)

    def bearer(authorization: str = Header(default="")) -> bytes:
        scheme, _, value = authorization.partition(" ")
        try:
            if scheme.lower() != "bearer":
                raise ValueError
            return b64d(value.strip(), TOKEN_LEN)
        except ValueError:
            raise ApiError(401) from None

    def owner(token: bytes, discord_id: str) -> None:
        """Solo el dueño del ID (según OAuth2) puede tocar su registro."""
        token_id = repo.token_owner(token)
        if token_id != discord_id:
            if token_id is not None:
                audit.event("acceso_ajeno", logging.WARNING, ids={"id": token_id, "objetivo": discord_id})
            raise ApiError(401)

    def decode(text: str, length: int) -> bytes:
        try:
            return b64d(text, length)
        except ValueError:
            raise ApiError(400) from None

    # --- OAuth2 -----------------------------------------------------------------------

    @app.get("/auth/login", dependencies=[limit("auth", settings.write_limit)])
    def login():
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        repo.save_oauth_state(state.encode(), verifier, settings.oauth_state_ttl)
        return RedirectResponse(oauth.authorize_url(state, verifier), status_code=302, headers=NO_STORE)

    @app.get("/auth/callback", dependencies=[limit("auth", settings.write_limit)])
    def callback(code: str = Query(default="", max_length=512), state: str = Query(default="", max_length=128)):
        verifier = repo.pop_oauth_state(state.encode()) if state else None
        if not code or verifier is None:
            return _page("No se pudo iniciar sesión", "Vuelve a intentarlo desde el principio.", 400)
        try:
            discord_id = oauth.discord_id(code, verifier)
        except OAuthError:
            return _page("No se pudo iniciar sesión", "Discord no confirmó la cuenta. Vuelve a intentarlo.", 400)
        token = secrets.token_bytes(TOKEN_LEN)
        repo.create_token(token, discord_id, settings.token_ttl)
        audit.event("login", ids={"id": discord_id})
        return _page("Token de registro",
                     "Pégalo en tu cliente. Vale 10 minutos y una sola publicación. No lo compartas.",
                     200, token=b64e(token))

    # --- llaves -----------------------------------------------------------------------

    @app.post("/v1/challenge", dependencies=[limit("write", settings.write_limit)])
    def challenge(body: ChallengeRequest, token: bytes = Depends(bearer)):
        owner(token, body.discord_id)
        nonce = secrets.token_bytes(NONCE_LEN)
        repo.create_challenge(nonce, body.discord_id, body.purpose, settings.challenge_ttl)
        return JSONResponse({"nonce": b64e(nonce), "expires_in": settings.challenge_ttl}, headers=NO_STORE)

    @app.put("/v1/keys/{discord_id}", status_code=204, dependencies=[limit("write", settings.write_limit)])
    def publish(body: PublishKey, discord_id: str = DiscordIdPath, token: bytes = Depends(bearer)):
        owner(token, discord_id)
        public_key, nonce = decode(body.public_key, KEY_LEN), decode(body.nonce, NONCE_LEN)
        signature = decode(body.signature, SIG_LEN)
        old_signature = decode(body.old_signature, SIG_LEN) if body.old_signature else None
        if public_key == CANCEL_MARKER:
            raise ApiError(400)
        if not repo.consume_challenge(nonce, discord_id, "register"):
            raise ApiError(401)
        try:
            verify_registration(public_key, discord_id, nonce, signature)
            if old_signature is not None:  # cambio autorizado además por la llave anterior
                current = repo.get_key(discord_id)
                if current is None or current == public_key:
                    raise ApiError(400)
                verify_key_change(current, discord_id, public_key, nonce, old_signature)
        except SignatureError:
            audit.event("firma_invalida", logging.WARNING, ids={"id": discord_id})
            raise ApiError(401) from None
        result = repo.publish_key(token, discord_id, public_key, body.consent_version)
        if result is None:
            raise ApiError(401)
        audit.event({"created": "registro", "changed": "cambio_de_llave", "same": "renovacion"}[result],
                    logging.WARNING if result == "changed" else logging.INFO, ids={"id": discord_id},
                    aviso=body.consent_version)
        return Response(status_code=204, headers=NO_STORE)

    @app.get("/v1/keys/{discord_id}", dependencies=[limit("lookup", settings.lookup_limit)])
    def lookup(discord_id: str = DiscordIdPath):
        public_key = repo.get_key(discord_id)
        if public_key is None:
            audit.count("consulta_inexistente")
            raise ApiError(404)
        return JSONResponse({"discord_id": discord_id, "public_key": b64e(public_key)}, headers=NO_STORE)

    @app.delete("/v1/keys/{discord_id}", status_code=204, dependencies=[limit("write", settings.write_limit)])
    def cancel(body: CancelKey, discord_id: str = DiscordIdPath, token: bytes = Depends(bearer)):
        """Cancelación (C-11): la persona borra su registro con su llave vigente y una sesión OAuth2."""
        owner(token, discord_id)
        nonce, signature = decode(body.nonce, NONCE_LEN), decode(body.signature, SIG_LEN)
        if not repo.consume_challenge(nonce, discord_id, "cancel"):
            raise ApiError(401)
        current = repo.get_key(discord_id)
        if current is None:
            raise ApiError(401)
        try:
            verify_key_change(current, discord_id, CANCEL_MARKER, nonce, signature)
        except SignatureError:
            audit.event("firma_invalida", logging.WARNING, ids={"id": discord_id})
            raise ApiError(401) from None
        if not repo.cancel(token, discord_id):
            raise ApiError(401)
        audit.event("cancelacion", ids={"id": discord_id})
        return Response(status_code=204, headers=NO_STORE)

    return app


def _page(title: str, text: str, status: int, token: str | None = None) -> HTMLResponse:
    token_html = f'<pre style="user-select:all;word-break:break-all">{html.escape(token)}</pre>' if token else ""
    body = (f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
            f'<body style="font-family:sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem">'
            f"<h1>{html.escape(title)}</h1><p>{html.escape(text)}</p>{token_html}</body>")
    return HTMLResponse(body, status_code=status, headers=HTML_HEADERS)


def create_app_from_env() -> FastAPI:
    settings = Settings.from_env()
    setup_logging(settings.audit_log_dir)
    return create_app(settings)

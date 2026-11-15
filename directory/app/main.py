"""Directorio de llaves (F1): asocia IDs de Discord a llaves públicas de firma Ed25519.

Arranque: `uvicorn --factory directory.app.main:create_app_from_env --host 127.0.0.1 --port 8000`.

Publicar, cambiar o cancelar una llave exige dos cosas a la vez:
* **OAuth2 con Discord** (`/auth/login`) y **TOTP** (`/auth/mfa/verify`): control del ID y del autenticador.
  Solo tras ambos pasos se emite un token de registro de 10 minutos, de un solo uso y ligado a ese ID.
* **Prueba de posesión**: firma `verify_registration` sobre un nonce de un solo uso entregado por `/v1/challenge`.
"""
import contextlib
import html
import logging
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import Depends, FastAPI, Header, Path, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from crypto import SignatureError, verify_key_change, verify_registration, verify_unlock

from . import errors
from .audit import AlertMonitor, Audit, setup_logging
from .config import Settings
from .errors import ApiError
from .mfa import Authenticator
from . import mfa_pages
from .oauth import DiscordOAuth, OAuthError
from .ratelimit import RateLimiter
from .repo import REPLACED_KEY_RETENTION_DAYS, Repo
from .schemas import DISCORD_ID, CancelKey, ChallengeRequest, PublishKey, SessionChallenge, SessionVerify, b64d, b64e

KEY_LEN, SIG_LEN, NONCE_LEN, TOKEN_LEN = 32, 64, 32, 32
# La cancelación se firma como un "cambio de llave" hacia una llave nula, que nadie puede registrar.
# Pendiente: reemplazarlo por sign_cancellation/verify_cancellation con contexto propio en crypto/ (Elmer).
CANCEL_MARKER = bytes(KEY_LEN)
NO_STORE = {"Cache-Control": "no-store"}
USER_AGENT = "DiscordBot (https://github.com/EV081/EySDatos_Proyect, 1.0) e2ee-directory"
HTML_HEADERS = {**NO_STORE, "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
                "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}

DiscordIdPath = Path(pattern=DISCORD_ID)


def create_app(settings: Settings, repo: Repo | None = None, http: httpx.Client | None = None,
               limiter: RateLimiter | None = None, monitor: AlertMonitor | None = None) -> FastAPI:
    repo = repo or Repo(settings.database_url)
    # User-Agent descriptivo: Discord lo exige y Cloudflare frena a los genéricos (p. ej. desde IPs de nube compartidas).
    http = http or httpx.Client(timeout=10, headers={"User-Agent": USER_AGENT})
    limiter = limiter or RateLimiter()
    oauth = DiscordOAuth(settings.discord_client_id, settings.discord_client_secret,
                         settings.discord_redirect_uri, http)
    authenticator = Authenticator(settings.totp_encryption_key)
    secure_cookie = urlsplit(settings.discord_redirect_uri).scheme == "https"
    cookie_name = "__Secure-directory_mfa" if secure_cookie else "directory_mfa"
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

    @app.get("/health")
    def health():
        return Response(status_code=204, headers=NO_STORE)

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
            logging.getLogger(__name__).warning("oauth callback rejected: missing code or state (state_present=%s code_present=%s)",
                                                bool(state), bool(code))
            return _page("No se pudo iniciar sesión", "Vuelve a intentarlo desde el principio.", 400)
        try:
            discord_id = oauth.discord_id(code, verifier)
        except OAuthError:
            logging.getLogger(__name__).warning("oauth callback failed: discord did not confirm account")
            return _page("No se pudo iniciar sesión", "Discord no confirmó la cuenta. Vuelve a intentarlo.", 400)
        session, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        ciphertext, enrolling = repo.start_mfa(discord_id, session.encode("ascii"), csrf.encode("ascii"),
                                              authenticator.new_secret())
        page = mfa_pages.verification(csrf, authenticator, discord_id, ciphertext if enrolling else None)
        page.set_cookie(cookie_name, session, max_age=300, httponly=True, secure=secure_cookie,
                        samesite="strict", path="/auth/mfa")
        return page

    @app.post("/auth/mfa/verify", dependencies=[limit("mfa", settings.write_limit)])
    async def verify_mfa(request: Request):
        # Formulario pequeño, sin multipart ni secretos en la URL. El token CSRF está ligado a la cookie.
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            raise ApiError(400)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 1024:
                raise ApiError(400)
        try:
            form = parse_qs(body.decode("ascii"), max_num_fields=2, strict_parsing=True)
            csrf, code = form["csrf"][0], form["code"][0].strip()
            session = request.cookies.get(cookie_name, "")
            if len(csrf) != 43 or len(session) != 43 or len(code) > 35:
                raise ValueError
            csrf_bytes, session_bytes = csrf.encode("ascii"), session.encode("ascii")
        except (UnicodeError, ValueError, KeyError):
            raise ApiError(400) from None
        token = secrets.token_bytes(TOKEN_LEN)
        result = await run_in_threadpool(repo.verify_mfa, session_bytes, csrf_bytes, code,
                                         authenticator, token, settings.token_ttl)
        if result is None:
            audit.event("mfa_rechazado", logging.WARNING)
            return mfa_pages.verification(csrf, authenticator, error=True)
        discord_id, recovery_codes, reset_secret = result
        if reset_secret:
            audit.event("mfa_recuperacion", ids={"id": discord_id})
            page = mfa_pages.verification(csrf, authenticator, discord_id, reset_secret)
            page.set_cookie(cookie_name, session, max_age=300, httponly=True, secure=secure_cookie,
                            samesite="strict", path="/auth/mfa")
            return page
        audit.event("login", ids={"id": discord_id})
        page = mfa_pages.success(b64e(token), recovery_codes)
        page.delete_cookie(cookie_name, path="/auth/mfa", secure=secure_cookie,
                           httponly=True, samesite="strict")
        return page

    # --- sesiones habituales: sin OAuth ni token de registro ---------------------------

    @app.post("/v1/sessions/challenge", dependencies=[limit("session", settings.write_limit)])
    def session_challenge(body: SessionChallenge):
        # El ID ya se publica en /v1/keys; no entregar nonces para cuentas sin factor confirmado.
        factor = repo.mfa_status(body.discord_id)
        if repo.get_key(body.discord_id) is None or not factor or not factor["enabled"]:
            raise ApiError(401)
        nonce = secrets.token_bytes(NONCE_LEN)
        repo.create_challenge(nonce, body.discord_id, "unlock", settings.challenge_ttl)
        return JSONResponse({"nonce": b64e(nonce), "expires_in": settings.challenge_ttl}, headers=NO_STORE)

    @app.post("/v1/sessions/verify", status_code=204, dependencies=[limit("session", settings.write_limit)])
    def session_verify(body: SessionVerify):
        nonce, signature = decode(body.nonce, NONCE_LEN), decode(body.signature, SIG_LEN)
        if not repo.consume_challenge(nonce, body.discord_id, "unlock"):
            raise ApiError(401)
        public_key = repo.get_key(body.discord_id)
        try:
            if public_key is None:
                raise SignatureError("sin llave")
            verify_unlock(public_key, body.discord_id, nonce, signature)
        except SignatureError:
            audit.event("mfa_rechazado", logging.WARNING)
            raise ApiError(401) from None
        if not repo.verify_session_mfa(body.discord_id, public_key, body.code, authenticator):
            audit.event("mfa_rechazado", logging.WARNING)
            raise ApiError(401)
        audit.event("sesion_local", ids={"id": body.discord_id})
        # No expedir otro token, ni una autorización que pueda guardarse para el próximo desbloqueo.
        return Response(status_code=204, headers=NO_STORE)

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

    @app.get("/v1/me", dependencies=[limit("write", settings.write_limit)])
    def my_record(token: bytes = Depends(bearer)):
        """Derecho de acceso: la persona ve todo lo que el directorio guarda de ella. Basta el token de OAuth2
        (no se consume: leer no cambia nada) y solo devuelve el registro del dueño del token."""
        discord_id = repo.token_owner(token)
        if discord_id is None:
            raise ApiError(401)
        record = repo.get_record(discord_id)
        if record is None:
            raise ApiError(404)
        audit.event("acceso", ids={"id": discord_id})
        retention = timedelta(days=REPLACED_KEY_RETENTION_DAYS)
        return JSONResponse({
            "discord_id": discord_id, "public_key": b64e(record["public_key"]),
            "registered_at": _iso(record["registered_at"]), "key_changed_at": _iso(record["key_changed_at"]),
            "consent_version": record["consent_version"], "consent_at": _iso(record["consent_at"]),
            "mfa": repo.mfa_status(discord_id),
            "replaced_keys": [{"public_key": b64e(k["public_key"]), "replaced_at": _iso(k["replaced_at"]),
                               "delete_after": _iso(k["replaced_at"] + retention)}
                              for k in repo.replaced_keys(discord_id)],
        }, headers=NO_STORE)

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


def _iso(moment) -> str | None:
    return moment.isoformat() if moment else None


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

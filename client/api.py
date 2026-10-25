"""API HTTP local (solo 127.0.0.1) que consume el frontend. No contiene lógica de seguridad propia:
delega en el `Orchestrator`. Defensas del propio servidor local: token por ejecución, CORS
restringido al origen del frontend y validación del Host (contra DNS rebinding)."""
import asyncio
import contextlib
import hmac
import json

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .errors import ClientError
from .orchestrator import Orchestrator

ID_PATTERN = r"^[0-9]{1,25}$"
PeerId = Path(pattern=ID_PATTERN)
TICK_SECONDS = 5


class CreateIdentity(BaseModel):
    discord_id: str = Field(pattern=ID_PATTERN)
    password: str = Field(min_length=10, max_length=256)
    consent_version: str = Field(min_length=1, max_length=16)


class ImportIdentity(BaseModel):
    discord_id: str = Field(pattern=ID_PATTERN)
    vault: dict
    password: str = Field(min_length=1, max_length=256)
    consent_version: str = Field(min_length=1, max_length=16)


class Password(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ExportRequest(BaseModel):
    password: str = Field(min_length=10, max_length=256)


class AddContact(BaseModel):
    discord_id: str = Field(pattern=ID_PATTERN)
    alias: str | None = Field(default=None, max_length=64)


class VerifyRequest(BaseModel):
    fingerprint: str = Field(min_length=1, max_length=120)


class SendMessage(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


def create_app(orchestrator: Orchestrator, token: str, allowed_origins: list[str],
               allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1"), run_ticker: bool = True) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async def loop():
            while True:
                await asyncio.sleep(TICK_SECONDS)
                await asyncio.to_thread(orchestrator.tick)

        task = asyncio.create_task(loop()) if run_ticker else None
        try:
            yield
        finally:
            if task:
                task.cancel()
            orchestrator.lock()

    app = FastAPI(title="Cliente local E2EE", version="1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))

    def require_token(authorization: str | None = Header(default=None)) -> None:
        supplied = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        if not hmac.compare_digest(supplied.encode(), token.encode()):
            raise HTTPException(status_code=401, detail="token inválido")

    @app.exception_handler(ClientError)
    async def client_error(_request: Request, exc: ClientError):
        return JSONResponse(status_code=exc.status, content={"error": exc.code, "detail": str(exc)})

    api = Depends(require_token)

    @app.get("/health")
    def health():
        return {"ok": True}

    # --- identidad ---------------------------------------------------------------------
    @app.get("/status", dependencies=[api])
    def status():
        return orchestrator.status()

    @app.post("/identity", status_code=201, dependencies=[api])
    def create_identity(body: CreateIdentity):
        return orchestrator.create_identity(body.discord_id, body.password, body.consent_version)

    @app.post("/identity/unlock", dependencies=[api])
    def unlock(body: Password):
        return orchestrator.unlock(body.password)

    @app.post("/identity/lock", status_code=204, dependencies=[api])
    def lock():
        orchestrator.lock()

    @app.post("/identity/export", dependencies=[api])
    def export_identity(body: ExportRequest):
        return {"vault": json.loads(orchestrator.export_identity(body.password))}

    @app.post("/identity/import", status_code=201, dependencies=[api])
    def import_identity(body: ImportIdentity):
        return orchestrator.import_identity(body.discord_id, json.dumps(body.vault).encode(), body.password,
                                           body.consent_version)

    # --- contactos y verificación --------------------------------------------------------
    @app.get("/contacts", dependencies=[api])
    def contacts():
        return orchestrator.contacts()

    @app.post("/contacts", status_code=201, dependencies=[api])
    def add_contact(body: AddContact):
        return orchestrator.add_contact(body.discord_id, body.alias)

    @app.get("/contacts/{discord_id}", dependencies=[api])
    def contact(discord_id: str = PeerId):
        return orchestrator.contact(discord_id)

    @app.get("/contacts/{discord_id}/fingerprint", dependencies=[api])
    def fingerprint(discord_id: str = PeerId):
        return orchestrator.fingerprint(discord_id)

    @app.post("/contacts/{discord_id}/verify", dependencies=[api])
    def verify(body: VerifyRequest, discord_id: str = PeerId):
        return orchestrator.verify_contact(discord_id, body.fingerprint)

    # --- conversaciones --------------------------------------------------------------------
    @app.get("/conversations", dependencies=[api])
    def conversations():
        return orchestrator.conversations()

    @app.get("/conversations/{discord_id}/messages", dependencies=[api])
    def messages(discord_id: str = PeerId, since: int = 0):
        return orchestrator.history(discord_id, since)

    @app.post("/conversations/{discord_id}/messages", status_code=202, dependencies=[api])
    def send(body: SendMessage, discord_id: str = PeerId):
        return orchestrator.send_text(discord_id, body.text)

    @app.post("/conversations/{discord_id}/retry", status_code=202, dependencies=[api])
    def retry(discord_id: str = PeerId):
        return orchestrator.retry(discord_id)

    return app

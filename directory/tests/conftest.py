"""Las pruebas corren contra el Postgres de docker-compose, en una base aparte (`directory_test`) que se recrea
en cada ejecución. Si no hay Postgres, se saltan. OAuth2 de Discord se simula con httpx.MockTransport."""
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from crypto import Identity, Pseudonymizer, sign_registration
from crypto.pseudonym import generate_key
from directory.app.config import Settings
from directory.app.main import create_app
from directory.app.repo import Repo
from directory.app.schemas import b64e
from directory.migrations.apply import apply

ALICE, BOB, MALLORY = "111111111111111111", "222222222222222222", "333333333333333333"
CONSENT = "1.0"
TEST_DB = "directory_test"
TABLES = ("challenges", "auth_tokens", "oauth_states", "replaced_keys", "keys")


def _env(name: str) -> str | None:
    """Variable de entorno o, si falta, la del .env de la raíz del repositorio."""
    if os.environ.get(name):
        return os.environ[name]
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == name:
                return value.strip()
    return None


def _with_db(url: str, dbname: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path="/" + dbname))


@pytest.fixture(scope="session")
def urls():
    admin, app_password = _env("DATABASE_ADMIN_URL"), _env("DIRECTORY_APP_PASSWORD")
    if not admin or not app_password:
        pytest.skip("faltan DATABASE_ADMIN_URL y DIRECTORY_APP_PASSWORD (.env)")
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=3) as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(TEST_DB)))
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))
    except psycopg.OperationalError:
        pytest.skip("no hay Postgres: docker compose up -d db")
    test_admin = _with_db(admin, TEST_DB)
    apply(test_admin, app_password)
    app_url = urlunsplit(urlsplit(test_admin)._replace(
        netloc=f"directory_app:{app_password}@{urlsplit(admin).hostname}:{urlsplit(admin).port}"))
    return {"admin": test_admin, "app": app_url}


@pytest.fixture(scope="session")
def repo(urls):
    r = Repo(urls["app"])
    yield r
    r.close()


@pytest.fixture
def admin_db(urls):
    with psycopg.connect(urls["admin"], autocommit=True) as conn:
        yield conn


@pytest.fixture(autouse=True)
def _clean(request):
    if "urls" in request.fixturenames or "api" in request.fixturenames:
        admin = request.getfixturevalue("urls")["admin"]
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute("TRUNCATE " + ", ".join(f"directory.{t}" for t in TABLES))
    yield


class FakeDiscordOAuth:
    """Discord simulado: el código `code-<id>` corresponde a la cuenta `<id>`."""

    def __init__(self):
        self.revoked: list[str] = []
        self.fail = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(500)
        if request.url.path == "/api/oauth2/token":
            form = parse_qs(request.content.decode())
            code = form["code"][0]
            if not code.startswith("code-") or not form.get("code_verifier"):
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "at-" + code[5:], "token_type": "Bearer"})
        if request.url.path == "/api/users/@me":
            return httpx.Response(200, json={"id": request.headers["Authorization"].removeprefix("Bearer at-")})
        if request.url.path == "/api/oauth2/token/revoke":
            self.revoked.append(parse_qs(request.content.decode())["token"][0])
            return httpx.Response(200)
        return httpx.Response(404)


@pytest.fixture
def discord():
    return FakeDiscordOAuth()


@pytest.fixture
def settings(urls):
    return Settings(database_url=urls["app"], discord_client_id="cid", discord_client_secret="secret",
                    discord_redirect_uri="http://127.0.0.1:8000/auth/callback",
                    pseudonymizer=Pseudonymizer(generate_key()), write_limit=1000, lookup_limit=1000)


@pytest.fixture
def make_api(settings, repo, discord):
    def build(**overrides) -> TestClient:
        s = Settings(**{**settings.__dict__, **overrides})
        app = create_app(s, repo=repo, http=httpx.Client(transport=httpx.MockTransport(discord)))
        return TestClient(app, raise_server_exceptions=False, follow_redirects=False)
    return build


@pytest.fixture
def api(make_api):
    return make_api()


def login(api: TestClient, discord_id: str) -> str:
    """Recorre /auth/login y /auth/callback como lo haría el navegador; devuelve el token de registro."""
    redirect = api.get("/auth/login")
    assert redirect.status_code == 302
    state = parse_qs(urlsplit(redirect.headers["location"]).query)["state"][0]
    page = api.get("/auth/callback", params={"code": f"code-{discord_id}", "state": state})
    assert page.status_code == 200, page.text
    return re.search(r"<pre[^>]*>([A-Za-z0-9_-]+)</pre>", page.text).group(1)


def challenge(api: TestClient, token: str, discord_id: str, purpose: str = "register"):
    return api.post("/v1/challenge", json={"discord_id": discord_id, "purpose": purpose},
                    headers={"Authorization": f"Bearer {token}"})


def publish(api: TestClient, token: str, discord_id: str, identity: Identity, nonce: bytes | None = None,
            signer: Identity | None = None, **extra):
    """Pide un nonce (si no se da uno) y publica la llave de `identity` firmada por `signer`."""
    if nonce is None:
        from directory.app.schemas import b64d
        resp = challenge(api, token, discord_id)
        assert resp.status_code == 200, resp.text
        nonce = b64d(resp.json()["nonce"], 32)
    body = {"public_key": b64e(identity.public_key), "nonce": b64e(nonce),
            "signature": b64e(sign_registration(signer or identity, discord_id, nonce)),
            "consent_version": CONSENT, **extra}
    return api.put(f"/v1/keys/{discord_id}", json=body, headers={"Authorization": f"Bearer {token}"})

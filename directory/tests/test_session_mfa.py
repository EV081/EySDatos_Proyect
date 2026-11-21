import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pyotp
import pytest
from fastapi.testclient import TestClient

from client.api import create_app
from client.fakes import FakeChannel, FakeDiscord
from client.orchestrator import Orchestrator
from client.privacy import NOTICE_VERSION
from crypto import Identity, KdfParams, sign_registration, sign_unlock
from directory.app.schemas import b64d, b64e
from directory.client_lib import DirectoryClient

from conftest import ALICE, BOB, login, publish


def next_code(api, admin_db, discord_id=ALICE):
    ciphertext, last_step = admin_db.execute(
        "SELECT encrypted_secret, last_step FROM directory.mfa_accounts WHERE discord_id = %s",
        (discord_id,)).fetchone()
    now = max(time.time(), (last_step + 1) * 30 + 1)
    secret = api.app.state.test_authenticator.secret(ciphertext)
    return now, pyotp.TOTP(secret).at(now)


def session_body(api, identity, code, discord_id=ALICE):
    response = api.post("/v1/sessions/challenge", json={"discord_id": discord_id})
    assert response.status_code == 200, response.text
    nonce = b64d(response.json()["nonce"], 32)
    return {"discord_id": discord_id, "code": code, "nonce": b64e(nonce),
            "signature": b64e(sign_unlock(identity, discord_id, nonce))}


@pytest.fixture
def enrolled(api):
    identity = Identity.create()
    assert publish(api, login(api, ALICE), ALICE, identity).status_code == 204
    return identity


def test_C06_sesion_exige_firma_y_mfa_sin_emitir_token_de_registro(api, enrolled, admin_db):
    now, code = next_code(api, admin_db)
    body = session_body(api, enrolled, code)
    before = admin_db.execute("SELECT count(*) FROM directory.auth_tokens").fetchone()[0]
    with patch("directory.app.mfa.time", return_value=now):
        response = api.post("/v1/sessions/verify", json=body)
        assert response.status_code == 204
        assert response.headers["cache-control"] == "no-store"
        assert api.post("/v1/sessions/verify", json=body).status_code == 401
        # Un nuevo nonce tampoco permite reutilizar el código anterior.
        assert api.post("/v1/sessions/verify", json=session_body(api, enrolled, code)).status_code == 401
    assert admin_db.execute("SELECT count(*) FROM directory.auth_tokens").fetchone()[0] == before


def test_firma_de_registro_no_autoriza_sesion_ni_consume_el_codigo(api, enrolled, admin_db):
    now, code = next_code(api, admin_db)
    body = session_body(api, enrolled, code)
    body["signature"] = b64e(sign_registration(enrolled, ALICE, b64d(body["nonce"], 32)))
    with patch("directory.app.mfa.time", return_value=now):
        assert api.post("/v1/sessions/verify", json=body).status_code == 401
        assert api.post("/v1/sessions/verify", json=session_body(api, enrolled, code)).status_code == 204


def test_C06_firma_ajena_y_nonce_de_otro_proposito_se_rechazan(api, enrolled, admin_db):
    now, code = next_code(api, admin_db)
    with patch("directory.app.mfa.time", return_value=now):
        other = session_body(api, Identity.create(), code)
        assert api.post("/v1/sessions/verify", json=other).status_code == 401
        token = login(api, ALICE)
        response = api.post("/v1/challenge", json={"discord_id": ALICE, "purpose": "register"},
                            headers={"Authorization": f"Bearer {token}"})
        nonce = b64d(response.json()["nonce"], 32)
        body = {"discord_id": ALICE, "code": code, "nonce": b64e(nonce),
                "signature": b64e(sign_unlock(enrolled, ALICE, nonce))}
        assert api.post("/v1/sessions/verify", json=body).status_code == 401


def test_bloqueo_de_intentos_compartido_entre_oauth_y_sesion(api, enrolled, admin_db):
    now, code = next_code(api, admin_db)
    with patch("directory.app.mfa.time", return_value=now):
        valid_codes = {pyotp.TOTP(api.app.state.test_authenticator.secret(
            admin_db.execute("SELECT encrypted_secret FROM directory.mfa_accounts").fetchone()[0])).at(now + d)
                       for d in (-30, 0, 30)}
        wrong = next(f"{n:06d}" for n in range(10) if f"{n:06d}" not in valid_codes)
        for _ in range(5):
            assert api.post("/v1/sessions/verify", json=session_body(api, enrolled, wrong)).status_code == 401
        assert api.post("/v1/sessions/verify", json=session_body(api, enrolled, code)).status_code == 401
    assert admin_db.execute("SELECT locked_until > now() FROM directory.mfa_accounts").fetchone()[0]


def test_cuentas_sin_registro_o_sin_mfa_no_inician_sesion(api, enrolled):
    assert api.post("/v1/sessions/challenge", json={"discord_id": BOB}).status_code == 401


def test_nonce_vencido_y_llave_reemplazada_no_desbloquean(api, enrolled, admin_db):
    now, code = next_code(api, admin_db)
    body = session_body(api, enrolled, code)
    admin_db.execute("UPDATE directory.challenges SET expires_at = now() - interval '1 second'")
    with patch("directory.app.mfa.time", return_value=now):
        assert api.post("/v1/sessions/verify", json=body).status_code == 401
        body = session_body(api, enrolled, code)
        admin_db.execute("UPDATE directory.keys SET public_key = %s WHERE discord_id = %s",
                         (Identity.create().public_key, ALICE))
        assert api.post("/v1/sessions/verify", json=body).status_code == 401


def test_dos_sesiones_simultaneas_no_comparten_el_mismo_codigo(api, enrolled, admin_db, repo):
    now, code = next_code(api, admin_db)
    def verify():
        return repo.verify_session_mfa(ALICE, enrolled.public_key, code, api.app.state.test_authenticator)
    with patch("directory.app.mfa.time", return_value=now), ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(lambda _: verify(), range(2))) == 1


def test_desbloqueo_completo_desde_api_local_hasta_directorio(api, admin_db, tmp_path):
    password = "contrasena-maestra-de-prueba"
    # El alta inicial ya está autorizada con OAuth y MFA mediante el token de registro.
    directory = DirectoryClient("http://testserver", auth_token=login(api, ALICE), transport=api._transport)
    orch = Orchestrator(tmp_path, directory, FakeDiscord(FakeChannel()), kdf=KdfParams(1, 64, 1), session_ttl=60)
    local = TestClient(create_app(orch, "local-test", ["http://localhost"], run_ticker=False),
                       base_url="http://localhost")
    headers = {"Authorization": "Bearer local-test"}
    assert local.post("/identity", headers=headers, json={
        "discord_id": ALICE, "password": password, "consent_version": NOTICE_VERSION,
    }).status_code == 201
    before = (tmp_path / "vault.json").read_bytes()
    local.post("/identity/lock", headers=headers)
    assert local.get("/status", headers=headers).json()["mfa_required"]
    rejected = local.post("/identity/unlock", headers=headers, json={"password": password})
    assert rejected.status_code == 403 and rejected.json()["error"] == "mfa_required"
    assert local.get("/conversations", headers=headers).status_code == 423
    now, code = next_code(api, admin_db)
    with patch("directory.app.mfa.time", return_value=now):
        response = local.post("/identity/unlock", headers=headers, json={"password": password, "mfa_code": code})
        assert response.status_code == 200 and response.json()["unlocked"]
        local.post("/identity/lock", headers=headers)
        assert local.post("/identity/unlock", headers=headers, json={
            "password": password, "mfa_code": code,
        }).status_code == 401
        assert local.get("/conversations", headers=headers).status_code == 423
    # El desbloqueo no migra ni altera el cifrado de los archivos de la persona.
    assert (tmp_path / "vault.json").read_bytes() == before
    directory.close()

import base64
import re
import secrets
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pyotp
import pytest
from cryptography.fernet import Fernet, InvalidToken

from crypto import Identity, sign_key_change

from directory.app.config import Settings
from directory.app.audit import setup_logging, audit_log, alert_log
from directory.app.mfa import Authenticator, recovery_digest
from directory.app.schemas import b64d, b64e

from conftest import ALICE, BOB, challenge, login, publish


def begin(api, discord_id=ALICE):
    redirect = api.get("/auth/login")
    state = parse_qs(urlsplit(redirect.headers["location"]).query)["state"][0]
    page = api.get("/auth/callback", params={"code": f"code-{discord_id}", "state": state})
    assert page.status_code == 200
    csrf = re.search(r'name="csrf" value="([A-Za-z0-9_-]+)"', page.text).group(1)
    return page, csrf


def submit(api, csrf, code):
    return api.post("/auth/mfa/verify", data={"csrf": csrf, "code": code})


def secret_from(page):
    return re.search(r'id="setup-secret">([A-Z2-7]+)</code>', page.text).group(1)


def test_totp_rfc6238_y_no_reutilizacion():
    authenticator = Authenticator(Fernet.generate_key())
    # Vector RFC 6238 SHA-1 (semilla ASCII "1234567890" x2), reducido a los seis dígitos usados por Authenticator.
    rfc_seed = base64.b32encode(b"1234567890" * 2)
    ciphertext = authenticator.cipher.encrypt(rfc_seed).decode()
    with patch("directory.app.mfa.time", return_value=59):
        assert authenticator.matching_step(ciphertext, "287082", -1) == 1
        assert authenticator.matching_step(ciphertext, "287082", 1) is None
        assert authenticator.matching_step(ciphertext, "１２３４５６", -1) is None


def test_clave_cifrada_no_se_puede_leer_con_otra_clave():
    first, other = Authenticator(Fernet.generate_key()), Authenticator(Fernet.generate_key())
    ciphertext = first.new_secret()
    assert first.secret(ciphertext) not in ciphertext
    with pytest.raises(InvalidToken):
        other.secret(ciphertext)


def test_configuracion_exige_clave_mfa(monkeypatch):
    monkeypatch.delenv("TOTP_ENCRYPTION_KEY", raising=False)
    with pytest.raises(KeyError, match="TOTP_ENCRYPTION_KEY"):
        Settings.from_env()
    monkeypatch.setenv("TOTP_ENCRYPTION_KEY", "invalida")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_oauth_no_entrega_token_hasta_confirmar_qr(api, admin_db, discord):
    page, csrf = begin(api)
    secret = secret_from(page)
    assert "<svg" in page.text and "Microsoft Authenticator" in page.text
    assert "<pre" not in page.text
    assert discord.revoked == [f"at-{ALICE}"]
    assert admin_db.execute("SELECT count(*) FROM directory.auth_tokens").fetchone()[0] == 0
    stored = admin_db.execute("SELECT encrypted_secret, enabled FROM directory.mfa_accounts").fetchone()
    assert secret not in stored[0] and not stored[1]
    # Un desafío inventado no sirve para acceder a las operaciones del directorio.
    assert challenge(api, b64e(b"\0" * 32), ALICE).status_code == 401
    result = submit(api, csrf, pyotp.TOTP(secret).now())
    assert result.status_code == 200 and "<pre" in result.text
    codes = re.findall(r'<li><code>([A-F0-9-]+)</code></li>', result.text)
    assert len(codes) == len(set(codes)) == 10
    stored = admin_db.execute("SELECT enabled, recovery_hashes FROM directory.mfa_accounts").fetchone()
    assert stored[0] and bytes(stored[1][0]) == recovery_digest(codes[0])
    assert submit(api, csrf, pyotp.TOTP(secret).now()).status_code != 200


def test_siguiente_login_no_revela_secreto_y_rechaza_codigo_reutilizado(api, admin_db):
    page, csrf = begin(api)
    secret = secret_from(page)
    now = time.time()
    with patch("directory.app.mfa.time", return_value=now):
        code = pyotp.TOTP(secret).at(now)
        assert submit(api, csrf, code).status_code == 200
        page, csrf = begin(api)
        assert "<svg" not in page.text and secret not in page.text
        assert submit(api, csrf, code).status_code == 401
    with patch("directory.app.mfa.time", return_value=now + 30):
        result = submit(api, csrf, pyotp.TOTP(secret).at(now + 30))
        assert result.status_code == 200 and "recovery-codes" not in result.text
    assert admin_db.execute("SELECT count(*) FROM directory.auth_tokens").fetchone()[0] == 2


def test_intentos_persisten_entre_sesiones_y_bloquean_por_cuenta(api, admin_db):
    page, csrf = begin(api)
    secret = secret_from(page)
    # Formato no válido evita que el código de prueba coincida por casualidad.
    for _ in range(5):
        assert submit(api, csrf, "incorrecto").status_code == 401
        _, csrf = begin(api)
    assert submit(api, csrf, pyotp.TOTP(secret).now()).status_code == 401
    assert admin_db.execute("SELECT locked_until > now() FROM directory.mfa_accounts").fetchone()[0]
    admin_db.execute("UPDATE directory.mfa_accounts SET locked_until = now() - interval '1 second'")
    assert submit(api, csrf, pyotp.TOTP(secret).now()).status_code == 200


def test_sesion_vencida_csrf_y_cuenta_ajena_no_emiten_token(api, admin_db):
    page, csrf = begin(api)
    code = pyotp.TOTP(secret_from(page)).now()
    assert submit(api, "x" * 43, code).status_code == 401
    assert admin_db.execute("SELECT failed_attempts FROM directory.mfa_accounts").fetchone()[0] == 0
    admin_db.execute("UPDATE directory.mfa_sessions SET expires_at = now() - interval '1 second'")
    assert submit(api, csrf, code).status_code == 401
    page, csrf = begin(api, BOB)
    other = pyotp.TOTP(secret_from(page)).now()
    # Buscar un código distinto para que la prueba no dependa de una colisión de seis dígitos.
    wrong = "000000" if other != "000000" else "111111"
    assert submit(api, csrf, wrong).status_code == 401
    assert admin_db.execute("SELECT count(*) FROM directory.auth_tokens").fetchone()[0] == 0


def test_recuperacion_exige_nuevo_qr_e_invalida_todos_los_codigos_anteriores(api, admin_db):
    page, csrf = begin(api)
    old_secret = secret_from(page)
    done = submit(api, csrf, pyotp.TOTP(old_secret).now())
    codes = re.findall(r'<li><code>([A-F0-9-]+)</code></li>', done.text)
    _, csrf = begin(api)
    reset = submit(api, csrf, codes[0])
    assert reset.status_code == 200 and "<pre" not in reset.text
    new_secret = secret_from(reset)
    assert new_secret != old_secret
    assert admin_db.execute("SELECT count(*) FROM directory.auth_tokens").fetchone()[0] == 0
    done = submit(api, csrf, pyotp.TOTP(new_secret).now())
    assert done.status_code == 200 and "<pre" in done.text
    assert not any(c in done.text for c in codes)
    _, csrf = begin(api)
    assert submit(api, csrf, codes[0]).status_code == 401
    assert submit(api, csrf, codes[1]).status_code == 401


def test_dos_verificaciones_concurrentes_solo_emiten_un_token(api, repo):
    page, csrf = begin(api)
    code = pyotp.TOTP(secret_from(page)).now()
    session = api.cookies.get("directory_mfa").encode()
    def verify():
        return repo.verify_mfa(session, csrf.encode(), code, api.app.state.test_authenticator,
                               secrets.token_bytes(32), 600)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: verify(), range(2)))
    assert sum(r is not None for r in results) == 1


def test_cabeceras_y_cookie_seguras(make_api):
    api = make_api(discord_redirect_uri="https://testserver/auth/callback")
    page, _ = begin(api)
    cookie = page.headers["set-cookie"]
    assert "__Secure-directory_mfa=" in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    assert "Path=/auth/mfa" in cookie and "Max-Age=300" in cookie
    assert page.headers["cache-control"] == "no-store"
    assert "form-action 'self'" in page.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]


def test_formularios_no_validos_se_rechazan(api):
    assert api.post("/auth/mfa/verify", json={"code": "123456"}).status_code == 400
    assert api.post("/auth/mfa/verify", data={"csrf": "x" * 1100, "code": "123456"}).status_code == 400
    assert api.post("/auth/mfa/verify", data={"code": "123456"}).status_code == 400


def test_cancelar_borra_factor_sesiones_y_tokens(api, repo, admin_db):
    identity = Identity.create()
    assert publish(api, login(api, ALICE), ALICE, identity).status_code == 204
    token = login(api, ALICE)
    begin(api)  # Otra sesión pendiente también debe desaparecer.
    nonce = b64d(challenge(api, token, ALICE, "cancel").json()["nonce"], 32)
    result = api.request("DELETE", f"/v1/keys/{ALICE}", headers={"Authorization": f"Bearer {token}"},
                         json={"nonce": b64e(nonce), "signature": b64e(sign_key_change(identity, ALICE, b"\0" * 32, nonce))})
    assert result.status_code == 204
    assert repo.mfa_status(ALICE) is None
    for table in ("mfa_accounts", "mfa_sessions", "auth_tokens", "challenges"):
        assert admin_db.execute(f"SELECT count(*) FROM directory.{table}").fetchone()[0] == 0


def test_purga_estado_mfa_pendiente_y_conserva_factor_confirmado(api, repo, admin_db):
    login(api, ALICE)
    begin(api, BOB)
    admin_db.execute("UPDATE directory.mfa_accounts SET created_at = now() - interval '2 days'")
    admin_db.execute("UPDATE directory.mfa_sessions SET expires_at = now() - interval '1 second'")
    counts = repo.purge()
    assert counts["mfa_sessions"] == counts["mfa_pending"] == 1
    assert repo.mfa_status(ALICE)["enabled"]
    assert repo.mfa_status(BOB) is None


@pytest.fixture
def mfa_logs(tmp_path):
    loggers = [logging.getLogger("directory"), audit_log, alert_log]
    before = {lg: list(lg.handlers) for lg in loggers}
    setup_logging(tmp_path)
    yield tmp_path
    for lg in loggers:
        for handler in lg.handlers[:]:
            if handler not in before[lg]:
                handler.close()
                lg.removeHandler(handler)


def test_auditoria_no_registra_secretos_mfa(api, mfa_logs):
    page, csrf = begin(api)
    secret = secret_from(page)
    code = pyotp.TOTP(secret).now()
    assert submit(api, csrf, "incorrecto").status_code == 401
    session = api.cookies.get("directory_mfa")
    done = submit(api, csrf, code)
    codes = re.findall(r'<li><code>([A-F0-9-]+)</code></li>', done.text)
    assert len(codes) == 10
    _, csrf2 = begin(api)
    assert submit(api, csrf2, codes[0]).status_code == 200
    logs = (mfa_logs / "audit.jsonl").read_text()
    for value in (ALICE, secret, code, session, csrf, csrf2, *codes):
        assert value not in logs
    assert "mfa_rechazado" in logs and "mfa_recuperacion" in logs

"""Derechos ARCO desde el cliente local: acceso, rectificación (cambio de llave), cancelación/oposición y
borrado de los datos del dispositivo."""
import pytest
from fastapi.testclient import TestClient

from client.api import create_app
from client.errors import BadPassword, DirectoryUnavailable, KeyChanged, Locked, LoginRequired, NotFound
from client.ports import DirectoryError
from client.privacy import NOTICE_VERSION
from crypto.encoding import b64e
from conftest import ALICE, BOB, PASSWORD


# --- Acceso ---------------------------------------------------------------------------------

def test_acceso_muestra_datos_locales_y_del_directorio(pair):
    world, alice, _ = pair
    alice.send_text(BOB, "hola")
    data = alice.my_data()
    local = data["local"]
    assert local["discord_id"] == ALICE and local["public_key"] == b64e(world.directory.keys[ALICE])
    assert local["consent"]["version"] == NOTICE_VERSION
    assert local["contacts"] == [{"discord_id": BOB, "alias": "Bob", "verified": False}]
    assert local["messages"] >= 1
    assert data["directory"]["consent_version"] == NOTICE_VERSION and data["directory_error"] is None


def test_acceso_sin_sesion_de_discord_lo_indica_sin_fallar(world, monkeypatch):
    alice = world.user(ALICE)

    def sin_token(_id):
        raise DirectoryError("falta el token", 401)

    monkeypatch.setattr(world.directory, "record", sin_token)
    data = alice.my_data()
    assert data["directory"] is None and data["directory_error"] == "login_required"
    assert data["local"]["discord_id"] == ALICE


def test_acceso_exige_identidad_desbloqueada(world):
    alice = world.user(ALICE)
    alice.lock()
    with pytest.raises(Locked):
        alice.my_data()


# --- Rectificación ----------------------------------------------------------------------------

def test_rectificacion_cambia_la_llave_y_conserva_el_historial(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "antes del cambio")
    world.flush()
    old = world.directory.keys[ALICE]
    status = alice.rotate_key(PASSWORD)
    assert world.directory.keys[ALICE] != old
    assert status["public_key"] == b64e(world.directory.keys[ALICE])
    assert world.directory.records[ALICE]["replaced_keys"][0]["public_key"] == b64e(old)
    assert any(e["text"] == "antes del cambio" for e in alice.history(BOB))
    alice = world.restart(ALICE)  # la bóveda en disco ya tiene la llave nueva
    assert alice.status()["public_key"] == b64e(world.directory.keys[ALICE])


def test_rectificacion_avisa_al_contacto_que_la_habia_verificado(pair):
    world, alice, bob = pair
    bob.verify_contact(ALICE, bob.fingerprint(ALICE)["fingerprint"])
    alice.rotate_key(PASSWORD)
    with pytest.raises(KeyChanged):  # al volver a consultar la llave, Bob detecta el cambio y no sigue (RF8)
        bob.add_contact(ALICE)
    view = bob.contact(ALICE)
    assert not view["verified"] and view["session"] == "key_changed"


def test_rectificacion_con_contrasena_incorrecta_no_cambia_nada(pair):
    world, alice, _ = pair
    old = world.directory.keys[ALICE]
    with pytest.raises(BadPassword):
        alice.rotate_key("incorrecta")
    assert world.directory.keys[ALICE] == old


def test_rectificacion_con_directorio_caido_vuelve_a_la_llave_anterior(pair):
    world, alice, _ = pair
    old = world.directory.keys[ALICE]
    world.directory.down = True
    with pytest.raises(DirectoryUnavailable):
        alice.rotate_key(PASSWORD)
    world.directory.down = False
    assert alice.status()["public_key"] == b64e(old)
    alice = world.restart(ALICE)
    assert alice.status()["public_key"] == b64e(old)  # en disco también quedó la anterior


def test_rectificacion_sin_sesion_de_discord_pide_iniciarla(world, monkeypatch):
    alice = world.user(ALICE)

    def sin_token(*_args, **_kwargs):
        raise DirectoryError("falta el token", 401)

    monkeypatch.setattr(world.directory, "register", sin_token)
    with pytest.raises(LoginRequired):
        alice.rotate_key(PASSWORD)


# --- Cancelación y oposición ------------------------------------------------------------------

def test_cancelacion_borra_el_registro_y_los_datos_locales(pair, tmp_path):
    world, alice, _ = pair
    status = alice.cancel_registration(PASSWORD, delete_local=True)
    assert ALICE not in world.directory.keys
    assert status == {"unlocked": False, "vault_exists": False, "discord_id": None, "public_key": None,
                      "mfa_required": False, "session_expires_at": None}
    assert not (tmp_path / ALICE / "vault.json").exists() and not (tmp_path / ALICE / "store.enc").exists()


def test_cancelacion_conservando_lo_local_retira_el_consentimiento(pair):
    world, alice, _ = pair
    alice.cancel_registration(PASSWORD, delete_local=False)
    assert ALICE not in world.directory.keys
    assert alice.status()["unlocked"]
    assert "withdrawn_at" in alice.my_data()["local"]["consent"]
    assert alice.my_data()["directory_error"] == "not_registered"


def test_cancelacion_con_contrasena_incorrecta_no_borra_nada(pair):
    world, alice, _ = pair
    with pytest.raises(BadPassword):
        alice.cancel_registration("incorrecta", delete_local=True)
    assert ALICE in world.directory.keys and alice.status()["vault_exists"]


def test_si_el_directorio_falla_no_se_borra_lo_local(pair):
    world, alice, _ = pair
    world.directory.down = True
    with pytest.raises(DirectoryUnavailable):
        alice.cancel_registration(PASSWORD, delete_local=True)
    assert alice.status()["vault_exists"]


# --- Borrado local ------------------------------------------------------------------------------

def test_borrado_local_funciona_aun_bloqueada_y_no_toca_el_directorio(pair, tmp_path):
    world, alice, _ = pair
    alice.lock()
    with pytest.raises(BadPassword):
        alice.delete_local_data("incorrecta")
    assert (tmp_path / ALICE / "vault.json").exists()
    assert alice.delete_local_data(PASSWORD)["vault_exists"] is False
    assert not list((tmp_path / ALICE).iterdir())
    assert ALICE in world.directory.keys
    with pytest.raises(NotFound):
        alice.delete_local_data(PASSWORD)


def test_tras_el_borrado_local_se_puede_crear_otra_identidad(world):
    alice = world.user(ALICE)
    alice.delete_local_data(PASSWORD)
    assert alice.create_identity(ALICE, PASSWORD, NOTICE_VERSION)["unlocked"]


# --- API HTTP -------------------------------------------------------------------------------------

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def http(world):
    orch = world.user(ALICE)
    return world, TestClient(create_app(orch, TOKEN, ["http://127.0.0.1:5173"], run_ticker=False),
                             base_url="http://localhost")


def test_api_arco_exige_el_token(http):
    _, c = http
    assert c.get("/privacy/my-data").status_code == 401
    for path in ("/identity/rotate", "/identity/cancel", "/identity/delete-local"):
        assert c.post(path, json={"password": PASSWORD}).status_code == 401


def test_api_acceso_rectificacion_y_cancelacion(http):
    world, c = http
    assert c.get("/privacy/my-data", headers=AUTH).json()["local"]["discord_id"] == ALICE
    old = world.directory.keys[ALICE]
    assert c.post("/identity/rotate", json={"password": PASSWORD}, headers=AUTH).status_code == 200
    assert world.directory.keys[ALICE] != old
    r = c.post("/identity/cancel", json={"password": "incorrecta"}, headers=AUTH)
    assert r.status_code == 401 and r.json()["error"] == "bad_password"
    r = c.post("/identity/cancel", json={"password": PASSWORD}, headers=AUTH)
    assert r.status_code == 200 and r.json()["vault_exists"] is False
    assert ALICE not in world.directory.keys


def test_api_sin_sesion_de_discord_responde_login_required(http, monkeypatch):
    world, c = http

    def sin_token(*_args, **_kwargs):
        raise DirectoryError("falta el token", 401)

    monkeypatch.setattr(world.directory, "cancel", sin_token)
    r = c.post("/identity/cancel", json={"password": PASSWORD}, headers=AUTH)
    assert r.status_code == 403 and r.json()["error"] == "login_required"

"""Derechos ARCO en el directorio: acceso al propio registro y rectificación (cambio de llave autorizado)."""
import pytest

from crypto import Identity, sign_key_change, sign_registration
from directory.app.schemas import b64e
from directory.client_lib import DirectoryClient, DirectoryError

from conftest import ALICE, BOB, CONSENT, login, publish


def me(api, token):
    return api.get("/v1/me", headers={"Authorization": f"Bearer {token}"})


def test_acceso_devuelve_todo_el_registro_del_dueno(api):
    old, new = Identity.create(), Identity.create()
    publish(api, login(api, ALICE), ALICE, old)
    publish(api, login(api, ALICE), ALICE, new)
    resp = me(api, login(api, ALICE))
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"
    body = resp.json()
    assert body["discord_id"] == ALICE and body["public_key"] == b64e(new.public_key)
    assert body["consent_version"] == CONSENT
    assert body["registered_at"] and body["consent_at"] and body["key_changed_at"]
    assert [k["public_key"] for k in body["replaced_keys"]] == [b64e(old.public_key)]
    assert body["replaced_keys"][0]["delete_after"] > body["replaced_keys"][0]["replaced_at"]


def test_acceso_exige_token_y_no_lo_consume(api):
    alice = Identity.create()
    publish(api, login(api, ALICE), ALICE, alice)
    assert api.get("/v1/me").status_code == 401
    assert me(api, b64e(b"\x00" * 32)).status_code == 401
    token = login(api, ALICE)
    assert me(api, token).status_code == 200
    assert publish(api, token, ALICE, alice).status_code == 204  # el token sigue sirviendo


def test_acceso_solo_muestra_el_registro_propio(api):
    publish(api, login(api, ALICE), ALICE, Identity.create())
    resp = me(api, login(api, BOB))  # Bob no está registrado: no ve el de Alice ni ningún otro
    assert resp.status_code == 404


@pytest.fixture
def lib(api):
    return lambda token=None: DirectoryClient("http://testserver", auth_token=token, transport=api._transport)


def test_client_lib_record(api, lib):
    alice = Identity.create()
    lib(login(api, ALICE)).register(ALICE, alice.public_key, lambda n: sign_registration(alice, ALICE, n), CONSENT)
    assert lib(login(api, ALICE)).record(ALICE)["public_key"] == b64e(alice.public_key)


def test_client_lib_record_sin_token_indica_401(lib, monkeypatch):
    monkeypatch.delenv("DIRECTORY_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("DIRECTORY_AUTH_TOKEN_FILE", raising=False)
    with pytest.raises(DirectoryError) as exc:
        lib().record(ALICE)
    assert exc.value.status == 401


def test_rectificacion_cambio_de_llave_firmado_por_la_anterior(api, lib):
    old = Identity.create()
    lib(login(api, ALICE)).register(ALICE, old.public_key, lambda n: sign_registration(old, ALICE, n), CONSENT)
    new = old.rotate()
    lib(login(api, ALICE)).register(ALICE, new.public_key, lambda n: sign_registration(new, ALICE, n), CONSENT,
                                    sign_old=lambda n: sign_key_change(old, ALICE, new.public_key, n))
    assert lib().get_key(ALICE) == new.public_key


def test_rectificacion_con_firma_anterior_falsa_se_rechaza(api, lib):
    old, new, impostor = Identity.create(), Identity.create(), Identity.create()
    lib(login(api, ALICE)).register(ALICE, old.public_key, lambda n: sign_registration(old, ALICE, n), CONSENT)
    with pytest.raises(DirectoryError) as exc:
        lib(login(api, ALICE)).register(ALICE, new.public_key, lambda n: sign_registration(new, ALICE, n), CONSENT,
                                        sign_old=lambda n: sign_key_change(impostor, ALICE, new.public_key, n))
    assert exc.value.status == 401
    assert lib().get_key(ALICE) == old.public_key

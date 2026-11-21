import pytest
from fastapi.testclient import TestClient

from client.api import create_app
from client.errors import BadPassword, Conflict
from conftest import ALICE, BOB, PASSWORD

NUEVA = "Otra-Clave-Maestra-456"


def test_cambiar_contrasena_maestra_conserva_llave_contactos_e_historial(pair, world):
    _, alice, _ = pair
    alice.send_text(BOB, "hola")
    world.flush()
    llave = alice.status()["public_key"]
    publicada = world.directory.get_key(ALICE)

    alice.change_password(PASSWORD, NUEVA)

    alice.lock()
    with pytest.raises(BadPassword):
        alice.unlock(PASSWORD)
    alice.unlock(NUEVA)
    assert alice.status()["public_key"] == llave
    assert world.directory.get_key(ALICE) == publicada  # no se tocó el directorio
    assert [c["discord_id"] for c in alice.contacts()] == [BOB]
    assert [e["text"] for e in alice.history(BOB)] == ["hola"]


def test_con_la_contrasena_actual_incorrecta_no_cambia_nada(pair):
    _, alice, _ = pair
    with pytest.raises(BadPassword):
        alice.change_password("no-es-la-clave", NUEVA)
    alice.lock()
    alice.unlock(PASSWORD)


def test_la_nueva_no_puede_ser_igual_a_la_actual(pair):
    _, alice, _ = pair
    with pytest.raises(Conflict):
        alice.change_password(PASSWORD, PASSWORD)


def test_cambiar_contrasena_por_http(world):
    auth = {"Authorization": "Bearer t"}
    alice = world.user(ALICE)
    c = TestClient(create_app(alice, "t", ["http://127.0.0.1:5173"], run_ticker=False), base_url="http://localhost")
    assert c.post("/identity/password", json={"password": PASSWORD, "new_password": NUEVA}).status_code == 401
    assert c.post("/identity/password", headers=auth, json={"password": PASSWORD, "new_password": "corta"}).status_code == 422
    r = c.post("/identity/password", headers=auth, json={"password": "mala-clave", "new_password": NUEVA})
    assert r.status_code == 401 and r.json()["error"] == "bad_password"
    r = c.post("/identity/password", headers=auth, json={"password": PASSWORD, "new_password": NUEVA})
    assert r.status_code == 200 and r.json()["unlocked"] is True
    c.post("/identity/lock", headers=auth)
    assert c.post("/identity/unlock", headers=auth, json={"password": NUEVA}).status_code == 200

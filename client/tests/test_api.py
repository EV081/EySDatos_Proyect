import json

import pytest
from fastapi.testclient import TestClient

from client.api import create_app
from conftest import ALICE, BOB, PASSWORD

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
ORIGIN = "http://127.0.0.1:5173"


@pytest.fixture
def apis(world):
    clientes = {}
    for uid in (ALICE, BOB):
        orch = world.user(uid, create=False)
        app = create_app(orch, TOKEN, [ORIGIN], run_ticker=False)
        clientes[uid] = TestClient(app, base_url="http://localhost")
    return world, clientes


def test_sin_token_o_con_token_incorrecto_no_se_accede(apis):
    _, c = apis
    assert c[ALICE].get("/status").status_code == 401
    assert c[ALICE].get("/status", headers={"Authorization": "Bearer otro"}).status_code == 401
    assert c[ALICE].get("/contacts", headers={"Authorization": TOKEN}).status_code == 401
    assert c[ALICE].get("/health").status_code == 200


def test_host_ajeno_se_rechaza_contra_dns_rebinding(apis):
    _, c = apis
    r = c[ALICE].get("/status", headers={**AUTH, "Host": "evil.example"})
    assert r.status_code == 400


def test_cors_solo_para_el_origen_del_frontend(apis):
    _, c = apis
    ok = c[ALICE].options("/contacts", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == ORIGIN
    mal = c[ALICE].options("/contacts", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in mal.headers


def test_validacion_de_entradas(apis):
    _, c = apis
    assert c[ALICE].post("/identity", headers=AUTH, json={"discord_id": ALICE, "password": "corta"}).status_code == 422
    assert c[ALICE].post("/identity", headers=AUTH, json={"discord_id": "no-numerico", "password": PASSWORD}).status_code == 422
    assert c[ALICE].get("/contacts/abc", headers=AUTH).status_code == 422


def test_bloqueado_responde_423_sin_detalles_internos(apis):
    _, c = apis
    r = c[ALICE].get("/contacts", headers=AUTH)
    assert r.status_code == 423 and r.json()["error"] == "locked"
    assert "Traceback" not in r.text


def test_flujo_completo_por_http_entre_dos_usuarios(apis):
    world, c = apis
    for uid in (ALICE, BOB):
        assert c[uid].post("/identity", headers=AUTH, json={"discord_id": uid, "password": PASSWORD}).status_code == 201
    other = {ALICE: BOB, BOB: ALICE}
    for uid in (ALICE, BOB):
        assert c[uid].post("/contacts", headers=AUTH, json={"discord_id": other[uid], "alias": "x"}).status_code == 201

    r = c[ALICE].post(f"/conversations/{BOB}/messages", headers=AUTH, json={"text": "hola por http"})
    assert r.status_code == 202
    world.flush()
    mensajes = c[BOB].get(f"/conversations/{ALICE}/messages", headers=AUTH).json()
    assert [m["text"] for m in mensajes] == ["hola por http"] and mensajes[0]["status"] == "received"
    assert c[BOB].get(f"/conversations/{ALICE}/messages?since={mensajes[0]['seq']}", headers=AUTH).json() == []

    huella = c[ALICE].get(f"/contacts/{BOB}/fingerprint", headers=AUTH).json()["fingerprint"]
    assert c[BOB].get(f"/contacts/{ALICE}/fingerprint", headers=AUTH).json()["fingerprint"] == huella
    mala = c[ALICE].post(f"/contacts/{BOB}/verify", headers=AUTH, json={"fingerprint": "00000"})
    assert mala.status_code == 409
    ok = c[ALICE].post(f"/contacts/{BOB}/verify", headers=AUTH, json={"fingerprint": huella})
    assert ok.status_code == 200 and ok.json()["verified"] is True
    assert c[ALICE].get("/conversations", headers=AUTH).json()[0]["session"] == "active"


def test_exportar_e_importar_por_http(apis):
    world, c = apis
    c[ALICE].post("/identity", headers=AUTH, json={"discord_id": ALICE, "password": PASSWORD})
    exportada = c[ALICE].post("/identity/export", headers=AUTH, json={"password": "otra-contraseña-1"})
    assert exportada.status_code == 200
    vault = exportada.json()["vault"]
    assert c[BOB].post("/identity/import", headers=AUTH,
                       json={"discord_id": ALICE, "vault": vault, "password": "incorrecta"}).status_code == 401
    ok = c[BOB].post("/identity/import", headers=AUTH,
                     json={"discord_id": ALICE, "vault": vault, "password": "otra-contraseña-1"})
    assert ok.status_code == 201 and ok.json()["discord_id"] == ALICE


def test_bloquear_y_desbloquear_por_http(apis):
    _, c = apis
    c[ALICE].post("/identity", headers=AUTH, json={"discord_id": ALICE, "password": PASSWORD})
    assert c[ALICE].post("/identity/lock", headers=AUTH).status_code == 204
    assert c[ALICE].get("/status", headers=AUTH).json()["unlocked"] is False
    assert c[ALICE].post("/identity/unlock", headers=AUTH, json={"password": "mal"}).status_code == 401
    assert c[ALICE].post("/identity/unlock", headers=AUTH, json={"password": PASSWORD}).status_code == 200

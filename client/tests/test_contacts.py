import pytest
from fastapi.testclient import TestClient

from client.api import create_app
from client.errors import NotFound
from conftest import ALICE, BOB, CAROL, PASSWORD


def test_quitar_contacto_borra_sesion_verificacion_historial_y_cola(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "hola bob")
    world.flush()
    assert alice.contact(BOB)["session"] == "active"
    alice.verify_contact(BOB, bob.fingerprint(ALICE)["fingerprint"])
    world.channel.flush = lambda: False  # lo siguiente queda en cola
    alice.send_text(BOB, "en cola")

    alice.remove_contact(BOB)

    assert alice.contacts() == [] and alice.conversations() == []
    with pytest.raises(NotFound):
        alice.history(BOB)
    assert alice.my_data()["local"]["messages"] == 0 and alice.my_data()["local"]["queued"] == 0


def test_quitar_contacto_se_conserva_al_reiniciar(pair, world):
    _, alice, _ = pair
    alice.remove_contact(BOB)
    assert world.restart(ALICE).contacts() == []


def test_quitar_un_contacto_desconocido_es_404(pair):
    _, alice, _ = pair
    with pytest.raises(NotFound):
        alice.remove_contact(CAROL)


def test_lo_que_llega_por_la_sesion_vieja_se_descarta(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "hola")
    world.flush()
    alice.remove_contact(BOB)
    bob.send_text(ALICE, "por la sesión vieja")
    world.flush()
    assert alice.contacts() == []


def test_si_el_contacto_quitado_abre_otra_sesion_reaparece_sin_verificar(pair, world):
    _, alice, bob = pair
    alice.send_text(BOB, "hola")
    world.flush()
    alice.verify_contact(BOB, bob.fingerprint(ALICE)["fingerprint"])
    alice.remove_contact(BOB)
    bob = world.restart(BOB)  # sin sesión: su próximo mensaje empieza con un hs1
    bob.send_text(ALICE, "sigo aquí")
    world.flush()
    contacto = alice.contact(BOB)
    assert contacto["verified"] is False and contacto["alias"] is None
    assert [e["text"] for e in alice.history(BOB)] == ["sigo aquí"]


def test_quitar_contacto_por_http(world):
    token, auth = "token-de-prueba", {"Authorization": "Bearer token-de-prueba"}
    alice, _ = world.user(ALICE), world.user(BOB)
    alice.add_contact(BOB, "Bob")
    c = TestClient(create_app(alice, token, ["http://127.0.0.1:5173"], run_ticker=False), base_url="http://localhost")
    assert c.delete(f"/contacts/{BOB}").status_code == 401
    assert c.delete(f"/contacts/{BOB}", headers=auth).status_code == 204
    assert c.get("/contacts", headers=auth).json() == []
    r = c.delete(f"/contacts/{BOB}", headers=auth)
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    assert c.delete("/contacts/abc", headers=auth).status_code == 422
    alice.lock()
    assert c.delete(f"/contacts/{BOB}", headers=auth).status_code == 423
    pre = c.options(f"/contacts/{BOB}", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "DELETE"})
    assert pre.status_code == 200


def test_un_hs1_vencido_del_canal_no_revive_al_contacto_quitado(pair, world, clock):
    from crypto.constants import HANDSHAKE_TTL
    _, alice, _ = pair
    alice.remove_contact(BOB)
    bob = world.restart(BOB)
    bob.send_text(ALICE, "viejo")  # su hs1 queda en el canal
    clock.advance(HANDSHAKE_TTL + 600)  # se relee días después (p. ej. al desbloquear)
    world.flush()
    assert alice.contacts() == []
    assert world.restart(ALICE).contacts() == []

import pytest

from client.errors import Conflict, KeyChanged, PeerUnavailable
from conftest import ALICE, BOB
from crypto import Identity, fingerprint


def textos(orch, peer):
    return [(e["dir"], e["text"], e["status"]) for e in orch.history(peer)]


def verificar_ambos(alice, bob):
    alice.verify_contact(BOB, bob.fingerprint(ALICE)["fingerprint"])  # lo que Bob le dicta a Alice
    bob.verify_contact(ALICE, alice.fingerprint(BOB)["fingerprint"])


def test_RF6_ambos_extremos_ven_la_misma_huella(pair):
    _, alice, bob = pair
    huella = alice.fingerprint(BOB)["fingerprint"]
    assert huella == bob.fingerprint(ALICE)["fingerprint"]
    assert len(huella.split()) == 12


def test_RF7_se_verifica_con_la_huella_leida_fuera_de_discord(pair):
    _, alice, bob = pair
    assert alice.contact(BOB)["verified"] is False
    assert alice.verify_contact(BOB, bob.fingerprint(ALICE)["fingerprint"])["verified"] is True
    # también vale sin espacios (p. ej. lo escaneado de un QR)
    assert bob.verify_contact(ALICE, alice.fingerprint(BOB)["fingerprint"].replace(" ", ""))["verified"]


def test_RF7_una_huella_incorrecta_no_verifica(pair):
    _, alice, bob = pair
    huella = bob.fingerprint(ALICE)["fingerprint"]
    mala = huella[:-1] + str((int(huella[-1]) + 1) % 10)
    with pytest.raises(Conflict):
        alice.verify_contact(BOB, mala)
    assert alice.contact(BOB)["verified"] is False


def test_RF8_cambio_de_llave_de_un_contacto_verificado_revoca_aborta_y_alerta(pair):
    world, alice, bob = pair
    verificar_ambos(alice, bob)
    atacante = Identity.create()
    world.directory.keys[BOB] = atacante.public_key  # directorio comprometido o Bob cambió de llave

    alice.send_text(BOB, "no debe salir")
    world.flush()
    vista = alice.contact(BOB)
    assert vista["verified"] is False and vista["key_changed"] is True
    assert vista["session"] == "key_changed" and vista["queued"] == 1
    assert world.channel.log == []  # no se envió ni un solo mensaje, ni siquiera un hs1
    assert alice.history(BOB)[-1]["status"] == "key_changed"  # alerta visible en la conversación
    with pytest.raises(KeyChanged):
        alice._peer_key(alice._contacts[BOB])


def test_RF8_el_hs1_de_un_contacto_cuya_llave_cambio_se_ignora(pair):
    world, alice, bob = pair
    verificar_ambos(alice, bob)
    world.directory.keys[ALICE] = Identity.create().public_key
    bob.send_text(ALICE, "hola")
    world.flush()
    assert alice.contact(BOB)["session"] == "none"
    assert textos(alice, BOB) == []


def test_RF8_no_hay_continuar_de_todos_modos_solo_reverificar_con_la_huella_nueva(pair):
    world, alice, bob = pair
    verificar_ambos(alice, bob)
    nueva = Identity.create()
    world.directory.keys[BOB] = nueva.public_key
    alice.send_text(BOB, "hola")
    antigua = bob.fingerprint(ALICE)["fingerprint"]
    with pytest.raises(Conflict):  # la huella vieja ya no sirve
        alice.verify_contact(BOB, antigua)
    assert alice.contact(BOB)["session"] == "key_changed"
    pendiente = alice.fingerprint(BOB)
    assert pendiente["key_pending"] is True
    # tras comparar la huella nueva fuera de Discord, la ceremonia se completa
    nueva_huella = fingerprint(alice._identity.public_key, nueva.public_key)
    vista = alice.verify_contact(BOB, nueva_huella)
    assert vista["verified"] is True and vista["key_changed"] is False


def test_la_llave_cambia_otra_vez_mientras_se_verifica(pair):
    world, alice, bob = pair
    verificar_ambos(alice, bob)
    world.directory.keys[BOB] = Identity.create().public_key
    alice.send_text(BOB, "hola")
    huella = alice.fingerprint(BOB)["fingerprint"]
    world.directory.keys[BOB] = Identity.create().public_key  # cambia de nuevo
    with pytest.raises(Conflict):
        alice.verify_contact(BOB, huella)


def test_un_contacto_sin_verificar_que_cambia_de_llave_solo_se_marca(pair):
    world, alice, bob = pair
    nueva = Identity.create()
    world.directory.keys[BOB] = nueva.public_key
    alice._peer_key(alice._contacts[BOB])
    vista = alice.contact(BOB)
    assert vista["key_changed"] is True and vista["verified"] is False
    assert alice._contacts[BOB].pk == nueva.public_key


def test_si_el_directorio_vuelve_a_la_llave_anclada_se_desbloquea(pair):
    world, alice, bob = pair
    verificar_ambos(alice, bob)
    original = world.directory.keys[BOB]
    world.directory.keys[BOB] = Identity.create().public_key
    alice.send_text(BOB, "hola")
    assert alice.contact(BOB)["session"] == "key_changed"
    world.directory.keys[BOB] = original
    alice.retry(BOB)
    world.flush()
    assert alice.contact(BOB)["session"] == "active"


def test_directorio_caido_el_mensaje_espera_y_se_reintenta(pair):
    world, alice, bob = pair
    world.directory.down = True
    alice.send_text(BOB, "hola")
    world.flush()
    assert alice.contact(BOB)["queued"] == 1 and world.channel.log == []
    world.directory.down = False
    world.clock.advance(61)
    alice.tick()
    world.flush()
    assert textos(bob, ALICE) == [("in", "hola", "received")]


def test_agregar_contacto_con_directorio_caido(world):
    alice = world.user(ALICE)
    world.directory.keys[BOB] = Identity.create().public_key
    world.directory.down = True
    with pytest.raises(PeerUnavailable):
        alice.add_contact(BOB)
    assert alice.contacts() == []


def test_verificado_sobrevive_a_reiniciar_la_app(pair):
    world, alice, bob = pair
    verificar_ambos(alice, bob)
    alice = world.restart(ALICE)
    assert alice.contact(BOB)["verified"] is True

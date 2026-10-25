import pytest

from client.errors import Conflict, NotFound, PeerUnavailable
from client.orchestrator import MAX_ATTEMPTS
from conftest import ALICE, BOB, CAROL, PASSWORD
from crypto.constants import HANDSHAKE_TTL, MAX_PLAINTEXT, ROTATE_AFTER_MESSAGES


def textos(orch, peer):
    return [(e["dir"], e["text"], e["status"]) for e in orch.history(peer)]


# --- camino feliz ---------------------------------------------------------------------

def test_RF3_RF5_conversacion_completa_con_handshake_automatico(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "hola bob")
    assert alice.contact(BOB)["session"] == "handshaking"
    world.flush()
    assert alice.contact(BOB)["session"] == bob.contact(ALICE)["session"] == "active"
    assert textos(alice, BOB) == [("out", "hola bob", "sent")]
    assert textos(bob, ALICE) == [("in", "hola bob", "received")]
    bob.send_text(ALICE, "hola alice")
    world.flush()
    assert textos(alice, BOB)[-1] == ("in", "hola alice", "received")


def test_RF3_en_el_canal_solo_hay_mensajes_del_protocolo_y_ciphertext(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "contrasena-super-secreta")
    world.flush()
    bob.send_text(ALICE, "otra-cosa-privada")
    world.flush()
    assert len(world.channel.log) >= 5  # hs1, hs2, hs3 y mensajes
    assert all(t.startswith("E2EE1:") for t in world.channel.log)
    assert not any("secreta" in t or "privada" in t for t in world.channel.log)


def test_un_texto_largo_se_parte_en_varios_mensajes(pair):
    world, alice, bob = pair
    largo = "ñ" * (MAX_PLAINTEXT)  # 2 bytes por carácter: no cabe en un solo mensaje
    alice.send_text(BOB, largo)
    world.flush()
    recibido = "".join(e["text"] for e in bob.history(ALICE))
    assert recibido == largo and len(bob.history(ALICE)) > 1


def test_mensaje_vacio(pair):
    _, alice, _ = pair
    with pytest.raises(Conflict):
        alice.send_text(BOB, "   ")


def test_contacto_desconocido(pair):
    _, alice, _ = pair
    with pytest.raises(NotFound):
        alice.send_text(CAROL, "hola")
    with pytest.raises(PeerUnavailable):
        alice.add_contact(CAROL)  # no está en el directorio
    assert CAROL not in [c["discord_id"] for c in alice.contacts()]


# --- RF14: contacto desconectado, cola y reintentos ----------------------------------------

def test_RF14_el_mensaje_espera_en_cola_y_el_intento_caduca_y_se_reintenta_a_los_15_min(pair):
    world, alice, bob = pair
    world.discord[BOB].online = False
    alice.send_text(BOB, "¿estás?")
    world.flush()
    assert alice.contact(BOB)["session"] == "handshaking" and alice.contact(BOB)["queued"] == 1
    n_hs1 = sum(t.count("E2EE1:") for t in world.channel.log)

    world.clock.advance(HANDSHAKE_TTL + 1)  # el intento caduca; el mensaje NO
    alice.tick()
    assert alice.contact(BOB)["session"] == "waiting" and alice.contact(BOB)["queued"] == 1

    world.clock.advance(15 * 60 - 2)  # faltan segundos para cumplirse los 15 minutos de espera
    alice.tick()
    assert len(world.channel.log) == n_hs1

    world.clock.advance(5)
    world.discord[BOB].online = True  # Bob vuelve
    alice.tick()  # segundo intento, ahora con Bob conectado
    world.flush()
    assert bob.contact(ALICE)["session"] == "active"
    assert textos(bob, ALICE) == [("in", "¿estás?", "received")]
    assert alice.contact(BOB)["queued"] == 0


def test_la_espera_entre_reintentos_crece_15_30_60(pair):
    world, alice, bob = pair
    world.discord[BOB].online = False
    alice.send_text(BOB, "hola")
    esperas = []
    for _ in range(3):
        world.clock.advance(HANDSHAKE_TTL + 1)
        alice.tick()
        antes = world.clock()
        n = len(world.channel.log)
        while len(world.channel.log) == n:
            world.clock.advance(60)
            alice.tick()
        esperas.append(round((world.clock() - antes) / 60))
    assert esperas[0] >= 15 and esperas[1] >= 30 and esperas[2] >= 60 - 1


def test_tras_el_maximo_de_intentos_queda_no_disponible_y_se_puede_reintentar(pair):
    world, alice, bob = pair
    world.discord[BOB].online = False
    alice.send_text(BOB, "hola")
    for _ in range(MAX_ATTEMPTS + 2):
        world.clock.advance(HANDSHAKE_TTL + 1)
        alice.tick()
        world.clock.advance(3600)
        alice.tick()
    assert alice.contact(BOB)["session"] == "unavailable" and alice.contact(BOB)["queued"] == 1
    n = len(world.channel.log)
    world.discord[BOB].online = True
    alice.retry(BOB)
    world.flush()
    assert len(world.channel.log) > n and textos(bob, ALICE) == [("in", "hola", "received")]


def test_RF14_la_cola_sobrevive_a_cerrar_la_app_y_la_llave_efimera_no(pair):
    world, alice, bob = pair
    world.discord[BOB].online = False
    alice.send_text(BOB, "mensaje pendiente")
    alice = world.restart(ALICE)  # se cierra y reabre: la memoria (sesiones, handshake) se pierde
    assert alice.contact(BOB)["queued"] == 1 and alice.contact(BOB)["session"] in ("none", "waiting")
    world.discord[BOB].online = True
    alice.retry(BOB)
    world.flush()
    assert textos(bob, ALICE) == [("in", "mensaje pendiente", "received")]


def test_un_hs1_viejo_reentregado_al_reconectar_no_abre_sesion(pair):
    world, alice, bob = pair
    world.discord[BOB].online = False
    alice.send_text(BOB, "hola")
    world.flush()
    world.clock.advance(HANDSHAKE_TTL + 60)
    world.discord[BOB].reconnect_with_backlog()  # Bob ve el hs1 de hace 6 minutos
    world.flush()
    assert bob.contact(ALICE)["session"] == "none"
    assert textos(bob, ALICE) == []


def test_si_discord_falla_el_mensaje_sigue_en_cola(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "uno")
    world.flush()
    world.discord[ALICE].fail_sends = True
    alice.send_text(BOB, "dos")
    assert alice.contact(BOB)["queued"] == 1
    world.discord[ALICE].fail_sends = False
    alice.tick()
    world.flush()
    assert [t for _, t, _ in textos(bob, ALICE)] == ["uno", "dos"]


# --- cosas que llegan al canal y no son para mí ----------------------------------------------

def test_se_ignora_lo_que_no_es_del_protocolo_ni_va_dirigido_al_usuario(pair):
    world, alice, bob = pair
    for basura in ("hola a todos", "E2EE1:xxxx", "", "E2EE1:" + "A" * 3000):
        bob.on_discord_message(basura)
    carol = world.user(CAROL)
    carol.add_contact(ALICE)
    carol.send_text(ALICE, "para alice, no para bob")
    world.flush()
    assert bob.history(ALICE) == []
    assert CAROL not in [c["discord_id"] for c in bob.contacts()]


def test_un_desconocido_registrado_en_el_directorio_queda_como_contacto_sin_verificar(pair):
    world, alice, bob = pair
    carol = world.user(CAROL)
    carol.add_contact(ALICE)
    carol.send_text(ALICE, "hola, soy Carol")
    world.flush()
    nuevo = {c["discord_id"]: c for c in alice.contacts()}[CAROL]
    assert nuevo["verified"] is False and nuevo["session"] == "active"
    assert textos(alice, CAROL) == [("in", "hola, soy Carol", "received")]


def test_ids_no_registrados_en_el_directorio_no_crean_contactos(pair):
    from crypto import Identity, Initiator, encode
    from crypto.encoding import b64d
    world, alice, bob = pair
    falso = Initiator(Identity.create(), "444444444444444444", ALICE, b64d(alice.status()["public_key"]))
    alice.on_discord_message(encode(falso.start()))
    assert "444444444444444444" not in [c["discord_id"] for c in alice.contacts()]


# --- RF11, RS5, RS14 ------------------------------------------------------------------------------

def test_RF11_mensaje_alterado_aparece_como_no_descifrable(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "hola")
    world.flush()
    alice.send_text(BOB, "segundo")
    world.flush()
    original = world.channel.log[-1]
    from crypto import decode, encode
    from dataclasses import replace
    msg = decode(original)
    falso = replace(msg, ctr=msg.ctr + 5, ct=bytes([msg.ct[0] ^ 1]) + msg.ct[1:])
    bob.on_discord_message(encode(falso))
    ultimo = bob.history(ALICE)[-1]
    assert ultimo["status"] == "undecryptable" and ultimo["text"] is None


def test_RS14_replay_del_mismo_mensaje_no_se_muestra_dos_veces(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "una sola vez")
    world.flush()
    bob.on_discord_message(world.channel.log[-1])
    bob.on_discord_message(world.channel.log[-1])
    assert textos(bob, ALICE) == [("in", "una sola vez", "received")]


def test_el_historial_del_canal_reentregado_no_duplica_ni_marca_errores(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "hola")
    world.flush()
    bob = world.restart(BOB)
    world.discord[BOB].reconnect_with_backlog()
    world.flush()
    assert textos(bob, ALICE) == [("in", "hola", "received")]


# --- RS9: rotación ---------------------------------------------------------------------------------

def test_RS9_la_sesion_se_rota_a_los_100_mensajes_sin_perder_ninguno(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "inicial")
    world.flush()
    sid_antes = alice._peers[BOB].session.sid
    for i in range(ROTATE_AFTER_MESSAGES):
        alice.send_text(BOB, f"m{i}")
        world.flush()
    alice.tick()
    world.flush()
    assert alice._peers[BOB].session.sid != sid_antes
    alice.send_text(BOB, "después de rotar")
    world.flush()
    recibidos = [t for _, t, _ in textos(bob, ALICE)]
    assert recibidos[0] == "inicial" and recibidos[-1] == "después de rotar"
    assert len(recibidos) == ROTATE_AFTER_MESSAGES + 2
    assert all(s != "undecryptable" for _, _, s in textos(bob, ALICE))


def test_RS9_la_sesion_anterior_se_destruye_tras_la_gracia(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "hola")
    world.flush()
    vieja = alice._peers[BOB].session
    world.clock.advance(8 * 3600)
    alice.tick()
    world.flush()
    assert alice._peers[BOB].session is not vieja and not vieja.destroyed
    world.clock.advance(61)
    alice.tick()
    assert vieja.destroyed


def test_los_dos_inician_a_la_vez_y_queda_una_sola_sesion_funcional(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "de alice")
    bob.send_text(ALICE, "de bob")
    world.flush()
    assert alice.contact(BOB)["session"] == bob.contact(ALICE)["session"] == "active"
    assert ("in", "de bob", "received") in textos(alice, BOB)
    assert ("in", "de alice", "received") in textos(bob, ALICE)
    assert alice._peers[BOB].session.sid == bob._peers[ALICE].session.sid


# --- bloqueo ---------------------------------------------------------------------------------------

def test_al_bloquear_se_destruyen_las_sesiones(pair):
    world, alice, bob = pair
    alice.send_text(BOB, "hola")
    world.flush()
    sesion = alice._peers[BOB].session
    alice.lock()
    assert sesion.destroyed
    alice.on_discord_message(world.channel.log[-1])  # no hace nada y no explota

import json

import pytest

from client.errors import BadPassword, Conflict, Locked, NotFound, TooManyAttempts
from client.ports import DirectoryError
from conftest import ALICE, BOB, PASSWORD


def test_crear_publicar_y_desbloquear(world):
    alice = world.user(ALICE)
    assert alice.status()["unlocked"] and world.directory.keys[ALICE]
    alice.lock()
    assert not alice.status()["unlocked"]
    assert alice.unlock(PASSWORD)["discord_id"] == ALICE


def test_RS2_contrasena_incorrecta_y_bloqueo_temporal(world, clock):
    alice = world.user(ALICE)
    alice.lock()
    for _ in range(5):
        with pytest.raises(BadPassword):
            alice.unlock("incorrecta")
    with pytest.raises(TooManyAttempts):
        alice.unlock(PASSWORD)  # ni la correcta pasa durante el bloqueo
    clock.advance(31)
    assert alice.unlock(PASSWORD)["unlocked"]


def test_bloqueado_nada_funciona(world):
    alice = world.user(ALICE)
    alice.lock()
    for call in (alice.contacts, alice.conversations, lambda: alice.send_text(BOB, "hola")):
        with pytest.raises(Locked):
            call()


def test_no_se_sobrescribe_una_identidad(world):
    alice = world.user(ALICE)
    with pytest.raises(Conflict):
        alice.create_identity(ALICE, PASSWORD)


def test_unlock_sin_identidad(world):
    with pytest.raises(NotFound):
        world.user(ALICE, create=False).unlock(PASSWORD)


def test_RS1_RS2_nada_secreto_en_claro_en_disco(world):
    alice, bob = world.user(ALICE), world.user(BOB)
    alice.add_contact(BOB)
    alice.send_text(BOB, "texto-secreto-que-no-debe-estar-en-disco")
    contenido = b"".join(p.read_bytes() for p in (world.tmp / ALICE).iterdir())
    assert b"texto-secreto" not in contenido
    assert b"Bob" not in contenido  # ni siquiera los alias


def test_RF12_exportar_e_importar_en_otro_dispositivo(world, tmp_path):
    alice = world.user(ALICE)
    blob = alice.export_identity("contraseña-de-exportación")
    otro = world.user("999999999999999999", create=False)
    otro_status = otro.import_identity(ALICE, blob, "contraseña-de-exportación")
    assert otro_status["public_key"] == alice.status()["public_key"]
    with pytest.raises(BadPassword):
        world.user("888888888888888888", create=False).import_identity(ALICE, blob, "incorrecta")


def test_directorio_caido_al_crear_identidad(world):
    world.directory.down = True
    with pytest.raises(Exception):
        world.user(ALICE)


def test_si_el_directorio_falla_se_puede_reintentar_la_creacion(world):
    world.directory.down = True
    with pytest.raises(Exception):
        world.user(ALICE)
    world.directory.down = False
    alice = world.user(ALICE)
    assert alice.status()["unlocked"] and ALICE in world.directory.keys

import json

import pytest

from client.errors import BadPassword, Conflict, Locked, NotFound, TooManyAttempts
from client.ports import DirectoryError
from client.privacy import NOTICE_VERSION
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
        alice.create_identity(ALICE, PASSWORD, NOTICE_VERSION)


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
    otro_status = otro.import_identity(ALICE, blob, "contraseña-de-exportación", NOTICE_VERSION)
    assert otro_status["public_key"] == alice.status()["public_key"]
    with pytest.raises(BadPassword):
        world.user("888888888888888888", create=False).import_identity(ALICE, blob, "incorrecta", NOTICE_VERSION)


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


def test_publicar_la_llave_exige_aceptar_el_aviso_de_privacidad_vigente(world):
    alice = world.user(ALICE, create=False)
    for version in ("", "0.9", "2.0"):
        with pytest.raises(Conflict):
            alice.create_identity(ALICE, PASSWORD, version)
    assert world.directory.keys == {} and not alice.status()["vault_exists"]  # no se creó ni publicó nada


def test_el_directorio_recibe_la_version_del_aviso_aceptado(world):
    world.user(ALICE)
    assert world.directory.consents[ALICE] == NOTICE_VERSION


def test_importar_tambien_exige_el_consentimiento(world):
    blob = world.user(ALICE).export_identity("contraseña-de-exportación")
    otro = world.user("999999999999999999", create=False)
    with pytest.raises(Conflict):
        otro.import_identity(ALICE, blob, "contraseña-de-exportación", "")
    assert not otro.status()["vault_exists"]


def test_el_consentimiento_queda_registrado_en_el_almacen_cifrado(world, clock):
    alice = world.user(ALICE)
    assert alice._doc["consent"] == {"version": NOTICE_VERSION, "at": clock()}

import pytest

from client.errors import BadPassword, DirectoryUnavailable, Locked, MfaRejected, MfaRequired
from client.ports import DirectoryError

from conftest import ALICE, BOB, PASSWORD


@pytest.fixture
def secured(world):
    world.directory.requires_mfa = True
    calls = []

    def authenticate(discord_id, code, sign):
        calls.append((discord_id, code))
        if world.directory.down:
            raise DirectoryError("directorio caído")
        if code != "123456":
            raise DirectoryError("código rechazado", 401)

    world.directory.authenticate_session = authenticate
    return world, world.user(ALICE), calls


def test_desbloquear_requiere_factor_aunque_la_contrasena_sea_correcta(secured):
    _, alice, calls = secured
    alice.lock()
    with pytest.raises(MfaRequired):
        alice.unlock(PASSWORD)
    with pytest.raises(MfaRejected):
        alice.unlock(PASSWORD, "000000")
    assert not alice.unlocked
    assert calls == [(ALICE, "000000")]
    with pytest.raises(Locked):
        alice.export_identity(PASSWORD)


def test_contrasena_incorrecta_no_envia_el_factor_al_directorio(secured):
    _, alice, calls = secured
    alice.lock()
    with pytest.raises(BadPassword):
        alice.unlock("incorrecta", "123456")
    assert not calls and not alice.unlocked


def test_cada_bloqueo_y_reinicio_exige_otra_verificacion(secured):
    world, alice, calls = secured
    for _ in range(2):
        alice.lock()
        assert alice.unlock(PASSWORD, "123456")["unlocked"]
    alice.lock()
    restarted = world.user(ALICE, create=False)
    with pytest.raises(MfaRequired):
        restarted.unlock(PASSWORD)
    assert restarted.unlock(PASSWORD, "123456")["unlocked"]
    assert len(calls) == 3


def test_directorio_caido_mantiene_identidad_e_historial_bloqueados(secured):
    world, alice, _ = secured
    alice.lock()
    world.directory.down = True
    with pytest.raises(DirectoryUnavailable):
        alice.unlock(PASSWORD, "123456")
    assert not alice.unlocked and alice._doc == {}


def test_sesion_caduca_y_destruye_las_llaves_de_conversacion(secured):
    world, alice, calls = secured
    bob = world.user(BOB)
    alice.add_contact(BOB)
    bob.add_contact(ALICE)
    alice.verify_contact(BOB, bob.fingerprint(ALICE)["fingerprint"])
    bob.verify_contact(ALICE, alice.fingerprint(BOB)["fingerprint"])
    alice.send_text(BOB, "mensaje privado")
    world.flush()
    session = alice._peers[BOB].session
    assert session and not session.destroyed
    deadline = alice.status()["session_expires_at"]
    world.clock.now = deadline
    with pytest.raises(Locked):
        alice.history(BOB)
    assert session.destroyed
    assert alice._doc == {} and alice._peers == {} and not alice.status()["unlocked"]
    with pytest.raises(MfaRequired):
        alice.unlock(PASSWORD)
    assert alice.unlock(PASSWORD, "123456")["unlocked"]
    assert len(calls) == 1

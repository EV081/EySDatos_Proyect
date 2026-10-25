from dataclasses import replace

import pytest

from crypto import DecryptError, Initiator, ReplayError, Responder, SessionExpired, WireError, decode, encode
from crypto import aead
from crypto.constants import (
    HARD_LIMIT_FACTOR, MAX_PLAINTEXT, REPLAY_WINDOW, ROTATE_AFTER_MESSAGES, ROTATE_AFTER_SECONDS,
)
from conftest import ALICE, BOB


def flip(data: bytes) -> bytes:
    return bytes([data[0] ^ 1]) + data[1:]


def new_sessions(alice, bob, clock):
    init = Initiator(alice, ALICE, BOB, bob.public_key, clock)
    resp = Responder(bob, BOB, ALICE, alice.public_key, clock=clock)
    hs3, a = init.finish(resp.respond(init.start()))
    return a, resp.finish(hs3)


# --- RS4, RS5: AES-256-GCM ------------------------------------------------------------

def test_RF3_ida_y_vuelta_incluyendo_unicode_y_vacio(handshake):
    a, b = handshake["a"], handshake["b"]
    for texto in (b"", "¡ñandú 🔒!".encode(), b"x" * MAX_PLAINTEXT):
        assert b.decrypt(a.encrypt(texto)) == texto


def test_RF3_el_texto_plano_no_aparece_en_el_mensaje(handshake):
    msg = handshake["a"].encrypt(b"contrasena-super-secreta")
    assert b"contrasena" not in encode(msg).encode() and b"contrasena" not in msg.ct


def test_RS4_nonces_de_96_bits_y_nunca_repetidos(handshake):
    a = handshake["a"]
    nonces = [a.encrypt(b"m").nonce for _ in range(150)]
    assert all(len(n) == 12 for n in nonces) and len(set(nonces)) == 150


def test_RS4_si_el_csprng_repitiera_un_nonce_la_sesion_no_lo_reutiliza(handshake, monkeypatch):
    salidas = iter([b"\x01" * 12, b"\x01" * 12, b"\x02" * 12])
    monkeypatch.setattr(aead, "new_nonce", lambda: next(salidas))
    a = handshake["a"]
    assert a.encrypt(b"1").nonce == b"\x01" * 12
    assert a.encrypt(b"2").nonce == b"\x02" * 12


@pytest.mark.parametrize("campo", ["ct", "nonce"])
def test_RS5_etiqueta_gcm_invalida_se_rechaza(handshake, campo):
    msg = handshake["a"].encrypt(b"hola")
    with pytest.raises(DecryptError):
        handshake["b"].decrypt(replace(msg, **{campo: flip(getattr(msg, campo))}))


def test_RS5_ultimo_byte_de_la_etiqueta(handshake):
    msg = handshake["a"].encrypt(b"hola")
    ct = msg.ct[:-1] + bytes([msg.ct[-1] ^ 0x80])
    with pytest.raises(DecryptError):
        handshake["b"].decrypt(replace(msg, ct=ct))


def test_RS5_el_contexto_esta_ligado_al_criptograma(handshake):
    a, b = handshake["a"], handshake["b"]
    msg = a.encrypt(b"hola")
    for alterado in (replace(msg, sender=BOB), replace(msg, receiver=ALICE), replace(msg, sid=b"z" * 16)):
        with pytest.raises(DecryptError):
            b.decrypt(alterado)
    with pytest.raises(Exception):  # cambiar el contador rompe el AAD
        b.decrypt(replace(msg, ctr=msg.ctr + 1))
    assert b.decrypt(msg) == b"hola"  # los intentos fallidos no gastaron el mensaje


def test_un_mensaje_que_no_cabe_se_rechaza(handshake):
    with pytest.raises(WireError):
        handshake["a"].encrypt(b"x" * (MAX_PLAINTEXT + 1))


# --- reflexión y separación entre sesiones --------------------------------------------

def test_RS15_un_mensaje_propio_no_se_acepta_reflejado(handshake):
    a, b = handshake["a"], handshake["b"]
    msg = a.encrypt(b"hola")
    with pytest.raises(DecryptError):
        a.decrypt(msg)  # reflejado hacia el emisor
    reflejado = replace(msg, sender=BOB, receiver=ALICE)  # y maquillado como si fuera de Bob
    with pytest.raises(DecryptError):
        a.decrypt(reflejado)


def test_un_mensaje_de_otra_sesion_se_rechaza(alice, bob, clock):
    a1, _ = new_sessions(alice, bob, clock)
    _, b2 = new_sessions(alice, bob, clock)
    with pytest.raises(DecryptError):
        b2.decrypt(a1.encrypt(b"otra sesion"))


# --- RS14: anti-replay ------------------------------------------------------------------

def test_RS14_replay_exacto_se_rechaza(handshake):
    msg = handshake["a"].encrypt(b"una vez")
    assert handshake["b"].decrypt(msg) == b"una vez"
    with pytest.raises(ReplayError):
        handshake["b"].decrypt(msg)


def test_RS14_desorden_dentro_de_la_ventana_se_acepta(handshake):
    a, b = handshake["a"], handshake["b"]
    mensajes = [a.encrypt(bytes([i])) for i in range(5)]
    for i in (4, 2, 0, 3, 1):
        assert b.decrypt(mensajes[i]) == bytes([i])
    for m in mensajes:
        with pytest.raises(ReplayError):
            b.decrypt(m)


def test_RS14_mensajes_fuera_de_la_ventana_se_rechazan(alice, bob, clock, monkeypatch):
    monkeypatch.setattr("crypto.session.ROTATE_AFTER_MESSAGES", 10_000)
    a, b = new_sessions(alice, bob, clock)
    viejo = a.encrypt(b"viejo")
    for _ in range(REPLAY_WINDOW + 1):
        b.decrypt(a.encrypt(b"relleno"))
    with pytest.raises(ReplayError):
        b.decrypt(viejo)


def test_RS14_un_mensaje_falso_no_adelanta_la_ventana(handshake):
    a, b = handshake["a"], handshake["b"]
    legitimo = a.encrypt(b"legitimo")  # ctr 1
    falso = replace(a.encrypt(b"x"), ctr=500)
    with pytest.raises(DecryptError):
        b.decrypt(falso)
    assert b.decrypt(legitimo) == b"legitimo"


def test_contador_cero_o_negativo(handshake):
    msg = handshake["a"].encrypt(b"x")
    with pytest.raises(ReplayError):
        handshake["b"].decrypt(replace(msg, ctr=0))


# --- RS9: rotación ---------------------------------------------------------------------

def test_RS9_pide_rotar_por_numero_de_mensajes(handshake):
    a, b = handshake["a"], handshake["b"]
    assert not a.needs_rotation()
    for _ in range(ROTATE_AFTER_MESSAGES):
        b.decrypt(a.encrypt(b"m"))
    assert a.needs_rotation() and b.needs_rotation()


def test_RS9_pide_rotar_por_tiempo(handshake, clock):
    assert not handshake["a"].needs_rotation()
    clock.advance(ROTATE_AFTER_SECONDS)
    assert handshake["a"].needs_rotation()


def test_RS9_pasado_el_limite_duro_la_sesion_se_destruye(handshake, clock):
    clock.advance(ROTATE_AFTER_SECONDS * HARD_LIMIT_FACTOR)
    with pytest.raises(SessionExpired):
        handshake["a"].encrypt(b"x")
    assert handshake["a"].destroyed
    with pytest.raises(SessionExpired):
        handshake["a"].decrypt(handshake["b"].encrypt(b"x"))


def test_RS9_limite_duro_por_mensajes(alice, bob, clock):
    a, b = new_sessions(alice, bob, clock)
    with pytest.raises(SessionExpired):
        for _ in range(ROTATE_AFTER_MESSAGES * HARD_LIMIT_FACTOR + 1):
            b.decrypt(a.encrypt(b"m"))


def test_destruir_borra_las_llaves(handshake):
    a = handshake["a"]
    llave = a._send_key
    a.destroy()
    assert a.destroyed and a._send_key is None and not any(llave)
    with pytest.raises(SessionExpired):
        a.encrypt(b"x")


def test_RF11_el_cliente_puede_distinguir_un_mensaje_no_descifrable(handshake):
    texto = encode(handshake["a"].encrypt(b"hola"))
    msg = decode(texto)
    with pytest.raises(DecryptError):
        handshake["b"].decrypt(replace(msg, ct=flip(msg.ct)))

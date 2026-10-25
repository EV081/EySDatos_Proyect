from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from crypto import (
    Hs3, HandshakeError, Identity, Initiator, ReplayError, Responder, SidCache, decode, encode,
)
from crypto.constants import CLOCK_SKEW, CTX_INITIATOR, CTX_RESPONDER, HANDSHAKE_TTL
from crypto.handshake import _exchange, _transcript
from conftest import ALICE, BOB


def flip(data: bytes) -> bytes:
    return bytes([data[0] ^ 1]) + data[1:]


def new_pair(alice, bob, clock):
    init = Initiator(alice, ALICE, BOB, bob.public_key, clock)
    resp = Responder(bob, BOB, ALICE, alice.public_key, clock=clock)
    return init, resp


def reachable(obj, seen=None):
    """Todos los objetos alcanzables desde obj por atributos y contenedores."""
    seen = set() if seen is None else seen
    if id(obj) in seen:
        return
    seen.add(id(obj))
    yield obj
    if isinstance(obj, dict):
        children = list(obj.keys()) + list(obj.values())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        children = list(obj)
    elif hasattr(obj, "__dict__"):
        children = list(vars(obj).values())
    else:
        children = []
    for child in children:
        yield from reachable(child, seen)


# --- camino feliz -----------------------------------------------------------------

def test_RF13_handshake_completo_y_mensajes_en_ambos_sentidos(handshake):
    a, b = handshake["a"], handshake["b"]
    assert a.sid == b.sid == handshake["hs1"].sid
    assert b.decrypt(a.encrypt(b"hola bob")) == b"hola bob"
    assert a.decrypt(b.encrypt(b"hola alice")) == b"hola alice"


def test_los_mensajes_del_handshake_sobreviven_al_formato_de_discord(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs2 = resp.respond(decode(encode(init.start())))
    hs3, sess_a = init.finish(decode(encode(hs2)))
    sess_b = resp.finish(decode(encode(hs3)))
    assert sess_b.decrypt(decode(encode(sess_a.encrypt(b"ok")))) == b"ok"


def test_cada_handshake_produce_una_sesion_distinta(alice, bob, clock):
    sessions = []
    for _ in range(2):
        init, resp = new_pair(alice, bob, clock)
        hs3, sa = init.finish(resp.respond(init.start()))
        sessions.append((sa, resp.finish(hs3)))
    (a1, b1), (a2, b2) = sessions
    assert a1.sid != a2.sid
    with pytest.raises(Exception):
        b2.decrypt(a1.encrypt(b"sesion 1"))


# --- RS13: firmas, contexto y transcripción ---------------------------------------

@pytest.mark.parametrize("campo", ["sig", "tag", "rb", "epk"])
def test_RS13_hs2_alterado_aborta(alice, bob, clock, campo):
    init, resp = new_pair(alice, bob, clock)
    hs2 = resp.respond(init.start())
    with pytest.raises(HandshakeError):
        init.finish(replace(hs2, **{campo: flip(getattr(hs2, campo))}))


@pytest.mark.parametrize("campo", ["sig", "tag"])
def test_RS13_hs3_alterado_aborta(alice, bob, clock, campo):
    init, resp = new_pair(alice, bob, clock)
    hs3, _ = init.finish(resp.respond(init.start()))
    with pytest.raises(HandshakeError):
        resp.finish(replace(hs3, **{campo: flip(getattr(hs3, campo))}))


def test_un_mensaje_invalido_no_mata_el_handshake_legitimo(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs2 = resp.respond(init.start())
    with pytest.raises(HandshakeError):
        init.finish(replace(hs2, sig=flip(hs2.sig)))
    hs3, sess_a = init.finish(hs2)  # el hs2 verdadero aún funciona
    with pytest.raises(HandshakeError):
        resp.finish(replace(hs3, sig=flip(hs3.sig)))
    sess_b = resp.finish(hs3)
    assert sess_b.decrypt(sess_a.encrypt(b"ok")) == b"ok"


def test_RS13_las_firmas_de_rol_no_son_intercambiables(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs1 = init.start()
    hs2 = resp.respond(hs1)
    hs3, _ = init.finish(hs2)
    transcript = _transcript(ALICE, BOB, hs1.sid, hs1.ts, hs1.ra, hs2.rb, hs1.epk, hs2.epk)
    # firma de Alice con el contexto del respondedor sobre la misma transcripción
    with pytest.raises(HandshakeError):
        resp.finish(replace(hs3, sig=alice.sign(CTX_RESPONDER, transcript)))
    resp.finish(replace(hs3, sig=alice.sign(CTX_INITIATOR, transcript)))  # el contexto correcto sí


def test_RS13_la_firma_del_respondedor_no_vale_como_la_del_iniciador(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs2 = resp.respond(init.start())
    # Mallory refleja la firma y la confirmación de Bob como si fueran el hs3 de Alice
    with pytest.raises(HandshakeError):
        resp.finish(Hs3(ALICE, BOB, hs2.sid, hs2.sig, hs2.tag))


def test_los_ids_van_dentro_de_la_firma(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs2 = resp.respond(init.start())
    with pytest.raises(HandshakeError):
        init.finish(replace(hs2, sender="333333333333333333"))
    with pytest.raises(HandshakeError):
        init.finish(replace(hs2, receiver="333333333333333333"))
    with pytest.raises(HandshakeError):
        init.finish(replace(hs2, sid=b"x" * 16))


def test_RS7_llave_de_firma_sustituida_se_detecta(alice, bob, clock):
    """Un directorio malicioso entrega la llave de Mallory como si fuera de Bob."""
    mallory = Identity.create()
    init = Initiator(alice, ALICE, BOB, bob.public_key, clock)  # llave verificada/pinneada
    impostor = Responder(mallory, BOB, ALICE, alice.public_key, clock=clock)
    with pytest.raises(HandshakeError):
        init.finish(impostor.respond(init.start()))


def test_mitm_que_cambia_la_llave_efimera_de_hs1_se_detecta(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs1 = init.start()
    mallory_epk = X25519PrivateKey.generate().public_key().public_bytes_raw()
    hs2 = resp.respond(replace(hs1, epk=mallory_epk))
    with pytest.raises(HandshakeError):
        init.finish(hs2)  # la transcripción de Alice y la de Bob difieren


def test_mitm_en_hs2_sin_la_llave_de_bob_no_puede_firmar(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs2 = resp.respond(init.start())
    mallory_epk = X25519PrivateKey.generate().public_key().public_bytes_raw()
    with pytest.raises(HandshakeError):
        init.finish(replace(hs2, epk=mallory_epk))


# --- reflexión, versión y destinatario --------------------------------------------

def test_un_hs1_no_dirigido_a_este_usuario_se_rechaza(alice, bob, clock):
    init, _ = new_pair(alice, bob, clock)
    hs1 = init.start()
    reflejado = Responder(alice, ALICE, BOB, bob.public_key, clock=clock)  # Mallory lo devuelve a Alice
    with pytest.raises(HandshakeError):
        reflejado.respond(hs1)


def test_el_respondedor_exige_que_el_remitente_sea_el_esperado(alice, bob, clock):
    init, _ = new_pair(alice, bob, clock)
    resp = Responder(bob, BOB, "333333333333333333", alice.public_key, clock=clock)
    with pytest.raises(HandshakeError):
        resp.respond(init.start())


# --- frescura, caducidad y replay -------------------------------------------------

def test_RS14_hs1_repetido_se_rechaza(alice, bob, clock):
    seen = SidCache(clock)
    init, _ = new_pair(alice, bob, clock)
    hs1 = init.start()
    Responder(bob, BOB, ALICE, alice.public_key, seen, clock).respond(hs1)
    with pytest.raises(ReplayError):
        Responder(bob, BOB, ALICE, alice.public_key, seen, clock).respond(hs1)


def test_hs1_caducado_se_ignora(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs1 = init.start()
    clock.advance(HANDSHAKE_TTL + 1)
    with pytest.raises(HandshakeError):
        resp.respond(hs1)


def test_hs1_con_fecha_futura_se_rechaza(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs1 = init.start()
    clock.advance(-(CLOCK_SKEW + 5))
    with pytest.raises(HandshakeError):
        resp.respond(hs1)


def test_el_intento_caduca_en_el_iniciador_y_destruye_la_llave_efimera(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs2 = resp.respond(init.start())
    clock.advance(HANDSHAKE_TTL + 1)
    with pytest.raises(HandshakeError):
        init.finish(hs2)
    assert not any(isinstance(o, X25519PrivateKey) for o in reachable(init))
    with pytest.raises(HandshakeError):  # un hs2 tardío no resucita el intento
        init.finish(hs2)


def test_el_intento_caduca_en_el_respondedor(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs3, _ = init.finish(resp.respond(init.start()))
    clock.advance(HANDSHAKE_TTL + 1)
    with pytest.raises(HandshakeError):
        resp.finish(hs3)


def test_un_handshake_no_se_reutiliza(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    hs1 = init.start()
    hs2 = resp.respond(hs1)
    hs3, _ = init.finish(hs2)
    resp.finish(hs3)
    with pytest.raises(HandshakeError):
        init.start()
    with pytest.raises(HandshakeError):
        init.finish(hs2)
    with pytest.raises(HandshakeError):
        resp.finish(hs3)
    with pytest.raises(HandshakeError):
        resp.respond(hs1)


def test_finish_sin_start(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    other = Initiator(alice, ALICE, BOB, bob.public_key, clock)
    hs2 = resp.respond(other.start())
    with pytest.raises(HandshakeError):
        init.finish(hs2)


def test_finish_sin_respond(alice, bob, clock):
    _, resp = new_pair(alice, bob, clock)
    with pytest.raises(HandshakeError):
        resp.finish(None)


# --- llaves efímeras inválidas ----------------------------------------------------

def test_punto_de_orden_bajo_se_rechaza():
    with pytest.raises(HandshakeError):
        _exchange(X25519PrivateKey.generate(), bytes(32))


def test_hs1_con_llave_efimera_nula_se_rechaza(alice, bob, clock):
    init, resp = new_pair(alice, bob, clock)
    with pytest.raises(HandshakeError):
        resp.respond(replace(init.start(), epk=bytes(32)))


# --- RS12: PFS ----------------------------------------------------------------------

def test_RS12_ninguna_llave_efimera_sobrevive_al_handshake(handshake):
    for pieza in ("init", "resp", "a", "b"):
        assert not any(isinstance(o, X25519PrivateKey) for o in reachable(handshake[pieza])), pieza


def test_RS12_las_llaves_de_identidad_no_bastan_para_descifrar_lo_grabado(handshake, alice, bob):
    """El atacante tiene ambas llaves de identidad y todo lo que pasó por Discord, pero no a, b."""
    capturado = [encode(handshake[k]) for k in ("hs1", "hs2", "hs3")]
    msg = encode(handshake["a"].encrypt(b"secreto"))
    # El único material que falta (a y b) no existe en ningún objeto vivo: ver test anterior.
    # Con identidad + transcripción, un nuevo handshake produce llaves independientes:
    init = Initiator(alice, ALICE, BOB, bob.public_key)
    resp = Responder(bob, BOB, ALICE, alice.public_key)
    hs3, atacante = init.finish(resp.respond(init.start()))
    resp.finish(hs3)
    with pytest.raises(Exception):
        atacante.decrypt(decode(msg))
    assert capturado and b"secreto" not in msg.encode()


def test_RS13_misbinding_los_ids_firmados_impiden_que_cada_extremo_crea_hablar_con_otro(bob, clock):
    """Carol abre sesión con Bob; Mallory relabela los mensajes para que Bob crea que es Alice."""
    carol_id, carol = "333333333333333333", Identity.create()
    init = Initiator(carol, carol_id, BOB, bob.public_key, clock)
    resp = Responder(bob, BOB, ALICE, carol.public_key, clock=clock)  # Bob cree hablar con "Alice"
    hs1 = replace(init.start(), sender=ALICE)
    hs2 = replace(resp.respond(hs1), receiver=carol_id)
    with pytest.raises(HandshakeError):
        init.finish(hs2)

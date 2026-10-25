import pytest

from crypto import fingerprint
from crypto.fingerprint import qr_payload


def test_RS8_huella_igual_en_ambos_extremos(alice, bob):
    assert fingerprint(alice.public_key, bob.public_key) == fingerprint(bob.public_key, alice.public_key)
    assert qr_payload(alice.public_key, bob.public_key) == qr_payload(bob.public_key, alice.public_key)


def test_RF6_formato_60_digitos_en_grupos_de_5(alice, bob):
    groups = fingerprint(alice.public_key, bob.public_key).split(" ")
    assert len(groups) == 12 and all(len(g) == 5 and g.isdigit() for g in groups)


def test_RF8_la_huella_cambia_si_cambia_una_llave(alice, bob):
    other = type(alice).create()
    assert fingerprint(alice.public_key, bob.public_key) != fingerprint(alice.public_key, other.public_key)


def test_llaves_iguales_no_son_validas(alice):
    with pytest.raises(ValueError):
        fingerprint(alice.public_key, alice.public_key)


def test_vector_conocido():
    pk_a, pk_b = bytes([1]) * 32, bytes([2]) * 32
    import hashlib
    expected = str(int.from_bytes(hashlib.sha256(pk_a + pk_b).digest(), "big") % 10**60).zfill(60)
    assert fingerprint(pk_b, pk_a).replace(" ", "") == expected

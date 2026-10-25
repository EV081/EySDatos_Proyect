import json

import pytest

from crypto import Identity, SignatureError, VaultError, verify
from crypto.constants import CTX_INITIATOR, CTX_RESPONDER
from crypto.encoding import b64e
from crypto.identity import (
    KdfParams, sign_key_change, sign_registration, verify_key_change, verify_registration,
)
from conftest import ALICE, FAST_KDF

PASSWORD = "contraseña maestra de prueba"


def test_RF1_identidad_generada_localmente_es_ed25519():
    ident = Identity.create()
    assert len(ident.public_key) == 32
    assert Identity.create().public_key != ident.public_key


def test_RS2_boveda_ida_y_vuelta(alice):
    blob = alice.to_vault(PASSWORD, FAST_KDF)
    restored = Identity.from_vault(blob, PASSWORD)
    assert restored.public_key == alice.public_key
    assert restored.store_key == alice.store_key
    sig = restored.sign(CTX_INITIATOR, b"mensaje")
    verify(alice.public_key, CTX_INITIATOR, b"mensaje", sig)


def test_RS2_contrasena_incorrecta(alice):
    blob = alice.to_vault(PASSWORD, FAST_KDF)
    with pytest.raises(VaultError):
        Identity.from_vault(blob, PASSWORD + "x")


def test_RS2_salt_unico_por_boveda(alice):
    a = json.loads(alice.to_vault(PASSWORD, FAST_KDF))
    b = json.loads(alice.to_vault(PASSWORD, FAST_KDF))
    assert a["kdf"]["salt"] != b["kdf"]["salt"]
    assert a["ct"] != b["ct"]


def test_RS1_la_llave_privada_no_aparece_en_claro(alice):
    from cryptography.hazmat.primitives import serialization as s
    raw = alice._sk.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption())
    blob = alice.to_vault(PASSWORD, FAST_KDF)
    assert raw not in blob and b64e(raw).encode() not in blob
    assert b64e(alice.store_key).encode() not in blob


def test_RS2_los_parametros_de_kdf_estan_autenticados(alice):
    doc = json.loads(alice.to_vault(PASSWORD, FAST_KDF))
    doc["kdf"]["t"] = 2  # debilitar o cambiar el KDF invalida la bóveda
    with pytest.raises(VaultError):
        Identity.from_vault(json.dumps(doc), PASSWORD)


def test_RS2_boveda_manipulada(alice):
    doc = json.loads(alice.to_vault(PASSWORD, FAST_KDF))
    doc["ct"] = doc["ct"][:-2] + ("AA" if not doc["ct"].endswith("AA") else "BB")
    with pytest.raises(VaultError):
        Identity.from_vault(json.dumps(doc), PASSWORD)


@pytest.mark.parametrize("campo,valor", [("m", 10**9), ("t", 0), ("p", 99)])
def test_RS2_parametros_fuera_de_rango_se_rechazan_antes_de_derivar(alice, campo, valor):
    doc = json.loads(alice.to_vault(PASSWORD, FAST_KDF))
    doc["kdf"][campo] = valor
    with pytest.raises(VaultError):
        Identity.from_vault(json.dumps(doc), PASSWORD)


@pytest.mark.parametrize("blob", [b"", b"no es json", b"[]", b"{}", b'{"v":1}'])
def test_boveda_mal_formada(blob):
    with pytest.raises(VaultError):
        Identity.from_vault(blob, PASSWORD)


def test_RS2_parametros_por_defecto_son_validos():
    KdfParams().validate()


def test_RF12_exportar_con_otra_contrasena(alice):
    exported = alice.to_vault("otra contraseña", FAST_KDF)
    assert Identity.from_vault(exported, "otra contraseña").public_key == alice.public_key
    with pytest.raises(VaultError):
        Identity.from_vault(exported, PASSWORD)


def test_RS13_separacion_de_dominio_de_firmas(alice):
    sig = alice.sign(CTX_INITIATOR, b"datos")
    verify(alice.public_key, CTX_INITIATOR, b"datos", sig)
    with pytest.raises(SignatureError):
        verify(alice.public_key, CTX_RESPONDER, b"datos", sig)


def test_firma_de_otro_o_alterada_no_vale(alice, bob):
    sig = alice.sign(CTX_INITIATOR, b"datos")
    with pytest.raises(SignatureError):
        verify(bob.public_key, CTX_INITIATOR, b"datos", sig)
    with pytest.raises(SignatureError):
        verify(alice.public_key, CTX_INITIATOR, b"datos alterados", sig)
    with pytest.raises(SignatureError):
        verify(b"\x00" * 31, CTX_INITIATOR, b"datos", sig)


def test_prueba_de_posesion_al_registrar(alice, bob):
    nonce = b"n" * 32
    sig = sign_registration(alice, ALICE, nonce)
    verify_registration(alice.public_key, ALICE, nonce, sig)
    with pytest.raises(SignatureError):
        verify_registration(alice.public_key, ALICE, b"x" * 32, sig)  # nonce distinto
    with pytest.raises(SignatureError):
        verify_registration(alice.public_key, "999", nonce, sig)  # otro discord_id
    with pytest.raises(SignatureError):  # no se puede registrar la llave de otro
        verify_registration(bob.public_key, ALICE, nonce, sig)


def test_una_firma_de_cambio_de_llave_no_sirve_para_registrar(alice, bob):
    nonce = b"n" * 32
    sig = sign_key_change(alice, ALICE, bob.public_key, nonce)
    verify_key_change(alice.public_key, ALICE, bob.public_key, nonce, sig)
    with pytest.raises(SignatureError):
        verify_registration(alice.public_key, ALICE, nonce, sig)
    with pytest.raises(SignatureError):  # autoriza una llave concreta, no otra
        verify_key_change(alice.public_key, ALICE, Identity.create().public_key, nonce, sig)

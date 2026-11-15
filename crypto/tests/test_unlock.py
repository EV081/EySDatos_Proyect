import os

import pytest

from crypto import Identity, SignatureError, sign_key_change, sign_registration, sign_unlock, verify_unlock


def test_firma_de_desbloqueo_ligada_a_id_llave_y_nonce():
    identity = Identity.create()
    nonce = os.urandom(32)
    signature = sign_unlock(identity, "111111111111111111", nonce)
    verify_unlock(identity.public_key, "111111111111111111", nonce, signature)
    for key, owner, challenge in (
        (identity.public_key, "222222222222222222", nonce),
        (Identity.create().public_key, "111111111111111111", nonce),
        (identity.public_key, "111111111111111111", os.urandom(32)),
    ):
        with pytest.raises(SignatureError):
            verify_unlock(key, owner, challenge, signature)


def test_firmas_de_registro_y_cambio_no_autorizan_desbloquear():
    identity = Identity.create()
    nonce = os.urandom(32)
    for signature in (
        sign_registration(identity, "111111111111111111", nonce),
        sign_key_change(identity, "111111111111111111", identity.public_key, nonce),
    ):
        with pytest.raises(SignatureError):
            verify_unlock(identity.public_key, "111111111111111111", nonce, signature)

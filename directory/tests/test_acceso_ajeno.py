"""Pruebas de acceso ajeno por endpoint: con su propia sesión OAuth2, Mallory no puede tocar el registro de
Alice (C-06, C-08). Además, entradas maliciosas y límites de solicitudes."""
import logging

from crypto import Identity, sign_key_change
from directory.app.main import CANCEL_MARKER
from directory.app.schemas import b64d, b64e

from conftest import ALICE, MALLORY, challenge, login, publish


def test_C06_token_de_otro_id_no_puede_publicar(api, repo):
    alice = Identity.create()
    publish(api, login(api, ALICE), ALICE, alice)
    mallory_token = login(api, MALLORY)
    assert challenge(api, mallory_token, ALICE).status_code == 401
    # aunque consiga un nonce para sí, no puede usarlo sobre el ID de Alice
    nonce = b64d(challenge(api, mallory_token, MALLORY).json()["nonce"], 32)
    mallory = Identity.create()
    assert publish(api, mallory_token, ALICE, mallory, nonce=nonce).status_code == 401
    assert repo.get_key(ALICE) == alice.public_key


def test_C06_token_de_otro_id_no_puede_cancelar(api, repo):
    alice = Identity.create()
    publish(api, login(api, ALICE), ALICE, alice)
    mallory_token = login(api, MALLORY)
    nonce = b64d(challenge(api, mallory_token, MALLORY, "cancel").json()["nonce"], 32)
    body = {"nonce": b64e(nonce), "signature": b64e(sign_key_change(alice, ALICE, CANCEL_MARKER, nonce))}
    resp = api.request("DELETE", f"/v1/keys/{ALICE}", json=body,
                       headers={"Authorization": f"Bearer {mallory_token}"})
    assert resp.status_code == 401
    assert repo.get_key(ALICE) == alice.public_key


def test_acceso_ajeno_queda_en_auditoria_seudonimizado(api, caplog):
    mallory_token = login(api, MALLORY)
    with caplog.at_level(logging.INFO, logger="directory.audit"):
        challenge(api, mallory_token, ALICE)
    assert "acceso_ajeno" in caplog.text
    assert ALICE not in caplog.text and MALLORY not in caplog.text


def test_errores_son_genericos(api):
    """Firma mala, token ajeno y token inventado responden exactamente igual."""
    publish(api, login(api, ALICE), ALICE, Identity.create())
    bad_sig = publish(api, login(api, ALICE), ALICE, Identity.create(), signer=Identity.create())
    foreign = challenge(api, login(api, MALLORY), ALICE)
    invented = challenge(api, b64e(b"\x02" * 32), ALICE)
    assert {r.status_code for r in (bad_sig, foreign, invented)} == {401}
    assert bad_sig.json() == foreign.json() == invented.json() == {"error": "solicitud rechazada"}


def test_C08_inyeccion_en_discord_id(api, repo):
    publish(api, login(api, ALICE), ALICE, Identity.create())
    for evil in ("1' OR '1'='1", "111111111111111111;DROP TABLE keys", "%27%20OR%201=1--"):
        resp = api.get(f"/v1/keys/{evil}")
        assert resp.status_code in (400, 404)
    assert repo.get_key(ALICE) is not None


def test_C08_entradas_malformadas_responden_400(api):
    token = login(api, ALICE)
    headers = {"Authorization": f"Bearer {token}"}
    assert api.post("/v1/challenge", json={"discord_id": "12", "purpose": "register"},
                    headers=headers).status_code == 400
    assert api.post("/v1/challenge", json={"discord_id": ALICE, "purpose": "admin"},
                    headers=headers).status_code == 400
    body = {"public_key": "no*es*base64", "nonce": "x", "signature": "y", "consent_version": "1.0"}
    assert api.put(f"/v1/keys/{ALICE}", json=body, headers=headers).status_code == 400
    body = {"public_key": b64e(b"\x01" * 31), "nonce": b64e(b"\x01" * 32), "signature": b64e(b"\x01" * 64),
            "consent_version": "1.0"}
    assert api.put(f"/v1/keys/{ALICE}", json=body, headers=headers).status_code == 400


def test_rate_limit_responde_429(make_api):
    api = make_api(lookup_limit=3)
    codes = [api.get(f"/v1/keys/{ALICE}").status_code for _ in range(5)]
    assert codes == [404, 404, 404, 429, 429]
    assert api.get(f"/v1/keys/{ALICE}").json() == {"error": "demasiadas solicitudes"}

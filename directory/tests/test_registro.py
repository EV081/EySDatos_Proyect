from crypto import Identity, sign_key_change
from directory.app.main import CANCEL_MARKER
from directory.app.schemas import b64d, b64e

from conftest import ALICE, BOB, CONSENT, challenge, login, publish


def test_RF2_registrar_y_consultar_llave(api):
    alice = Identity.create()
    assert publish(api, login(api, ALICE), ALICE, alice).status_code == 204
    resp = api.get(f"/v1/keys/{ALICE}")
    assert resp.status_code == 200
    assert b64d(resp.json()["public_key"], 32) == alice.public_key
    assert resp.headers["cache-control"] == "no-store"


def test_RF2_id_no_registrado_responde_404(api):
    resp = api.get(f"/v1/keys/{BOB}")
    assert resp.status_code == 404
    assert resp.json() == {"error": "no encontrado"}


def test_C14_guarda_version_y_fecha_del_aviso(api, repo):
    publish(api, login(api, ALICE), ALICE, Identity.create())
    record = repo.get_record(ALICE)
    assert record["consent_version"] == CONSENT
    assert record["consent_at"] is not None and record["registered_at"] is not None
    assert record["key_changed_at"] is None


def test_C06_firma_de_otra_llave_se_rechaza(api):
    """Prueba de posesión: no se puede publicar una llave cuya privada no se tiene."""
    alice, mallory = Identity.create(), Identity.create()
    resp = publish(api, login(api, ALICE), ALICE, alice, signer=mallory)
    assert resp.status_code == 401
    assert api.get(f"/v1/keys/{ALICE}").status_code == 404


def test_C06_nonce_no_se_puede_reutilizar(api):
    alice = Identity.create()
    token = login(api, ALICE)
    nonce = b64d(challenge(api, token, ALICE).json()["nonce"], 32)
    assert publish(api, token, ALICE, alice, signer=Identity.create(), nonce=nonce).status_code == 401
    # aunque la firma ahora sea correcta, el nonce ya se consumió
    assert publish(api, token, ALICE, alice, nonce=nonce).status_code == 401


def test_C06_nonce_inventado_se_rechaza(api):
    assert publish(api, login(api, ALICE), ALICE, Identity.create(), nonce=b"\x07" * 32).status_code == 401


def test_C06_token_de_un_solo_uso(api):
    token = login(api, ALICE)
    assert publish(api, token, ALICE, Identity.create()).status_code == 204
    assert challenge(api, token, ALICE).status_code == 401


def test_C06_sin_token_o_token_inventado_se_rechaza(api):
    assert api.post("/v1/challenge", json={"discord_id": ALICE, "purpose": "register"}).status_code == 401
    fake = {"Authorization": "Bearer " + b64e(b"\x01" * 32)}
    assert api.post("/v1/challenge", json={"discord_id": ALICE, "purpose": "register"},
                    headers=fake).status_code == 401


def test_misma_llave_de_nuevo_es_idempotente(api, repo):
    """Reimportar la identidad en otro dispositivo vuelve a publicar la misma llave."""
    alice = Identity.create()
    publish(api, login(api, ALICE), ALICE, alice)
    assert publish(api, login(api, ALICE), ALICE, alice).status_code == 204
    assert repo.get_record(ALICE)["key_changed_at"] is None


def test_cambio_de_llave_con_oauth_guarda_la_anterior(api, repo, admin_db):
    old, new = Identity.create(), Identity.create()
    publish(api, login(api, ALICE), ALICE, old)
    assert publish(api, login(api, ALICE), ALICE, new).status_code == 204
    assert repo.get_key(ALICE) == new.public_key
    assert repo.get_record(ALICE)["key_changed_at"] is not None
    rows = admin_db.execute("SELECT public_key FROM directory.replaced_keys WHERE discord_id = %s",
                            (ALICE,)).fetchall()
    assert [bytes(r[0]) for r in rows] == [old.public_key]


def test_cambio_de_llave_firmado_por_la_anterior(api, repo):
    old, new = Identity.create(), Identity.create()
    publish(api, login(api, ALICE), ALICE, old)
    token = login(api, ALICE)
    nonce = b64d(challenge(api, token, ALICE).json()["nonce"], 32)
    bad = b64e(sign_key_change(Identity.create(), ALICE, new.public_key, nonce))
    assert publish(api, token, ALICE, new, nonce=nonce, old_signature=bad).status_code == 401
    assert repo.get_key(ALICE) == old.public_key
    nonce = b64d(challenge(api, token, ALICE).json()["nonce"], 32)
    good = b64e(sign_key_change(old, ALICE, new.public_key, nonce))
    assert publish(api, token, ALICE, new, nonce=nonce, old_signature=good).status_code == 204
    assert repo.get_key(ALICE) == new.public_key


def _cancel(api, token, discord_id, signer):
    nonce = b64d(challenge(api, token, discord_id, "cancel").json()["nonce"], 32)
    body = {"nonce": b64e(nonce), "signature": b64e(sign_key_change(signer, discord_id, CANCEL_MARKER, nonce))}
    return api.request("DELETE", f"/v1/keys/{discord_id}", json=body,
                       headers={"Authorization": f"Bearer {token}"})


def test_C11_cancelacion_borra_el_registro(api, repo, admin_db):
    old, new = Identity.create(), Identity.create()
    publish(api, login(api, ALICE), ALICE, old)
    publish(api, login(api, ALICE), ALICE, new)
    assert _cancel(api, login(api, ALICE), ALICE, new).status_code == 204
    assert api.get(f"/v1/keys/{ALICE}").status_code == 404
    assert admin_db.execute("SELECT count(*) FROM directory.replaced_keys").fetchone()[0] == 0


def test_C11_cancelacion_exige_la_llave_vigente(api, repo):
    alice = Identity.create()
    publish(api, login(api, ALICE), ALICE, alice)
    assert _cancel(api, login(api, ALICE), ALICE, Identity.create()).status_code == 401
    assert repo.get_key(ALICE) == alice.public_key


def test_C11_firma_de_registro_no_sirve_para_cancelar(api, repo):
    """El nonce lleva propósito: uno de registro no vale para cancelar."""
    alice = Identity.create()
    publish(api, login(api, ALICE), ALICE, alice)
    token = login(api, ALICE)
    nonce = b64d(challenge(api, token, ALICE, "register").json()["nonce"], 32)
    body = {"nonce": b64e(nonce), "signature": b64e(sign_key_change(alice, ALICE, CANCEL_MARKER, nonce))}
    resp = api.request("DELETE", f"/v1/keys/{ALICE}", json=body, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert repo.get_key(ALICE) == alice.public_key


def test_no_se_puede_registrar_la_llave_nula(api):
    token = login(api, ALICE)
    nonce = b64d(challenge(api, token, ALICE).json()["nonce"], 32)
    body = {"public_key": b64e(CANCEL_MARKER), "nonce": b64e(nonce), "signature": b64e(b"\x00" * 64),
            "consent_version": CONSENT}
    resp = api.put(f"/v1/keys/{ALICE}", json=body, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_C10_purga_llaves_reemplazadas_de_mas_de_90_dias(api, repo, admin_db):
    publish(api, login(api, ALICE), ALICE, Identity.create())
    publish(api, login(api, ALICE), ALICE, Identity.create())
    admin_db.execute("UPDATE directory.replaced_keys SET replaced_at = now() - interval '91 days'")
    counts = repo.purge()
    assert counts["replaced_keys"] == 1
    assert counts["auth_tokens"] == 2  # los dos tokens ya usados

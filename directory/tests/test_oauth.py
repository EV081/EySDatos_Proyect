from urllib.parse import parse_qs, urlsplit

from conftest import ALICE, login


def _state(api):
    location = api.get("/auth/login").headers["location"]
    return location, parse_qs(urlsplit(location).query)


def test_login_redirige_a_discord_con_identify_y_pkce(api):
    location, query = _state(api)
    assert location.startswith("https://discord.com/oauth2/authorize?")
    assert query["scope"] == ["identify"]
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["state"][0]) >= 32


def test_callback_emite_token_y_revoca_el_de_discord(api, discord):
    token = login(api, ALICE)
    assert len(token) == 43  # 32 bytes en base64url
    assert discord.revoked == [f"at-{ALICE}"]


def test_state_es_de_un_solo_uso(api):
    _, query = _state(api)
    state = query["state"][0]
    assert api.get("/auth/callback", params={"code": f"code-{ALICE}", "state": state}).status_code == 200
    assert api.get("/auth/callback", params={"code": f"code-{ALICE}", "state": state}).status_code == 400


def test_state_inventado_se_rechaza(api):
    resp = api.get("/auth/callback", params={"code": f"code-{ALICE}", "state": "inventado"})
    assert resp.status_code == 400
    assert "<pre" not in resp.text


def test_discord_caido_no_emite_token(api, discord):
    _, query = _state(api)
    discord.fail = True
    resp = api.get("/auth/callback", params={"code": f"code-{ALICE}", "state": query["state"][0]})
    assert resp.status_code == 400
    assert "<pre" not in resp.text


def test_pagina_del_token_no_se_guarda_en_cache(api):
    _, query = _state(api)
    resp = api.get("/auth/callback", params={"code": f"code-{ALICE}", "state": query["state"][0]})
    assert resp.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in resp.headers["content-security-policy"]

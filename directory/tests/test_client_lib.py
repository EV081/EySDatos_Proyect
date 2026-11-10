"""`DirectoryClient` contra el directorio real (en proceso): debe comportarse como `client.fakes.FakeDirectory`."""
import pytest

from crypto import Identity, sign_key_change, sign_registration
from directory.client_lib import DirectoryClient, DirectoryError

from conftest import ALICE, BOB, MALLORY, login


@pytest.fixture
def lib(api):
    def build(token=None):
        return DirectoryClient("http://testserver", auth_token=token, transport=api._transport)
    return build


def test_RF2_register_y_get_key(api, lib, repo):
    alice = Identity.create()
    lib(login(api, ALICE)).register(ALICE, alice.public_key, lambda n: sign_registration(alice, ALICE, n), "1.0")
    assert lib().get_key(ALICE) == alice.public_key
    assert repo.get_record(ALICE)["consent_version"] == "1.0"


def test_get_key_de_no_registrado_devuelve_none(lib):
    assert lib().get_key(BOB) is None


def test_prueba_de_posesion_invalida_lanza_directory_error(api, lib):
    alice, other = Identity.create(), Identity.create()
    with pytest.raises(DirectoryError):
        lib(login(api, ALICE)).register(ALICE, alice.public_key, lambda n: sign_registration(other, ALICE, n),
                                        "1.0")


def test_sin_token_lanza_directory_error(lib, monkeypatch):
    monkeypatch.delenv("DIRECTORY_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("DIRECTORY_AUTH_TOKEN_FILE", raising=False)
    alice = Identity.create()
    with pytest.raises(DirectoryError):
        lib().register(ALICE, alice.public_key, lambda n: sign_registration(alice, ALICE, n), "1.0")


def test_token_desde_archivo(api, lib, monkeypatch, tmp_path):
    path = tmp_path / "token"
    path.write_text(login(api, ALICE) + "\n")
    monkeypatch.delenv("DIRECTORY_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("DIRECTORY_AUTH_TOKEN_FILE", str(path))
    alice = Identity.create()
    lib().register(ALICE, alice.public_key, lambda n: sign_registration(alice, ALICE, n), "1.0")
    assert lib().get_key(ALICE) == alice.public_key


def test_token_ajeno_lanza_directory_error(api, lib):
    mallory = Identity.create()
    with pytest.raises(DirectoryError):
        lib(login(api, MALLORY)).register(ALICE, mallory.public_key,
                                          lambda n: sign_registration(mallory, ALICE, n), "1.0")


def test_C11_cancel(api, lib):
    alice = Identity.create()
    lib(login(api, ALICE)).register(ALICE, alice.public_key, lambda n: sign_registration(alice, ALICE, n), "1.0")
    lib(login(api, ALICE)).cancel(ALICE, lambda pk, n: sign_key_change(alice, ALICE, pk, n))
    assert lib().get_key(ALICE) is None


def test_directorio_caido_lanza_directory_error():
    lib = DirectoryClient("http://127.0.0.1:9")  # puerto cerrado
    with pytest.raises(DirectoryError):
        lib.get_key(ALICE)


def test_solo_https_salvo_en_localhost():
    with pytest.raises(ValueError):
        DirectoryClient("http://directorio.example.com")
    with pytest.raises(ValueError):
        DirectoryClient("https://directorio.example.com")  # sin la CA del proyecto


def test_login_rechaza_un_token_pegado_varias_veces():
    from directory.client_lib.login import clean_token
    token = "A" * 43
    assert clean_token(f"  {token}\n") == token
    for bad in (token * 3, token[:-1], "hola", token + "!"):
        with pytest.raises(SystemExit):
            clean_token(bad)


def test_ca_publica_solo_si_se_pide_a_proposito():
    DirectoryClient("https://directorio.onrender.com", public_ca=True).close()
    with pytest.raises(ValueError):
        DirectoryClient("https://directorio.onrender.com", public_ca=False)
    with pytest.raises(ValueError):
        DirectoryClient("http://directorio.onrender.com", public_ca=True)  # http nunca

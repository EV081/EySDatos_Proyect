import base64
import hashlib

import pytest

from crypto.pseudonym import MIN_KEY_LEN, PSEUDONYM_LEN, Pseudonymizer, generate_key, mask_id

ID = "123456789012345678"


def test_C09_el_seudonimo_es_estable_con_la_misma_clave():
    p = Pseudonymizer(generate_key())
    assert p.pseudonym(ID) == p.pseudonym(ID)
    assert len(p.pseudonym(ID)) == PSEUDONYM_LEN and int(p.pseudonym(ID), 16) >= 0


def test_C09_una_clave_distinta_da_otro_seudonimo():
    assert Pseudonymizer(generate_key()).pseudonym(ID) != Pseudonymizer(generate_key()).pseudonym(ID)


def test_C09_ids_distintos_dan_seudonimos_distintos():
    p = Pseudonymizer(generate_key())
    assert p.pseudonym("1") != p.pseudonym("2")
    assert len({p.pseudonym(str(10**17 + i)) for i in range(20_000)}) == 20_000


def test_C09_no_es_un_hash_sin_clave_que_se_pueda_invertir_probando_candidatos():
    """El atacante conoce el rango de IDs y recorre todos los candidatos con SHA-256: no debe encontrar el seudónimo."""
    p = Pseudonymizer(generate_key())
    objetivo = p.pseudonym("100000000000000500")
    tabla = {hashlib.sha256(str(10**17 + i).encode()).hexdigest()[:PSEUDONYM_LEN] for i in range(1000)}
    assert objetivo not in tabla
    assert p.pseudonym(ID) != hashlib.sha256(ID.encode()).hexdigest()[:PSEUDONYM_LEN]


def test_C09_la_clave_debe_ser_fuerte():
    with pytest.raises(ValueError):
        Pseudonymizer(b"corta")
    Pseudonymizer(b"k" * MIN_KEY_LEN)


def test_C09_la_clave_se_lee_del_entorno(monkeypatch):
    key = generate_key()
    monkeypatch.setenv("PSEUDONYM_KEY", base64.urlsafe_b64encode(key).decode().rstrip("="))
    assert Pseudonymizer.from_env().pseudonym(ID) == Pseudonymizer(key).pseudonym(ID)


@pytest.mark.parametrize("valor", [None, "", "no es base64!!", base64.urlsafe_b64encode(b"corta").decode()])
def test_C09_sin_clave_valida_en_el_entorno_no_arranca(monkeypatch, valor):
    monkeypatch.delenv("PSEUDONYM_KEY", raising=False)
    if valor is not None:
        monkeypatch.setenv("PSEUDONYM_KEY", valor)
    with pytest.raises(ValueError):
        Pseudonymizer.from_env()


def test_el_identificador_debe_ser_texto():
    with pytest.raises(TypeError):
        Pseudonymizer(generate_key()).pseudonym(123)
    with pytest.raises(TypeError):
        mask_id(123)


def test_el_enmascarado_deja_solo_el_inicio_y_el_final():
    assert mask_id(ID) == "1234…5678"
    assert mask_id(ID, visible=2) == "12…78"
    assert "5678901234" not in mask_id(ID)


@pytest.mark.parametrize("corto", ["", "1", "1234", "12345678"])
def test_el_enmascarado_de_ids_cortos_no_revela_nada(corto):
    assert mask_id(corto) == "*" * len(corto)

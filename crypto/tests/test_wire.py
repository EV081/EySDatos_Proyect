import base64
import json
from dataclasses import replace

import pytest

from crypto import Hs1, Hs2, Hs3, Msg, WireError, decode, encode
from crypto.constants import MAX_PLAINTEXT, MAX_WIRE_LEN, WIRE_PREFIX
from crypto.encoding import b64d, b64e

ID_A, ID_B = "123456789012345678", "987654321098765432"
HS1 = Hs1(ID_A, ID_B, b"s" * 16, b"r" * 32, b"e" * 32, 1_800_000_000)
HS2 = Hs2(ID_B, ID_A, b"s" * 16, b"r" * 32, b"e" * 32, b"g" * 64, b"t" * 32)
HS3 = Hs3(ID_A, ID_B, b"s" * 16, b"g" * 64, b"t" * 32)
MSG = Msg(ID_A, ID_B, b"s" * 16, 7, b"n" * 12, b"c" * 40)


def _raw(doc: dict) -> str:
    return WIRE_PREFIX + b64e(json.dumps(doc, separators=(",", ":")).encode())


def _doc(obj) -> dict:
    return json.loads(b64d(encode(obj)[len(WIRE_PREFIX):]))


@pytest.mark.parametrize("obj", [HS1, HS2, HS3, MSG])
def test_ida_y_vuelta(obj):
    assert decode(encode(obj)) == obj


def test_el_mensaje_mas_grande_cabe_en_un_mensaje_de_discord():
    big = Msg("1" * 25, "2" * 25, b"s" * 16, 200, b"n" * 12, b"c" * (MAX_PLAINTEXT + 16))
    assert len(encode(big)) <= MAX_WIRE_LEN


def test_mensaje_demasiado_grande_se_rechaza():
    with pytest.raises(WireError):
        encode(replace(MSG, ct=b"c" * (MAX_PLAINTEXT + 17)))


@pytest.mark.parametrize("texto", [
    "", "hola", "E2EE2:abc", WIRE_PREFIX, WIRE_PREFIX + "no es base64!!", WIRE_PREFIX + b64e(b"no json"),
    WIRE_PREFIX + b64e(b"[]"), WIRE_PREFIX + b64e(b"\xff\xfe"),
])
def test_texto_que_no_es_del_protocolo(texto):
    with pytest.raises(WireError):
        decode(texto)


def test_tipo_no_str():
    with pytest.raises(WireError):
        decode(None)


def test_base64_no_canonico_se_rechaza():
    texto = encode(MSG)
    with pytest.raises(WireError):
        decode(texto + "=")


def test_campos_extra_o_faltantes():
    doc = _doc(MSG)
    with pytest.raises(WireError):
        decode(_raw({**doc, "extra": 1}))
    doc.pop("sid")
    with pytest.raises(WireError):
        decode(_raw(doc))


@pytest.mark.parametrize("cambio", [
    {"v": 2}, {"t": "xx"}, {"from": "abc"}, {"to": ""}, {"from": 5}, {"sid": b64e(b"corto")},
    {"c": True}, {"c": -1}, {"c": 2**63}, {"c": "1"}, {"n": b64e(b"x" * 11)}, {"ct": b64e(b"x" * 15)},
])
def test_campos_invalidos(cambio):
    with pytest.raises(WireError):
        decode(_raw({**_doc(MSG), **cambio}))


def test_ct_excesivo_se_rechaza():
    with pytest.raises(WireError):
        decode(_raw({**_doc(MSG), "ct": b64e(b"x" * (MAX_PLAINTEXT + 17))}))


def test_mensaje_de_mas_de_2000_caracteres_se_rechaza():
    with pytest.raises(WireError):
        decode(WIRE_PREFIX + "A" * MAX_WIRE_LEN)

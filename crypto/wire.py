"""Formato de los mensajes del protocolo: `E2EE1:` + base64url(JSON compacto).

Discord muestra como autor a un bot, así que el emisor y el receptor viajan dentro del
mensaje (`from`, `to`). Nada de lo que llega por aquí se considera confiable hasta que
el handshake o el AES-GCM lo autentican.
"""
import json
import re
from dataclasses import dataclass, fields

from . import aead
from .constants import MAX_PLAINTEXT, MAX_WIRE_LEN, VERSION, WIRE_PREFIX
from .encoding import b64d, b64e
from .errors import WireError

_ID_RE = re.compile(r"[0-9]{1,25}")
_MAX_INT = 2**63 - 1
_TAG_LEN = 16


@dataclass(frozen=True)
class Hs1:
    TYPE = "hs1"
    sender: str
    receiver: str
    sid: bytes
    ra: bytes
    epk: bytes
    ts: int


@dataclass(frozen=True)
class Hs2:
    TYPE = "hs2"
    sender: str
    receiver: str
    sid: bytes
    rb: bytes
    epk: bytes
    sig: bytes
    tag: bytes


@dataclass(frozen=True)
class Hs3:
    TYPE = "hs3"
    sender: str
    receiver: str
    sid: bytes
    sig: bytes
    tag: bytes


@dataclass(frozen=True)
class Msg:
    TYPE = "msg"
    sender: str
    receiver: str
    sid: bytes
    ctr: int
    nonce: bytes
    ct: bytes


# atributo -> (clave JSON, tipo). Tipo: "id", "int", longitud fija en bytes o "ct".
_SCHEMA = {
    Hs1: {"sender": ("from", "id"), "receiver": ("to", "id"), "sid": ("sid", 16),
          "ra": ("ra", 32), "epk": ("epk", 32), "ts": ("ts", "int")},
    Hs2: {"sender": ("from", "id"), "receiver": ("to", "id"), "sid": ("sid", 16),
          "rb": ("rb", 32), "epk": ("epk", 32), "sig": ("sig", 64), "tag": ("tag", 32)},
    Hs3: {"sender": ("from", "id"), "receiver": ("to", "id"), "sid": ("sid", 16),
          "sig": ("sig", 64), "tag": ("tag", 32)},
    Msg: {"sender": ("from", "id"), "receiver": ("to", "id"), "sid": ("sid", 16),
          "ctr": ("c", "int"), "nonce": ("n", aead.NONCE_LEN), "ct": ("ct", "ct")},
}
_BY_TYPE = {cls.TYPE: cls for cls in _SCHEMA}


def encode(obj) -> str:
    schema = _SCHEMA.get(type(obj))
    if schema is None:
        raise WireError("tipo de mensaje desconocido")
    doc = {"t": obj.TYPE, "v": VERSION}
    for attr, (key, kind) in schema.items():
        value = getattr(obj, attr)
        doc[key] = value if kind in ("id", "int") else b64e(value)
    text = WIRE_PREFIX + b64e(json.dumps(doc, separators=(",", ":")).encode("ascii"))
    if len(text) > MAX_WIRE_LEN:
        raise WireError("el mensaje excede el límite de Discord")
    _check(schema, {key: doc[key] for _, (key, _) in schema.items()})
    return text


def _check(schema: dict, doc: dict) -> dict:
    """Valida tipos y longitudes; devuelve los valores ya decodificados por atributo."""
    out = {}
    for attr, (key, kind) in schema.items():
        value = doc[key]
        try:
            if kind == "id":
                if not isinstance(value, str) or not _ID_RE.fullmatch(value):
                    raise ValueError
            elif kind == "int":
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _MAX_INT:
                    raise ValueError
            elif kind == "ct":
                value = b64d(value) if isinstance(value, str) else value
                if not _TAG_LEN <= len(value) <= MAX_PLAINTEXT + _TAG_LEN:
                    raise ValueError
            else:
                value = b64d(value, kind) if isinstance(value, str) else value
                if len(value) != kind:
                    raise ValueError
        except ValueError:
            raise WireError(f"campo inválido: {key}") from None
        out[attr] = value
    return out


def decode(text: str):
    """Convierte un texto de Discord en Hs1/Hs2/Hs3/Msg o lanza WireError."""
    if not isinstance(text, str) or not text.startswith(WIRE_PREFIX) or len(text) > MAX_WIRE_LEN:
        raise WireError("no es un mensaje del protocolo")
    try:
        doc = json.loads(b64d(text[len(WIRE_PREFIX):]))
    except (ValueError, UnicodeDecodeError):
        raise WireError("contenido mal formado") from None
    if not isinstance(doc, dict) or doc.get("v") != VERSION or doc.get("t") not in _BY_TYPE:
        raise WireError("versión o tipo no soportado")
    cls = _BY_TYPE[doc["t"]]
    schema = _SCHEMA[cls]
    if set(doc) != {"t", "v"} | {key for key, _ in schema.values()}:
        raise WireError("campos inesperados o faltantes")
    return cls(**_check(schema, doc))

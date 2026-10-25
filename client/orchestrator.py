"""Une `crypto/`, el directorio y Discord. Es el único lugar donde viven las sesiones y el texto plano.

Es síncrono y thread-safe (un RLock): Discord entrega los mensajes desde otro hilo y la API
local lo llama desde el pool de FastAPI. El tiempo siempre viene de `clock`, para poder probarlo.
"""
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from crypto import (
    CryptoError, DecryptError, Identity, Initiator, KdfParams, ReplayError,
    Responder, SidCache, VaultError, WireError, decode, encode, fingerprint, sign_registration,
)
from crypto.constants import HANDSHAKE_TTL, MAX_PLAINTEXT
from crypto.encoding import b64d, b64e
from crypto.fingerprint import qr_payload
from crypto.wire import Hs1, Hs2, Hs3, Msg

from .errors import (
    BadPassword, Conflict, KeyChanged, Locked, NotFound, PeerUnavailable, TooManyAttempts,
)
from .ports import DirectoryPort, DiscordPort
from .store import EncryptedStore, VaultFile

log = logging.getLogger("client")  # solo eventos: nunca texto plano, llaves ni contraseñas (RS3)

RETRY_DELAYS = (15 * 60, 30 * 60, 60 * 60)  # espera tras cada intento sin respuesta; el último se repite
MAX_ATTEMPTS = 6
KEY_LOOKUP_RETRY = 60  # segundos de espera si el directorio no respondió o la llave cambió
PREVIOUS_SESSION_GRACE = 60  # segundos que sigue descifrando la sesión anterior tras una rotación
MAX_SEEN = 5000
MAX_UNLOCK_FAILURES = 5
UNLOCK_BLOCK_SECONDS = 30


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def _chunks(text: str) -> list[str]:
    """Parte el texto en trozos de a lo sumo MAX_PLAINTEXT bytes sin cortar un carácter."""
    parts, current, size = [], [], 0
    for ch in text:
        n = len(ch.encode("utf-8"))
        if size + n > MAX_PLAINTEXT:
            parts.append("".join(current))
            current, size = [], 0
        current.append(ch)
        size += n
    if current:
        parts.append("".join(current))
    return parts


@dataclass
class Contact:
    discord_id: str
    alias: str | None = None
    pk: bytes | None = None  # llave en la que confiamos y con la que se firman los handshakes
    pending_pk: bytes | None = None  # llave nueva observada de un contacto verificado, a la espera de re-verificar
    verified: bool = False
    key_changed: bool = False

    def to_doc(self) -> dict:
        return {"alias": self.alias, "pk": b64e(self.pk) if self.pk else None,
                "pending_pk": b64e(self.pending_pk) if self.pending_pk else None,
                "verified": self.verified, "key_changed": self.key_changed}

    @classmethod
    def from_doc(cls, discord_id: str, doc: dict) -> "Contact":
        return cls(discord_id, doc.get("alias"), b64d(doc["pk"]) if doc.get("pk") else None,
                   b64d(doc["pending_pk"]) if doc.get("pending_pk") else None,
                   bool(doc.get("verified")), bool(doc.get("key_changed")))


@dataclass
class _Peer:
    """Estado en memoria de la conversación con un contacto. Las llaves de sesión nunca se guardan."""

    session: object | None = None
    previous: tuple[object, float] | None = None  # (sesión, momento en que se destruye)
    initiator: tuple[Initiator, float] | None = None
    responders: dict = field(default_factory=dict)  # sid -> (Responder, inicio)
    attempts: int = 0
    next_attempt_at: float = 0.0


class Orchestrator:
    def __init__(self, data_dir, directory: DirectoryPort, discord: DiscordPort, clock=time.time,
                 kdf: KdfParams | None = None):
        self._dir = Path(data_dir)
        self._directory, self._discord, self._clock = directory, discord, clock
        self._kdf = kdf or KdfParams()
        self._vault_file = VaultFile(self._dir)
        self._lock = threading.RLock()
        self._identity: Identity | None = None
        self._my_id: str | None = None
        self._store: EncryptedStore | None = None
        self._doc: dict = {}
        self._contacts: dict[str, Contact] = {}
        self._peers: dict[str, _Peer] = {}
        self._seen_sids = SidCache(clock)
        self._failures, self._blocked_until = 0, 0.0
        discord.set_receiver(self.on_discord_message)

    # ------------------------------------------------------------------ identidad

    @property
    def unlocked(self) -> bool:
        return self._identity is not None

    def status(self) -> dict:
        with self._lock:
            return {"unlocked": self.unlocked, "vault_exists": self._vault_file.exists(),
                    "discord_id": self._my_id if self.unlocked else None,
                    "public_key": b64e(self._identity.public_key) if self.unlocked else None}

    def create_identity(self, discord_id: str, password: str) -> dict:
        with self._lock:
            if self._vault_file.exists():
                raise Conflict("ya existe una identidad en este dispositivo")
            identity = Identity.create()
            self._vault_file.save(discord_id, identity.to_vault(password, self._kdf))
            self._open(identity, discord_id)
            self._publish_or_rollback()
            return self.status()

    def import_identity(self, discord_id: str, vault: bytes, password: str) -> dict:
        """RF12: carga en este dispositivo una identidad exportada desde otro."""
        with self._lock:
            if self._vault_file.exists():
                raise Conflict("ya existe una identidad en este dispositivo")
            try:
                identity = Identity.from_vault(vault, password)
            except VaultError:
                raise BadPassword("contraseña incorrecta o bóveda corrupta") from None
            self._vault_file.save(discord_id, identity.to_vault(password, self._kdf))
            self._open(identity, discord_id)
            self._publish_or_rollback()
            return self.status()

    def unlock(self, password: str) -> dict:
        with self._lock:
            if self.unlocked:
                return self.status()
            if not self._vault_file.exists():
                raise NotFound("no hay una identidad en este dispositivo")
            if self._clock() < self._blocked_until:
                raise TooManyAttempts("demasiados intentos; espera unos segundos")
            discord_id, blob = self._vault_file.load()
            try:
                identity = Identity.from_vault(blob, password)
            except VaultError:
                self._failures += 1
                if self._failures >= MAX_UNLOCK_FAILURES:
                    self._failures, self._blocked_until = 0, self._clock() + UNLOCK_BLOCK_SECONDS
                raise BadPassword("contraseña incorrecta") from None
            self._failures = 0
            self._open(identity, discord_id)
            return self.status()

    def lock(self) -> None:
        """Descarta sesiones y llaves de la memoria. Nada queda abierto sin la contraseña."""
        with self._lock:
            for peer in self._peers.values():
                for s in (peer.session, peer.previous[0] if peer.previous else None):
                    if s is not None:
                        s.destroy()
            self._peers.clear()
            self._contacts.clear()
            self._doc = {}
            self._identity = self._store = self._my_id = None

    def export_identity(self, new_password: str) -> bytes:
        with self._lock:
            return self._need_identity().to_vault(new_password, self._kdf)

    def _open(self, identity: Identity, discord_id: str) -> None:
        self._identity, self._my_id = identity, discord_id
        self._store = EncryptedStore(self._dir, identity.store_key)
        self._doc = self._store.load()
        self._doc.setdefault("history", {})
        self._doc.setdefault("outbox", {})
        self._doc.setdefault("seen", [])
        self._doc.setdefault("seq", 0)
        self._doc.setdefault("retry", {})
        self._contacts = {cid: Contact.from_doc(cid, c) for cid, c in self._doc.get("contacts", {}).items()}
        self._seen_set = set(self._doc["seen"])
        self._peers = {}
        for cid, state in self._doc["retry"].items():
            self._peer(cid).attempts, self._peer(cid).next_attempt_at = state["attempts"], state["next"]

    def _publish_or_rollback(self) -> None:
        """Una identidad no publicada no sirve: si el directorio falla, se deshace todo para poder reintentar."""
        try:
            self._publish_key()
        except PeerUnavailable:
            self.lock()
            self._vault_file.path.unlink(missing_ok=True)
            (self._dir / "store.enc").unlink(missing_ok=True)
            raise

    def _publish_key(self) -> None:
        ident, my_id = self._identity, self._my_id
        try:
            self._directory.register(my_id, ident.public_key, lambda nonce: sign_registration(ident, my_id, nonce))
        except Exception:
            log.warning("no se pudo publicar la llave en el directorio")
            raise PeerUnavailable("no se pudo publicar la llave en el directorio") from None

    def _need_identity(self) -> Identity:
        if self._identity is None:
            raise Locked("desbloquea la identidad con tu contraseña maestra")
        return self._identity

    def _save(self) -> None:
        self._doc["contacts"] = {cid: c.to_doc() for cid, c in self._contacts.items()}
        self._doc["retry"] = {cid: {"attempts": p.attempts, "next": p.next_attempt_at}
                              for cid, p in self._peers.items() if p.attempts or p.next_attempt_at}
        self._store.save(self._doc)

    # ------------------------------------------------------------------ contactos y verificación

    def add_contact(self, discord_id: str, alias: str | None = None) -> Contact:
        with self._lock:
            self._need_identity()
            if discord_id == self._my_id:
                raise Conflict("no puedes agregarte a ti mismo")
            contact = self._contacts.get(discord_id) or Contact(discord_id)
            contact.alias = alias or contact.alias
            self._peer_key(contact)  # TOFU: registra la llave observada, o falla si no existe
            self._contacts[discord_id] = contact  # solo se agrega si el directorio conoce su llave
            self._save()
            return self._contact_view(contact)

    def contacts(self) -> list[dict]:
        with self._lock:
            self._need_identity()
            return [self._contact_view(c) for c in self._contacts.values()]

    def contact(self, discord_id: str) -> dict:
        with self._lock:
            self._need_identity()
            return self._contact_view(self._get_contact(discord_id))

    def _get_contact(self, discord_id: str) -> Contact:
        contact = self._contacts.get(discord_id)
        if contact is None:
            raise NotFound("contacto desconocido")
        return contact

    def _contact_view(self, c: Contact) -> dict:
        peer = self._peers.get(c.discord_id)
        return {"discord_id": c.discord_id, "alias": c.alias, "verified": c.verified,
                "key_changed": c.key_changed, "session": self._session_state(c, peer),
                "queued": len(self._doc["outbox"].get(c.discord_id, []))}

    def _session_state(self, c: Contact, peer: _Peer | None) -> str:
        if c.pending_pk is not None:
            return "key_changed"
        if peer is None:
            return "none"
        if peer.session is not None and not peer.session.destroyed:
            return "active"
        if peer.initiator is not None or peer.responders:
            return "handshaking"
        if peer.attempts >= MAX_ATTEMPTS:
            return "unavailable"
        return "waiting" if peer.next_attempt_at > self._clock() else "none"

    def fingerprint(self, discord_id: str) -> dict:
        """Huella para la ceremonia OOB. Si hay una llave nueva pendiente, muestra la de la nueva."""
        with self._lock:
            ident = self._need_identity()
            contact = self._get_contact(discord_id)
            pk = contact.pending_pk or contact.pk
            if pk is None:
                raise PeerUnavailable("el contacto no tiene llave registrada")
            return {"fingerprint": fingerprint(ident.public_key, pk), "qr": qr_payload(ident.public_key, pk).hex(),
                    "verified": contact.verified, "key_pending": contact.pending_pk is not None}

    def verify_contact(self, discord_id: str, fingerprint_read: str) -> dict:
        """RF7: el usuario compara la huella fuera de Discord y escribe/escanea la que le dicta el otro."""
        with self._lock:
            ident = self._need_identity()
            contact = self._get_contact(discord_id)
            current = self._directory_key(contact)  # la llave que el directorio publica ahora
            if current is None:
                raise PeerUnavailable("el contacto no tiene llave registrada")
            candidate = contact.pending_pk or contact.pk
            if current != candidate:
                raise Conflict("la llave del contacto cambió mientras verificabas; repite la ceremonia")
            expected = _digits(fingerprint(ident.public_key, candidate))
            if _digits(fingerprint_read) != expected:
                raise Conflict("la huella no coincide: no se verificó el contacto")
            contact.pk, contact.pending_pk = candidate, None
            contact.verified, contact.key_changed = True, False
            self._save()
            self._pump(discord_id)
            return self._contact_view(contact)

    def _directory_key(self, contact: Contact) -> bytes | None:
        try:
            return self._directory.get_key(contact.discord_id)
        except Exception:
            log.warning("el directorio no respondió")
            raise PeerUnavailable("no se pudo consultar el directorio") from None

    def _peer_key(self, contact: Contact) -> bytes:
        """Llave de firma con la que se habla con el contacto, comparada con el pin (RF8)."""
        current = self._directory_key(contact)
        if current is None:
            raise PeerUnavailable("el contacto no está registrado en el directorio")
        if contact.pk is None:  # primer contacto: confianza en el primer uso, hasta que se verifique
            contact.pk = current
        elif current != contact.pk:
            if contact.verified:  # RS7/RF8: se revoca la verificación y se aborta; nunca se continúa
                contact.verified, contact.key_changed, contact.pending_pk = False, True, current
                self._alert(contact.discord_id, "key_changed")
                self._save()
                raise KeyChanged("la llave del contacto verificado cambió")
            contact.pk, contact.key_changed = current, True  # sin verificar no había nada que revocar
        elif contact.pending_pk is not None:  # el directorio volvió a la llave anclada
            contact.pending_pk = None
        if contact.pending_pk is not None:
            raise KeyChanged("la llave del contacto cambió; verifica la nueva huella")
        return contact.pk

    # ------------------------------------------------------------------ historial

    def history(self, discord_id: str, since: int = 0) -> list[dict]:
        with self._lock:
            self._need_identity()
            self._get_contact(discord_id)
            return [dict(e) for e in self._doc["history"].get(discord_id, []) if e["seq"] > since]

    def conversations(self) -> list[dict]:
        with self._lock:
            self._need_identity()
            out = []
            for c in self._contacts.values():
                hist = self._doc["history"].get(c.discord_id, [])
                out.append({**self._contact_view(c), "last": hist[-1] if hist else None})
            return out

    def _add_history(self, peer_id: str, direction: str, text: str | None, status: str) -> dict:
        self._doc["seq"] += 1
        entry = {"seq": self._doc["seq"], "id": uuid.uuid4().hex, "dir": direction, "text": text,
                 "status": status, "ts": self._clock()}
        self._doc["history"].setdefault(peer_id, []).append(entry)
        return entry

    def _alert(self, peer_id: str, kind: str) -> None:
        self._add_history(peer_id, "sys", None, kind)

    def _mark_seen(self, key: str) -> None:
        self._doc["seen"].append(key)
        self._seen_set.add(key)
        if len(self._doc["seen"]) > MAX_SEEN:
            self._seen_set.discard(self._doc["seen"].pop(0))

    # ------------------------------------------------------------------ envío

    def send_text(self, discord_id: str, text: str) -> dict:
        with self._lock:
            self._need_identity()
            contact = self._get_contact(discord_id)
            if not text or not text.strip():
                raise Conflict("el mensaje está vacío")
            for part in _chunks(text):
                entry = self._add_history(discord_id, "out", part, "queued")
                self._doc["outbox"].setdefault(discord_id, []).append(entry["id"])
            self._save()
            self._pump(discord_id)
            return self._contact_view(contact)

    def retry(self, discord_id: str) -> dict:
        with self._lock:
            self._need_identity()
            contact = self._get_contact(discord_id)
            peer = self._peer(discord_id)
            peer.attempts, peer.next_attempt_at = 0, 0.0
            self._save()
            self._pump(discord_id)
            return self._contact_view(contact)

    def _peer(self, discord_id: str) -> _Peer:
        return self._peers.setdefault(discord_id, _Peer())

    def _pump(self, discord_id: str) -> None:
        """Envía lo que se pueda; si no hay sesión, intenta abrir una."""
        peer = self._peer(discord_id)
        session = peer.session
        if session is not None and session.destroyed:
            peer.session = session = None
        queue = self._doc["outbox"].get(discord_id, [])
        if session is not None and not session.expired():
            by_id = {e["id"]: e for e in self._doc["history"].get(discord_id, [])}
            while queue:
                entry = by_id.get(queue[0])
                if entry is not None:
                    try:
                        wire = encode(session.encrypt(entry["text"].encode("utf-8")))
                        self._discord.send(wire)
                    except CryptoError:
                        break
                    except Exception:
                        log.warning("Discord no aceptó el mensaje; sigue en cola")
                        break
                    entry["status"] = "sent"
                queue.pop(0)
            self._save()
        if session is None and queue:
            self._try_start(discord_id)
        elif session is not None and session.needs_rotation():
            self._try_start(discord_id)  # RS9: nuevo handshake mientras la actual sigue sirviendo

    def _try_start(self, discord_id: str) -> None:
        peer = self._peer(discord_id)
        now = self._clock()
        if peer.initiator is not None or peer.responders or peer.attempts >= MAX_ATTEMPTS:
            return
        if now < peer.next_attempt_at:
            return
        contact = self._get_contact(discord_id)
        try:
            pk = self._peer_key(contact)
        except (KeyChanged, PeerUnavailable):
            peer.next_attempt_at = now + KEY_LOOKUP_RETRY  # el mensaje sigue en cola
            self._save()
            return
        init = Initiator(self._identity, self._my_id, discord_id, pk, self._clock)
        hs1 = init.start()
        peer.initiator = (init, now)  # primero el estado: la respuesta puede llegar de inmediato
        peer.attempts += 1
        self._save()
        self._send_protocol(hs1)

    def _schedule_retry(self, peer: _Peer) -> None:
        """Espera creciente tras un intento sin respuesta: 15, 30 y luego 60 minutos."""
        delay = RETRY_DELAYS[min(max(peer.attempts, 1), len(RETRY_DELAYS)) - 1]
        peer.next_attempt_at = self._clock() + delay

    def _send_protocol(self, obj) -> None:
        try:
            self._discord.send(encode(obj))
        except Exception:
            log.warning("Discord no aceptó un mensaje del protocolo")

    # ------------------------------------------------------------------ recepción

    def on_discord_message(self, text: str) -> None:
        """Punto de entrada desde Discord. Nada de lo que llega se asume confiable."""
        with self._lock:
            if self._identity is None:
                return
            try:
                obj = decode(text)
            except WireError:
                return  # no es del protocolo (otro texto del canal)
            if obj.receiver != self._my_id or obj.sender == self._my_id:
                return
            try:
                if isinstance(obj, Hs1):
                    self._on_hs1(obj)
                elif isinstance(obj, Hs2):
                    self._on_hs2(obj)
                elif isinstance(obj, Hs3):
                    self._on_hs3(obj)
                elif isinstance(obj, Msg):
                    self._on_msg(obj)
            except (CryptoError, KeyChanged, PeerUnavailable) as exc:
                log.info("mensaje del protocolo descartado: %s", type(exc).__name__)

    def _on_hs1(self, hs1: Hs1) -> None:
        # Alguien nuevo en el canal privado queda como contacto sin verificar, pero solo si el
        # directorio conoce su llave; así un tercero no puede llenar la lista con ids inventados.
        contact = self._contacts.get(hs1.sender) or Contact(hs1.sender)
        pk = self._peer_key(contact)
        self._contacts[hs1.sender] = contact
        peer = self._peer(hs1.sender)
        if peer.initiator is not None:
            if int(self._my_id) < int(hs1.sender):
                return  # los dos iniciaron a la vez: gana el id menor
            peer.initiator = None  # abandono el mío y respondo
        responder = Responder(self._identity, self._my_id, hs1.sender, pk, self._seen_sids, self._clock)
        hs2 = responder.respond(hs1)
        peer.responders[hs1.sid] = (responder, self._clock())
        self._save()
        self._send_protocol(hs2)

    def _on_hs2(self, hs2: Hs2) -> None:
        peer = self._peers.get(hs2.sender)
        if peer is None or peer.initiator is None:
            return
        hs3, session = peer.initiator[0].finish(hs2)
        self._activate(hs2.sender, session)
        self._send_protocol(hs3)
        self._pump(hs2.sender)

    def _on_hs3(self, hs3: Hs3) -> None:
        peer = self._peers.get(hs3.sender)
        entry = peer.responders.get(hs3.sid) if peer else None
        if entry is None:
            return
        session = entry[0].finish(hs3)
        peer.responders.pop(hs3.sid, None)
        self._activate(hs3.sender, session)
        self._pump(hs3.sender)

    def _activate(self, discord_id: str, session) -> None:
        peer = self._peer(discord_id)
        if peer.previous is not None:
            peer.previous[0].destroy()
        if peer.session is not None and not peer.session.destroyed:
            peer.previous = (peer.session, self._clock() + PREVIOUS_SESSION_GRACE)
        peer.session, peer.initiator = session, None
        peer.attempts, peer.next_attempt_at = 0, 0.0
        self._save()

    def _on_msg(self, msg: Msg) -> None:
        key = f"{msg.sid.hex()}:{msg.ctr}"
        if msg.sender not in self._contacts or key in self._seen_set:
            return  # ya procesado (p. ej. historial del canal reentregado)
        peer = self._peer(msg.sender)
        session = next((s for s in (peer.session, peer.previous[0] if peer.previous else None)
                        if s is not None and s.sid == msg.sid and not s.destroyed), None)
        if session is None:
            return self._undecryptable(msg, key, "sesión desconocida o ya destruida")
        try:
            plain = session.decrypt(msg)
        except ReplayError:
            return
        except (DecryptError, CryptoError):
            return self._undecryptable(msg, key, "autenticación fallida")
        self._mark_seen(key)
        self._add_history(msg.sender, "in", plain.decode("utf-8", errors="replace"), "received")
        self._save()

    def _undecryptable(self, msg: Msg, key: str, reason: str) -> None:
        """RF11: marcador de mensaje no descifrable; el contenido se descarta."""
        self._mark_seen(key)
        entry = self._add_history(msg.sender, "in", None, "undecryptable")
        entry["reason"] = reason
        self._save()

    # ------------------------------------------------------------------ reloj

    def tick(self) -> None:
        """Se llama cada pocos segundos: caduca intentos, reintenta, rota y destruye sesiones viejas."""
        with self._lock:
            if self._identity is None:
                return
            now = self._clock()
            for discord_id, peer in list(self._peers.items()):
                if peer.previous is not None and now >= peer.previous[1]:
                    peer.previous[0].destroy()
                    peer.previous = None
                if peer.session is not None and (peer.session.destroyed or peer.session.expired()):
                    peer.session.destroy()
                    peer.session = None
                for sid, (_, started) in list(peer.responders.items()):
                    if now - started > HANDSHAKE_TTL:
                        del peer.responders[sid]
                if peer.initiator is not None and now - peer.initiator[1] > HANDSHAKE_TTL:
                    peer.initiator = None  # la llave efímera `a` ya fue destruida por la librería
                    self._schedule_retry(peer)
                    self._save()
                if discord_id in self._contacts:
                    self._pump(discord_id)

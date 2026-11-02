"""F3: el adaptador sobre un Discord simulado (mismo contrato que el backend de discord.py). La prueba final usa
dos clientes reales (`client.Orchestrator`) para comprobar el contrato `DiscordPort` de punta a punta."""
import datetime as dt
import itertools
import threading
import time

import pytest

from client.fakes import FakeDirectory
from client.orchestrator import Orchestrator
from client.privacy import NOTICE_VERSION
from crypto import KdfParams
from discord_adapter import DiscordAdapter, is_protocol
from discord_adapter.check import problems

CHANNEL, OTHER_CHANNEL = 1000, 2000
ALICE, BOB = "111111111111111111", "222222222222222222"
WIRE = "E2EE1:eyJ0eXBlIjoibXNnIn0"


class FakeGuild:
    """Un servidor de Discord: guarda lo publicado y lo reparte a todos los bots conectados."""

    def __init__(self):
        self.messages: list[tuple[int, int, str, dt.datetime]] = []
        self.backends: list["FakeBackend"] = []
        self._ids = itertools.count(1)
        self.lock = threading.Lock()

    def post(self, channel_id: int, content: str, author: str = "bot") -> int:
        with self.lock:
            mid = next(self._ids)
            self.messages.append((channel_id, mid, content, dt.datetime.now(dt.timezone.utc)))
            online = [b for b in self.backends if b.online]
        for b in online:
            b.adapter.on_message(channel_id, mid, content)
        return mid


class FakeBackend:
    def __init__(self, guild: FakeGuild, fail_sends: bool = False):
        self.guild, self.fail_sends, self.online, self.adapter = guild, fail_sends, False, None
        guild.backends.append(self)

    def run(self, adapter):
        self.adapter = adapter
        self.connect(first=True)

    def connect(self, first=False):
        self.online = True
        self.adapter.on_connect(first)

    def disconnect(self):
        self.online = False
        self.adapter.on_disconnect()

    def send(self, text, timeout):
        if self.fail_sends:
            raise RuntimeError("HTTP 503")
        self.guild.post(self.adapter.channel_id, text)

    def history(self, after, limit):
        rows = [(c, m, t) for c, m, t, at in self.guild.messages
                if (m > after if isinstance(after, int) else at > after)]
        return rows[:limit]

    def close(self):
        self.online = False


def wait_for(condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def guild():
    return FakeGuild()


def make(guild, **kw):
    received: list[str] = []
    adapter = DiscordAdapter(channel_id=CHANNEL, backend=FakeBackend(guild, **kw))
    adapter.set_receiver(received.append)
    assert wait_for(adapter._ready.is_set)
    return adapter, received


def test_RF3_publica_y_entrega_mensajes_del_protocolo(guild):
    a, _ = make(guild)
    _, got_b = make(guild)
    a.send(WIRE)
    assert wait_for(lambda: got_b == [WIRE])


def test_ignora_otros_canales_y_textos_que_no_son_del_protocolo(guild):
    _, got = make(guild)
    guild.post(OTHER_CHANNEL, WIRE)
    guild.post(CHANNEL, "hola a todos, texto normal")
    guild.post(CHANNEL, "E2EE1:" + "x" * 2000)  # demasiado largo
    guild.post(CHANNEL, WIRE)
    assert wait_for(lambda: got == [WIRE])
    time.sleep(0.05)
    assert got == [WIRE]


def test_RS3_se_niega_a_publicar_texto_plano(guild):
    a, _ = make(guild)
    for text in ("hola en claro", "", "e2ee1:minusculas", "E2EE1:" + "x" * 1995):
        with pytest.raises(ValueError):
            a.send(text)
    assert guild.messages == []


def test_el_autor_no_importa(guild):
    _, got = make(guild)
    guild.post(CHANNEL, WIRE, author="cualquier-bot")
    assert wait_for(lambda: got == [WIRE])


def test_fallo_de_discord_se_reporta_como_connection_error(guild):
    a, _ = make(guild, fail_sends=True)
    with pytest.raises(ConnectionError):
        a.send(WIRE)


def test_sin_conexion_send_falla_rapido(guild):
    adapter = DiscordAdapter(channel_id=CHANNEL, backend=FakeBackend(guild), start=False, send_timeout=0.1)
    with pytest.raises(ConnectionError):
        adapter.send(WIRE)


def test_al_conectar_entrega_lo_publicado_mientras_no_estaba(guild):
    guild.post(CHANNEL, WIRE + "A")
    _, got = make(guild)
    assert wait_for(lambda: got == [WIRE + "A"])


def test_lo_que_llega_antes_de_registrar_el_receptor_no_se_pierde(guild):
    # client.main crea el adaptador (que ya conecta) y el orquestador registra el receptor después
    guild.post(CHANNEL, WIRE + "A")
    adapter = DiscordAdapter(channel_id=CHANNEL, backend=FakeBackend(guild))
    assert wait_for(adapter._ready.is_set)
    time.sleep(0.1)
    got = []
    adapter.set_receiver(got.append)
    assert wait_for(lambda: got == [WIRE + "A"])


def test_al_reconectar_entrega_lo_perdido_sin_repetir(guild):
    a, got = make(guild)
    guild.post(CHANNEL, WIRE + "1")
    assert wait_for(lambda: got == [WIRE + "1"])
    a._backend.disconnect()
    guild.post(CHANNEL, WIRE + "2")
    a._backend.connect()
    assert wait_for(lambda: got == [WIRE + "1", WIRE + "2"])
    time.sleep(0.05)
    assert got == [WIRE + "1", WIRE + "2"]


def test_replay_backlog_reentrega_aunque_ya_se_hayan_visto(guild):
    a, got = make(guild)
    guild.post(CHANNEL, WIRE)
    assert wait_for(lambda: got == [WIRE])
    a.replay_backlog()
    assert wait_for(lambda: got == [WIRE, WIRE])


def test_un_receptor_que_falla_no_detiene_la_entrega(guild):
    a, _ = make(guild)
    got = []

    def flaky(text):
        if text.endswith("malo"):
            raise RuntimeError("boom")
        got.append(text)
    a.set_receiver(flaky)
    guild.post(CHANNEL, WIRE + "malo")
    guild.post(CHANNEL, WIRE + "bueno")
    assert wait_for(lambda: got == [WIRE + "bueno"])


def test_RS10_sin_token_no_arranca():
    with pytest.raises(ValueError):
        DiscordAdapter(token="", channel_id=CHANNEL)


def test_RF3_RF5_dos_clientes_reales_conversan_por_el_adaptador(guild, tmp_path):
    """Contrato DiscordPort de punta a punta; además prueba que `send()` dentro del receptor no se bloquea."""
    directory = FakeDirectory()
    orch = {}
    for uid in (ALICE, BOB):
        adapter = DiscordAdapter(channel_id=CHANNEL, backend=FakeBackend(guild))
        orch[uid] = Orchestrator(tmp_path / uid, directory, adapter, kdf=KdfParams(1, 64, 1))
        orch[uid].create_identity(uid, "contraseña-maestra-123", NOTICE_VERSION)
    orch[ALICE].add_contact(BOB, "Bob")
    orch[BOB].add_contact(ALICE, "Alice")
    orch[ALICE].send_text(BOB, "hola bob, esto va cifrado")
    assert wait_for(lambda: [e.get("text") for e in orch[BOB].history(ALICE)] == ["hola bob, esto va cifrado"])
    orch[BOB].send_text(ALICE, "recibido")
    assert wait_for(lambda: orch[ALICE].history(BOB)[-1].get("text") == "recibido")
    published = [m[2] for m in guild.messages]
    assert all(is_protocol(t) for t in published)
    assert not any("hola bob" in t or "recibido" in t for t in published)


def test_C23_revision_del_canal():
    ok = {"everyone_can_view": False, "bot_is_admin": False, "bot_extra_permissions": [],
          "roles_with_access": ["e2ee"]}
    assert problems(ok) == []
    bad = {**ok, "everyone_can_view": True, "bot_is_admin": True, "bot_extra_permissions": ["manage_messages"]}
    assert len(problems(bad)) == 3

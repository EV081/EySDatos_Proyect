"""Adaptador de Discord (F3): implementa `client.ports.DiscordPort` con un bot propio por persona.

* Solo publica y entrega mensajes del protocolo (`E2EE1:...`, ≤ 2000 caracteres) del canal configurado. Se niega a
  publicar cualquier otro texto: así un error del cliente no puede filtrar texto plano al canal.
* El autor que muestra Discord se ignora (siempre es un bot); el emisor viaja dentro del mensaje y lo autentica
  el protocolo.
* El token del bot sale de la variable de entorno `DISCORD_TOKEN` (RS10) y nunca se registra.
* La conexión corre en su propio hilo y bucle de eventos. Los mensajes se entregan al cliente desde otro hilo,
  porque el cliente puede responder con `send()` mientras procesa uno (si se entregaran desde el bucle de
  Discord, `send()` esperaría a ese mismo bucle y se bloquearía).
* Al conectarse por primera vez entrega lo publicado en los últimos días (`backlog`); al reconectarse, lo que
  llegó desde el último mensaje visto. El cliente descarta repetidos y *handshakes* vencidos.
"""
import datetime as dt
import logging
import queue
import threading
from collections import OrderedDict
from typing import Callable, Protocol

PREFIX = "E2EE1:"
MAX_LEN = 2000
_SEEN_MAX = 5000

log = logging.getLogger("discord_adapter")


class Backend(Protocol):
    def run(self, adapter: "DiscordAdapter") -> None:
        """Bloquea: conecta y llama a `adapter.on_connect` y `adapter.on_message`."""

    def send(self, text: str, timeout: float) -> None: ...

    def history(self, after: int | dt.datetime, limit: int) -> list[tuple[int, int, str]]:
        """Mensajes (channel_id, message_id, content) posteriores a `after`, del más antiguo al más nuevo."""

    def close(self) -> None: ...


class DiscordAdapter:
    def __init__(self, token: str | None = None, channel_id: int = 0, backend: Backend | None = None,
                 backlog: dt.timedelta = dt.timedelta(days=7), send_timeout: float = 15.0, start: bool = True):
        if backend is None:
            if not token:
                raise ValueError("falta el token del bot (DISCORD_TOKEN)")
            from .discordpy import DiscordPyBackend
            backend = DiscordPyBackend(token, channel_id)
        self.channel_id, self._backend = channel_id, backend
        self._backlog, self._send_timeout = backlog, send_timeout
        self._receiver: Callable[[str], None] | None = None
        self._seen: OrderedDict[int, None] = OrderedDict()
        self._last_id: int | None = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._inbox: queue.Queue[str | None] = queue.Queue()
        self._worker = threading.Thread(target=self._deliver, name="discord-entrega", daemon=True)
        self._worker.start()
        self._thread: threading.Thread | None = None
        if start:
            self.start()

    # --- DiscordPort ------------------------------------------------------------------

    def send(self, text: str) -> None:
        if not is_protocol(text):
            raise ValueError("solo se publican mensajes del protocolo E2EE1 de hasta 2000 caracteres")
        if not self._ready.wait(self._send_timeout):
            raise ConnectionError("Discord no está conectado")
        try:
            self._backend.send(text, self._send_timeout)
        except Exception as exc:
            raise ConnectionError(f"Discord no aceptó el mensaje ({type(exc).__name__})") from None

    def set_receiver(self, callback: Callable[[str], None]) -> None:
        self._receiver = callback

    # --- ciclo de vida ----------------------------------------------------------------

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._backend.run, args=(self,), name="discord", daemon=True)
            self._thread.start()

    def close(self) -> None:
        self._ready.clear()
        self._backend.close()
        self._inbox.put(None)

    def replay_backlog(self) -> None:
        """Vuelve a entregar lo publicado en el periodo de `backlog` (p. ej., tras desbloquear la identidad,
        porque con la identidad bloqueada el cliente descarta lo que llega)."""
        self._catch_up(self._now() - self._backlog, force=True)

    # --- llamadas del backend ---------------------------------------------------------

    def on_connect(self, first: bool) -> None:
        self._ready.set()
        after = self._now() - self._backlog if first or self._last_id is None else self._last_id
        threading.Thread(target=self._catch_up, args=(after,), daemon=True).start()

    def on_disconnect(self) -> None:
        self._ready.clear()

    def on_message(self, channel_id: int, message_id: int, content: str, force: bool = False) -> bool:
        """Filtra y encola. Devuelve True si el mensaje se entregará."""
        if channel_id != self.channel_id or not is_protocol(content):
            return False
        with self._lock:
            if message_id in self._seen and not force:
                return False
            self._seen[message_id] = None
            self._seen.move_to_end(message_id)
            while len(self._seen) > _SEEN_MAX:
                self._seen.popitem(last=False)
            self._last_id = max(self._last_id or 0, message_id)
        self._inbox.put(content)
        return True

    # --- internos ---------------------------------------------------------------------

    def _catch_up(self, after: int | dt.datetime, force: bool = False) -> None:
        try:
            for channel_id, message_id, content in self._backend.history(after, limit=1000):
                self.on_message(channel_id, message_id, content, force=force)
        except Exception as exc:
            log.warning("no se pudo leer el historial del canal (%s)", type(exc).__name__)

    def _deliver(self) -> None:
        while (text := self._inbox.get()) is not None:
            receiver = self._receiver
            if receiver is None:
                continue
            try:
                receiver(text)
            except Exception as exc:  # un mensaje malo no debe detener la entrega de los demás
                log.warning("el cliente no pudo procesar un mensaje (%s)", type(exc).__name__)

    @staticmethod
    def _now() -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)


def is_protocol(text: object) -> bool:
    return isinstance(text, str) and text.startswith(PREFIX) and len(text) <= MAX_LEN

"""Registros de auditoría y alertas del directorio (F5, C-09, C-10).

* Cada evento es una línea JSON en `AUDIT_LOG_DIR/audit.jsonl`; las alertas, en `alerts.jsonl`. Ambos rotan a
  medianoche (UTC) y se conservan 90 días.
* **Nunca** se registran texto de mensajes, llaves, tokens, IPs ni IDs en claro: los IDs llegan ya seudonimizados
  (HMAC, `Pseudonymizer`). Como segunda barrera, `RedactFilter` borra de cada línea cualquier cosa con forma de
  ID de Discord, secreto en base64url o mensaje del protocolo.
* `AlertMonitor` cuenta eventos en ventanas de tiempo y dispara alertas (fallos de firma, acceso ajeno,
  enumeración, cambios de llave). Las alertas solo llevan la regla y el conteo, nunca identificadores.
"""
import json
import logging
import logging.handlers
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

RETENTION_DAYS = 90
audit_log = logging.getLogger("directory.audit")
alert_log = logging.getLogger("directory.alerts")

_REDACTIONS = (
    (re.compile(r"E2EE1:\S*"), "[protocolo]"),
    (re.compile(r"(?i)bearer\s+\S+"), "Bearer [secreto]"),
    (re.compile(r"(?<![0-9])[0-9]{17,20}(?![0-9])"), "[id]"),
    (re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{40,}={0,2}"), "[secreto]"),
)


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg, record.args = redact(record.getMessage()), None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                 "level": record.levelname.lower(), "logger": record.name}
        fields = getattr(record, "fields", None)
        if fields:
            entry.update({k: redact(str(v)) for k, v in fields.items()})
        else:
            entry["message"] = record.getMessage()
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(log_dir: str | Path | None, level: int = logging.INFO) -> None:
    """Archivos con rotación diaria y 90 días de retención; sin `log_dir`, solo consola (también redactada)."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        for name, logger in (("audit.jsonl", audit_log), ("alerts.jsonl", alert_log)):
            fh = logging.handlers.TimedRotatingFileHandler(path / name, when="midnight", utc=True,
                                                           backupCount=RETENTION_DAYS, encoding="utf-8")
            fh.setFormatter(JsonFormatter())
            fh.addFilter(RedactFilter())
            logger.addHandler(fh)
    for h in handlers:
        h.setFormatter(JsonFormatter())
        h.addFilter(RedactFilter())
    root = logging.getLogger("directory")
    root.setLevel(level)
    for h in handlers:
        root.addHandler(h)


def purge_logs(log_dir: str | Path, days: int = RETENTION_DAYS, now: float | None = None) -> list[Path]:
    """Borra archivos rotados con más de `days` días (por si el servicio no estuvo corriendo al rotar)."""
    now = now or time.time()
    removed = []
    for path in Path(log_dir).glob("*.jsonl*"):
        if now - path.stat().st_mtime > days * 86400:
            path.unlink()
            removed.append(path)
    return removed


@dataclass(frozen=True)
class Rule:
    event: str
    threshold: int
    window: float  # segundos
    message: str


RULES = (
    Rule("acceso_ajeno", 1, 600, "intento de modificar el registro de otra persona"),
    Rule("firma_invalida", 5, 600, "pruebas de posesión inválidas repetidas"),
    Rule("limite", 3, 300, "límite de solicitudes alcanzado varias veces: posible enumeración"),
    Rule("consulta_inexistente", 20, 600, "muchas consultas de IDs no registrados: posible enumeración"),
    Rule("cambio_de_llave", 1, 3600, "cambio de llave registrado: revisar si fue legítimo"),
    Rule("cambio_de_llave", 3, 3600, "varios cambios de llave en una hora: posible toma de cuentas"),
)


class AlertMonitor:
    def __init__(self, rules=RULES, clock=time.monotonic, webhook_url: str | None = None,
                 sink: Callable[[dict], None] | None = None):
        self._rules, self._clock = rules, clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._last_fired: dict[Rule, float] = {}
        self._lock = threading.Lock()
        self._webhook = webhook_url
        self._sink = sink
        self.fired: list[dict] = []

    def record(self, event: str) -> None:
        now = self._clock()
        alerts = []
        with self._lock:
            hits = self._events[event]
            hits.append(now)
            longest = max((r.window for r in self._rules if r.event == event), default=0)
            while hits and now - hits[0] > longest:
                hits.popleft()
            for rule in self._rules:
                if rule.event != event:
                    continue
                count = sum(1 for t in hits if now - t <= rule.window)
                last = self._last_fired.get(rule)
                if count >= rule.threshold and (last is None or now - last > rule.window):
                    self._last_fired[rule] = now  # una alerta por ventana: sin avalanchas
                    alerts.append({"alert": rule.message, "event": rule.event, "count": count,
                                   "window_s": int(rule.window)})
        for alert in alerts:
            self._fire(alert)

    def _fire(self, alert: dict) -> None:
        self.fired.append(alert)
        alert_log.warning("alerta", extra={"fields": alert})
        if self._sink:
            self._sink(alert)
        if self._webhook:  # p. ej., un webhook de un canal privado de operadores; sin datos personales
            threading.Thread(target=self._post, args=(alert,), daemon=True).start()

    def _post(self, alert: dict) -> None:
        try:
            httpx.post(self._webhook, json={"content": f"[directorio] {alert['alert']} ({alert['count']})"},
                       timeout=10)
        except httpx.HTTPError:
            alert_log.error("no se pudo enviar la alerta al webhook")


class Audit:
    """Registra eventos de auditoría y alimenta el monitor de alertas."""

    def __init__(self, pseudonymize: Callable[[str], str], monitor: AlertMonitor | None = None):
        self._pseudonym = pseudonymize
        self.monitor = monitor or AlertMonitor()

    def event(self, name: str, level: int = logging.INFO, ids: dict[str, str] | None = None, **fields) -> None:
        """`ids` se seudonimizan aquí; `fields` no deben llevar datos personales."""
        data = {"event": name, **{k: self._pseudonym(v) for k, v in (ids or {}).items()}, **fields}
        audit_log.log(level, name, extra={"fields": data})
        self.monitor.record(name)

    def count(self, name: str) -> None:
        """Cuenta para las alertas sin dejar registro (p. ej., cada consulta de un ID inexistente)."""
        self.monitor.record(name)

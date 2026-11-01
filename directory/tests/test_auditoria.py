"""F5 / C-09: los registros no contienen texto, llaves, tokens ni IDs en claro; las alertas se disparan."""
import json
import logging
import os
import time

import pytest

from crypto import Identity
from directory.app.audit import AlertMonitor, Rule, alert_log, audit_log, purge_logs, redact, setup_logging
from directory.app.schemas import b64e

from conftest import ALICE, BOB, MALLORY, challenge, login, publish


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def log_files(tmp_path):
    loggers = [logging.getLogger("directory"), audit_log, alert_log]
    before = {lg: list(lg.handlers) for lg in loggers}
    setup_logging(tmp_path)
    yield tmp_path
    for lg in loggers:
        for h in lg.handlers[:]:
            if h not in before[lg]:
                h.close()
                lg.removeHandler(h)


def _lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_C09_registros_reales_sin_datos_personales_ni_secretos(api, settings, log_files):
    alice, other = Identity.create(), Identity.create()
    token = login(api, ALICE)
    publish(api, token, ALICE, alice)
    publish(api, login(api, ALICE), ALICE, other, signer=Identity.create())  # firma inválida
    publish(api, login(api, ALICE), ALICE, other)                            # cambio de llave
    challenge(api, login(api, MALLORY), ALICE)                                # acceso ajeno
    api.get(f"/v1/keys/{BOB}")
    text = (log_files / "audit.jsonl").read_text(encoding="utf-8")
    events = [e["event"] for e in _lines(log_files / "audit.jsonl")]
    assert {"login", "registro", "firma_invalida", "cambio_de_llave", "acceso_ajeno"} <= set(events)
    for secret in (ALICE, MALLORY, BOB, token, b64e(alice.public_key), b64e(other.public_key), "E2EE1:", "Bearer"):
        assert secret not in text
    assert settings.pseudonymizer.pseudonym(ALICE) in text  # el ID aparece solo seudonimizado
    alerts = (log_files / "alerts.jsonl").read_text(encoding="utf-8")
    assert "acceso_ajeno" in alerts and ALICE not in alerts and MALLORY not in alerts


def test_C09_filtro_de_redaccion_como_segunda_barrera():
    raw = (f"id {ALICE} pk {b64e(os.urandom(32))} Bearer abc.def E2EE1:eyJ0eXAiOiJtc2cifQ "
           f"pseudonimo 0123456789abcdef")
    clean = redact(raw)
    assert ALICE not in clean and "E2EE1" not in clean and "abc.def" not in clean
    assert "0123456789abcdef" in clean  # los seudónimos (16 hex) sí se conservan


def test_alerta_por_firmas_invalidas_repetidas():
    clock = Clock()
    mon = AlertMonitor(clock=clock)
    for _ in range(4):
        mon.record("firma_invalida")
    assert mon.fired == []
    mon.record("firma_invalida")
    assert [a["event"] for a in mon.fired] == ["firma_invalida"]
    mon.record("firma_invalida")  # misma ventana: no repite
    assert len(mon.fired) == 1
    clock.now += 601
    for _ in range(5):
        mon.record("firma_invalida")
    assert len(mon.fired) == 2


def test_eventos_viejos_no_cuentan():
    clock = Clock()
    mon = AlertMonitor(rules=(Rule("x", 3, 60, "m"),), clock=clock)
    mon.record("x")
    mon.record("x")
    clock.now += 61
    mon.record("x")
    assert mon.fired == []


def test_alerta_de_enumeracion_en_el_servicio(make_api):
    api = make_api()
    for i in range(20):
        api.get(f"/v1/keys/{900000000000000000 + i}")
    fired = api.app.state.audit.monitor.fired
    assert [a["event"] for a in fired] == ["consulta_inexistente"]
    assert all(str(900000000000000000) not in json.dumps(a) for a in fired)


def test_alerta_por_limite_de_solicitudes(make_api):
    api = make_api(lookup_limit=1)
    for _ in range(4):
        api.get(f"/v1/keys/{ALICE}")
    assert "limite" in [a["event"] for a in api.app.state.audit.monitor.fired]


def test_cambio_de_llave_alerta_a_operadores(api):
    publish(api, login(api, ALICE), ALICE, Identity.create())
    publish(api, login(api, ALICE), ALICE, Identity.create())
    assert [a["event"] for a in api.app.state.audit.monitor.fired] == ["cambio_de_llave"]


def test_sink_recibe_alertas_sin_identificadores():
    got = []
    AlertMonitor(sink=got.append).record("acceso_ajeno")
    assert got and set(got[0]) == {"alert", "event", "count", "window_s"}


def test_C10_retencion_de_90_dias(tmp_path):
    old, new = tmp_path / "audit.jsonl.2026-07-01", tmp_path / "audit.jsonl"
    old.write_text("{}")
    new.write_text("{}")
    long_ago = time.time() - 91 * 86400
    os.utime(old, (long_ago, long_ago))
    assert purge_logs(tmp_path) == [old]
    assert new.exists()

"""F10 / RS21: estadísticas del directorio con privacidad diferencial, contribución acotada y presupuesto."""
import datetime as dt
import json
import os
import statistics

import psycopg
import pytest

from ops.dp import experiment, metrics
from ops.dp.metrics import Libro, PresupuestoAgotado

AHORA = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)
FIN = dt.date(2026, 11, 20)
SEUDONIMO = "ps_3f9a1c7e5b2d4f60"


def evento(nombre: str, persona: str, dia: str) -> dict:
    return {"ts": f"{dia}T10:00:00Z", "level": "info", "logger": "directory.audit", "event": nombre, "id": persona}


def test_RS21_el_ruido_esta_calibrado_segun_epsilon_y_sensibilidad():
    # Laplace discreto con escala b = sensibilidad/ε: el error absoluto medio se acerca a b (algo menos, por ser
    # discreto) y crece al bajar ε o subir la sensibilidad.
    def error_medio(sens, eps):
        return statistics.fmean(abs(v - 100) for v in metrics.mecanismo(2000, sens, eps)([100] * 2000))

    assert 0.7 * 2 < error_medio(1, 0.5) < 1.1 * 2
    assert 0.7 * 4 < error_medio(2, 0.5) < 1.1 * 4
    assert error_medio(1, 0.1) > 3 * error_medio(1, 1.0)


def test_RS21_opendp_certifica_la_perdida_de_privacidad():
    m = metrics.mecanismo(5, 2, 0.4)
    assert m.map(2) <= 0.4 + 1e-9  # cambiar una persona (hasta 2 unidades) cuesta como mucho ε
    with pytest.raises(ValueError):
        metrics.mecanismo(5, 1, 0)


def test_RS21_la_salida_nunca_es_negativa():
    assert all(v >= 0 for v in metrics.liberar([0] * 500, 1, 0.1))


def test_RS21_la_contribucion_de_cada_persona_esta_acotada():
    registros = [evento("cambio_de_llave", SEUDONIMO, "2026-11-10") for _ in range(50)]
    registros += [evento("login", "ps_otra", "2026-11-11")]
    conteos = metrics.eventos_por_tipo(registros, dt.date(2026, 11, 1), FIN, maximo=2)
    assert conteos[metrics.EVENTOS.index("cambio_de_llave")] == 2  # 50 cambios de una persona cuentan como 2
    assert conteos[metrics.EVENTOS.index("login")] == 1
    assert sum(conteos) == 3


def test_RS21_los_contenedores_son_publicos_y_no_dependen_de_los_datos():
    # Una versión desconocida no crea una categoría con su nombre: cae en "otra".
    assert metrics.personas_por_version(["1.0", "1.0", "9.9-beta"]) == [2, 1]
    assert metrics.semanas(FIN, 2) == [(dt.date(2026, 11, 6), dt.date(2026, 11, 13)),
                                       (dt.date(2026, 11, 13), dt.date(2026, 11, 20))]
    fuera = metrics.eventos_por_tipo([evento("login", "ps_x", "2026-01-01"), {"event": "limite", "grupo": "a"}],
                                     dt.date(2026, 11, 1), FIN)
    assert sum(fuera) == 0


def test_RS21_el_libro_se_niega_a_superar_el_presupuesto_mensual(tmp_path):
    libro = Libro(tmp_path / "presupuesto.json", tope_mensual=2.0)
    libro.cobrar(1.0, AHORA, "a")
    libro.cobrar(1.0, AHORA, "b")
    with pytest.raises(PresupuestoAgotado):
        libro.cobrar(0.5, AHORA, "c")
    assert libro.gastado(AHORA) == 2.0
    assert libro.gastado(AHORA + dt.timedelta(days=15)) == 0  # mes nuevo, presupuesto nuevo
    with pytest.raises(PresupuestoAgotado):  # el reporte no se calcula si no hay presupuesto
        metrics.reporte([], [], [], FIN, 4, 1.0, libro, AHORA)


def test_RS21_el_reporte_no_contiene_ids_ni_seudonimos(tmp_path):
    ids = [str(111111111111111111 + i) for i in range(30)]
    fechas = [AHORA - dt.timedelta(days=i % 50) for i in range(30)]
    auditoria = [evento("registro", f"ps_{i:016x}", (FIN - dt.timedelta(days=i % 20)).isoformat()) for i in range(30)]
    r = metrics.reporte(fechas, ["1.0"] * 30, auditoria, FIN, 8, 1.0, Libro(tmp_path / "l.json"), AHORA)
    texto = json.dumps(r) + metrics.markdown(r)
    assert not any(i in texto for i in ids) and "ps_" not in texto
    assert r["privacidad"]["epsilon_reporte"] == 1.0
    assert len(r["registros_por_semana"]) == 8
    assert json.loads((tmp_path / "l.json").read_text())[0]["epsilon"] == 1.0


def test_RS21_el_experimento_muestra_el_compromiso_entre_utilidad_y_privacidad():
    filas = {f["epsilon"]: f for f in experiment.correr(reps=200, epsilons=(0.1, 5.0))}
    assert filas[5.0]["mae"] < filas[0.1]["mae"]
    assert filas[5.0]["pico"] > filas[0.1]["pico"]
    assert "Tendencia" in experiment.markdown(list(filas.values()), 200)


def test_RS21_lee_la_base_con_el_rol_de_solo_lectura(database):
    with psycopg.connect(database["admin"], autocommit=True) as conn:
        conn.execute("TRUNCATE directory.keys CASCADE")
        for i in range(5):
            conn.execute("INSERT INTO directory.keys (discord_id, public_key, consent_version) VALUES (%s, %s, '1.0')",
                         (str(333333333333333333 + i), os.urandom(32)))
    fechas, versiones = metrics.leer_base(database["backup"])
    assert len(fechas) == 5 and versiones == ["1.0"] * 5
    with psycopg.connect(database["backup"]) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("DELETE FROM directory.keys")

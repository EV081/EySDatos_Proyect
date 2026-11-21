"""Reporte de estadísticas del directorio con privacidad diferencial (F10, RS21).

    python -m ops.dp.metrics report [--epsilon 1.0] [--semanas 8] [--salida ops/reports/dp] [--env .env]

El equipo necesita saber cómo se usa el directorio (cuántas personas se registran, si aceptan el aviso vigente, qué
operaciones hacen) para el curso, la DPIA y las decisiones de operación. Publicar esos conteos exactos permitiría
inferir si una persona concreta se registró o cambió su llave en una semana dada (un ataque de diferenciación:
comparar dos reportes o cruzar un conteo pequeño con lo que se sabe de alguien). Por eso el reporte solo sale con
privacidad diferencial:

* **Unidad de privacidad:** una persona (un ID de Discord). Dos bases son vecinas si difieren en una persona.
* **Consultas** (contenedores públicos, fijados antes de mirar los datos):
  1. registros por semana, de la tabla `keys` (cada persona cae en una sola semana: sensibilidad L1 = 1);
  2. personas por versión del aviso aceptado (una versión por persona: sensibilidad 1);
  3. operaciones por tipo, de los registros de auditoría (IDs ya seudonimizados con HMAC). Cada persona aporta como
     máximo `MAX_EVENTOS_POR_PERSONA` eventos en el periodo (se descartan los demás), así que la sensibilidad es esa.
* **Mecanismo:** Laplace discreto de OpenDP (`make_laplace` sobre enteros), con escala = sensibilidad / ε_i. El
  muestreo de OpenDP es exacto sobre enteros, sin el defecto de punto flotante de las implementaciones ingenuas
  (Mironov, 2012). Luego se trunca en 0, que es posprocesamiento y no gasta presupuesto.
* **Presupuesto:** cada reporte gasta ε (por defecto 1), repartido en partes iguales entre las tres consultas
  (composición secuencial). Un libro de presupuesto (`DP_LEDGER`) suma lo gastado en el mes calendario y el
  programa se niega a publicar si se pasaría del tope mensual (`DP_EPSILON_MENSUAL`, por defecto 4).

Lee la base con el rol de solo lectura de las copias (`BACKUP_DATABASE_URL`) y los registros de `AUDIT_LOG_DIR`. El
reporte no contiene IDs, seudónimos ni conteos exactos.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import opendp.prelude as dp

dp.enable_features("contrib")  # el mecanismo de Laplace sobre enteros está en el grupo "contrib" de OpenDP

EVENTOS = ("registro", "cambio_de_llave", "renovacion", "cancelacion", "login", "acceso", "firma_invalida",
           "acceso_ajeno")
VERSIONES = ("1.0",)
OTRA = "otra"
MAX_EVENTOS_POR_PERSONA = 2
CONSULTAS = 3
EPSILON_REPORTE = 1.0
EPSILON_MENSUAL = 4.0


class PresupuestoAgotado(Exception):
    """Publicar este reporte superaría el tope de ε del mes."""


# --- Conteos exactos (nunca salen de este módulo sin ruido) ----------------------------------------------------

def semanas(fin: dt.date, n: int) -> list[tuple[dt.date, dt.date]]:
    """`n` semanas consecutivas [inicio, fin) que terminan en `fin` (excluido). Son públicas: no dependen de datos."""
    return [(fin - dt.timedelta(weeks=n - i), fin - dt.timedelta(weeks=n - i - 1)) for i in range(n)]


def registros_por_semana(fechas: Iterable[dt.datetime], contenedores: list[tuple[dt.date, dt.date]]) -> list[int]:
    conteos = [0] * len(contenedores)
    for fecha in fechas:
        dia = fecha.date() if isinstance(fecha, dt.datetime) else fecha
        for i, (inicio, fin) in enumerate(contenedores):
            if inicio <= dia < fin:
                conteos[i] += 1
                break
    return conteos


def personas_por_version(versiones: Iterable[str], categorias: tuple[str, ...] = VERSIONES) -> list[int]:
    """Una versión por persona; lo que no está en la lista pública va a `otra` (no se crean categorías nuevas)."""
    conteos = [0] * (len(categorias) + 1)
    for version in versiones:
        conteos[categorias.index(version) if version in categorias else len(categorias)] += 1
    return conteos


def eventos_por_tipo(registros: Iterable[dict], desde: dt.date, hasta: dt.date,
                     maximo: int = MAX_EVENTOS_POR_PERSONA) -> list[int]:
    """Cuenta operaciones por tipo con la contribución de cada persona acotada a `maximo` eventos (los primeros)."""
    por_persona: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in registros:
        evento, persona, ts = r.get("event"), r.get("id"), r.get("ts", "")
        if evento not in EVENTOS or not persona or not desde.isoformat() <= ts[:10] < hasta.isoformat():
            continue
        por_persona[persona].append((ts, evento))
    conteos = [0] * len(EVENTOS)
    for eventos in por_persona.values():
        for _, evento in sorted(eventos)[:maximo]:
            conteos[EVENTOS.index(evento)] += 1
    return conteos


# --- Mecanismo -------------------------------------------------------------------------------------------------

def mecanismo(n: int, sensibilidad: int, epsilon: float):
    """Laplace discreto sobre un vector de `n` conteos con sensibilidad L1 `sensibilidad`; garantiza ε-DP pura."""
    if epsilon <= 0 or sensibilidad < 1:
        raise ValueError("epsilon debe ser positivo y la sensibilidad al menos 1")
    m = dp.m.make_laplace(dp.vector_domain(dp.atom_domain(T=int), size=n), dp.l1_distance(T=int),
                          scale=sensibilidad / epsilon)
    if m.map(sensibilidad) > epsilon * (1 + 1e-9):  # OpenDP calcula la pérdida real; no confiar solo en la fórmula
        raise RuntimeError("el mecanismo no cumple el ε pedido")
    return m


def liberar(conteos: list[int], sensibilidad: int, epsilon: float) -> list[int]:
    ruidosos = mecanismo(len(conteos), sensibilidad, epsilon)(list(conteos))
    return [max(0, v) for v in ruidosos]  # posprocesamiento: no gasta presupuesto


# --- Libro de presupuesto --------------------------------------------------------------------------------------

class Libro:
    """Suma el ε gastado por mes calendario (UTC). Solo guarda fechas y ε; ningún dato de personas."""

    def __init__(self, ruta: str | Path, tope_mensual: float = EPSILON_MENSUAL):
        self.ruta, self.tope = Path(ruta), tope_mensual

    def _entradas(self) -> list[dict]:
        return json.loads(self.ruta.read_text(encoding="utf-8")) if self.ruta.exists() else []

    def gastado(self, ahora: dt.datetime) -> float:
        mes = ahora.strftime("%Y-%m")
        return sum(e["epsilon"] for e in self._entradas() if e["fecha"].startswith(mes))

    def cobrar(self, epsilon: float, ahora: dt.datetime, motivo: str) -> None:
        if self.gastado(ahora) + epsilon > self.tope + 1e-9:
            raise PresupuestoAgotado(f"el mes ya gastó ε={self.gastado(ahora):g} de {self.tope:g}; "
                                     f"este reporte pide ε={epsilon:g}")
        entradas = self._entradas() + [{"fecha": ahora.isoformat(timespec="seconds"), "epsilon": epsilon,
                                        "motivo": motivo}]
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ruta.with_suffix(".tmp")
        tmp.write_text(json.dumps(entradas, indent=2), encoding="utf-8")
        tmp.replace(self.ruta)


# --- Reporte ---------------------------------------------------------------------------------------------------

def reporte(fechas_registro: list[dt.datetime], versiones: list[str], auditoria: list[dict], fin: dt.date,
            n_semanas: int, epsilon: float, libro: Libro, ahora: dt.datetime | None = None,
            categorias: tuple[str, ...] = VERSIONES) -> dict:
    """Calcula y libera las tres consultas. Cobra el presupuesto **antes** de mirar los datos con ruido."""
    ahora = ahora or dt.datetime.now(dt.timezone.utc)
    libro.cobrar(epsilon, ahora, f"reporte de {n_semanas} semanas hasta {fin.isoformat()}")
    eps_i = epsilon / CONSULTAS
    contenedores = semanas(fin, n_semanas)
    sem = liberar(registros_por_semana(fechas_registro, contenedores), 1, eps_i)
    ver = liberar(personas_por_version(versiones, categorias), 1, eps_i)
    eve = liberar(eventos_por_tipo(auditoria, contenedores[0][0], fin), MAX_EVENTOS_POR_PERSONA, eps_i)
    return {
        "generado": ahora.isoformat(timespec="seconds"),
        "periodo": {"desde": contenedores[0][0].isoformat(), "hasta": fin.isoformat()},
        "privacidad": {"unidad": "persona (ID de Discord)", "garantia": "ε-DP pura", "epsilon_reporte": epsilon,
                       "epsilon_por_consulta": round(eps_i, 6), "mecanismo": "Laplace discreto (OpenDP)",
                       "max_eventos_por_persona": MAX_EVENTOS_POR_PERSONA,
                       "error_tipico": {"registros": round(1 / eps_i, 2), "versiones": round(1 / eps_i, 2),
                                        "eventos": round(MAX_EVENTOS_POR_PERSONA / eps_i, 2)},
                       "gastado_en_el_mes": libro.gastado(ahora), "tope_mensual": libro.tope},
        "registros_por_semana": [{"semana": a.isoformat(), "personas": v} for (a, _), v in zip(contenedores, sem)],
        "personas_por_version_del_aviso": dict(zip((*categorias, OTRA), ver)),
        "operaciones_por_tipo": dict(zip(EVENTOS, eve)),
    }


def markdown(r: dict) -> str:
    p = r["privacidad"]
    filas = "\n".join(f"| {s['semana']} | {s['personas']} |" for s in r["registros_por_semana"])
    versiones = "\n".join(f"| {k} | {v} |" for k, v in r["personas_por_version_del_aviso"].items())
    eventos = "\n".join(f"| {k} | {v} |" for k, v in r["operaciones_por_tipo"].items())
    return f"""# Estadísticas del directorio con privacidad diferencial

Periodo: {r['periodo']['desde']} a {r['periodo']['hasta']} (generado {r['generado']}).

Garantía: {p['garantia']} con ε = {p['epsilon_reporte']} para todo el reporte ({p['epsilon_por_consulta']} por
consulta), unidad de privacidad: {p['unidad']}; mecanismo: {p['mecanismo']}. Los valores llevan ruido a propósito:
el error típico es de ±{p['error_tipico']['registros']} personas en las dos primeras tablas y de
±{p['error_tipico']['eventos']} operaciones en la tercera. Presupuesto gastado en el mes: ε = {p['gastado_en_el_mes']:g}
de {p['tope_mensual']:g}.

## Registros nuevos por semana

| Semana que empieza | Personas |
|---|---|
{filas}

## Personas por versión del aviso aceptado

| Versión | Personas |
|---|---|
{versiones}

## Operaciones por tipo (máx. {p['max_eventos_por_persona']} por persona)

| Operación | Cantidad |
|---|---|
{eventos}
"""


# --- Fuentes de datos ------------------------------------------------------------------------------------------

def leer_base(url: str) -> tuple[list[dt.datetime], list[str]]:
    import psycopg

    with psycopg.connect(url, connect_timeout=5) as conn:
        filas = conn.execute("SELECT registered_at, consent_version FROM directory.keys").fetchall()
    return [f[0] for f in filas], [f[1] for f in filas]


def leer_auditoria(carpeta: str | Path) -> list[dict]:
    registros = []
    for ruta in sorted(Path(carpeta).glob("audit.jsonl*")):
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            try:
                registros.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return registros


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m ops.dp.metrics", description=__doc__.splitlines()[0])
    parser.add_argument("accion", choices=["report"])
    parser.add_argument("--epsilon", type=float, default=EPSILON_REPORTE)
    parser.add_argument("--semanas", type=int, default=8)
    parser.add_argument("--salida", default="ops/reports/dp")
    parser.add_argument("--env")
    args = parser.parse_args(argv)
    if args.env:
        from ops.scheduled import load_env

        load_env(args.env)
    if not 1 <= args.semanas <= 12:  # los registros de auditoría solo se conservan 90 días
        parser.error("--semanas debe estar entre 1 y 12")
    salida = Path(args.salida)
    libro = Libro(os.environ.get("DP_LEDGER", salida / "presupuesto.json"),
                  float(os.environ.get("DP_EPSILON_MENSUAL", EPSILON_MENSUAL)))
    fechas, versiones = leer_base(os.environ["BACKUP_DATABASE_URL"])
    auditoria = leer_auditoria(os.environ.get("AUDIT_LOG_DIR", "logs"))
    hoy = dt.datetime.now(dt.timezone.utc).date()
    try:
        r = reporte(fechas, versiones, auditoria, hoy, args.semanas, args.epsilon, libro)
    except PresupuestoAgotado as exc:
        print(f"no se publica: {exc}", file=sys.stderr)
        return 2
    salida.mkdir(parents=True, exist_ok=True)
    base = salida / f"reporte-{hoy:%Y%m%d}"
    base.with_suffix(".json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    base.with_suffix(".md").write_text(markdown(r), encoding="utf-8")
    print(f"reporte en {base}.md (ε={args.epsilon:g})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

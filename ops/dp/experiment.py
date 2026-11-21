"""Experimento de utilidad frente a privacidad (F10, RS21): `python -m ops.dp.experiment [--repeticiones 1000]`.

Usa datos **sintéticos** (ningún dato real) que imitan el uso esperado del directorio en un curso, y libera cada
consulta muchas veces con el mismo mecanismo que `ops.dp.metrics`, para cada ε del reporte completo (que se reparte
entre tres consultas). Mide tres usos:

A. **Tendencia** de registros en 12 semanas: error absoluto medio por semana, error relativo del total y cuántas
   veces la semana pico se ubica a ±1 semana de la real.
B. **Grupo pequeño**: 3 personas con una versión vieja del aviso frente a 45 con la vigente; error relativo del grupo
   pequeño y cuántas veces el reporte dice 0 (el grupo "desaparece").
C. **Detección de abuso** con el umbral de la alerta de enumeración (20): si el conteo llevara ruido, cuántas veces
   se detecta un ataque real (20 eventos) y cuántas se alerta en falso (10 eventos).

Escribe `ops/reports/dp-experimento.md`.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

from ops.dp.metrics import CONSULTAS, MAX_EVENTOS_POR_PERSONA, liberar

EPSILONS = (0.1, 0.5, 1.0, 2.0, 5.0)
SEMANAS = [3, 5, 8, 12, 18, 25, 30, 28, 22, 15, 10, 6]  # adopción en un curso: sube, llega a un pico y baja
VERSIONES = [45, 3]  # vigente, vieja
UMBRAL, ATAQUE, NORMAL = 20, 20, 10
SALIDA = Path(__file__).resolve().parents[1] / "reports" / "dp-experimento.md"


def tendencia(eps_i: float, reps: int) -> dict:
    total, pico = sum(SEMANAS), SEMANAS.index(max(SEMANAS))
    mae, rel, acierto = [], [], 0
    for _ in range(reps):
        r = liberar(SEMANAS, 1, eps_i)
        mae.append(statistics.fmean(abs(a - b) for a, b in zip(r, SEMANAS)))
        rel.append(abs(sum(r) - total) / total)
        acierto += abs(r.index(max(r)) - pico) <= 1
    return {"mae": statistics.fmean(mae), "rel_total": statistics.fmean(rel), "pico": acierto / reps}


def grupo_pequeno(eps_i: float, reps: int) -> dict:
    rel, ceros = [], 0
    for _ in range(reps):
        r = liberar(VERSIONES, 1, eps_i)
        rel.append(abs(r[1] - VERSIONES[1]) / VERSIONES[1])
        ceros += r[1] == 0
    return {"rel_pequeno": statistics.fmean(rel), "desaparece": ceros / reps}


def deteccion(eps_i: float, reps: int) -> dict:
    s = MAX_EVENTOS_POR_PERSONA
    detecta = sum(liberar([ATAQUE], s, eps_i)[0] >= UMBRAL for _ in range(reps))
    falsas = sum(liberar([NORMAL], s, eps_i)[0] >= UMBRAL for _ in range(reps))
    return {"detecta": detecta / reps, "falsas": falsas / reps}


def correr(reps: int = 1000, epsilons: tuple[float, ...] = EPSILONS) -> list[dict]:
    filas = []
    for eps in epsilons:
        eps_i = eps / CONSULTAS
        filas.append({"epsilon": eps, "eps_i": eps_i, **tendencia(eps_i, reps), **grupo_pequeno(eps_i, reps),
                      **deteccion(eps_i, reps)})
    return filas


def markdown(filas: list[dict], reps: int) -> str:
    pct = lambda x: f"{100 * x:.0f} %"  # noqa: E731
    a = "\n".join(f"| {f['epsilon']:g} | {f['eps_i']:.3f} | {f['mae']:.1f} | {pct(f['rel_total'])} | {pct(f['pico'])} |"
                  for f in filas)
    b = "\n".join(f"| {f['epsilon']:g} | {pct(f['rel_pequeno'])} | {pct(f['desaparece'])} |" for f in filas)
    c = "\n".join(f"| {f['epsilon']:g} | {pct(f['detecta'])} | {pct(f['falsas'])} |" for f in filas)
    return f"""# Experimento: utilidad frente a privacidad diferencial

Generado con `python -m ops.dp.experiment --repeticiones {reps}` sobre datos sintéticos. Cada fila es el ε del
reporte completo; cada una de las {CONSULTAS} consultas recibe ε/{CONSULTAS}. Mecanismo: Laplace discreto de OpenDP.
Los valores cambian un poco en cada ejecución porque el ruido es aleatorio.

## A. Tendencia de registros (12 semanas, {sum(SEMANAS)} personas, pico de {max(SEMANAS)})

| ε del reporte | ε de la consulta | Error medio por semana (personas) | Error relativo del total | Pico a ±1 semana |
|---|---|---|---|---|
{a}

## B. Grupo pequeño ({VERSIONES[1]} personas con un aviso viejo frente a {VERSIONES[0]})

| ε del reporte | Error relativo del grupo pequeño | Veces que el reporte dice 0 |
|---|---|---|
{b}

## C. Detección de abuso con ruido (umbral {UMBRAL}, sensibilidad {MAX_EVENTOS_POR_PERSONA})

| ε del reporte | Detecta un ataque de {ATAQUE} eventos | Alerta falsa con {NORMAL} eventos |
|---|---|---|
{c}
"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m ops.dp.experiment")
    parser.add_argument("--repeticiones", type=int, default=1000)
    parser.add_argument("--salida", default=str(SALIDA))
    args = parser.parse_args(argv)
    Path(args.salida).write_text(markdown(correr(args.repeticiones), args.repeticiones), encoding="utf-8")
    print(f"experimento en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

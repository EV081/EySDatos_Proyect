"""Tabla de trazabilidad requerimiento ↔ evidencia (F8): `python -m ops.trazabilidad [--check]`.

Lee los requerimientos del informe (`**RF1:**`, `**RS1:**`), las restricciones de la DPIA (`**C-05**`) y los nombres
de las pruebas (`test_RS4_nonce_unico`, `test('RF9 ...')`), y escribe `docs/trazabilidad.md`. Con `--check`
(en CI) falla si el archivo no está al día o si un requerimiento no tiene ninguna evidencia.
"""
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "trazabilidad.md"
PY_TESTS = ("crypto", "client", "directory", "discord_adapter", "ops")
TS_TESTS = ("frontend/test", "frontend/e2e")
TAG = re.compile(r"^(RF\d+|RS\d+|C-?\d{2})$")

# Requerimientos que se cumplen con las pruebas de otra etiqueta (la sección 3.3 del informe los deriva de la DPIA).
ALIASES = {"RF15": ["C-11"], "RS16": ["C-06"], "RS17": ["C-08"], "RS18": ["C-07"], "RS19": ["C-09"],
           "RS20": ["C-12"]}

# Evidencia que no es una prueba automática (documento, revisión o componente que la cumple por construcción).
MANUAL = {
    "RF4": "Lo cubren las pruebas del *handshake* (RS12, RS13) y la conversación completa (`test_RF3_RF5_*`); diseño en 4.2.3",
    "RF10": "`discord_adapter/` (token de bot en `DISCORD_TOKEN`, nunca en la interfaz) y OAuth2 del directorio; `test_RS10_sin_token_no_arranca`",
    "RS7": "Ceremonia de verificación fuera de banda (4.2.6); el cliente solo marca como verificado tras comparar la huella (`test_RF7_*`)",
    "RS11": "Todo el material aleatorio sale de `os.urandom`/`secrets` (revisión de `crypto/`; Bandit sin hallazgos de B311)",
    "C-01": "`test_RF3_en_el_canal_solo_hay_mensajes_del_protocolo_y_ciphertext` (cliente) y "
            "`test_RS3_se_niega_a_publicar_texto_plano` (adaptador)",
    "C-02": "`test_RS1_RS2_nada_secreto_en_claro_en_disco`; `test_RS12_ninguna_llave_efimera_sobrevive_al_handshake`",
    "C-03": "`KdfParams` por defecto; `test_RS2_los_parametros_de_kdf_estan_autenticados`",
    "C-04": "`test_RS2_contrasena_incorrecta_y_bloqueo_temporal`; `test_al_bloquear_se_destruyen_las_sesiones`",
    "C-13": "gitleaks en CI sin hallazgos (`ops/reports/despues/`); `frontend/test/conn.test.ts`",
    "C-16": "`test_RF8_*` del cliente",
    "C-17": "Prueba e2e del frontend (`frontend/e2e/smoke.mjs`)",
    "C-18": "Pruebas de la API local (`client/tests/test_api.py`)",
    "C-19": "[Plan de respuesta a incidentes](politicas/respuesta-incidentes.md)",
    "C-20": "CI (`.github/workflows/ci.yml`) y reportes antes/después en [`ops/reports/`](../ops/reports/README.md)",
    "C-21": "Pendiente (Elmer): botón de borrado local",
    "C-22": "Informe 4.2.7 y pruebas negativas de `crypto/` y `client/`",
    "C-24": "Fuera del alcance de la entrega (requisitos previos a un uso real)",
}


def _norm(tag: str) -> str:
    return f"C-{tag[-2:]}" if tag.startswith("C") else tag


def requirements() -> list[tuple[str, str]]:
    found = []
    report = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for m in re.finditer(r"^\* \*\*(R[FS]\d+):\*\* (.+)$", report, re.M):
        found.append((m.group(1), m.group(2).strip()))
    dpia = (ROOT / "docs" / "dpia" / "DPIA.md").read_text(encoding="utf-8")
    seen = set()
    for m in re.finditer(r"^\| \*\*(C-\d{2})\*\* \| ([^|]+)\|", dpia, re.M):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            found.append((m.group(1), m.group(2).strip()))
    return found


def _tags(name: str) -> set[str]:
    return {_norm(t) for t in re.split(r"[^A-Za-z0-9-]+|_", name) if TAG.match(t)}


def tests() -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    for comp in PY_TESTS:
        for path in sorted((ROOT / comp / "tests").glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    for tag in _tags(node.name):
                        index[tag].append(f"`{path.relative_to(ROOT).as_posix()}::{node.name}`")
    for folder in TS_TESTS:
        for path in sorted((ROOT / folder).glob("*.*s")):
            for m in re.finditer(r"""\b(?:test|it)\(\s*(['"`])(.+?)\1""", path.read_text(encoding="utf-8")):
                for tag in _tags(m.group(2)):
                    index[tag].append(f"`{path.relative_to(ROOT).as_posix()}`: {m.group(2)}")
    return index


def render() -> tuple[str, list[str]]:
    reqs, index = requirements(), tests()
    missing = []
    lines = ["# Trazabilidad requerimiento ↔ evidencia", "",
             "Generado por `python -m ops.trazabilidad` a partir de los nombres de las pruebas; la CI comprueba que esté "
             "al día. Requerimientos: informe, sección 3; restricciones C-xx: DPIA, sección 6.", "",
             "| Requerimiento | Descripción | Pruebas | Evidencia |", "|---|---|---|---|"]
    for rid, text in reqs:
        found = index.get(rid, []) + [f"{ref} (vía {alias})" for alias in ALIASES.get(rid, [])
                                       for ref in index.get(alias, [])]
        manual = MANUAL.get(rid, "")
        if not found and not manual:
            missing.append(rid)
        short = text if len(text) <= 110 else text[:107].rstrip() + "…"
        cell = "<br>".join(found + ([manual] if manual else [])) or "—"
        lines.append(f"| **{rid}** | {short.replace('|', '/')} | {len(found)} | {cell} |")
    total = sum(len(v) for v in index.values())
    lines += ["", f"**Resumen:** {len(reqs)} requerimientos y restricciones; {len(reqs) - len(missing)} con evidencia; "
              f"{total} referencias desde pruebas automáticas."]
    if missing:
        lines.append(f"**Sin evidencia:** {', '.join(missing)}.")
    return "\n".join(lines) + "\n", missing


def main(argv: list[str]) -> None:
    text, missing = render()
    if "--check" in argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current.replace("\r\n", "\n") != text:
            raise SystemExit("docs/trazabilidad.md no está al día: ejecuta python -m ops.trazabilidad")
        if missing:
            raise SystemExit(f"requerimientos sin evidencia: {', '.join(missing)}")
        print("trazabilidad al día")
        return
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"escrito {OUTPUT.relative_to(ROOT)}" + (f"; sin evidencia: {', '.join(missing)}" if missing else ""))


if __name__ == "__main__":
    main(sys.argv[1:])

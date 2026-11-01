"""Análisis de seguridad del código (F6, C-20): `python -m ops.scan <etiqueta>` (p. ej., `antes` o `despues`).

Deja los reportes en `ops/reports/<etiqueta>/` y un resumen en `resumen.md`:

| Herramienta | Qué busca | Cómo corre |
|---|---|---|
| Bandit | Patrones inseguros en Python | `bandit` del venv |
| Semgrep | Reglas `p/python`, `p/secrets`, `p/typescript`, `p/react` | imagen Docker fijada |
| pip-audit | Vulnerabilidades conocidas en dependencias Python, con SBOM CycloneDX por componente | `pip-audit` del venv |
| npm audit + npm sbom | Lo mismo para el frontend | `npm` |
| gitleaks | Secretos en el historial de git y en los archivos del árbol | imagen Docker fijada |

Las pruebas de acceso ajeno por endpoint (`directory/tests/test_acceso_ajeno.py`) corren con el resto de pruebas.
"""
import json
import shutil
# Bandit B404 aceptado: argumentos en lista y sin shell.
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_COMPONENTS = ("crypto", "client", "directory", "discord_adapter")
PY_SOURCES = ["crypto", "client", "directory", "discord_adapter", "ops"]
GITLEAKS = "zricethezav/gitleaks:v8.30.1"
SEMGREP = "semgrep/semgrep:1.182.1"


def _run(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    print("$", " ".join(args), flush=True)
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",  # nosec B603
                          errors="replace", check=False)


def _python_tool(name: str) -> list[str]:
    return [sys.executable, "-m", name]


def bandit(out: Path) -> dict:
    _run(_python_tool("bandit") + ["-r", *PY_SOURCES, "-x", "*/tests/*", "-f", "json", "-o", str(out / "bandit.json"),
                                   "-q"])
    _run(_python_tool("bandit") + ["-r", *PY_SOURCES, "-x", "*/tests/*", "-f", "txt", "-o", str(out / "bandit.txt"),
                                   "-q"])
    results = json.loads((out / "bandit.json").read_text(encoding="utf-8"))["results"]
    by = {s: sum(r["issue_severity"] == s for r in results) for s in ("HIGH", "MEDIUM", "LOW")}
    return {"herramienta": "Bandit", "hallazgos": len(results), "detalle": by}


def pip_audit(out: Path) -> dict:
    vulns: dict[str, int] = {}
    for comp in PYTHON_COMPONENTS:
        target = out / f"sbom-{comp}.cdx.json"
        _run(_python_tool("pip_audit") + ["-r", f"{comp}/requirements.txt", "-f", "cyclonedx-json", "-o", str(target),
                                          "--progress-spinner", "off"])
        data = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
        vulns[comp] = len(data.get("vulnerabilities", []))
    return {"herramienta": "pip-audit (SBOM CycloneDX)", "hallazgos": sum(vulns.values()), "detalle": vulns}


def npm_audit(out: Path) -> dict:
    npm = shutil.which("npm")
    if not npm:
        return {"herramienta": "npm audit", "hallazgos": None, "detalle": "npm no está instalado"}
    result = _run([npm, "audit", "--json"], cwd=ROOT / "frontend")
    (out / "npm-audit.json").write_text(result.stdout, encoding="utf-8")
    sbom = _run([npm, "sbom", "--sbom-format", "cyclonedx", "--package-lock-only"], cwd=ROOT / "frontend")
    (out / "sbom-frontend.cdx.json").write_text(sbom.stdout, encoding="utf-8")
    counts = json.loads(result.stdout or "{}").get("metadata", {}).get("vulnerabilities", {})
    return {"herramienta": "npm audit (SBOM CycloneDX)", "hallazgos": counts.get("total", 0), "detalle": counts}


def _docker(image: str, args: list[str]) -> subprocess.CompletedProcess:
    return _run(["docker", "run", "--rm", "-v", f"{ROOT}:/src", "-w", "/src", image, *args])


def gitleaks(out: Path) -> dict:
    rel = out.relative_to(ROOT).as_posix()
    found = {}
    for mode, args in (("historial", ["git", "/src"]), ("arbol", ["dir", "/src"])):
        report = f"{rel}/gitleaks-{mode}.json"
        _docker(GITLEAKS, [*args, "--config", "/src/.gitleaks.toml", "--redact", "--no-banner",
                           "--report-format", "json", "--report-path", f"/src/{report}", "--exit-code", "0"])
        path = ROOT / report
        found[mode] = len(json.loads(path.read_text(encoding="utf-8") or "[]")) if path.exists() else None
    return {"herramienta": "gitleaks", "hallazgos": sum(v or 0 for v in found.values()), "detalle": found}


def semgrep(out: Path) -> dict:
    rel = out.relative_to(ROOT).as_posix()
    _docker(SEMGREP, ["semgrep", "scan", "--metrics=off", "--quiet", "--config", "p/python", "--config", "p/secrets",
                      "--config", "p/typescript", "--config", "p/react", "--json", "-o", f"/src/{rel}/semgrep.json"])
    path = out / "semgrep.json"
    results = json.loads(path.read_text(encoding="utf-8")).get("results", []) if path.exists() else []
    by: dict[str, int] = {}
    for r in results:
        sev = r.get("extra", {}).get("severity", "?")
        by[sev] = by.get(sev, 0) + 1
    return {"herramienta": "Semgrep", "hallazgos": len(results), "detalle": by}


def main(argv: list[str]) -> None:
    label = argv[0] if argv else "actual"
    out = ROOT / "ops" / "reports" / label
    out.mkdir(parents=True, exist_ok=True)
    summary = [step(out) for step in (bandit, semgrep, pip_audit, npm_audit, gitleaks)]
    (out / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# Análisis de código: {label}", "", "| Herramienta | Hallazgos | Detalle |", "|---|---|---|"]
    lines += [f"| {s['herramienta']} | {s['hallazgos']} | `{json.dumps(s['detalle'], ensure_ascii=False)}` |"
              for s in summary]
    (out / "resumen.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1:])

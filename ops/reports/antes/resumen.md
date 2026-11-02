# Análisis de código: antes

| Herramienta | Hallazgos | Detalle |
|---|---|---|
| Bandit | 5 | `{"HIGH": 0, "MEDIUM": 0, "LOW": 5}` |
| Semgrep | 4 | `{"ERROR": 4}` |
| pip-audit (SBOM CycloneDX) | 0 | `{"crypto": 0, "client": 0, "directory": 0, "discord_adapter": 0}` |
| npm audit (SBOM CycloneDX) | 0 | `{"info": 0, "low": 0, "moderate": 0, "high": 0, "critical": 0, "total": 0}` |
| gitleaks | 2 | `{"historial": 0, "arbol": 2}` |

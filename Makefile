# Atajos (Linux/macOS/WSL; en Windows, ejecutar los comandos equivalentes con .venv\Scripts\python).
PY ?= .venv/bin/python

.PHONY: dev db certs directory test scan backup verify-backup restore daily trazabilidad

dev:            ## dos clientes en memoria, sin Discord ni directorio reales
	$(PY) -m client.dev

db:             ## Postgres + roles y esquema
	docker compose up -d db
	set -a; . ./.env; set +a; $(PY) -m directory.migrations.apply

certs:          ## CA propia y certificado del directorio (una vez)
	set -a; . ./.env; set +a; $(PY) -m ops.certs.pki init

directory:      ## directorio con TLS 1.3 en https://localhost:8443
	set -a; . ./.env; set +a; $(PY) -m directory.serve

test:
	for c in crypto client directory discord_adapter ops; do (cd $$c && ../$(PY) -m pytest -q) || exit 1; done
	$(PY) -m ops.trazabilidad --check

scan:           ## make scan ETIQUETA=despues
	$(PY) -m ops.scan $(or $(ETIQUETA),actual)

backup:
	set -a; . ./.env; set +a; $(PY) -m ops.backup.backup create

verify-backup:
	set -a; . ./.env; set +a; $(PY) -m ops.backup.backup verify

restore:        ## make restore ARCHIVO=/ruta/directory-....dump.enc
	set -a; . ./.env; set +a; $(PY) -m ops.backup.backup restore $(ARCHIVO)

daily:
	$(PY) -m ops.scheduled daily --env .env

trazabilidad:
	$(PY) -m ops.trazabilidad

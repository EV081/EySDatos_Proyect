# Copias de seguridad del directorio (F4, C-10, C-12)

```bash
set -a; . ./.env; set +a
python -m ops.backup.backup create     # copia cifrada en BACKUP_DIR + rotación de 30 días
python -m ops.backup.backup verify     # restaura la última en una base temporal y compara conteos
python -m ops.backup.backup restore D:/e2ee-backups/directory-20261031T225559Z.dump.enc
```

## Qué se protege y cómo

| Requisito | Cómo se cumple | Prueba |
|---|---|---|
| Programada | `python -m ops.scheduled daily` (copia, purga y retención) en el Programador de tareas o cron. Ver abajo | — |
| Cifrada | AES-256-GCM con `BACKUP_KEY` (32 bytes); el nombre del archivo va en los datos autenticados | `test_C12_copia_cifrada_sin_datos_en_claro`, `test_copia_alterada_o_clave_incorrecta_se_rechaza`, `test_renombrar_una_copia_vieja_se_detecta` |
| Sin texto plano en disco | El volcado va de `pg_dump` a memoria y de memoria a `pg_restore` (stdin) | `test_C12_copia_cifrada_sin_datos_en_claro` |
| Mínimo privilegio | `pg_dump` corre como `directory_backup` (solo `SELECT`); la contraseña va en `PGPASSWORD`, no en la línea de comandos | `test_rol_de_copias_es_de_solo_lectura` |
| Fuera del servidor | `BACKUP_DIR` en otro disco o recurso de red; el script se niega a escribir dentro del repositorio | `test_destino_dentro_del_repositorio_se_rechaza` |
| Restauración probada | `verify` restaura en una base aparte y compara; además, la restauración real deja la app funcionando con sus permisos mínimos | `test_C12_restauracion_probada`, `test_C12_restaurar_recupera_el_servicio_tras_perder_datos` |
| Rotación de 30 días | Se borran las copias de más de 30 días: una cancelación (C-11) desaparece de las copias en ese plazo | `test_C10_rotacion_de_30_dias` |
| Minimización | No se copian los datos efímeros (state de OAuth2, tokens, nonces) | `test_no_se_copian_datos_efimeros` |

**Custodia de `BACKUP_KEY`:** se guarda fuera del servidor del directorio (gestor de contraseñas del responsable). Una copia sin su clave no sirve, y la clave sin las copias tampoco. Si la clave se filtra: generar una nueva, hacer una copia nueva y borrar las anteriores (ver el plan de incidentes).

## Objetivos

* **RPO 24 h:** copia diaria; en el peor caso se pierden los registros del último día, y la persona solo tiene que volver a publicar su llave (el cliente lo hace al crear o importar la identidad).
* **RTO 30 min:** `docker compose up -d db`, luego `python -m directory.migrations.apply` y `restore`. Medido en local: menos de 5 segundos para el esquema y los datos.

## Programación

Windows (Programador de tareas), todos los días a las 03:00:

```powershell
schtasks /Create /SC DAILY /ST 03:00 /TN "e2ee-directorio-diario" /TR "D:\UTEC\EticaSeguridadDatos\EySDatos_Proyect\.venv\Scripts\python.exe -m ops.scheduled daily --env D:\UTEC\EticaSeguridadDatos\EySDatos_Proyect\.env"
```

Linux (cron): `0 3 * * * cd /ruta/al/repo && .venv/bin/python -m ops.scheduled daily --env .env`

Además, `verify` se ejecuta una vez por semana, y su salida se guarda como evidencia.

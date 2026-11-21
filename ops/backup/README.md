# Copias de seguridad del directorio (F4, C-10, C-12)

```bash
set -a; . ./.env; set +a
python -m ops.backup.backup create     # copia cifrada en BACKUP_DIR + rotación de 30 días
python -m ops.backup.backup verify     # restaura la última en una base temporal y compara conteos
python -m ops.backup.backup restore D:/e2ee-backups/directory-20261031T225559Z.dump.enc
```

## Estado e instalación en EC2

El código dispone de respaldo cifrado local y subida a S3 con verificación de tamaño y SHA-256 y limpieza remota de 30 días (19 casos de prueba de S3, TLS y carga del entorno). Realizamos el ensayo de 2026-11-01 en local; ese ensayo no acredita una tarea activa en Supabase o EC2. Después verificamos la primera copia real en S3 ([evidencia](../reports/f4-s3-smoke.txt)) e instalamos el crontab con el servicio activo. Descargamos la copia de S3 y la restauramos en PostgreSQL 17 aislado: recuperamos 2 registros y desciframos 1 factor MFA con la clave original. Nos falta observar una ejecución automática.

El procedimiento operativo está en la [guía de EC2, sección 8](../../docs/guia/despliegue-ec2.md#8-activar-el-respaldo-diario-de-supabase-en-s3). `make backup-remote` exige `BACKUP_S3_BUCKET`; `ENV_FILE=.env.backup` permite separar su configuración de la API. La clave TOTP y `BACKUP_KEY` no se suben al bucket.

La plantilla [`.env.example.ec2`](../../.env.example.ec2) incluye la sección de respaldos para EC2. Complétala antes de ejecutar `make backup-remote`; las credenciales administrativas de migraciones permanecen en un archivo separado.

## Qué se protege y cómo

| Requisito | Cómo se cumple | Prueba |
|---|---|---|
| Programada en EC2 | `make backup-remote` para S3; cron instalado y activo. `python -m ops.scheduled daily` corresponde al mantenimiento completo | Copia manual real verificada; primera ejecución automática pendiente de observar |
| Cifrada | AES-256-GCM con `BACKUP_KEY` (32 bytes); el nombre del archivo va en los datos autenticados | `test_C12_copia_cifrada_sin_datos_en_claro`, `test_copia_alterada_o_clave_incorrecta_se_rechaza`, `test_renombrar_una_copia_vieja_se_detecta` |
| Sin texto plano en disco | El volcado va de `pg_dump` a memoria y de memoria a `pg_restore` (stdin) | `test_C12_copia_cifrada_sin_datos_en_claro` |
| Mínimo privilegio | `pg_dump` corre como `directory_backup` (solo `SELECT`); la contraseña va en `PGPASSWORD`, no en la línea de comandos | `test_rol_de_copias_es_de_solo_lectura` |
| Fuera del servidor | En modo remoto, bucket S3 privado y `BACKUP_DIR` como staging cifrado; en modo local, destino externo. Se impide escribir dentro del repositorio | `test_destino_dentro_del_repositorio_se_rechaza` |
| Restauración probada | `verify` restaura en una base aparte y compara; además, la restauración real deja la app funcionando con sus permisos mínimos | `test_C12_restauracion_probada`, `test_C12_restaurar_recupera_el_servicio_tras_perder_datos` |
| Rotación de 30 días | Se borran las copias de más de 30 días: una cancelación (C-11) desaparece de las copias en ese plazo | `test_C10_rotacion_de_30_dias` |
| Minimización | No se copian los datos efímeros (state de OAuth2, tokens, nonces y sesiones MFA) | `test_no_se_copian_datos_efimeros` |

**Custodia de `BACKUP_KEY`:** la guardamos fuera del servidor del directorio, en el gestor de contraseñas del responsable. Una copia sin su clave no sirve, y la clave sin las copias tampoco. Si la clave se filtra: generar una nueva, hacer una copia nueva y borrar las anteriores (ver el plan de incidentes).

Las copias incluyen el secreto TOTP ya cifrado y los hashes de recuperación. Para recuperar el servicio
también hace falta la misma `TOTP_ENCRYPTION_KEY`, custodiada por separado del respaldo. Las sesiones
MFA pendientes no se restauran: la persona debe iniciar de nuevo el flujo de Discord.

## Objetivos

* **RPO 24 h:** copia diaria; en el peor caso se pierden los registros del último día, y la persona solo tiene que volver a publicar su llave (el cliente lo hace al crear o importar la identidad).
* **RTO 30 min:** `docker compose up -d db`, luego `python -m directory.migrations.apply` y `restore`. Medimos menos de 5 segundos en local para recuperar el esquema y los datos.

## Referencia de programación

Los comandos históricos siguientes son ejemplos; no prueban que estén activos en EC2. Para S3 usa el procedimiento de la guía operativa.

Windows (Programador de tareas), todos los días a las 03:00:

```powershell
schtasks /Create /SC DAILY /ST 03:00 /TN "e2ee-directorio-diario" /TR "D:\UTEC\EticaSeguridadDatos\EySDatos_Proyect\.venv\Scripts\python.exe -m ops.scheduled daily --env D:\UTEC\EticaSeguridadDatos\EySDatos_Proyect\.env"
```

Linux (cron): `0 3 * * * cd /ruta/al/repo && .venv/bin/python -m ops.scheduled daily --env .env`

`verify` debe ensayarse en una base aislada con permisos para crear bases temporales. No se da por ejecutado en el despliegue de Supabase.

"""Copias de seguridad del directorio (F4, C-10, C-12).

    python -m ops.backup.backup create            # pg_dump cifrado en BACKUP_DIR + rotación de 30 días
    python -m ops.backup.backup create-remote     # copia cifrada y subida verificada a BACKUP_S3_BUCKET
    python -m ops.backup.backup verify            # restaura la última copia en una base temporal y compara
    python -m ops.backup.backup restore <archivo> # restaura sobre DATABASE_ADMIN_URL (reemplaza el esquema)
    python -m ops.backup.backup rotate            # solo la rotación

* `pg_dump` corre con el rol de solo lectura `directory_backup` (`BACKUP_DATABASE_URL`).
* El volcado nunca toca el disco en claro: sale de `pg_dump` a memoria, se cifra con AES-256-GCM
  (`BACKUP_KEY`, base64url de 32 bytes) y solo se escribe el resultado. Para restaurar, se descifra en memoria y
  se pasa a `pg_restore` por la entrada estándar.
* No se copian los datos efímeros (state de OAuth2, tokens y nonces): no hacen falta para recuperar el servicio.
* Sin S3, `BACKUP_DIR` debe ser un destino externo. Con `BACKUP_S3_BUCKET`, es el área temporal de copias
  ya cifradas antes de subirlas al bucket privado. El script impide escribir dentro del repositorio.
* Rotación de 30 días: una cancelación (C-11) desaparece también de las copias a más tardar en ese plazo.
"""
import base64
import binascii
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
# Bandit B404 aceptado: argumentos en lista, sin shell; herramientas de PostgreSQL y AWS CLI.
import subprocess  # nosec B404
import sys
from pathlib import Path

import psycopg
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

MAGIC = b"E2EEBAK1"
RETENTION_DAYS = 30
EPHEMERAL = ("oauth_states", "auth_tokens", "challenges", "mfa_sessions")
NAME = re.compile(r"^directory-(\d{8}T\d{6}Z)\.dump\.enc$")
REPO_ROOT = Path(__file__).resolve().parents[2]


class BackupError(Exception):
    pass


def load_key(raw: str | None = None) -> bytes:
    raw = raw if raw is not None else os.environ.get("BACKUP_KEY", "")
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (binascii.Error, ValueError):
        raise BackupError("BACKUP_KEY no es base64url válido") from None
    if len(key) != 32:
        raise BackupError("BACKUP_KEY debe ser de 32 bytes")
    return key


def _pg_env(url: str) -> dict:
    """La contraseña va por PGPASSWORD, no en la línea de comandos (visible en la lista de procesos)."""
    info = conninfo_to_dict(url)
    env = {**os.environ}
    for key, var in (("host", "PGHOST"), ("port", "PGPORT"), ("user", "PGUSER"), ("password", "PGPASSWORD"),
                     ("dbname", "PGDATABASE"), ("sslmode", "PGSSLMODE"), ("sslrootcert", "PGSSLROOTCERT")):
        if info.get(key):
            env[var] = str(info[key])
    return env


def _tool(name: str) -> str:
    path = shutil.which(name, path=os.environ.get("PG_BIN")) or shutil.which(name)
    if not path:
        raise BackupError(f"no se encontró {name}; instala el cliente de PostgreSQL 17 o define PG_BIN")
    return path


def check_destination(directory: Path) -> Path:
    directory = directory.resolve()
    if directory == REPO_ROOT or REPO_ROOT in directory.parents:
        raise BackupError("BACKUP_DIR no puede estar dentro del repositorio")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def encrypt(key: bytes, plain: bytes, name: str) -> bytes:
    nonce = secrets.token_bytes(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, plain, MAGIC + name.encode())


def decrypt(key: bytes, blob: bytes, name: str) -> bytes:
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 12 + 16:
        raise BackupError("no es una copia de seguridad del directorio")
    nonce = blob[len(MAGIC):len(MAGIC) + 12]
    try:  # el nombre va en los datos autenticados: renombrar una copia vieja como nueva se detecta
        return AESGCM(key).decrypt(nonce, blob[len(MAGIC) + 12:], MAGIC + name.encode())
    except InvalidTag:
        raise BackupError("la copia fue alterada o la clave no es la correcta") from None


def create(db_url: str, key: bytes, directory: Path, now: dt.datetime | None = None) -> Path:
    directory = check_destination(directory)
    now = now or dt.datetime.now(dt.timezone.utc)
    name = f"directory-{now:%Y%m%dT%H%M%SZ}.dump.enc"
    args = [_tool("pg_dump"), "--format=custom", "--schema=directory", "--no-password"]
    args += [f"--exclude-table-data=directory.{t}" for t in EPHEMERAL]
    result = subprocess.run(args, env=_pg_env(db_url), capture_output=True, check=False)  # nosec B603
    if result.returncode != 0:
        raise BackupError("pg_dump falló: " + result.stderr.decode(errors="replace").strip()[:300])
    target = directory / name
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(encrypt(key, result.stdout, name))
    tmp.replace(target)  # nunca queda una copia a medio escribir con el nombre final
    return target


def rotate(directory: Path, now: dt.datetime | None = None, days: int = RETENTION_DAYS) -> list[Path]:
    now = now or dt.datetime.now(dt.timezone.utc)
    removed = []
    for path in Path(directory).iterdir():
        match = NAME.match(path.name)
        if not match:
            continue
        stamp = dt.datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        if now - stamp > dt.timedelta(days=days):
            path.unlink()
            removed.append(path)
    return removed


def latest(directory: Path) -> Path:
    copies = sorted(p for p in Path(directory).iterdir() if NAME.match(p.name))
    if not copies:
        raise BackupError("no hay copias en BACKUP_DIR")
    return copies[-1]


def restore(path: Path, key: bytes, admin_url: str) -> None:
    """Restaura en la base de `admin_url`, reemplazando el esquema `directory` en una sola transacción."""
    plain = decrypt(key, Path(path).read_bytes(), Path(path).name)
    args = [_tool("pg_restore"), "--clean", "--if-exists", "--single-transaction", "--exit-on-error",
            "--no-password", f"--dbname={conninfo_to_dict(admin_url).get('dbname', 'postgres')}"]
    result = subprocess.run(args, input=plain, env=_pg_env(admin_url), capture_output=True,  # nosec B603
                            check=False)
    if result.returncode != 0:
        raise BackupError("pg_restore falló: " + result.stderr.decode(errors="replace").strip()[:300])


def _counts(url: str) -> dict[str, int]:
    with psycopg.connect(url) as conn:
        return {t: conn.execute(sql.SQL("SELECT count(*) FROM directory.{}").format(sql.Identifier(t))).fetchone()[0]
                for t in ("keys", "replaced_keys")}


def verify(path: Path, key: bytes, admin_url: str, scratch: str = "directory_restore_check") -> dict[str, int]:
    """Prueba de restauración: restaura en una base temporal y compara los conteos con la base de origen.

    Las filas creadas después de la copia hacen que el origen tenga más; nunca debe tener menos."""
    scratch_url = psycopg.conninfo.make_conninfo(admin_url, dbname=scratch)
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(scratch)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(scratch)))
    try:
        restore(path, key, scratch_url)
        restored, source = _counts(scratch_url), _counts(admin_url)
        if any(restored[t] > source[t] for t in restored):
            raise BackupError(f"la copia tiene filas que el origen no: {restored} vs {source}")
        return restored
    finally:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(scratch)))


def _aws(action: str, *args: str) -> dict:
    executable = shutil.which("aws")
    if not executable:
        raise BackupError("falta AWS CLI v2 en el equipo que ejecuta el respaldo")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    command = [executable, "s3api", action, *args, "--region", region, "--output", "json", "--no-cli-pager"]
    try:
        # AWS CLI se ejecuta con una lista, sin shell: la región del entorno es un argumento.
        # Las operaciones s3api vienen del código y bucket/prefijo se validan en sync_s3.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
        result = subprocess.run(command, capture_output=True, check=False, timeout=300)  # nosec B603
    except subprocess.TimeoutExpired:
        raise BackupError(f"se agotó el tiempo de AWS S3: {action}") from None
    if result.returncode:
        # La salida de AWS puede contener detalles del entorno. No se vuelca al registro público.
        raise BackupError(f"AWS S3 rechazó {action} (código {result.returncode}); revisa el rol y el bucket")
    try:
        data = json.loads(result.stdout or b"{}")
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (ValueError, UnicodeError):
        raise BackupError(f"respuesta inválida de AWS S3: {action}") from None


def sync_s3(path: Path, bucket: str, prefix: str = "directory", now: dt.datetime | None = None) -> tuple[str, int]:
    """Sube solo la copia cifrada, comprueba SHA-256 y borra copias propias de más de 30 días.

    Exige un bucket privado sin versionado. La limpieza se limita al prefijo configurado y al patrón
    de archivos del proyecto; nunca elimina otros objetos ni borra copias antes de verificar la nueva.
    AWS CLI usa el rol de EC2 o las credenciales de la sesión, sin llaves de AWS en esta configuración.
    """
    prefix = prefix.strip("/")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise BackupError("BACKUP_S3_BUCKET debe ser el nombre del bucket, sin s3://")
    if not prefix or any(not re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in prefix.split("/")):
        raise BackupError("BACKUP_S3_PREFIX debe contener segmentos simples, sin puntos ni rutas relativas")
    if not NAME.fullmatch(path.name):
        raise BackupError("solo se pueden publicar archivos de copia del proyecto")
    size = path.stat().st_size
    if size > 5 * 1024**3:
        raise BackupError("la copia supera los 5 GiB admitidos por esta subida; requiere carga multiparte")
    with path.open("rb") as source:
        if source.read(len(MAGIC)) != MAGIC:
            raise BackupError("la copia que se iba a subir no está cifrada")
        source.seek(0)
        digest = base64.b64encode(hashlib.file_digest(source, "sha256").digest()).decode("ascii")
    controls = _aws("get-public-access-block", "--bucket", bucket).get("PublicAccessBlockConfiguration", {})
    if not all(controls.get(key) is True for key in (
            "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")):
        raise BackupError("el bucket debe tener activados los cuatro bloqueos de acceso público")
    if _aws("get-bucket-versioning", "--bucket", bucket).get("Status"):
        raise BackupError("usa un bucket nuevo sin versionado para cumplir la eliminación de las copias")
    key = f"{prefix}/{path.name}"
    _aws("put-object", "--bucket", bucket, "--key", key, "--body", str(path),
         "--server-side-encryption", "AES256", "--checksum-algorithm", "SHA256",
         "--checksum-sha256", digest, "--if-none-match", "*")
    remote = _aws("head-object", "--bucket", bucket, "--key", key, "--checksum-mode", "ENABLED")
    if remote.get("ContentLength") != size or remote.get("ChecksumSHA256") != digest:
        raise BackupError("la copia remota no coincide en tamaño o SHA-256; se conservan las copias anteriores")
    cutoff = (now or dt.datetime.now(dt.timezone.utc)) - dt.timedelta(days=RETENTION_DAYS)
    objects = _aws("list-objects-v2", "--bucket", bucket, "--prefix", prefix + "/").get("Contents", [])
    deleted = 0
    for item in objects:
        object_key = item.get("Key", "")
        if not object_key.startswith(prefix + "/"):
            continue
        match = NAME.fullmatch(object_key[len(prefix) + 1:])
        if not match:
            continue
        try:
            created = dt.datetime.strptime(match[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if object_key != key and created < cutoff:
            _aws("delete-object", "--bucket", bucket, "--key", object_key)
            deleted += 1
    return f"s3://{bucket}/{key}", deleted


def main(argv: list[str]) -> None:
    command = argv[0] if argv else ""
    directory = Path(os.environ.get("BACKUP_DIR", ""))
    try:
        key = load_key()
        if command in ("create", "create-remote"):
            bucket = os.environ.get("BACKUP_S3_BUCKET", "").strip()
            if command == "create-remote" and not bucket:
                raise BackupError("falta BACKUP_S3_BUCKET; no se considerará remoto un respaldo solo local")
            path = create(os.environ["BACKUP_DATABASE_URL"], key, directory)
            if bucket:
                uri, deleted = sync_s3(path, bucket, os.environ.get("BACKUP_S3_PREFIX", "directory"))
                print(f"copia remota verificada (SHA-256): {uri}; remotas rotadas: {deleted}")
            removed = rotate(directory)
            print(f"copia creada: {path.name} ({path.stat().st_size} bytes); rotadas: {len(removed)}")
        elif command == "rotate":
            print(f"rotadas: {len(rotate(directory))}")
        elif command == "verify":
            path = latest(directory)
            print(f"restauración de {path.name} correcta: {verify(path, key, os.environ['DATABASE_ADMIN_URL'])}")
        elif command == "restore" and len(argv) == 2:
            restore(Path(argv[1]), key, os.environ["DATABASE_ADMIN_URL"])
            print("restauración completa")
        else:
            raise SystemExit(__doc__)
    except BackupError as exc:
        raise SystemExit(f"error: {exc}") from None
    except KeyError as exc:
        raise SystemExit(f"falta la variable de configuración {exc.args[0]}") from None


if __name__ == "__main__":
    main(sys.argv[1:])

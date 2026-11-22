"""Carga del archivo de entorno sin reemplazar el entorno de la tarea."""
from ops.scheduled import load_env


def test_archivo_env_no_sobrescribe_las_variables_del_proceso(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("BACKUP_S3_BUCKET", "bucket-de-la-tarea")
    path = tmp_path / "backup.env"
    path.write_text("BACKUP_S3_BUCKET=bucket-del-archivo\n")
    load_env(path)
    assert os.environ["BACKUP_S3_BUCKET"] == "bucket-de-la-tarea"

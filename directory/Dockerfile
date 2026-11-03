# Directorio de llaves (F1) para desplegarlo en un servidor. Contexto de construcción: la raíz del repositorio.
#   docker build -f directory/Dockerfile -t e2ee-directory .
# Los certificados (ops/certs) y los secretos NO van en la imagen: se montan y se pasan por entorno
# (ver docker-compose.yml, perfil "deploy", y docs/despliegue-directorio.md).
FROM python:3.12-slim

RUN useradd --system --uid 10001 --create-home app
WORKDIR /app

COPY crypto/requirements.txt crypto/requirements.txt
COPY directory/requirements.txt directory/requirements.txt
RUN pip install --no-cache-dir -r directory/requirements.txt

COPY crypto crypto
COPY directory directory
# ops/certs solo se monta en tiempo de ejecución: la llave de la CA y el certificado nunca entran a la imagen.
RUN mkdir -p ops/certs /var/log/directory && chown app /var/log/directory

USER app
ENV DIRECTORY_HOST=0.0.0.0 DIRECTORY_PORT=8443
EXPOSE 8443
# Sin registro de acceso: escribiría IP y rutas con el ID de Discord en claro (lo configura directory.serve).
CMD ["python", "-m", "directory.serve"]

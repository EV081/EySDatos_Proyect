# Mensajería cifrada sobre Discord

Cada persona ejecuta el cliente y el frontend en su computadora. El directorio de llaves y PostgreSQL se alojan en una instancia EC2 en Virginia del Norte (`us-east-1`).

Las dos guías operativas son:

- [Ejecutar la aplicación: `.env`, Discord, Authenticator, `make client` y `make frontend`](docs/ejecucion-local.md).
- [Desplegar y actualizar el directorio y PostgreSQL en EC2](docs/despliegue-ec2.md).

El informe y la DPIA están en `docs/`. La tabla de trazabilidad es evidencia generada de la entrega; la CI comprueba que coincida con los requerimientos y las pruebas.
